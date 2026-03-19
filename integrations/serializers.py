from rest_framework import serializers
from .models import Channel, ChannelType, SourceConnection


class ChannelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelType
        fields = ['id', 'key', 'label', 'icon', 'color', 'description',
                  'supports_media', 'supports_templates', 'is_active']


class ChannelSerializer(serializers.ModelSerializer):
    channel_type = ChannelTypeSerializer(read_only=True)
    channel_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ChannelType.objects.filter(is_active=True),
        source='channel_type',
        write_only=True,
    )

    class Meta:
        model = Channel
        fields = [
            'id', 'client_key', 'name', 'channel_type', 'channel_type_id',
            'access_token', 'webhook_secret', 'phone_number_id',
            'page_id', 'status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'client_key', 'status', 'created_at', 'updated_at']
        extra_kwargs = {
            'access_token': {'write_only': True},
            'webhook_secret': {'write_only': True},
        }


class ChannelStatusSerializer(serializers.ModelSerializer):
    """Lightweight serializer for status-only updates."""
    class Meta:
        model = Channel
        fields = ['status']


class SourceConnectionSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    connected_by   = serializers.SerializerMethodField()

    class Meta:
        model = SourceConnection
        fields = [
            'id', 'source', 'source_display',
            # Messenger
            'page_id', 'page_name',
            # WhatsApp
            'waba_id', 'waba_name',
            # Business metadata
            'business_manager_id', 'business_manager_name',
            'business_approved_status', 'business_verification_status',
            # Meta
            'connected_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
        # access_token and page_token are never returned

    def get_connected_by(self, obj):
        if obj.user:
            return {'id': str(obj.user.id), 'full_name': obj.user.full_name, 'email': obj.user.email}
        return None
