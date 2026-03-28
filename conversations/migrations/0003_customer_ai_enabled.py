from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conversations', '0002_add_send_error_to_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='ai_enabled',
            field=models.BooleanField(
                blank=True,
                null=True,
                default=None,
                help_text='None = follow business AI setting, True = force on, False = opt-out',
            ),
        ),
    ]
