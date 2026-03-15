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
    list_display = ['name', 'channel_type', 'business', 'status', 'created_at']
    list_filter = ['status', 'channel_type', 'business']
    search_fields = ['name', 'business__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


admin.site.register(SourceConnection)
