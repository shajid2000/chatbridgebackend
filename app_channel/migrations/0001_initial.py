import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('integrations', '0005_seed_app_channel_type'),
        ('conversations', '0002_add_send_error_to_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('anonymous_id', models.CharField(db_index=True, max_length=255)),
                ('last_seen_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='app_tokens', to='integrations.channel')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='app_tokens', to='conversations.customer')),
            ],
            options={
                'ordering': ['-last_seen_at'],
                'unique_together': {('channel', 'anonymous_id')},
            },
        ),
    ]
