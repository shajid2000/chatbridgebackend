from django.contrib import admin
from .models import ChannelType, Channel,SourceConnection


@admin.register(ChannelType)
class ChannelTypeAdmin(admin.ModelAdmin):
    list_display = ['label', 'key', 'is_active', 'supports_media', 'supports_templates', 'sort_order']
    list_editable = ['is_active', 'sort_order']
    search_fields = ['label', 'key']
    ordering = ['sort_order']


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'channel_type', 'business', 'status', 'client_key', 'created_at']
    list_filter = ['status', 'channel_type', 'business', 'created_at']
    search_fields = ['name', 'business__name', 'client_key']
    readonly_fields = ['id', 'client_key', 'created_at', 'updated_at']


admin.site.register(SourceConnection)
