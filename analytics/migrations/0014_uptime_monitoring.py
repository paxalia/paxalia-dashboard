import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0013_js_error'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='category',
            field=models.CharField(
                choices=[
                    ('anomaly', 'Anomaly'),
                    ('security', 'Security'),
                    ('report', 'Report'),
                    ('uptime', 'Uptime'),
                    ('general', 'General'),
                ],
                db_index=True, default='general', max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='UptimeMonitor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('url', models.URLField(max_length=500)),
                ('method', models.CharField(choices=[('GET', 'GET'), ('HEAD', 'HEAD'), ('POST', 'POST')], default='GET', max_length=6)),
                ('expected_status_code', models.PositiveIntegerField(default=200)),
                ('timeout_seconds', models.PositiveIntegerField(default=10)),
                ('check_interval_minutes', models.PositiveIntegerField(
                    default=5,
                    help_text='How often this monitor is checked. check_uptime can run as often as '
                              'you like (every minute is typical) — it only actually pings a monitor '
                              'once this many minutes have passed since its last check.',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uptime_monitors', to='analytics.site')),
            ],
            options={
                'verbose_name': 'Uptime Monitor',
                'verbose_name_plural': 'Uptime Monitors',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='UptimeCheck',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('checked_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('status', models.CharField(choices=[('up', 'Up'), ('down', 'Down')], db_index=True, max_length=10)),
                ('status_code', models.PositiveIntegerField(blank=True, null=True)),
                ('response_time_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('error_message', models.CharField(blank=True, max_length=500)),
                ('monitor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='checks', to='analytics.uptimemonitor')),
            ],
            options={
                'ordering': ['-checked_at'],
            },
        ),
        migrations.AddIndex(
            model_name='uptimecheck',
            index=models.Index(fields=['monitor', 'checked_at'], name='analytics_u_monitor_1a2b3c_idx'),
        ),
        migrations.CreateModel(
            name='UptimeIncident',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('resolved_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('cause', models.CharField(blank=True, help_text='error_message from the check that opened this incident.', max_length=500)),
                ('monitor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incidents', to='analytics.uptimemonitor')),
            ],
            options={
                'verbose_name': 'Uptime Incident',
                'verbose_name_plural': 'Uptime Incidents',
                'ordering': ['-started_at'],
            },
        ),
    ]
