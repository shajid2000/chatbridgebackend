import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIConfig',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('enabled', models.BooleanField(default=False)),
                ('provider', models.CharField(
                    choices=[('gemini', 'Google Gemini'), ('openai', 'OpenAI')],
                    default='gemini',
                    max_length=20,
                )),
                ('api_key', models.TextField(blank=True)),
                ('model_name', models.CharField(default='gemini-2.0-flash', max_length=100,
                    help_text='Provider model ID, e.g. gemini-2.0-flash')),
                ('system_prompt', models.TextField(blank=True,
                    help_text='Instructions and knowledge for the AI agent (business context, tone, FAQ, etc.)')),
                ('context_messages', models.PositiveSmallIntegerField(default=10,
                    help_text='Number of recent messages sent as context to the AI.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ai_config',
                    to='accounts.business',
                )),
            ],
        ),
    ]
