from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0005_seed_app_channel_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sourceconnection',
            name='source',
            field=models.CharField(
                choices=[
                    ('facebook.com', 'Facebook Messenger'),
                    ('instagram', 'Instagram Messaging'),
                    ('whatsapp', 'WhatsApp Business'),
                ],
                max_length=20,
            ),
        ),
    ]
