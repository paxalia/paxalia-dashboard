import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('paxalia', '0009_paxalia_api_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduledReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('recipient_emails', models.TextField(help_text='One email address per line.')),
                ('frequency', models.CharField(choices=[('weekly', 'Weekly'), ('monthly', 'Monthly')], default='weekly', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_reports', to='paxalia.site')),
            ],
            options={'verbose_name': 'Scheduled Report', 'verbose_name_plural': 'Scheduled Reports', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ShareLink',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('password_hash', models.CharField(blank=True, help_text='SHA-256. Blank means no password required.', max_length=64)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_viewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='share_links', to='paxalia.site')),
            ],
            options={'verbose_name': 'Share Link', 'verbose_name_plural': 'Share Links', 'ordering': ['-created_at']},
        ),
    ]
