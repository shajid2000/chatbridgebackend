from rest_framework import serializers
from .models import Channel, ChannelType


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
            'id', 'name', 'channel_type', 'channel_type_id',
            'access_token', 'webhook_secret', 'phone_number_id',
            'page_id', 'status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']
        extra_kwargs = {
            'access_token': {'write_only': True},
            'webhook_secret': {'write_only': True},
        }


class ChannelStatusSerializer(serializers.ModelSerializer):
    """Lightweight serializer for status-only updates."""
    class Meta:
        model = Channel
        fields = ['status']
