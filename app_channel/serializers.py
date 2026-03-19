from rest_framework import serializers
from conversations.models import Message


class CustomerPublicSerializer(serializers.Serializer):
    """Minimal customer info returned to app clients."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField()


class SessionInitSerializer(serializers.Serializer):
    """Input for POST /api/app/session/init/"""
    client_key = serializers.UUIDField()
    anonymous_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')


class SessionUpdateSerializer(serializers.Serializer):
    """Input for PATCH /api/app/session/me/"""
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)


class AppMessageSerializer(serializers.ModelSerializer):
    """Message serializer for app client responses."""
    speaker_label = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'speaker', 'speaker_label', 'channel_type',
            'content_type', 'content', 'attachments', 'is_read',
            'timestamp',
        ]

    def get_speaker_label(self, obj):
        if obj.speaker == Message.Speaker.CUSTOMER:
            return 'you'
        if obj.speaker == Message.Speaker.AGENT:
            return obj.speaker_agent.full_name if obj.speaker_agent else 'Support'
        return 'Bot'


class AppMessageCreateSerializer(serializers.Serializer):
    """Input for POST /api/app/messages/"""
    content = serializers.CharField(min_length=1)


class AppMessageReadSerializer(serializers.Serializer):
    """Input for POST /api/app/messages/read/"""
    up_to_message_id = serializers.UUIDField(
        required=False,
        help_text='Mark all messages up to and including this ID as read.',
    )
    message_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text='Explicit list of message IDs to mark as read.',
    )

    def validate(self, data):
        if not data.get('up_to_message_id') and not data.get('message_ids'):
            raise serializers.ValidationError('Provide up_to_message_id or message_ids.')
        return data
