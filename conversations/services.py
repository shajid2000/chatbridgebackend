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

        # Skip duplicates
        if external_id and Message.objects.filter(external_id=external_id).exists():
            logger.info('Duplicate message skipped: %s', external_id)
            return None

        business = Business.objects.get(id=business_id)
        channel = Channel.objects.get(id=channel_id)

        customer = MessageProcessor._identify_customer(
            business=business,
            channel_type=channel_type,
            sender_external_id=sender_external_id,
        )

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
        MessageProcessor._broadcast(customer, message)

        return message

    @staticmethod
    def _broadcast(customer, message):
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
            'timestamp': message.timestamp.isoformat(),
        }

        # Notify agents in the open chat window
        async_to_sync(channel_layer.group_send)(
            f'customer_{customer.id}',
            {'type': 'chat.message', 'message': payload},
        )

        # Notify the inbox sidebar
        async_to_sync(channel_layer.group_send)(
            f'inbox_{customer.business_id}',
            {'type': 'inbox.update', 'customer_id': str(customer.id), 'message': payload},
        )

    @staticmethod
    def _identify_customer(
        business: Business,
        channel_type: str,
        sender_external_id: str,
    ) -> Customer:
        """Find existing customer by platform identity or create a new one."""
        identity = CustomerChannel.objects.select_related('customer').filter(
            customer__business=business,
            channel_type=channel_type,
            external_id=sender_external_id,
        ).first()

        if identity:
            return identity.customer

        # New customer
        customer = Customer.objects.create(business=business)
        CustomerChannel.objects.create(
            customer=customer,
            channel_type=channel_type,
            external_id=sender_external_id,
        )
        return customer

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
                adapter.send_message(customer, message, channel)
            else:
                adapter.send_media(customer, message, channel)
        except Exception as e:
            logger.exception(
                'Adapter dispatch failed for message %s via %s: %s',
                message.id, channel.channel_type.key, e,
            )
            raise ValueError(f'Failed to deliver message via {channel.channel_type.label}: {e}')
