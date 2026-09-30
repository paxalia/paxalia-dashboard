"""Persistent state for Paxalia Transfer Center operations."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class PaxaliaTransfer(models.Model):
    DIRECTION_CHOICES = [('send', 'Send to server'), ('receive', 'Receive from server')]
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('preparing', 'Preparing'),
        ('transferring', 'Transferring'),
        ('paused', 'Paused'),
        ('interrupted', 'Interrupted'),
        ('verifying', 'Verifying'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='paxalia_transfers')
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES, db_index=True)
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    bytes_transferred = models.PositiveBigIntegerField(default=0)
    chunk_size = models.PositiveIntegerField(default=5 * 1024 * 1024)
    total_chunks = models.PositiveIntegerField(default=0)
    received_chunks = models.JSONField(default=list, blank=True)
    server_root_id = models.CharField(max_length=64, blank=True)
    server_relative_path = models.CharField(max_length=1024, blank=True)
    staging_path = models.CharField(max_length=1024, blank=True)
    upload_session = models.OneToOneField('FileUpload', on_delete=models.SET_NULL, null=True, blank=True, related_name='paxalia_transfer')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='queued', db_index=True)
    checksum_algorithm = models.CharField(max_length=16, default='sha256')
    source_checksum = models.CharField(max_length=64, blank=True)
    destination_checksum = models.CharField(max_length=64, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    error_message = models.CharField(max_length=500, blank=True)
    request_id = models.CharField(max_length=128, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Paxalia Transfer'
        verbose_name_plural = 'Paxalia Transfers'
        indexes = [
            models.Index(fields=['status', 'updated_at'], name='paxalia_transfer_status_idx'),
            models.Index(fields=['direction', 'created_at'], name='paxalia_transfer_direction_idx'),
        ]

    def __str__(self):
        return f"{self.filename} ({self.direction}, {self.status})"

    @property
    def progress_percent(self):
        if not self.size:
            return 0
        return min(100, round((self.bytes_transferred / self.size) * 100, 1))

    @property
    def duration_seconds(self):
        end = self.completed_at or self.updated_at or timezone.now()
        start = self.started_at or self.created_at
        return max(0, (end - start).total_seconds())

    @property
    def average_speed_bytes_per_second(self):
        duration = self.duration_seconds
        if duration <= 0 or not self.bytes_transferred:
            return 0
        return self.bytes_transferred / duration

    @property
    def app_checksum(self):
        """SHA-256 calculated from the application-side transfer payload."""
        return self.source_checksum if self.direction == "send" else self.destination_checksum

    @property
    def client_checksum(self):
        """Backward-compatible alias for the application-side checksum."""
        return self.app_checksum

    @property
    def server_checksum(self):
        """SHA-256 calculated from the server-side payload used by verification."""
        return self.destination_checksum if self.direction == "send" else self.source_checksum

    @property
    def server_checksum_scope(self):
        if self.direction == "send":
            return "server_destination"
        return "server_source"

    @property
    def app_checksum_scope(self):
        if self.direction == "send":
            return "local_source"
        return "downloaded_payload"

    @property
    def client_checksum_scope(self):
        """Backward-compatible alias for the application-side scope."""
        return self.app_checksum_scope

    @property
    def checksum_status(self):
        client = self.app_checksum
        server = self.server_checksum
        if client and server:
            return "verified" if client == server else "mismatch"
        if self.status == "verifying" or client or server:
            return "pending"
        return "not_available"


class PaxaliaTransferLock(models.Model):
    """Singleton row used to serialize global transfer-concurrency checks."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paxalia Transfer Concurrency Lock"
        verbose_name_plural = "Paxalia Transfer Concurrency Locks"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
