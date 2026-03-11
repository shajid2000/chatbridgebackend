from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Customer, CustomerChannel, Message


class CustomerChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerChannel
        fields = ['id', 'channel_type', 'external_id', 'created_at']


class CustomerSerializer(serializers.ModelSerializer):
    channel_identities = CustomerChannelSerializer(many=True, read_only=True)
    assigned_agent = UserSerializer(read_only=True)
    last_channel_type = serializers.SerializerMethodField()
    last_channel_id = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'email', 'avatar_url',
            'status', 'last_channel_type', 'last_channel_id', 'assigned_agent',
            'channel_identities', 'last_message_at', 'created_at',
        ]
        read_only_fields = ['id', 'last_message_at', 'created_at']

    def get_last_channel_type(self, obj):
        if obj.last_channel:
            return obj.last_channel.channel_type.key
        return None

    def get_last_channel_id(self, obj):
        if obj.last_channel:
            return str(obj.last_channel.id)
        return None


class MessageSerializer(serializers.ModelSerializer):
    speaker_agent = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'speaker', 'speaker_agent', 'channel_type',
            'content_type', 'content', 'attachments',
            'is_read', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField()
    content_type = serializers.ChoiceField(
        choices=Message.ContentType.choices,
        default=Message.ContentType.TEXT,
    )
    channel_id = serializers.UUIDField(
        required=False,
        help_text='Override reply channel. Defaults to customer last_channel.',
    )


class AssignAgentSerializer(serializers.Serializer):
    agent_id = serializers.UUIDField(allow_null=True)
