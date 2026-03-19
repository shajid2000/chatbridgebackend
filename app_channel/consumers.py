import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class AppConsumer(AsyncWebsocketConsumer):
    """
    WebSocket for end-user app clients.
    URL: ws/app/<token>/
    Auth: AppToken.token in URL (no JWT required).

    Client sends:    { "content": "Hello!" }
    Client receives: { "type": "message", "message": { ... } }

    Outbound messages (agent → customer) are pushed here by AppAdapter via group_send.
    Inbound messages (customer → agent) are broadcast to the agent's customer group.
    """

    async def connect(self):
        token = self.scope['url_route']['kwargs']['token']
        self.token_data = await self.get_token_data(token)
        if not self.token_data:
            await self.close(code=4001)
            return

        await self.accept()

        self.group_name = f'app_{token}'
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception:
            logger.exception('App WS: channel layer unavailable')
            await self.close(code=4500)
            return

        await self.touch_token(token)
        logger.info('App WS connected: customer=%s channel=%s', self.token_data['customer_id'], self.token_data['channel_id'])

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """End-user sends a message."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        content = data.get('content', '').strip()
        if not content:
            return

        message = await self.create_inbound_message(content)
        if not message:
            return

        # Notify agents: chat window + inbox sidebar
        try:
            await self.channel_layer.group_send(
                f'customer_{self.token_data["customer_id"]}',
                {'type': 'chat.message', 'message': message},
            )
            await self.channel_layer.group_send(
                f'inbox_{self.token_data["business_id"]}',
                {
                    'type': 'inbox.update',
                    'customer_id': self.token_data['customer_id'],
                    'message': message,
                },
            )
        except Exception:
            logger.warning('App WS: failed to broadcast to agent groups')

        # Echo the saved message back to the sender
        await self.send(text_data=json.dumps({'type': 'message', 'message': message}))

    async def app_message(self, event):
        """Agent/bot message pushed by AppAdapter — forward to app client."""
        await self.send(text_data=json.dumps({'type': 'message', 'message': event['message']}))

    # ── DB helpers ──────────────────────────────────────────────────────────

    @database_sync_to_async
    def get_token_data(self, token):
        from .models import AppToken
        try:
            t = AppToken.objects.select_related(
                'customer',
                'channel',
                'channel__channel_type',
                'channel__business',
            ).get(token=token)
            return {
                'pk': str(t.pk),
                'customer_id': str(t.customer.id),
                'business_id': str(t.channel.business_id),
                'channel_id': str(t.channel.id),
                'channel_type': t.channel.channel_type.key,
            }
        except AppToken.DoesNotExist:
            return None

    @database_sync_to_async
    def touch_token(self, token):
        from .models import AppToken
        AppToken.objects.filter(token=token).update(last_seen_at=timezone.now())

    @database_sync_to_async
    def create_inbound_message(self, content):
        from conversations.models import Customer, Message
        from integrations.models import Channel

        try:
            customer = Customer.objects.get(id=self.token_data['customer_id'])
            channel = Channel.objects.select_related('channel_type').get(
                id=self.token_data['channel_id']
            )

            message = Message.objects.create(
                customer=customer,
                speaker=Message.Speaker.CUSTOMER,
                channel_type=self.token_data['channel_type'],
                content_type=Message.ContentType.TEXT,
                content=content,
            )

            customer.last_channel = channel
            customer.last_message_at = timezone.now()
            customer.save(update_fields=['last_channel', 'last_message_at', 'updated_at'])

            return {
                'id': str(message.id),
                'speaker': message.speaker,
                'speaker_agent': None,
                'channel_type': message.channel_type,
                'content_type': message.content_type,
                'content': message.content,
                'attachments': message.attachments,
                'is_read': message.is_read,
                'send_error': None,
                'timestamp': message.timestamp.isoformat(),
            }
        except Exception as e:
            logger.exception('App WS: failed to save message: %s', e)
            return None
