import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_security_center'),
    ]

    operations = [
        migrations.CreateModel(
            name='CSPViolation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('blocked_uri', models.CharField(blank=True, max_length=2048)),
                ('violated_directive', models.CharField(blank=True, max_length=255)),
                ('document_uri', models.CharField(blank=True, max_length=2048)),
                ('source_file', models.CharField(blank=True, max_length=2048)),
                ('line_number', models.PositiveIntegerField(blank=True, null=True)),
                ('raw_report', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'CSP Violation',
                'verbose_name_plural': 'CSP Violations',
                'ordering': ['-created_at'],
            },
        ),
    ]
