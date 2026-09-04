# Migration for the Security Center: LoginEvent, BlockedIP, SecurityAuditLog
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('analytics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username_attempted', models.CharField(
                    blank=True, max_length=255,
                    help_text="Raw username submitted, kept even if it didn't match any account.")),
                ('result', models.CharField(choices=[('success', 'Success'), ('failed', 'Failed')],
                                             db_index=True, max_length=10)),
                ('failure_reason', models.CharField(blank=True, max_length=255)),
                ('ip_address', models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ('country_code', models.CharField(blank=True, max_length=2)),
                ('country_name', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('user_agent', models.TextField(blank=True)),
                ('browser', models.CharField(blank=True, max_length=100)),
                ('os', models.CharField(blank=True, max_length=100)),
                ('device', models.CharField(blank=True, max_length=50)),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ('is_new_location', models.BooleanField(
                    default=False,
                    help_text="True if this IP/country hadn't been seen before for this user.")),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('logged_out_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='login_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Login Event',
                'verbose_name_plural': 'Login Events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BlockedIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(unique=True)),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Blocked IP',
                'verbose_name_plural': 'Blocked IPs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SecurityAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(
                    db_index=True, max_length=100,
                    help_text="Dotted action code, e.g. 'backup.created', 'settings.updated'.")),
                ('detail', models.TextField(blank=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='security_audit_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Security Audit Log',
                'verbose_name_plural': 'Security Audit Log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='loginevent',
            index=models.Index(fields=['user', '-created_at'], name='analytics_l_user_id_9d1a5e_idx'),
        ),
        migrations.AddIndex(
            model_name='loginevent',
            index=models.Index(fields=['result', '-created_at'], name='analytics_l_result_5f3c2a_idx'),
        ),
    ]
