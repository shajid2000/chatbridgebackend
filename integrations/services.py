import hashlib
import hmac
import json
from accounts.models import Business
from .models import Channel, ChannelType


class ChannelService:

    @staticmethod
    def connect(business: Business, validated_data: dict) -> Channel:
        """Create and activate a new channel for a business."""
        channel = Channel.objects.create(
            business=business,
            status=Channel.Status.ACTIVE,
            **validated_data,
        )
        return channel

    @staticmethod
    def disconnect(channel: Channel) -> Channel:
        """Deactivate a channel."""
        channel.status = Channel.Status.INACTIVE
        channel.save(update_fields=['status', 'updated_at'])
        return channel


class WebhookVerifier:

    @staticmethod
    def verify_meta(payload: bytes, signature_header: str, secret: str) -> bool:
        """Verify Meta (WhatsApp / Instagram / Messenger) webhook signature."""
        if not signature_header or not signature_header.startswith('sha256='):
            return False
        expected = 'sha256=' + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    @staticmethod
    def verify_whatsapp(payload: bytes, signature_header: str, secret: str) -> bool:
        """WhatsApp Cloud API uses same sha256 scheme as Meta."""
        return WebhookVerifier.verify_meta(payload, signature_header, secret)


class MessageNormalizer:
    """
    Converts raw webhook payloads into a unified message format.
    Phase 3 will consume this normalized dict to create DB records.
    """

    @staticmethod
    def from_whatsapp(payload: dict) -> list[dict]:
        messages = []
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                for msg in value.get('messages', []):
                    messages.append({
                        'channel_type': 'whatsapp',
                        'external_id': msg.get('id'),
                        'sender_external_id': msg.get('from'),
                        'phone_number_id': value.get('metadata', {}).get('phone_number_id'),
                        'type': msg.get('type'),
                        'content': msg.get('text', {}).get('body', ''),
                        'raw': msg,
                    })
        return messages

    @staticmethod
    def from_instagram(payload: dict) -> list[dict]:
        messages = []
        for entry in payload.get('entry', []):
            for event in entry.get('messaging', []):
                msg = event.get('message', {})
                messages.append({
                    'channel_type': 'instagram',
                    'external_id': msg.get('mid'),
                    'sender_external_id': event.get('sender', {}).get('id'),
                    'page_id': entry.get('id'),
                    'type': 'text',
                    'content': msg.get('text', ''),
                    'raw': event,
                })
        return messages

    @staticmethod
    def from_messenger(payload: dict) -> list[dict]:
        """Messenger uses the same structure as Instagram."""
        messages = MessageNormalizer.from_instagram(payload)
        for m in messages:
            m['channel_type'] = 'messenger'
        return messages
