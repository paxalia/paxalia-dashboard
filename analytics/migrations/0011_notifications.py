import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0010_reporting_sharing'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(
                    choices=[('anomaly', 'Anomaly'), ('security', 'Security'), ('report', 'Report'), ('general', 'General')],
                    db_index=True, default='general', max_length=20)),
                ('subject', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='analytics.site')),
            ],
            options={'verbose_name': 'Notification', 'verbose_name_plural': 'Notifications', 'ordering': ['-created_at']},
        ),
    ]
