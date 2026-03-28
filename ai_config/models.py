import uuid
from django.db import models
from accounts.models import Business


class AIConfig(models.Model):
    """
    Per-business AI agent configuration.
    One config per business — controls provider, credentials, and behaviour.
    """

    class Provider(models.TextChoices):
        GEMINI = 'gemini', 'Google Gemini'
        OPENAI = 'openai', 'OpenAI'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name='ai_config'
    )
    enabled = models.BooleanField(default=False)
    provider = models.CharField(
        max_length=20, choices=Provider.choices, default=Provider.GEMINI
    )
    api_key = models.TextField(blank=True)
    model_name = models.CharField(
        max_length=100,
        default='gemini-2.0-flash',
        help_text='Provider model ID, e.g. gemini-2.0-flash',
    )
    system_prompt = models.TextField(
        blank=True,
        help_text='Instructions and knowledge for the AI agent (business context, tone, FAQ, etc.)',
    )
    # How many recent messages to include as context for each reply
    context_messages = models.PositiveSmallIntegerField(
        default=10,
        help_text='Number of recent messages sent as context to the AI.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'AIConfig({self.business.name}, {self.provider}, enabled={self.enabled})'
