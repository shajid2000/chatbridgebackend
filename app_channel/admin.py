from django.contrib import admin
from .models import AppToken

@admin.register(AppToken)
class AppTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'channel', 'anonymous_id', 'last_seen_at', 'created_at')
    search_fields = ('customer__name', 'channel__name', 'anonymous_id')
    list_filter = ('channel',)
    readonly_fields = ('id', 'token', 'created_at', 'last_seen_at')