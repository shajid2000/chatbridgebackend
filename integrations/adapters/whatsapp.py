import logging
from .base import BaseChannelAdapter, GRAPH_API_BASE

logger = logging.getLogger(__name__)


class WhatsappAdapter(BaseChannelAdapter):
    """
    WhatsApp Cloud API adapter.
    Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
    """

    def _get_recipient(self, customer, channel):
        identity = customer.channel_identities.filter(channel_type='whatsapp').first()
        if not identity:
            raise ValueError(f'No WhatsApp identity found for customer {customer.id}')
        return identity.external_id

    def send_message(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.phone_number_id}/messages'

        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': 'text',
            'text': {
                'preview_url': False,
                'body': message.content,
            },
        }

        logger.info('WhatsApp send_message → %s', recipient)
        return self._post(url, payload, channel.access_token)

    def send_media(self, customer, message, channel) -> dict:
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.phone_number_id}/messages'

        type_map = {
            'image': 'image',
            'video': 'video',
            'audio': 'audio',
            'file': 'document',
        }
        wa_type = type_map.get(message.content_type, 'document')
        attachment = message.attachments[0] if message.attachments else {}

        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': wa_type,
            wa_type: {
                'link': attachment.get('url', ''),
                'caption': message.content or '',
            },
        }

        logger.info('WhatsApp send_media (%s) → %s', wa_type, recipient)
        return self._post(url, payload, channel.access_token)

    def send_template(self, customer, channel, template_name: str, language: str = 'en_US', components: list = None) -> dict:
        """Send a WhatsApp template message — used for campaigns / first outbound contact."""
        recipient = self._get_recipient(customer, channel)
        url = f'{GRAPH_API_BASE}/{channel.phone_number_id}/messages'

        payload = {
            'messaging_product': 'whatsapp',
            'to': recipient,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language},
                'components': components or [],
            },
        }

        logger.info('WhatsApp send_template (%s) → %s', template_name, recipient)
        return self._post(url, payload, channel.access_token)
