import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class CustomerConsumer(AsyncWebsocketConsumer):
    """
    WebSocket for the chat window.
    Agents subscribe to a specific customer thread.

    Group name: customer_{customer_id}
    All agents viewing the same customer are in this group.
    """

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated or not user.business_id:
            await self.close(code=4001)
            return

        self.customer_id = self.scope['url_route']['kwargs']['customer_id']

        await self.accept()

        self.group_name = f'customer_{self.customer_id}'
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception:
            logger.exception('Chat WS: channel layer unavailable, closing')
            await self.close(code=4500)
            return

        # Verify customer belongs to the agent's business
        customer = await self.get_customer(self.customer_id, user.business_id)
        if not customer:
            await self.close(code=4004)
            return
        
        logger.info('WS connected: user=%s customer=%s', user.id, self.customer_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Agent sends a message or typing event via WebSocket."""
        user = self.scope['user']
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON.')
            return

        if data.get('type') == 'typing':
            try:
                await self.channel_layer.group_send(
                    f'app_customer_{self.customer_id}',
                    {'type': 'app.typing'},
                )
            except Exception:
                pass
            return

        content = data.get('content', '').strip()
        channel_id = data.get('channel_id')

        if not content:
            await self.send_error('Content is required.')
            return

        try:
            message = await self.save_and_send(user, self.customer_id, content, channel_id)
        except ValueError as e:
            # Pre-save error (e.g. no channel configured) — no message was created
            await self.send_error(str(e))
            return

        # Broadcast to all agents in this customer group (even if send_error is set)
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.message',
                'message': message,
            }
        )

        # Notify the inbox sidebar for this business
        await self.channel_layer.group_send(
            f'inbox_{user.business_id}',
            {
                'type': 'inbox.update',
                'customer_id': str(self.customer_id),
                'message': message,
            }
        )

    async def chat_message(self, event):
        """Receive broadcast and forward to WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def chat_typing(self, event):
        """Customer is typing — forward to dashboard agent."""
        await self.send(text_data=json.dumps({'type': 'typing'}))

    async def send_error(self, detail):
        await self.send(text_data=json.dumps({'type': 'error', 'detail': detail}))

    @database_sync_to_async
    def get_customer(self, customer_id, business_id):
        from conversations.models import Customer
        return Customer.objects.filter(id=customer_id, business_id=business_id).first()

    @database_sync_to_async
    def save_and_send(self, user, customer_id, content, channel_id):
        from conversations.models import Customer, Message
        from conversations.services import ReplyService
        from integrations.models import Channel

        customer = Customer.objects.select_related('last_channel__channel_type').get(
            id=customer_id, business_id=user.business_id
        )

        channel = None
        if channel_id:
            channel = Channel.objects.filter(
                id=channel_id, business_id=user.business_id, status='active'
            ).first()

        message = ReplyService.send(
            customer=customer,
            content=content,
            speaker=Message.Speaker.AGENT,
            channel=channel,
            agent=user,
        )

        return {
            'id': str(message.id),
            'speaker': message.speaker,
            'speaker_agent': {
                'id': str(user.id),
                'full_name': user.full_name,
            },
            'channel_type': message.channel_type,
            'content_type': message.content_type,
            'content': message.content,
            'attachments': message.attachments,
            'is_read': message.is_read,
            'send_error': message.send_error or None,
            'timestamp': message.timestamp.isoformat(),
        }


class InboxConsumer(AsyncWebsocketConsumer):
    """
    WebSocket for the inbox sidebar.
    All agents in a business share this connection.
    Receives notifications when any customer gets a new message.

    Group name: inbox_{business_id}
    """

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated or not user.business_id:
            await self.close(code=4001)
            return

        await self.accept()
        self.group_name = f'inbox_{user.business_id}'
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception:
            logger.exception('Inbox WS: channel layer unavailable, closing')
            await self.close(code=4500)
            return
        logger.info('Inbox WS connected: user=%s business=%s', user.id, user.business_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Inbox is read-only from client side
        pass

    async def inbox_update(self, event):
        """Forward inbox update to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'inbox_update',
            'customer_id': event['customer_id'],
            'message': event['message'],
        }))

    async def inbox_merged(self, event):
        """Notify clients that secondary customers were merged into a primary."""
        await self.send(text_data=json.dumps({
            'type': 'customer_merged',
            'primary_id': event['primary_id'],
            'merged_ids': event['merged_ids'],
        }))
