import logging

from .base import BaseChannelAdapter
from integrations.source_service import INSTAGRAM_GRAPH

logger = logging.getLogger(__name__)

# Instagram Messaging API uses graph.instagram.com
# Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging
INSTAGRAM_API_VERSION = 'v25.0'
INSTAGRAM_API_BASE = f'{INSTAGRAM_GRAPH}/{INSTAGRAM_API_VERSION}'


class InstagramAdapter(BaseChannelAdapter):
    """
    Instagram Messaging adapter.
    Endpoint : POST graph.instagram.com/{version}/{IG_ID}/messages
    Auth     : Bearer <instagram_user_access_token> (channel.access_token)
    IG_ID    : channel.page_id (the Instagram professional account ID)
    IGSID    : customer's CustomerChannel.external_id for channel_type='instagram'
    """

    def _get_recipient(self, customer):
        identity = customer.channel_identities.filter(channel_type='instagram').first()
        if not identity:
            raise ValueError(f'No Instagram identity found for customer {customer.id}')
        return identity.external_id

    def _messages_url(self, channel):
        return f'{INSTAGRAM_API_BASE}/{channel.page_id}/messages'

    def send_message(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer)
        payload = {
            'recipient': {'id': recipient},
            'message': {'text': message.content},
        }
        logger.info('Instagram send_message -> %s', recipient)
        return self._post(self._messages_url(channel), payload, channel.access_token)

    def send_media(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer)
        attachment = message.attachments[0] if message.attachments else {}
        media_url = attachment.get('url', '')

        if not media_url:
            raise ValueError(f'No Instagram media URL found for message {message.id}')

        if message.content_type == 'image':
            payload = {
                'recipient': {'id': recipient},
                'message': {
                    'attachments': [
                        {
                            'type': 'image',
                            'payload': {'url': media_url},
                        }
                    ]
                },
            }
            logger.info('Instagram send_media (image) -> %s', recipient)
            return self._post(self._messages_url(channel), payload, channel.access_token)

        type_map = {
            'video': 'video',
            'audio': 'audio',
            'file': 'file',
        }
        attachment_type = type_map.get(message.content_type, 'file')

        payload = {
            'recipient': {'id': recipient},
            'message': {
                'attachment': {
                    'type': attachment_type,
                    'payload': {'url': media_url},
                }
            },
        }
        logger.info('Instagram send_media (%s) -> %s', attachment_type, recipient)
        return self._post(self._messages_url(channel), payload, channel.access_token)
