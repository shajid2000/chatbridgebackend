import uuid
from django.db import models
from integrations.models import Channel
from conversations.models import Customer


class AppToken(models.Model):
    """
    Server-issued bearer token for an end-user app client.

    Identity is tracked by the existing CustomerChannel model:
        CustomerChannel(customer=..., channel_type='app', external_id=anonymous_id)

    This model only stores the auth token so the client can authenticate
    REST calls and WebSocket connections without re-sending credentials each time.

    Because the customer thread lives in Customer + CustomerChannel, the agent
    sees all messages across all channels (WhatsApp, App, etc.) in one place
    and can reply via any channel from the dashboard.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='app_tokens')
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='app_tokens')
    # Server-issued bearer token — sent as X-App-Token header
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    # Client-generated stable device/browser ID (mirrors CustomerChannel.external_id)
    anonymous_id = models.CharField(max_length=255, db_index=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('channel', 'anonymous_id')]
        ordering = ['-last_seen_at']

    def __str__(self):
        return f'AppToken({self.channel.name} / {self.anonymous_id[:12]})'
