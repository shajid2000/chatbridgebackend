import logging
from .base import BaseChannelAdapter, GRAPH_API_BASE

logger = logging.getLogger(__name__)


class MessengerAdapter(BaseChannelAdapter):
    """
    Facebook Messenger adapter via Meta Graph API Send API.
    Docs: https://developers.facebook.com/docs/messenger-platform/send-messages
    """

    def _get_recipient(self, customer, channel):
        identity = customer.channel_identities.filter(channel_type='messenger').first()
        if not identity:
            raise ValueError(f'No Messenger identity found for customer {customer.id}')
        return identity.external_id

    def send_message(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.page_id}/messages'

        payload = {
            'recipient': {'id': recipient},
            'message': {'text': message.content},
            'messaging_type': 'RESPONSE',
        }

        logger.info('Messenger send_message → %s', recipient)
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

        logger.info('Messenger send_media (%s) → %s', attachment_type, recipient)
        return self._post(url, payload, channel.access_token)

    def send_quick_replies(self, customer, channel, text: str, options: list[dict]) -> dict:
        """
        Send a message with quick reply buttons.
        options = [{'content_type': 'text', 'title': 'Yes', 'payload': 'YES'}]
        """
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.page_id}/messages'

        payload = {
            'recipient': {'id': recipient},
            'message': {
                'text': text,
                'quick_replies': options,
            },
            'messaging_type': 'RESPONSE',
        }

        logger.info('Messenger send_quick_replies → %s', recipient)
        return self._post(url, payload, channel.access_token)
