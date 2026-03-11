from django.db import migrations


CHANNEL_TYPES = [
    {
        'key': 'whatsapp',
        'label': 'WhatsApp',
        'icon': 'https://cdn.simpleicons.org/whatsapp',
        'color': '#25D366',
        'description': 'WhatsApp Cloud API',
        'is_active': True,
        'supports_media': True,
        'supports_templates': True,
        'sort_order': 1,
    },
    {
        'key': 'instagram',
        'label': 'Instagram',
        'icon': 'https://cdn.simpleicons.org/instagram',
        'color': '#E1306C',
        'description': 'Instagram Direct Messages via Meta',
        'is_active': True,
        'supports_media': True,
        'supports_templates': False,
        'sort_order': 2,
    },
    {
        'key': 'messenger',
        'label': 'Messenger',
        'icon': 'https://cdn.simpleicons.org/messenger',
        'color': '#0099FF',
        'description': 'Facebook Messenger via Meta',
        'is_active': True,
        'supports_media': True,
        'supports_templates': False,
        'sort_order': 3,
    },
    {
        'key': 'webchat',
        'label': 'Web Chat',
        'icon': 'https://cdn.simpleicons.org/chatbot',
        'color': '#6366F1',
        'description': 'Embeddable website chat widget',
        'is_active': True,
        'supports_media': True,
        'supports_templates': False,
        'sort_order': 4,
    },
    {
        'key': 'email',
        'label': 'Email',
        'icon': 'https://cdn.simpleicons.org/gmail',
        'color': '#EA4335',
        'description': 'Email channel via SMTP / IMAP',
        'is_active': True,
        'supports_media': True,
        'supports_templates': True,
        'sort_order': 5,
    },
]


def seed_channel_types(apps, schema_editor):
    ChannelType = apps.get_model('integrations', 'ChannelType')
    for ct in CHANNEL_TYPES:
        ChannelType.objects.get_or_create(key=ct['key'], defaults=ct)


def reverse_seed(apps, schema_editor):
    ChannelType = apps.get_model('integrations', 'ChannelType')
    ChannelType.objects.filter(key__in=[ct['key'] for ct in CHANNEL_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_channel_types, reverse_seed),
    ]
