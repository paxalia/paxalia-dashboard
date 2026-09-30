# Generated for Paxalia Dashboard v5 Server Files.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("paxalia", "0022_paxalia_admin_security"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="dashboardaccess",
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": [
                    ("view_billing", "Can view Billing section"),
                    ("view_security", "Can view Security Center"),
                    ("view_backups", "Can view Backups section"),
                    ("view_sites", "Can view Sites section"),
                    ("view_server", "Can view Server monitoring"),
                    ("view_compliance", "Can view Compliance tools"),
                    ("view_logs", "Can view Paxalia Logs"),
                    ("view_server_files", "Can view Paxalia Server Files"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ServerFileOperation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation", models.CharField(choices=[("list", "List directory"), ("preview", "Preview file"), ("download", "Download file"), ("upload", "Upload file"), ("mkdir", "Create directory"), ("rename", "Rename item"), ("move", "Move item"), ("copy", "Copy file"), ("delete", "Delete item"), ("history", "View operation history")], db_index=True, max_length=16)),
                ("root_id", models.CharField(blank=True, max_length=64)),
                ("path", models.CharField(blank=True, max_length=1024)),
                ("target_root_id", models.CharField(blank=True, max_length=64)),
                ("target_path", models.CharField(blank=True, max_length=1024)),
                ("status", models.CharField(choices=[("started", "Started"), ("success", "Succeeded"), ("failed", "Failed"), ("denied", "Denied")], db_index=True, default="started", max_length=12)),
                ("error_code", models.CharField(blank=True, max_length=64)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=128)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="paxalia_server_file_operations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Paxalia Server Files Operation",
                "verbose_name_plural": "Paxalia Server Files Operations",
                "ordering": ["-created_at", "-id"],
                "default_permissions": (),
                "permissions": [
                    ("download_server_files", "Can download files from Paxalia Server Files"),
                    ("upload_server_files", "Can upload files through Paxalia Server Files"),
                    ("modify_server_files", "Can create, rename, move, and copy files in Paxalia Server Files"),
                    ("delete_server_files", "Can delete files in Paxalia Server Files"),
                    ("view_sensitive_files", "Can view sensitive files through Paxalia Server Files"),
                    ("modify_sensitive_files", "Can modify sensitive files through Paxalia Server Files"),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="serverfileoperation",
            index=models.Index(fields=["created_at", "status"], name="pax_sfop_created_status_idx"),
        ),
        migrations.AddIndex(
            model_name="serverfileoperation",
            index=models.Index(fields=["root_id", "created_at"], name="pax_sfop_root_created_idx"),
        ),
    ]

