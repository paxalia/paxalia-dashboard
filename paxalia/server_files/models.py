"""Persistent, content-free Server Files operation history."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ServerFileOperation(models.Model):
    """Records who attempted a file operation without storing file contents.

    Path values are root-relative and are redacted for sensitive targets by
    the audit service. The row is created as ``started`` before an operation
    and finalized afterward, so an interrupted operation remains observable.
    """
    OPERATIONS = [
        ("list", "List directory"),
        ("preview", "Preview file"),
        ("download", "Download file"),
        ("upload", "Upload file"),
        ("mkdir", "Create directory"),
        ("rename", "Rename item"),
        ("move", "Move item"),
        ("copy", "Copy file"),
        ("delete", "Delete item"),
        ("history", "View operation history"),
    ]
    STATUSES = [
        ("started", "Started"),
        ("success", "Succeeded"),
        ("failed", "Failed"),
        ("denied", "Denied"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paxalia_server_file_operations",
    )
    operation = models.CharField(max_length=16, choices=OPERATIONS, db_index=True)
    root_id = models.CharField(max_length=64, blank=True)
    path = models.CharField(max_length=1024, blank=True)
    target_root_id = models.CharField(max_length=64, blank=True)
    target_path = models.CharField(max_length=1024, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default="started", db_index=True)
    error_code = models.CharField(max_length=64, blank=True)
    request_id = models.CharField(max_length=128, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "Paxalia Server Files Operation"
        verbose_name_plural = "Paxalia Server Files Operations"
        ordering = ["-created_at", "-id"]
        default_permissions = ()
        permissions = [
            ("view_server_files", "Can view Paxalia Server Files"),
            ("download_server_files", "Can download files from Paxalia Server Files"),
            ("upload_server_files", "Can upload files through Paxalia Server Files"),
            ("modify_server_files", "Can create, rename, move, and copy files in Paxalia Server Files"),
            ("delete_server_files", "Can delete files in Paxalia Server Files"),
            ("view_sensitive_files", "Can view sensitive files through Paxalia Server Files"),
            ("modify_sensitive_files", "Can modify sensitive files through Paxalia Server Files"),
        ]
        indexes = [
            models.Index(fields=["created_at", "status"], name="pax_sfop_created_status_idx"),
            models.Index(fields=["root_id", "created_at"], name="pax_sfop_root_created_idx"),
        ]

    def __str__(self):
        return f"{self.operation} ({self.status}) at {self.created_at:%Y-%m-%d %H:%M}"
