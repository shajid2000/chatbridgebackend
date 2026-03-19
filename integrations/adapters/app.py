import logging
from .base import BaseChannelAdapter

logger = logging.getLogger(__name__)


class AppAdapter(BaseChannelAdapter):
    """
    Adapter for the App channel type.
    Delivers outbound messages to end-user app clients via WebSocket push.
    No external HTTP call — the message is already saved; we push via the channel layer.
    """

    def send_message(self, customer, message, channel):
        self._push(customer, channel, message)

    def send_media(self, customer, message, channel):
        self._push(customer, channel, message)

    def _push(self, customer, channel, message):
        from app_channel.models import AppToken
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        sessions = list(AppToken.objects.filter(customer=customer, channel=channel))
        if not sessions:
            logger.info(
                'AppAdapter: no tokens for customer=%s channel=%s — message saved but not pushed in real-time',
                customer.id, channel.id,
            )
            return

        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning('AppAdapter: channel layer not available')
            return

        payload = {
            'id': str(message.id),
            'speaker': message.speaker,
            'channel_type': message.channel_type,
            'content_type': message.content_type,
            'content': message.content,
            'attachments': message.attachments,
            'timestamp': message.timestamp.isoformat(),
        }

        for t in sessions:
            try:
                async_to_sync(channel_layer.group_send)(
                    f'app_{t.token}',
                    {'type': 'app.message', 'message': payload},
                )
            except Exception:
                logger.warning('AppAdapter: push failed for token %s', t.token)
