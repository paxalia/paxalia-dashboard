# Generated for Paxalia Dashboard v5.0.0 operational infrastructure.
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


def backfill_interval_seconds(apps, schema_editor):
    Monitor = apps.get_model('paxalia', 'UptimeMonitor')
    for monitor in Monitor.objects.all().iterator():
        minutes = int(getattr(monitor, 'check_interval_minutes', 5) or 5)
        monitor.check_interval_seconds = max(30, min(86400, minutes * 60))
        monitor.save(update_fields=['check_interval_seconds'])


def backfill_incident_states(apps, schema_editor):
    Incident = apps.get_model('paxalia', 'UptimeIncident')
    for incident in Incident.objects.all().iterator():
        if incident.resolved_at is not None:
            incident.state = 'recovered'
            incident.first_confirmed_failure_at = incident.first_confirmed_failure_at or incident.started_at
            incident.first_confirmed_recovery_at = incident.first_confirmed_recovery_at or incident.resolved_at
        else:
            incident.state = 'open'
        incident.save(update_fields=['state', 'first_confirmed_failure_at', 'first_confirmed_recovery_at'])


def noop(apps, schema_editor):
    pass


def ensure_transfer_lock(apps, schema_editor):
    Lock = apps.get_model('paxalia', 'PaxaliaTransferLock')
    Lock.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ('paxalia', '0023_server_file_operations'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaxaliaTransferLock',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Paxalia Transfer Concurrency Lock',
                'verbose_name_plural': 'Paxalia Transfer Concurrency Locks',
            },
        ),
        migrations.RunPython(ensure_transfer_lock, noop),
        migrations.CreateModel(
            name='PaxaliaTransfer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('direction', models.CharField(choices=[('send', 'Send to server'), ('receive', 'Receive from server')], db_index=True, max_length=8)),
                ('filename', models.CharField(max_length=255)),
                ('size', models.PositiveBigIntegerField(default=0)),
                ('bytes_transferred', models.PositiveBigIntegerField(default=0)),
                ('chunk_size', models.PositiveIntegerField(default=5242880)),
                ('total_chunks', models.PositiveIntegerField(default=0)),
                ('received_chunks', models.JSONField(blank=True, default=list)),
                ('server_root_id', models.CharField(blank=True, max_length=64)),
                ('server_relative_path', models.CharField(blank=True, max_length=1024)),
                ('staging_path', models.CharField(blank=True, max_length=1024)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('preparing', 'Preparing'), ('transferring', 'Transferring'), ('paused', 'Paused'), ('interrupted', 'Interrupted'), ('verifying', 'Verifying'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('expired', 'Expired')], db_index=True, default='queued', max_length=16)),
                ('checksum_algorithm', models.CharField(default='sha256', max_length=16)),
                ('source_checksum', models.CharField(blank=True, max_length=64)),
                ('destination_checksum', models.CharField(blank=True, max_length=64)),
                ('retry_count', models.PositiveIntegerField(default=0)),
                ('max_retries', models.PositiveIntegerField(default=5)),
                ('error_message', models.CharField(blank=True, max_length=500)),
                ('request_id', models.CharField(blank=True, db_index=True, max_length=128)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('started_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('completed_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paxalia_transfers', to=settings.AUTH_USER_MODEL)),
                ('upload_session', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paxalia_transfer', to='paxalia.fileupload')),
            ],
            options={
                'verbose_name': 'Paxalia Transfer',
                'verbose_name_plural': 'Paxalia Transfers',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(model_name='paxaliatransfer', index=models.Index(fields=['status', 'updated_at'], name='paxalia_transfer_status_idx')),
        migrations.AddIndex(model_name='paxaliatransfer', index=models.Index(fields=['direction', 'created_at'], name='paxalia_transfer_direction_idx')),
        migrations.AddField(model_name='fileupload', name='purpose', field=models.CharField(choices=[('release', 'Release upload'), ('transfer_send', 'Transfer Center send')], db_index=True, default='release', max_length=24)),
        migrations.AddField(model_name='fileupload', name='transfer_id', field=models.UUIDField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name='uptimemonitor', name='kind', field=models.CharField(choices=[('server', 'Server'), ('website', 'Website'), ('api', 'API'), ('endpoint', 'Endpoint')], db_index=True, default='website', max_length=12)),
        migrations.AddField(model_name='uptimemonitor', name='check_interval_seconds', field=models.PositiveIntegerField(db_index=True, default=300)),
        migrations.AddField(model_name='uptimemonitor', name='failure_threshold', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='uptimemonitor', name='recovery_threshold', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='uptimemonitor', name='follow_redirects', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='uptimemonitor', name='request_headers', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='uptimemonitor', name='request_body', field=models.TextField(blank=True)),
        migrations.AddField(model_name='uptimemonitor', name='expected_content_type', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='uptimemonitor', name='response_assertions', field=models.JSONField(blank=True, default=list)),
        migrations.AddIndex(model_name='uptimemonitor', index=models.Index(fields=['is_active', 'check_interval_seconds'], name='paxalia_uptime_due_idx')),
        migrations.AddIndex(model_name='uptimemonitor', index=models.Index(fields=['kind', 'is_active'], name='paxalia_uptime_kind_active_idx')),
        migrations.AddField(model_name='uptimecheck', name='assertion_result', field=models.JSONField(blank=True, default=list)),
        migrations.AddIndex(model_name='uptimecheck', index=models.Index(fields=['monitor', 'status', 'checked_at'], name='paxalia_upt_status_time_idx')),
        migrations.AlterField(model_name='uptimecheck', name='status', field=models.CharField(choices=[('up', 'Up'), ('down', 'Down'), ('unknown', 'Unknown')], db_index=True, max_length=10)),
        migrations.AlterField(model_name='uptimemonitor', name='method', field=models.CharField(choices=[('GET', 'GET'), ('HEAD', 'HEAD'), ('POST', 'POST')], default='GET', max_length=6)),
        migrations.AlterModelOptions(name='uptimemonitor', options={'ordering': ['name'], 'verbose_name': 'Paxalia Availability Monitor', 'verbose_name_plural': 'Paxalia Availability Monitors'}),
        migrations.AddField(model_name='uptimeincident', name='state', field=models.CharField(choices=[('open', 'Open'), ('acknowledged', 'Acknowledged'), ('recovered', 'Recovered')], db_index=True, default='open', max_length=16)),
        migrations.AddField(model_name='uptimeincident', name='last_confirmed_healthy_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='uptimeincident', name='first_confirmed_failure_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='uptimeincident', name='first_confirmed_recovery_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='uptimeincident', name='status_code', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='uptimeincident', name='response_time_ms', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='uptimeincident', name='request_id', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='uptimeincident', name='acknowledged_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='uptimeincident', name='acknowledged_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acknowledged_paxalia_incidents', to=settings.AUTH_USER_MODEL)),
        migrations.AddIndex(model_name='uptimeincident', index=models.Index(fields=['monitor', 'state', '-started_at'], name='paxalia_incident_state_idx')),
        migrations.AlterModelOptions(name='uptimeincident', options={'ordering': ['-started_at'], 'verbose_name': 'Paxalia Availability Incident', 'verbose_name_plural': 'Paxalia Availability Incidents'}),
        migrations.AlterModelOptions(name='dashboardaccess', options={'managed': False, 'default_permissions': (), 'permissions': [
            ('view_billing', 'Can view Billing section'), ('view_security', 'Can view Security Center'),
            ('view_backups', 'Can view Backups section'), ('view_sites', 'Can view Sites section'),
            ('view_server', 'Can view Server monitoring'), ('view_compliance', 'Can view Compliance tools'),
            ('view_logs', 'Can view Paxalia Logs'), ('view_server_files', 'Can view Paxalia Server Files'),
            ('view_availability', 'Can view Paxalia Availability'),
            ('view_transfers', 'Can view Paxalia Transfer Center'), ('create_transfers', 'Can create Paxalia transfers'),
            ('manage_availability', 'Can manage Paxalia Availability'), ('view_incidents', 'Can view Paxalia Availability incidents'),
            ('manage_resource_policies', 'Can manage Paxalia resource policies'),
        ]}),
        migrations.RunPython(backfill_interval_seconds, noop),
        migrations.RunPython(backfill_incident_states, noop),
    ]
