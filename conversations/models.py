import uuid
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Business, User
from integrations.models import Channel


class Customer(models.Model):
    """A contact who messages the business — single thread across all channels."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    avatar_url = models.URLField(max_length=1000, blank=True)
    # Last channel used — default for replies
    last_channel = models.ForeignKey(
        Channel, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    assigned_agent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_customers'
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    # Stores raw platform profile data (e.g. Instagram username, follower_count, verification status)
    extra_fields = models.JSONField(default=dict, blank=True)
    # None = follow business AI setting, True = force on, False = opt-out
    ai_enabled = models.BooleanField(null=True, blank=True, default=None)
    status = models.CharField(
        max_length=20,
        choices=[('open', 'Open'), ('resolved', 'Resolved'), ('pending', 'Pending')],
        default='open',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']

    def __str__(self):
        return self.name or str(self.id)


class CustomerChannel(models.Model):
    """Maps a customer's platform identity to their unified Customer record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='channel_identities')
    channel_type = models.CharField(max_length=30)       # whatsapp, instagram, messenger, etc.
    external_id = models.CharField(max_length=255)       # platform-specific user ID
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'channel_type', 'external_id')

    def __str__(self):
        return f'{self.channel_type}:{self.external_id}'


class Message(models.Model):
    """A single message in the customer's unified thread."""

    class Speaker(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        AGENT = 'agent', 'Agent'
        BOT = 'bot', 'Bot'

    class ContentType(models.TextChoices):
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'
        FILE = 'file', 'File'
        TEMPLATE = 'template', 'Template'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='messages')
    speaker = models.CharField(max_length=20, choices=Speaker.choices)
    speaker_agent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_messages'
    )
    # Channel type the message was sent/received through (whatsapp, instagram, etc.)
    channel_type = models.CharField(max_length=30)
    content_type = models.CharField(max_length=20, choices=ContentType.choices, default=ContentType.TEXT)
    content = models.TextField(blank=True)
    # External message ID from the platform — used for deduplication
    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    attachments = models.JSONField(default=list, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    send_error = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'[{self.speaker}] {self.content[:50]}'


@receiver(post_save, sender=Customer)
def set_guest_name(sender, instance, created, **kwargs):
    """Assign a searchable Guest #<id> name to nameless customers on creation."""
    if created and not instance.name:
        Customer.objects.filter(pk=instance.pk).update(
            name=f"Guest #{str(instance.id).replace('-', '')[:6]}"
        )
