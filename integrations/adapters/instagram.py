import logging
from .base import BaseChannelAdapter, GRAPH_API_BASE

logger = logging.getLogger(__name__)


class InstagramAdapter(BaseChannelAdapter):
    """
    Instagram Messaging adapter via Meta Graph API.
    Docs: https://developers.facebook.com/docs/messenger-platform/instagram
    """

    def _get_recipient(self, customer, channel):
        identity = customer.channel_identities.filter(channel_type='instagram').first()
        if not identity:
            raise ValueError(f'No Instagram identity found for customer {customer.id}')
        return identity.external_id

    def send_message(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.page_id}/messages'

        payload = {
            'recipient': {'id': recipient},
            'message': {'text': message.content},
            'messaging_type': 'RESPONSE',
        }

        logger.info('Instagram send_message → %s', recipient)
        return self._post(url, payload, channel.access_token)

    def send_media(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.page_id}/messages'

        type_map = {
            'image': 'image',
            'video': 'video',
            'audio': 'audio',
            'file': 'file',
        }
        attachment_type = type_map.get(message.content_type, 'file')
        attachment = message.attachments[0] if message.attachments else {}

        payload = {
            'recipient': {'id': recipient},
            'message': {
                'attachment': {
                    'type': attachment_type,
                    'payload': {
                        'url': attachment.get('url', ''),
                        'is_reusable': True,
                    },
                }
            },
            'messaging_type': 'RESPONSE',
        }

        logger.info('Instagram send_media (%s) → %s', attachment_type, recipient)
        return self._post(url, payload, channel.access_token)
