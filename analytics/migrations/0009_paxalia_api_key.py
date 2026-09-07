import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('analytics', '0008_dashboard_access_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaxaliaAPIKey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text="A label to tell keys apart, e.g. 'Backend service'.", max_length=255)),
                ('key_prefix', models.CharField(editable=False, max_length=16, unique=True)),
                ('key_hash', models.CharField(editable=False, max_length=64)),
                ('scope_ingest', models.BooleanField(default=True, help_text='Allows posting events via the server-to-server ingestion endpoint.')),
                ('scope_read', models.BooleanField(default=False, help_text='Allows reading analytics data via the read API.')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='api_keys', to='analytics.site',
                    help_text='Restrict this key to one site, or leave blank for all sites.')),
            ],
            options={
                'verbose_name': 'Paxalia API Key',
                'verbose_name_plural': 'Paxalia API Keys',
                'ordering': ['-created_at'],
            },
        ),
    ]
