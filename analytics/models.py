import uuid
import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone


# Create your models here.


class PageView(models.Model):
    """Every page visit logged by middleware."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.CharField(max_length=2048)
    path = models.CharField(max_length=255, db_index=True)
    is_bot = models.BooleanField(default=False, help_text="True if the request path matches a bot path.")
    method = models.CharField(max_length=10, default='GET')
    status_code = models.PositiveIntegerField(default=200)
    ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True, max_length=2048)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Geolocation (populated by middleware if GeoIP database is available)
    country_code = models.CharField(max_length=2, blank=True, null=True, db_index=True)
    country_name = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Page View"
        verbose_name_plural = "Page Views"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.method} {self.path}"


class DailySiteStats(models.Model):
    """Aggregated stats per day."""
    date = models.DateField(unique=True, db_index=True)
    total_views = models.PositiveIntegerField(default=0)
    unique_ips = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    api_calls = models.PositiveIntegerField(default=0)
    top_pages = models.JSONField(default=dict, blank=True)
    total_sessions = models.PositiveIntegerField(default=0)
    bounces = models.PositiveIntegerField(default=0)
    bot_views = models.PositiveIntegerField(
        default=0,
        help_text="Requests to paths marked as bot/scanner traffic"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Daily Site Stats"
        verbose_name_plural = "Daily Site Stats"
        ordering = ['-date']

    def __str__(self):
        return f"Stats for {self.date}"


class AnalyticsSettings(models.Model):
    """Singleton model – stores configurable analytics options."""
    anonymize_ip = models.BooleanField(
        default=True,
        help_text="Hash IP addresses with SHA256 before storing"
    )
    ignored_prefixes = models.TextField(
        default="/admin/\n/static/\n/media/",
        help_text="One path prefix per line. Requests starting with these will not be logged."
    )
    ignored_extensions = models.TextField(
        default=".css\n.js\n.png\n.jpg\n.svg\n.ico\n.woff2",
        help_text="One extension per line. Requests to these file types will not be logged."
    )
    realtime_refresh_seconds = models.PositiveIntegerField(
        default=30,
        help_text="How often (in seconds) the real‑time dashboard refreshes"
    )
    tracked_paths = models.TextField(
        blank=True,
        help_text="One path prefix per line. If non‑empty, ONLY these paths will be logged (ignored_paths still apply)."
    )
    bot_paths = models.TextField(
        blank=True,
        help_text="One path prefix per line. Requests to these paths are counted as bot traffic (shown separately)."
    )

    class Meta:
        verbose_name = "Analytics Settings"
        verbose_name_plural = "Analytics Settings"

    def save(self, *args, **kwargs):
        # Enforce singleton
        if AnalyticsSettings.objects.exists() and not self.pk:
            existing = AnalyticsSettings.objects.first()
            for field in self._meta.fields:
                if field.name != 'id':
                    setattr(existing, field.name, getattr(self, field.name))
            existing.save()
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return "Analytics Settings"


class AnalyticsEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=100, db_index=True)
    action = models.CharField(max_length=100, db_index=True)
    label = models.CharField(max_length=255, blank=True, null=True)
    value = models.FloatField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True, null=True)
    session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    country_name = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Analytics Event'
        verbose_name_plural = 'Analytics Events'

    def __str__(self):
        return f"{self.category}:{self.action}"


class BackupConfiguration(models.Model):
    """
    Singleton model that stores backup settings.
    """
    backup_paths = models.TextField(
        blank=True,
        help_text="One path per line (absolute or relative to the project root). Directories and files to include."
    )
    storage_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Absolute path where backup archives will be stored. Must be writable by the web server."
    )
    enabled = models.BooleanField(
        default=False,
        help_text="Enable automatic backups (scheduled via cron)."
    )
    schedule = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual only'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='manual',
        help_text="How often to create backups (requires cron to run the management command)."
    )
    retention_count = models.PositiveIntegerField(
        default=5,
        help_text="Number of most recent backups to keep. Older backups are automatically deleted."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Backup Configuration"
        verbose_name_plural = "Backup Configurations"

    def save(self, *args, **kwargs):
        if BackupConfiguration.objects.exists() and not self.pk:
            existing = BackupConfiguration.objects.first()
            for field in self._meta.fields:
                if field.name != 'id':
                    setattr(existing, field.name, getattr(self, field.name))
            existing.save()
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return "Backup Configuration"

    def get_backup_paths_list(self):
        """Return non‑empty lines as a list."""
        return [p.strip() for p in self.backup_paths.splitlines() if p.strip()]


class BackupArchive(models.Model):
    """
    Metadata for a created backup archive.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(
        max_length=255,
        help_text="Name of the backup file (e.g., backup_20250320_123456.tar.gz)"
    )
    size = models.BigIntegerField(default=0, help_text="File size in bytes")
    created_at = models.DateTimeField(auto_now_add=True)
    storage_path = models.CharField(
        max_length=500,
        help_text="Absolute path to the backup file on disk"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('creating', 'Creating'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Backup Archive"
        verbose_name_plural = "Backup Archives"
        ordering = ['-created_at']

    def __str__(self):
        return self.filename


class LoginEvent(models.Model):
    """
    One row per authentication attempt against the site's normal Django
    auth (staff and, optionally, regular users — see
    ZAYDANY_ANALYTICS['SECURITY_TRACK_ONLY_STAFF']).

    Populated by analytics/signals.py via Django's built-in
    user_logged_in / user_logged_out / user_login_failed signals — no
    custom auth backend required.

    NOTE ON IP STORAGE: unlike PageView.ip_hash (hashed for visitor
    privacy), `ip_address` here is stored in the clear. This is
    operational security data about admin/staff sign-ins, not
    third-party visitor data, so retaining the real IP is intentional —
    you need it to investigate a compromised account. Retention is
    configurable via SECURITY_LOG_RETENTION_DAYS; see
    management/commands/prune_security_logs.py.
    """
    RESULT_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='login_events'
    )
    username_attempted = models.CharField(
        max_length=255, blank=True,
        help_text="Raw username submitted, kept even if it didn't match any account."
    )
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, db_index=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    country_code = models.CharField(max_length=2, blank=True)
    country_name = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    user_agent = models.TextField(blank=True)
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    device = models.CharField(max_length=50, blank=True)

    session_key = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    is_new_location = models.BooleanField(
        default=False,
        help_text="True if this IP/country hadn't been seen before for this user."
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    logged_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Login Event"
        verbose_name_plural = "Login Events"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['result', '-created_at']),
        ]

    def __str__(self):
        who = self.user or self.username_attempted or 'unknown'
        return f"{self.result}: {who} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_active_session(self):
        return self.result == 'success' and self.logged_out_at is None


class BlockedIP(models.Model):
    """IP address blocked from the dashboard / login, managed from the
    Security Center. Enforcement lives in
    analytics/middleware.py::SecurityBlockMiddleware."""
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Blocked IP"
        verbose_name_plural = "Blocked IPs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ip_address} ({'active' if self.active else 'inactive'})"


class SecurityAuditLog(models.Model):
    """
    Records what an authenticated admin *did* inside the dashboard —
    distinct from LoginEvent, which records how they got in.
    Write with analytics.security_audit.log_action(...) from any view.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='security_audit_entries'
    )
    action = models.CharField(
        max_length=100, db_index=True,
        help_text="Dotted action code, e.g. 'backup.created', 'settings.updated'."
    )
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Security Audit Log"
        verbose_name_plural = "Security Audit Log"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.user or 'system'} @ {self.created_at:%Y-%m-%d %H:%M}"


class CSPViolation(models.Model):
    """
    Stores Content-Security-Policy violation reports POSTed to
    analytics:csp_report. This package does not set the CSP header
    itself (that's the host project's job) — it only provides the
    collection endpoint. Point your CSP's report-uri/report-to at
    /<dashboard-path>/csp-report/ to start receiving reports here.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocked_uri = models.CharField(max_length=2048, blank=True)
    violated_directive = models.CharField(max_length=255, blank=True)
    document_uri = models.CharField(max_length=2048, blank=True)
    source_file = models.CharField(max_length=2048, blank=True)
    line_number = models.PositiveIntegerField(null=True, blank=True)
    raw_report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "CSP Violation"
        verbose_name_plural = "CSP Violations"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.violated_directive} blocked {self.blocked_uri}"[:120]


class FileUpload(models.Model):
    """
    Tracks a single chunked upload session. The actual bytes are written
    directly to disk as chunks arrive (see views/uploads.py) — this model
    only stores metadata, never file content, to keep the DB small.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('uploading', 'Uploading'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='file_uploads'
    )
    original_filename = models.CharField(max_length=255)
    total_size = models.BigIntegerField(
        help_text="Expected total size in bytes, sent by client at init"
    )
    bytes_received = models.BigIntegerField(default=0)
    chunk_size = models.IntegerField(
        help_text="Size of each chunk in bytes, as used by the client"
    )
    total_chunks = models.IntegerField()
    chunks_received = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    storage_path = models.CharField(
        max_length=500,
        help_text="Absolute path to the file on disk once completed"
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "File Upload"
        verbose_name_plural = "File Uploads"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_filename} ({self.status})"

    @property
    def progress_percent(self):
        if self.total_size == 0:
            return 0
        return round((self.bytes_received / self.total_size) * 100, 1)
