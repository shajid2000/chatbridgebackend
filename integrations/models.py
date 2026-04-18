import uuid
from django.db import models
from accounts.models import Business, User


class ChannelType(models.Model):
    """
    Defines a supported messaging platform.
    Managed via Django admin — no code change needed to update icons, labels, etc.
    """
    key = models.CharField(max_length=30, unique=True, help_text='e.g. whatsapp, instagram')
    label = models.CharField(max_length=100, help_text='Display name e.g. WhatsApp')
    icon = models.CharField(max_length=255, blank=True, help_text='Icon URL or CSS class')
    color = models.CharField(max_length=20, blank=True, help_text='Brand color hex e.g. #25D366')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, help_text='Show this channel type in the UI')
    supports_media = models.BooleanField(default=True)
    supports_templates = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'label']

    def __str__(self):
        return self.label


class Channel(models.Model):
    """A messaging platform connection belonging to a business."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ERROR = 'error', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='channels')
    channel_type = models.ForeignKey(ChannelType, on_delete=models.PROTECT, related_name='channels')
    name = models.CharField(max_length=100, help_text='Friendly label e.g. "Support WhatsApp"')
    access_token = models.TextField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    # WhatsApp specific
    phone_number_id = models.CharField(max_length=100, blank=True)
    # Instagram / Messenger specific
    page_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.channel_type.label}) — {self.business.name}'


class SourceConnection(models.Model):
    """
    OAuth-based connection to a Meta messaging source (Messenger, Instagram, or WhatsApp).
    One connection per business per source. Stores all Meta tokens and business metadata.
    After connection is finalized this syncs into the Channel model for webhook routing.
    """

    class SourceType(models.TextChoices):
        MESSENGER = 'facebook.com', 'Facebook Messenger'
        INSTAGRAM = 'instagram',    'Instagram Messaging'
        WHATSAPP  = 'whatsapp',     'WhatsApp Business'

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='source_connections')
    user     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='source_connections')
    source   = models.CharField(max_length=20, choices=SourceType.choices)

    # OAuth token (user-level)
    access_token = models.TextField(blank=True)

    # Messenger-specific
    page_name  = models.CharField(max_length=255, blank=True)
    page_id    = models.CharField(max_length=100, blank=True)
    page_token = models.TextField(blank=True)

    # WhatsApp-specific
    waba_id   = models.CharField(max_length=100, blank=True)
    waba_name = models.CharField(max_length=255, blank=True)

    # Business metadata (both)
    business_manager_id          = models.CharField(max_length=100, blank=True)
    business_manager_name        = models.CharField(max_length=255, blank=True)
    business_approved_status     = models.CharField(max_length=50,  blank=True)
    business_verification_status = models.CharField(max_length=50,  blank=True)

    # Raw platform profile data (e.g. Instagram: user_id, username, name, profile_picture_url)
    extra_fields = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('business', 'source')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_source_display()} — {self.business.name}'
