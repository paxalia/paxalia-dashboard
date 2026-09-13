import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paxalia', '0012_bot_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='JSError',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('message', models.CharField(db_index=True, max_length=500)),
                ('filename', models.CharField(blank=True, max_length=500)),
                ('lineno', models.PositiveIntegerField(blank=True, null=True)),
                ('colno', models.PositiveIntegerField(blank=True, null=True)),
                ('stack', models.TextField(blank=True, help_text='Truncated client-side; truncated again on write as defense in depth.')),
                ('path', models.CharField(blank=True, db_index=True, max_length=255)),
                ('user_agent', models.CharField(blank=True, max_length=512)),
                ('session_id', models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='js_errors', to='paxalia.site')),
            ],
            options={
                'verbose_name': 'JS Error',
                'verbose_name_plural': 'JS Errors',
                'ordering': ['-created_at'],
            },
        ),
    ]
