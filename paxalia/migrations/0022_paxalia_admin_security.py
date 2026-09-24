import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('paxalia', '0021_remove_loginevent_paxalia_log_is_ad_8ef5a0_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaxaliaDevice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('display_name', models.CharField(default='Paxalia Authenticator', max_length=120)),
                ('status', models.CharField(choices=[('active', 'Active'), ('revoked', 'Revoked'), ('disabled', 'Disabled')], db_index=True, default='active', max_length=16)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('last_authenticated_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('user', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='paxalia_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Paxalia Device',
                'verbose_name_plural': 'Paxalia Devices',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PaxaliaDeviceCredential',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('credential_id', models.CharField(db_index=True, max_length=1024, unique=True)),
                ('credential_public_key', models.BinaryField()),
                ('sign_count', models.PositiveBigIntegerField(default=0)),
                ('webauthn_user_handle', models.BinaryField(max_length=64)),
                ('device_type', models.CharField(blank=True, max_length=32)),
                ('authenticator_attachment', models.CharField(blank=True, max_length=32)),
                ('backed_up', models.BooleanField(default=False)),
                ('aaguid', models.CharField(blank=True, max_length=64)),
                ('transports', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('last_authenticated_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('device', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credential', to='paxalia.paxaliadevice')),
            ],
            options={
                'verbose_name': 'Paxalia Device Credential',
                'verbose_name_plural': 'Paxalia Device Credentials',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PaxaliaWebAuthnChallenge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('registration', 'Registration'), ('authentication', 'Authentication')], db_index=True, max_length=20)),
                ('challenge', models.CharField(db_index=True, max_length=128, unique=True)),
                ('user_handle', models.BinaryField(blank=True, max_length=64, null=True)),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('used_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='webauthn_challenges', to='paxalia.paxaliadevice')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paxalia_webauthn_challenges', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Paxalia WebAuthn Challenge',
                'verbose_name_plural': 'Paxalia WebAuthn Challenges',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PaxaliaRecoveryCode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code_hash', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('used_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paxalia_recovery_codes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Paxalia Recovery Code',
                'verbose_name_plural': 'Paxalia Recovery Codes',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='loginevent',
            name='admin_device',
            field=models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='login_events', to='paxalia.paxaliadevice'),
        ),
        migrations.AddIndex(
            model_name='paxaliadevice',
            index=models.Index(fields=['user', 'status'], name='paxalia_dev_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='paxaliadevicecredential',
            index=models.Index(fields=['device', '-last_authenticated_at'], name='paxalia_cred_last_auth_idx'),
        ),
        migrations.AddIndex(
            model_name='paxaliawebauthnchallenge',
            index=models.Index(fields=['user', 'kind', '-created_at'], name='paxalia_chal_user_kind_idx'),
        ),
        migrations.AddIndex(
            model_name='paxaliawebauthnchallenge',
            index=models.Index(fields=['expires_at', 'used_at'], name='paxalia_chal_exp_used_idx'),
        ),
        migrations.AddIndex(
            model_name='paxaliarecoverycode',
            index=models.Index(fields=['user', 'used_at', 'revoked_at'], name='paxalia_recovery_state_idx'),
        ),
    ]
