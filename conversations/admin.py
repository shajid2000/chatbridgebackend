from django.contrib import admin
from .models import Customer, CustomerChannel, Message


class CustomerChannelInline(admin.TabularInline):
    model = CustomerChannel
    extra = 0
    readonly_fields = ['channel_type', 'external_id', 'created_at']


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['speaker', 'channel_type', 'content', 'timestamp']
    ordering = ['timestamp']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'business', 'status', 'assigned_agent', 'last_message_at', 'created_at']
    list_filter = ['status', 'business']
    search_fields = ['name', 'phone', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_message_at']
    inlines = [CustomerChannelInline, MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['customer', 'speaker', 'channel_type', 'content_type', 'is_read', 'timestamp']
    list_filter = ['speaker', 'channel_type', 'is_read']
    search_fields = ['content', 'customer__name']
    readonly_fields = ['id', 'timestamp', 'external_id', 'raw_payload']
