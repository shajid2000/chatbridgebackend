from django.db import migrations


def seed_app_channel(apps, schema_editor):
    ChannelType = apps.get_model('integrations', 'ChannelType')
    ChannelType.objects.get_or_create(
        key='app',
        defaults={
            'label': 'App',
            'color': '#6366f1',
            'description': 'Direct integration via client key — web, mobile, or native app.',
            'supports_media': False,
            'supports_templates': False,
            'sort_order': 10,
        },
    )


def unseed_app_channel(apps, schema_editor):
    ChannelType = apps.get_model('integrations', 'ChannelType')
    ChannelType.objects.filter(key='app').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0004_channel_client_key'),
    ]

    operations = [
        migrations.RunPython(seed_app_channel, unseed_app_channel),
    ]
