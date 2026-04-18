import logging
from django.utils import timezone
from accounts.models import Business, User
from integrations.models import Channel
from .models import Customer, CustomerChannel, Message

logger = logging.getLogger(__name__)


class MessageProcessor:
    """
    Handles all incoming messages from webhooks.
    Identifies the customer, updates last_channel, stores the message.
    """

    @staticmethod
    def process(normalized: dict) -> Message:
        """
        Entry point called from the webhook dispatcher.

        normalized dict shape (from MessageNormalizer):
        {
            'business_id': str,
            'channel_id': str,
            'channel_type': str,
            'external_id': str,         # platform message ID
            'sender_external_id': str,  # platform user ID
            'content': str,
            'type': str,
            'raw': dict,
        }
        """
        business_id = normalized['business_id']
        channel_id = normalized['channel_id']
        channel_type = normalized['channel_type']
        sender_external_id = normalized['sender_external_id']
        external_id = normalized.get('external_id', '')
        name = normalized.get('name', '')
        phone = normalized.get('phone', '')

        # Skip duplicates
        if external_id and Message.objects.filter(external_id=external_id).exists():
            logger.info('Duplicate message skipped: %s', external_id)
            return None

        business = Business.objects.get(id=business_id)
        channel = Channel.objects.get(id=channel_id)

        customer, is_new = MessageProcessor._identify_customer(
            business=business,
            channel_type=channel_type,
            sender_external_id=sender_external_id,
            name=name,
            phone=phone,
        )

        # Enrich customer profile from Instagram if we don't have one yet
        if channel_type == 'instagram' and not customer.avatar_url:
            MessageProcessor._enrich_from_instagram(customer, sender_external_id, channel)

        # Update last seen channel
        customer.last_channel = channel
        customer.last_message_at = timezone.now()
        customer.save(update_fields=['last_channel', 'last_message_at', 'updated_at'])

        message = Message.objects.create(
            customer=customer,
            speaker=Message.Speaker.CUSTOMER,
            channel_type=channel_type,
            content_type=MessageProcessor._map_content_type(normalized.get('type', 'text')),
            content=normalized.get('content', ''),
            external_id=external_id,
            raw_payload=normalized.get('raw', {}),
        )

        logger.info('Message stored: customer=%s channel=%s', customer.id, channel_type)

        # Broadcast to agents viewing this customer thread + inbox sidebar
        MessageProcessor._broadcast(customer, message, is_new=is_new)

        # Trigger AI auto-reply (runs in background, never blocks here)
        from .ai_service import AIReplyService
        AIReplyService.dispatch(customer)

        return message

    @staticmethod
    def _broadcast(customer, message, is_new=False):
        """Push the new message to WebSocket groups via channel layer."""
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = {
            'id': str(message.id),
            'speaker': message.speaker,
            'speaker_agent': None,
            'channel_type': message.channel_type,
            'content_type': message.content_type,
            'content': message.content,
            'attachments': message.attachments,
            'is_read': message.is_read,
            'send_error': message.send_error or None,
            'timestamp': message.timestamp.isoformat(),
        }

        # Notify agents in the open chat window
        async_to_sync(channel_layer.group_send)(
            f'customer_{customer.id}',
            {'type': 'chat.message', 'message': payload},
        )

        if is_new:
            # New customer — send full customer object so the sidebar can prepend it
            from .serializers import CustomerSerializer
            customer.refresh_from_db()  # pick up last_channel set just before this call
            customer_data = CustomerSerializer(customer).data
            async_to_sync(channel_layer.group_send)(
                f'inbox_{customer.business_id}',
                {'type': 'inbox.new_customer', 'customer': customer_data},
            )
        else:
            # Existing customer — update their position/preview in the sidebar
            async_to_sync(channel_layer.group_send)(
                f'inbox_{customer.business_id}',
                {'type': 'inbox.update', 'customer_id': str(customer.id), 'message': payload},
            )

    @staticmethod
    def _identify_customer(
        business: Business,
        channel_type: str,
        sender_external_id: str,
        name: str = '',
        phone: str = '',
    ) -> Customer:
        """Find existing customer by platform identity or create a new one."""
        identity = CustomerChannel.objects.select_related('customer').filter(
            customer__business=business,
            channel_type=channel_type,
            external_id=sender_external_id,
        ).first()

        if identity:
            if identity.customer.name != name or identity.customer.phone != phone:
                identity.customer.name = name or identity.customer.name
                identity.customer.phone = phone or identity.customer.phone
                identity.customer.save(update_fields=['name', 'phone', 'updated_at'])
            return identity.customer, False

        # New customer
        new_cust_dic = {'business': business}
        if name:
            new_cust_dic['name'] = name
        if phone:
            new_cust_dic['phone'] = phone
        customer = Customer.objects.create(**new_cust_dic)
        CustomerChannel.objects.create(
            customer=customer,
            channel_type=channel_type,
            external_id=sender_external_id,
        )
        return customer, True

    @staticmethod
    def _enrich_from_instagram(customer, ig_scoped_id: str, channel):
        """
        Fetch Instagram user profile and save to customer.
        - name       → customer.name  (only if still a Guest placeholder)
        - profile_pic → customer.avatar_url
        - remaining keys → customer.extra_fields
        Silently skips if the API call fails or the channel has no access token.
        """
        if not channel.access_token:
            return

        from integrations.services import fetch_instagram_profile
        profile = fetch_instagram_profile(ig_scoped_id, channel.access_token)
        if not profile:
            return

        update_fields = []

        # Replace Guest placeholder names with the real Instagram name
        ig_name = profile.pop('name', None)
        if ig_name and customer.name.startswith('Guest #'):
            customer.name = ig_name
            update_fields.append('name')

        ig_pic = profile.pop('profile_pic', None)
        if ig_pic:
            customer.avatar_url = ig_pic
            update_fields.append('avatar_url')

        # Drop the redundant 'id' field (same as ig_scoped_id)
        profile.pop('id', None)

        # Merge remaining keys into extra_fields
        if profile:
            customer.extra_fields = {**customer.extra_fields, **profile}
            update_fields.append('extra_fields')

        if update_fields:
            update_fields.append('updated_at')
            customer.save(update_fields=update_fields)
            logger.info('Enriched customer %s from Instagram profile', customer.id)

    @staticmethod
    def _map_content_type(platform_type: str) -> str:
        mapping = {
            'text': Message.ContentType.TEXT,
            'image': Message.ContentType.IMAGE,
            'video': Message.ContentType.VIDEO,
            'audio': Message.ContentType.AUDIO,
            'document': Message.ContentType.FILE,
            'template': Message.ContentType.TEMPLATE,
        }
        return mapping.get(platform_type, Message.ContentType.TEXT)


class ReplyService:
    """Sends an outgoing reply from agent or bot."""

    @staticmethod
    def send(
        customer: Customer,
        content: str,
        speaker: str,
        channel: Channel = None,
        agent: User = None,
        content_type: str = Message.ContentType.TEXT,
    ) -> Message:
        """
        Send a reply to the customer.
        channel defaults to customer.last_channel if not provided.
        """
        reply_channel = channel or customer.last_channel

        if not reply_channel:
            raise ValueError('No channel available to send reply.')

        if reply_channel.status != Channel.Status.ACTIVE:
            raise ValueError(f'Channel {reply_channel.name} is not active.')

        message = Message.objects.create(
            customer=customer,
            speaker=speaker,
            speaker_agent=agent,
            channel_type=reply_channel.channel_type.key,
            content_type=content_type,
            content=content,
        )

        # Dispatch via channel adapter
        ReplyService._dispatch(customer, message, reply_channel)

        customer.last_message_at = timezone.now()
        customer.save(update_fields=['last_message_at', 'updated_at'])

        return message

    @staticmethod
    def _dispatch(customer, message, channel):
        """Send the message via the correct platform adapter."""
        from integrations.adapters import AdapterFactory

        if not AdapterFactory.supports(channel.channel_type.key):
            logger.warning(
                'No adapter for channel type "%s" — message saved but not delivered.',
                channel.channel_type.key,
            )
            return

        try:
            adapter = AdapterFactory.get(channel)
            if message.content_type == Message.ContentType.TEXT:
                resp = adapter.send_message(customer, message, channel)
            else:
                resp = adapter.send_media(customer, message, channel)
            # Save platform message ID so read receipts can be matched later
            # WhatsApp: {"messages": [{"id": "wamid..."}]}
            # Instagram / Messenger: {"message_id": "..."}
            r = resp or {}
            channel_key = channel.channel_type.key
            if channel_key == 'whatsapp':
                platform_mid = (r.get('messages') or [{}])[0].get('id')
            else:
                platform_mid = r.get('message_id')
            if platform_mid:
                message.external_id = platform_mid
                message.save(update_fields=['external_id'])
        except Exception as e:
            logger.exception(
                'Adapter dispatch failed for message %s via %s: %s',
                message.id, channel.channel_type.key, e,
            )
            message.send_error = f'Failed to deliver via {channel.channel_type.label}: {e}'
            message.save(update_fields=['send_error'])
