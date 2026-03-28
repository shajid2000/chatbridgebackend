from rest_framework import serializers
from .models import AIConfig


class AIConfigSerializer(serializers.ModelSerializer):
    # Write-only so the key is never exposed in GET responses
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Expose whether a key is saved without leaking it
    has_api_key = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AIConfig
        fields = [
            'enabled', 'provider', 'api_key', 'has_api_key',
            'model_name', 'system_prompt', 'context_messages',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

    def get_has_api_key(self, obj):
        return bool(obj.api_key)
