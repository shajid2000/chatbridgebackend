import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0003_source_connection'),
    ]

    operations = [
        migrations.AddField(
            model_name='channel',
            name='client_key',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
