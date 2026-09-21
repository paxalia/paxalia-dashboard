from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ('paxalia', '0019_sharelink_password_hash'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaxaliaLogGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('fingerprint', models.CharField(db_index=True, max_length=64, unique=True)),
                ('severity', models.CharField(db_index=True, max_length=10)),
                ('source', models.CharField(db_index=True, max_length=50)),
                ('category', models.CharField(blank=True, db_index=True, max_length=100)),
                ('exception_type', models.CharField(blank=True, max_length=255)),
                ('normalized_message', models.CharField(blank=True, max_length=2000)),
                ('first_seen', models.DateTimeField(db_index=True, default=timezone.now)),
                ('last_seen', models.DateTimeField(db_index=True, default=timezone.now)),
                ('occurrence_count', models.PositiveBigIntegerField(default=0)),
                ('suppressed_count', models.PositiveBigIntegerField(default=0)),
                ('window_started_at', models.DateTimeField(default=timezone.now)),
                ('sample_count', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Paxalia Log Group',
                'verbose_name_plural': 'Paxalia Log Groups',
                'ordering': ['-last_seen'],
                'indexes': [
                    models.Index(fields=['source', 'last_seen'], name='paxalia_plg_source_9f07a3_idx'),
                    models.Index(fields=['severity', 'last_seen'], name='paxalia_plg_severit_1e7f8a_idx'),
                    models.Index(fields=['category', 'last_seen'], name='paxalia_plg_category_79dc5c_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='PaxaliaLogEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('timestamp', models.DateTimeField(db_index=True, default=timezone.now)),
                ('received_at', models.DateTimeField(db_index=True, default=timezone.now)),
                ('severity', models.CharField(choices=[('DEBUG', 'Debug'), ('INFO', 'Info'), ('WARNING', 'Warning'), ('ERROR', 'Error'), ('CRITICAL', 'Critical')], db_index=True, max_length=10)),
                ('source', models.CharField(db_index=True, default='Other', max_length=50)),
                ('category', models.CharField(blank=True, db_index=True, max_length=100)),
                ('action', models.CharField(blank=True, db_index=True, max_length=100)),
                ('logger_name', models.CharField(blank=True, db_index=True, max_length=255)),
                ('message', models.TextField()),
                ('exception_type', models.CharField(blank=True, db_index=True, max_length=255)),
                ('stack_trace', models.TextField(blank=True)),
                ('module', models.CharField(blank=True, max_length=255)),
                ('file_name', models.CharField(blank=True, max_length=500)),
                ('line_number', models.PositiveIntegerField(blank=True, null=True)),
                ('function_name', models.CharField(blank=True, max_length=255)),
                ('session_id', models.CharField(blank=True, db_index=True, max_length=64)),
                ('request_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('correlation_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('trace_id', models.CharField(blank=True, db_index=True, max_length=100)),
                ('request_method', models.CharField(blank=True, max_length=20)),
                ('request_path', models.CharField(blank=True, db_index=True, max_length=2048)),
                ('response_status', models.PositiveSmallIntegerField(blank=True, db_index=True, null=True)),
                ('duration_ms', models.FloatField(blank=True, null=True)),
                ('traffic_type', models.CharField(choices=[('WEB', 'Web'), ('API', 'API'), ('BOT', 'Bot'), ('INTERNAL', 'Internal')], db_index=True, default='INTERNAL', max_length=12)),
                ('is_api', models.BooleanField(db_index=True, default=False)),
                ('is_bot', models.BooleanField(db_index=True, default=False)),
                ('bot_category', models.CharField(blank=True, db_index=True, max_length=30)),
                ('user_display', models.CharField(blank=True, max_length=255)),
                ('user_type', models.CharField(blank=True, max_length=100)),
                ('admin_flag', models.BooleanField(db_index=True, default=False)),
                ('ip_address', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('ip_mode', models.CharField(default='none', max_length=10)),
                ('user_agent', models.CharField(blank=True, max_length=512)),
                ('browser', models.CharField(blank=True, max_length=100)),
                ('operating_system', models.CharField(blank=True, max_length=100)),
                ('device', models.CharField(blank=True, max_length=50)),
                ('process_id', models.IntegerField(blank=True, null=True)),
                ('thread_name', models.CharField(blank=True, max_length=255)),
                ('host', models.CharField(blank=True, max_length=255)),
                ('environment', models.CharField(blank=True, max_length=100)),
                ('release', models.CharField(blank=True, max_length=100)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('fingerprint', models.CharField(db_index=True, max_length=64)),
                ('sensitive_data_state', models.CharField(choices=[('safe', 'Safe'), ('redacted', 'Redacted'), ('protected', 'Protected')], default='redacted', max_length=10)),
                ('group', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='paxalia.paxalialoggroup')),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paxalia_log_events', to='paxalia.site')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paxalia_log_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Paxalia Log Event',
                'verbose_name_plural': 'Paxalia Log Events',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['timestamp', 'severity'], name='paxalia_plo_timest_1e6d6f_idx'),
                    models.Index(fields=['source', 'timestamp'], name='paxalia_plo_source_3e4ce5_idx'),
                    models.Index(fields=['traffic_type', 'timestamp'], name='paxalia_plo_traffic_4a5f48_idx'),
                    models.Index(fields=['request_id', 'timestamp'], name='paxalia_plo_request_5e75ae_idx'),
                    models.Index(fields=['correlation_id', 'timestamp'], name='paxalia_plo_correlat_4f57d6_idx'),
                    models.Index(fields=['exception_type', 'timestamp'], name='paxalia_plo_exceptio_6c9d5d_idx'),
                    models.Index(fields=['fingerprint', 'timestamp'], name='paxalia_plo_fingerp_09d9df_idx'),
                ],
            },
        ),
        migrations.AddField(
            model_name='loginevent', name='event_type',
            field=models.CharField(choices=[('login', 'Login'), ('logout', 'Logout')], db_index=True, default='login', max_length=10),
        ),
        migrations.AddField(
            model_name='loginevent', name='is_admin',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='loginevent', name='request_id',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name='loginevent', name='correlation_id',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name='loginevent', name='trace_id',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name='loginevent', name='traffic_type',
            field=models.CharField(choices=[('WEB', 'Web'), ('API', 'API'), ('BOT', 'Bot'), ('INTERNAL', 'Internal')], db_index=True, default='WEB', max_length=12),
        ),
        migrations.AddField(
            model_name='loginevent', name='failure_category',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name='loginevent', name='identifier_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddIndex(
            model_name='loginevent', index=models.Index(fields=['is_admin', 'created_at'], name='paxalia_log_is_ad_8ef5a0_idx'),
        ),
        migrations.AddIndex(
            model_name='loginevent', index=models.Index(fields=['event_type', 'created_at'], name='paxalia_log_event_t_c37d22_idx'),
        ),
        migrations.AddIndex(
            model_name='loginevent', index=models.Index(fields=['failure_category', 'created_at'], name='paxalia_log_failur_429dee_idx'),
        ),
        migrations.AlterModelOptions(
            name='dashboardaccess',
            options={
                'default_permissions': (),
                'managed': False,
                'permissions': [
                    ('view_billing', 'Can view Billing section'),
                    ('view_security', 'Can view Security Center'),
                    ('view_backups', 'Can view Backups section'),
                    ('view_sites', 'Can view Sites section'),
                    ('view_server', 'Can view Server monitoring'),
                    ('view_compliance', 'Can view Compliance tools'),
                    ('view_logs', 'Can view Paxalia Logs'),
                ],
            },
        ),
    ]
