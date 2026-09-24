import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# Create your models here.

class Site(models.Model):
    """
    A tracked property/domain. This single Django install can serve (or
    receive tracking data for) more than one site — requests are matched
    to a Site by hostname (see AnalyticsMiddleware._resolve_site()).

    Unmatched hosts get site=None rather than being force-assigned to a
    default Site — see AUTO_CREATE_SITES in settings.py for the opt-in
    convenience behavior if you'd rather not pre-register every domain.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    domain = models.CharField(
        max_length=255, unique=True, db_index=True,
        help_text="Hostname only, no scheme/port, e.g. 'example.com'."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.domain})"


class PageView(models.Model):
    """Every page visit logged by middleware."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='page_views',
        help_text="Resolved from the request's hostname. Null if the host didn't match any registered Site."
    )
    url = models.CharField(max_length=2048)
    path = models.CharField(max_length=255, db_index=True)
    is_bot = models.BooleanField(
        default=False, db_index=True,
        help_text=(
            "True if the request path matched a known scanner/attack-probe "
            "path (AnalyticsSettings.bot_paths), OR the User-Agent matched a "
            "known crawler/bot pattern (see bot_classification.py) — this "
            "field's meaning was widened in the phase that added "
            "bot_category; see that module's BREAKING CHANGE note."
        )
    )
    bot_category = models.CharField(
        max_length=20, blank=True, default='', db_index=True,
        choices=[
            ('search_engine', 'Search engine'),
            ('ai_crawler', 'AI crawler'),
            ('social_preview', 'Social preview'),
            ('seo_tool', 'SEO tool'),
            ('unknown', 'Unknown bot'),
            ('malicious', 'Malicious / scanner'),
        ],
        help_text=(
            "Set once by the middleware at write time (see "
            "bot_classification.py::classify_bot) — empty string means "
            "not a bot. Existing rows from before this field was added "
            "can be backfilled with `manage.py backfill_pageview_bot_category`."
        )
    )
    is_api = models.BooleanField(
        default=False, db_index=True,
        help_text=(
            "True if the request path matched API_PATH_PREFIX. Set once by "
            "the middleware at write time so every view can filter page "
            "views and API calls apart with a plain field lookup instead of "
            "re-matching the path prefix in every query. Existing rows from "
            "before this field was added can be backfilled with "
            "`manage.py backfill_pageview_is_api`."
        )
    )
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

    # UTM campaign parameters, parsed once from the query string at write
    # time (same reasoning as is_bot/is_api — a plain field lookup beats
    # re-parsing the URL in every view that wants campaign data).
    utm_source = models.CharField(max_length=255, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True, db_index=True)
    utm_term = models.CharField(max_length=255, blank=True)
    utm_content = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Page View"
        verbose_name_plural = "Page Views"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.method} {self.path}"


class DailySiteStats(models.Model):
    """Aggregated stats per day, per site (site=None aggregates unmatched-host traffic)."""
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, null=True, blank=True, related_name='daily_stats'
    )
    date = models.DateField(db_index=True)
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
    imported_from = models.CharField(
        max_length=20, blank=True, default='',
        choices=[('ga', 'Google Analytics'), ('plausible', 'Plausible'), ('csv', 'Generic CSV')],
        help_text="Set by manage.py / the Data Import page when this row came from a historical CSV import "
                  "rather than this package's own live tracking. Empty for every normally-tracked day."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Daily Site Stats"
        verbose_name_plural = "Daily Site Stats"
        ordering = ['-date']
        # NOT unique_together=[('site','date')] — that never actually
        # protected the site=NULL case (SQL treats every NULL as
        # distinct from every other NULL for uniqueness), which is
        # exactly what caused the "MultipleObjectsReturned" bug fixed
        # in migration 0018. Two partial unique indexes replicate the
        # intended rule correctly for both a real site and the
        # NULL/unassigned bucket.
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'date'], condition=models.Q(site__isnull=False),
                name='unique_dailysitestats_site_date',
            ),
            models.UniqueConstraint(
                fields=['date'], condition=models.Q(site__isnull=True),
                name='unique_dailysitestats_date_when_site_null',
            ),
        ]

    def __str__(self):
        return f"Stats for {self.site or 'all sites'} on {self.date}"


class AnalyticsSettings(models.Model):
    """Singleton model – stores configurable paxalia options."""
    anonymize_ip = models.BooleanField(
        default=False,
        help_text="Hash IP addresses with SHA256 before storing. Off by default — turn on if you want visitor IPs anonymized."
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
    search_query_params = models.TextField(
        default="q\nsearch\nquery",
        blank=True,
        help_text="One query-string parameter name per line. A request whose URL includes any of these params is logged as a site-search event (see AnalyticsEvent, category='site_search')."
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
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
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


class JSError(models.Model):
    """
    Client-side JS errors reported via window.onerror /
    unhandledrejection — see paxalia-events.js. Kept as its own model
    (rather than squeezed into AnalyticsEvent's generic 255-char label)
    because a useful error report needs filename/line/column and a
    stack trace, which AnalyticsEvent has no room for.

    Every occurrence is stored as its own row (same approach as
    AnalyticsEvent) — the RUM dashboard groups them by message for a
    "top errors" view rather than deduplicating at write time, so nothing
    here needs a fingerprint/hash field.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='js_errors')
    message = models.CharField(max_length=500, db_index=True)
    filename = models.CharField(max_length=500, blank=True)
    lineno = models.PositiveIntegerField(null=True, blank=True)
    colno = models.PositiveIntegerField(null=True, blank=True)
    stack = models.TextField(blank=True, help_text="Truncated client-side; truncated again on write as defense in depth.")
    path = models.CharField(max_length=255, blank=True, db_index=True)
    user_agent = models.CharField(max_length=512, blank=True)
    session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'JS Error'
        verbose_name_plural = 'JS Errors'

    def __str__(self):
        return self.message[:80]


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

    def get_path_overlap_warning(self):
        """
        Return a warning string if storage_path is the same as, sits
        inside, or contains one of the configured backup_paths — any of
        which means each new backup would include previously-created
        backup archives, growing without bound. Returns None if
        nothing is configured yet, or if the paths look safe.

        Used both to block saving an unsafe configuration
        (views/backup.py) and by the Security Scorecard
        (security_scorecard.py) to flag an already-saved one.
        """
        if not self.storage_path:
            return None
        storage = os.path.normpath(os.path.abspath(self.storage_path))
        for raw in self.get_backup_paths_list():
            candidate = os.path.normpath(os.path.abspath(raw))
            if (
                storage == candidate
                or storage.startswith(candidate + os.sep)
                or candidate.startswith(storage + os.sep)
            ):
                return (
                    f'Storage path overlaps backup path "{raw}" — backups would '
                    'include previously-created archives and grow without bound.'
                )
        return None


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
    PAXALIA_DASHBOARD['SECURITY_TRACK_ONLY_STAFF']).

    Populated by paxalia/signals.py via Django's built-in
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
    EVENT_TYPE_CHOICES = [('login', 'Login'), ('logout', 'Logout')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=10, choices=EVENT_TYPE_CHOICES, default='login', db_index=True)
    is_admin = models.BooleanField(default=False, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=100, blank=True, db_index=True)
    trace_id = models.CharField(max_length=100, blank=True, db_index=True)
    traffic_type = models.CharField(max_length=12, choices=[('WEB','Web'),('API','API'),('BOT','Bot'),('INTERNAL','Internal')], default='WEB', db_index=True)
    failure_category = models.CharField(max_length=100, blank=True, db_index=True)
    identifier_hash = models.CharField(max_length=64, blank=True, db_index=True)
    admin_device = models.ForeignKey(
        'PaxaliaDevice', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='login_events', db_index=True,
    )
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
            models.Index(fields=['user', '-created_at'], name='paxalia_log_user_id_a63a3f_idx'),
            models.Index(fields=['result', '-created_at'], name='paxalia_log_result_9e90aa_idx'),
            models.Index(fields=['is_admin', '-created_at'], name='paxalia_log_is_admi_119e3b_idx'),
            models.Index(fields=['event_type', '-created_at'], name='paxalia_log_event_t_7d5a3e_idx'),
            models.Index(fields=['failure_category', '-created_at'], name='paxalia_log_failure_8314a0_idx'),
        ]

    def __str__(self):
        who = self.user or self.username_attempted or 'unknown'
        return f"{self.result}: {who} @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_active_session(self):
        return self.result == 'success' and self.logged_out_at is None


class PaxaliaDevice(models.Model):
    """Named WebAuthn authenticator owned by one Django administrator."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('revoked', 'Revoked'),
        ('disabled', 'Disabled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='paxalia_devices', db_index=True,
    )
    display_name = models.CharField(max_length=120, default='Paxalia Authenticator')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_authenticated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Paxalia Device'
        verbose_name_plural = 'Paxalia Devices'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='paxalia_dev_user_status_idx'),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.get_status_display()})"


class PaxaliaDeviceCredential(models.Model):
    """Server-side public WebAuthn credential metadata."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.OneToOneField(
        PaxaliaDevice, on_delete=models.CASCADE, related_name='credential',
    )
    credential_id = models.CharField(max_length=1024, unique=True, db_index=True)
    credential_public_key = models.BinaryField()
    sign_count = models.PositiveBigIntegerField(default=0)
    webauthn_user_handle = models.BinaryField(max_length=64)
    device_type = models.CharField(max_length=32, blank=True)
    authenticator_attachment = models.CharField(max_length=32, blank=True)
    backed_up = models.BooleanField(default=False)
    aaguid = models.CharField(max_length=64, blank=True)
    transports = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_authenticated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Paxalia Device Credential'
        verbose_name_plural = 'Paxalia Device Credentials'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device', '-last_authenticated_at'], name='paxalia_cred_last_auth_idx'),
        ]

    def __str__(self):
        return self.device.display_name


class PaxaliaWebAuthnChallenge(models.Model):
    """Short-lived, single-use WebAuthn ceremony challenge."""
    KIND_CHOICES = [
        ('registration', 'Registration'),
        ('authentication', 'Authentication'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paxalia_webauthn_challenges',
    )
    device = models.ForeignKey(
        PaxaliaDevice, on_delete=models.CASCADE, null=True, blank=True, related_name='webauthn_challenges',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    challenge = models.CharField(max_length=128, unique=True, db_index=True)
    user_handle = models.BinaryField(max_length=64, null=True, blank=True)
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Paxalia WebAuthn Challenge'
        verbose_name_plural = 'Paxalia WebAuthn Challenges'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'kind', '-created_at'], name='paxalia_chal_user_kind_idx'),
            models.Index(fields=['expires_at', 'used_at'], name='paxalia_chal_exp_used_idx'),
        ]

    def __str__(self):
        return f"{self.kind} challenge for {self.user}"


class PaxaliaRecoveryCode(models.Model):
    """One-time recovery code hash; plaintext codes are never stored."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paxalia_recovery_codes',
    )
    code_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Paxalia Recovery Code'
        verbose_name_plural = 'Paxalia Recovery Codes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'used_at', 'revoked_at'], name='paxalia_recovery_state_idx'),
        ]


class PaxaliaLogGroup(models.Model):
    """Stable fingerprint group for one class of observable event."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    severity = models.CharField(max_length=10, db_index=True)
    source = models.CharField(max_length=50, db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    exception_type = models.CharField(max_length=255, blank=True)
    normalized_message = models.CharField(max_length=2000, blank=True)
    first_seen = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    occurrence_count = models.PositiveBigIntegerField(default=0)
    suppressed_count = models.PositiveBigIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    sample_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Paxalia Log Group'
        verbose_name_plural = 'Paxalia Log Groups'
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['source', '-last_seen'], name='paxalia_pax_source_b2919b_idx'),
            models.Index(fields=['severity', '-last_seen'], name='paxalia_pax_severit_8f2790_idx'),
            models.Index(fields=['category', '-last_seen'], name='paxalia_pax_categor_457dd8_idx'),
        ]

    def __str__(self):
        return f"{self.severity} {self.source}: {self.normalized_message[:80]}"


class PaxaliaLogEvent(models.Model):
    """Canonical structured application/HTTP/browser observability event."""
    SEVERITY_CHOICES = [
        ('DEBUG', 'Debug'), ('INFO', 'Info'), ('WARNING', 'Warning'),
        ('ERROR', 'Error'), ('CRITICAL', 'Critical'),
    ]
    TRAFFIC_CHOICES = [
        ('WEB', 'Web'), ('API', 'API'), ('BOT', 'Bot'), ('INTERNAL', 'Internal'),
    ]
    SENSITIVE_STATES = [
        ('safe', 'Safe'), ('redacted', 'Redacted'), ('protected', 'Protected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    received_at = models.DateTimeField(default=timezone.now, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, db_index=True)
    source = models.CharField(max_length=50, default='Other', db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    action = models.CharField(max_length=100, blank=True, db_index=True)
    logger_name = models.CharField(max_length=255, blank=True, db_index=True)
    message = models.TextField()
    exception_type = models.CharField(max_length=255, blank=True, db_index=True)
    stack_trace = models.TextField(blank=True)
    module = models.CharField(max_length=255, blank=True)
    file_name = models.CharField(max_length=500, blank=True)
    line_number = models.PositiveIntegerField(null=True, blank=True)
    function_name = models.CharField(max_length=255, blank=True)

    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=100, blank=True, db_index=True)
    trace_id = models.CharField(max_length=100, blank=True, db_index=True)
    request_method = models.CharField(max_length=20, blank=True)
    request_path = models.CharField(max_length=2048, blank=True, db_index=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    duration_ms = models.FloatField(null=True, blank=True)

    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paxalia_log_events',
    )
    traffic_type = models.CharField(max_length=12, choices=TRAFFIC_CHOICES, default='INTERNAL', db_index=True)
    is_api = models.BooleanField(default=False, db_index=True)
    is_bot = models.BooleanField(default=False, db_index=True)
    bot_category = models.CharField(max_length=30, blank=True, db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='paxalia_log_events',
    )
    user_display = models.CharField(max_length=255, blank=True)
    user_type = models.CharField(max_length=100, blank=True)
    admin_flag = models.BooleanField(default=False, db_index=True)
    ip_address = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    ip_mode = models.CharField(max_length=10, default='none')
    user_agent = models.CharField(max_length=512, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    device = models.CharField(max_length=50, blank=True)

    process_id = models.IntegerField(null=True, blank=True)
    thread_name = models.CharField(max_length=255, blank=True)
    host = models.CharField(max_length=255, blank=True)
    environment = models.CharField(max_length=100, blank=True)
    release = models.CharField(max_length=100, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64, db_index=True)
    group = models.ForeignKey(
        PaxaliaLogGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='events', db_index=True,
    )
    sensitive_data_state = models.CharField(max_length=10, choices=SENSITIVE_STATES, default='redacted')

    class Meta:
        verbose_name = 'Paxalia Log Event'
        verbose_name_plural = 'Paxalia Log Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'severity'], name='paxalia_pax_timesta_037ce2_idx'),
            models.Index(fields=['source', 'timestamp'], name='paxalia_pax_source_a542fb_idx'),
            models.Index(fields=['traffic_type', 'timestamp'], name='paxalia_pax_traffic_c4b81c_idx'),
            models.Index(fields=['request_id', 'timestamp'], name='paxalia_pax_request_c74a7d_idx'),
            models.Index(fields=['correlation_id', 'timestamp'], name='paxalia_pax_correla_924d68_idx'),
            models.Index(fields=['exception_type', 'timestamp'], name='paxalia_pax_excepti_933c37_idx'),
            models.Index(fields=['fingerprint', 'timestamp'], name='paxalia_pax_fingerp_3a10aa_idx'),
        ]

    def __str__(self):
        return f"{self.severity}: {self.message[:100]}"


class BlockedIP(models.Model):
    """IP address blocked from the dashboard / login, managed from the
    Security Center. Enforcement lives in
    paxalia/middleware.py::SecurityBlockMiddleware."""
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
    Write with paxalia.security_audit.log_action(...) from any view.
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
    paxalia:csp_report. This package does not set the CSP header
    itself (that's the host project's job) — it only provides the
    collection endpoint. Point your CSP's report-uri/report-to at
    /<dashboard-path>/csp-report/ to start receiving reports here.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='csp_violations')
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


class Goal(models.Model):
    """
    A conversion goal: either "a visitor hit this page" or "a visitor
    fired this event." Conversion rate is computed on the fly against
    PageView/AnalyticsEvent — there's no separate completion-log table,
    since the underlying data already exists.
    """
    GOAL_TYPE_CHOICES = [
        ('page', 'Page visited'),
        ('event', 'Event fired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='goals')
    name = models.CharField(max_length=255)
    goal_type = models.CharField(max_length=10, choices=GOAL_TYPE_CHOICES)
    # For goal_type='page': match_value is a path (exact match against PageView.path).
    # For goal_type='event': match_value is "category:action" (both required).
    match_value = models.CharField(
        max_length=255,
        help_text="Path for a page goal (e.g. '/thank-you/'), or 'category:action' for an event goal (e.g. 'signup:completed')."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Goal"
        verbose_name_plural = "Goals"
        ordering = ['name']

    def __str__(self):
        return self.name

    def matching_category_action(self):
        """For an event goal, split match_value into (category, action). Returns (None, None) for a page goal."""
        if self.goal_type != 'event' or ':' not in self.match_value:
            return None, None
        category, _, action = self.match_value.partition(':')
        return category, action


class Funnel(models.Model):
    """An ordered sequence of steps. See FunnelStep for the steps
    themselves, and paxalia/funnels.py for how completion is computed."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='funnels')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Funnel"
        verbose_name_plural = "Funnels"
        ordering = ['name']

    def __str__(self):
        return self.name


class FunnelStep(models.Model):
    """One step of a Funnel. Reuses the same page/event match shape as Goal."""
    STEP_TYPE_CHOICES = [
        ('page', 'Page visited'),
        ('event', 'Event fired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    funnel = models.ForeignKey(Funnel, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    step_type = models.CharField(max_length=10, choices=STEP_TYPE_CHOICES)
    match_value = models.CharField(max_length=255, help_text="Same format as Goal.match_value.")

    class Meta:
        verbose_name = "Funnel Step"
        verbose_name_plural = "Funnel Steps"
        ordering = ['funnel', 'order']
        unique_together = [('funnel', 'order')]

    def __str__(self):
        return f"{self.funnel.name} — step {self.order}: {self.name}"

    def matching_category_action(self):
        if self.step_type != 'event' or ':' not in self.match_value:
            return None, None
        category, _, action = self.match_value.partition(':')
        return category, action


class Segment(models.Model):
    """
    A saved filter, reusable across Overview/Pages/Traffic. `filters` is
    a flat JSON dict of field -> value, applied as an AND of exact-match
    filters against PageView (see paxalia/segments.py::segment_scoped).
    Only a small, explicit set of fields is supported — see
    ALLOWED_FILTER_FIELDS in segments.py — to avoid turning this into an
    arbitrary-query injection surface.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='segments')
    name = models.CharField(max_length=255)
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Segment"
        verbose_name_plural = "Segments"
        ordering = ['name']

    def __str__(self):
        return self.name


class ChartAnnotation(models.Model):
    """A marker on a specific date, shown on the traffic charts (e.g. a
    deploy, a campaign launch). See Phase-13's deployment tracker for a
    more automated version of this same idea."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='annotations')
    date = models.DateField(db_index=True)
    label = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Chart Annotation"
        verbose_name_plural = "Chart Annotations"
        ordering = ['-date']

    def __str__(self):
        return f"{self.date}: {self.label}"


class DashboardAccess(models.Model):
    """
    Not a real table — this model exists purely to hold the custom
    permissions below in Django's standard auth_permission table, so
    per-section dashboard access can be granted through the ordinary
    Group/User "permissions" admin screens. See paxalia/permissions.py
    for how these are enforced.
    """
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('view_billing', 'Can view Billing section'),
            ('view_security', 'Can view Security Center'),
            ('view_backups', 'Can view Backups section'),
            ('view_sites', 'Can view Sites section'),
            ('view_server', 'Can view Server monitoring'),
            ('view_compliance', 'Can view Compliance tools'),
            ('view_logs', 'Can view Paxalia Logs'),
        ]


class PaxaliaAPIKey(models.Model):
    """
    A scoped, revocable credential for the Paxalia API — server-to-server
    event ingestion and/or read access to paxalia data. Distinct from
    the browser-facing public event endpoint (analytics_event_api),
    which stays anonymous/unauthenticated on purpose: a secret key can
    never be safely embedded in client-side JS (anyone viewing page
    source could extract it), so this only guards the server-to-server
    surfaces. See paxalia/api_keys.py for generation/verification.

    The raw key is shown exactly once, at creation — only its SHA-256
    hash is ever stored, same principle as a password. key_prefix is
    the first several characters of the raw key, safe to display in
    the UI for identification without exposing the secret.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, null=True, blank=True, related_name='api_keys',
        help_text="Restrict this key to one site, or leave blank for all sites."
    )
    name = models.CharField(max_length=255, help_text="A label to tell keys apart, e.g. 'Backend service'.")
    key_prefix = models.CharField(max_length=16, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    scope_ingest = models.BooleanField(
        default=True, help_text="Allows posting events via the server-to-server ingestion endpoint."
    )
    scope_read = models.BooleanField(
        default=False, help_text="Allows reading paxalia data via the read API."
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Paxalia API Key"
        verbose_name_plural = "Paxalia API Keys"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…)"


class ScheduledReport(models.Model):
    """A recurring email (optionally with a PDF attached — see
    paxalia/reporting.py) summarizing traffic for a site."""
    FREQUENCY_CHOICES = [('weekly', 'Weekly'), ('monthly', 'Monthly')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='scheduled_reports')
    name = models.CharField(max_length=255)
    recipient_emails = models.TextField(help_text="One email address per line.")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Scheduled Report"
        verbose_name_plural = "Scheduled Reports"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"

    def recipient_list(self):
        return [e.strip() for e in self.recipient_emails.split('\n') if e.strip()]


class ShareLink(models.Model):
    """
    A public, unauthenticated read-only link to a site's Overview
    snapshot. The UUID primary key doubles as the unguessable token —
    same 128-bit random-UUID4 pattern already used as a primary key
    everywhere else in this app, so no separate token field or
    generation logic needed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='share_links')
    name = models.CharField(max_length=255)
    password_hash = models.CharField(max_length=128, blank=True, help_text="Django password hash. Blank means no password required.")
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Share Link"
        verbose_name_plural = "Share Links"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at < timezone.now()

    @property
    def has_password(self):
        return bool(self.password_hash)

    @property
    def is_usable(self):
        return self.is_active and not self.is_expired


class Notification(models.Model):
    """
    Powers the in-dashboard notification center (bell icon). Written by
    paxalia.alerts.send_alert()/send_security_alert() alongside their
    existing email/webhook delivery — so every alert shows up here
    regardless of whether email/webhook are configured, or whether
    they succeed.

    Read state is deliberately global, not per-user: any staff member
    marking a notification read clears it for everyone. A per-user
    read/unread table would be more precise but is real added
    complexity (a through-model, migrations on every new staff
    account) for a feature that's mostly "did anyone see this yet" —
    documented here as a known simplification, not an oversight.
    """
    CATEGORY_CHOICES = [
        ('anomaly', 'Anomaly'),
        ('security', 'Security'),
        ('report', 'Report'),
        ('uptime', 'Uptime'),
        ('general', 'General'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', db_index=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return self.subject


class UptimeMonitor(models.Model):
    """
    A configured URL to periodically check — see paxalia/uptime.py
    for the actual HTTP check logic and paxalia/management/commands/
    check_uptime.py for the scheduled command that drives it.
    """
    METHOD_CHOICES = [('GET', 'GET'), ('HEAD', 'HEAD'), ('POST', 'POST')]

    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    method = models.CharField(max_length=6, choices=METHOD_CHOICES, default='GET')
    expected_status_code = models.PositiveIntegerField(default=200)
    timeout_seconds = models.PositiveIntegerField(default=10)
    check_interval_minutes = models.PositiveIntegerField(
        default=5,
        help_text="How often this monitor is checked. check_uptime can run as often as "
                  "you like (every minute is typical) — it only actually pings a monitor "
                  "once this many minutes have passed since its last check."
    )
    is_active = models.BooleanField(default=True)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='uptime_monitors')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['name']
        verbose_name = 'Uptime Monitor'
        verbose_name_plural = 'Uptime Monitors'

    def __str__(self):
        return self.name

    @property
    def latest_check(self):
        return self.checks.order_by('-checked_at').first()

    @property
    def open_incident(self):
        return self.incidents.filter(resolved_at__isnull=True).first()


class UptimeCheck(models.Model):
    """One HTTP check result. Every check is stored — see compute_uptime_percentage()
    in uptime.py for how these roll up into an uptime %."""
    STATUS_CHOICES = [('up', 'Up'), ('down', 'Down')]

    monitor = models.ForeignKey(UptimeMonitor, on_delete=models.CASCADE, related_name='checks')
    checked_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(
                fields=['monitor', 'checked_at'],
                name='paxalia_upt_monitor_d38f8e_idx',
            ),
        ]

    def __str__(self):
        return f"{self.monitor.name}: {self.status} @ {self.checked_at}"


class UptimeIncident(models.Model):
    """
    Opened on an up->down transition (or a monitor's very first check
    coming back down), resolved on the next down->up transition. See
    uptime.py::record_check() for the state-transition logic —
    deliberately transition-based rather than "one row per down check",
    so a monitor failing every minute for an hour is one incident, not
    sixty.
    """
    monitor = models.ForeignKey(UptimeMonitor, on_delete=models.CASCADE, related_name='incidents')
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cause = models.CharField(max_length=500, blank=True, help_text="error_message from the check that opened this incident.")

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Uptime Incident'
        verbose_name_plural = 'Uptime Incidents'

    def __str__(self):
        state = 'ongoing' if self.resolved_at is None else 'resolved'
        return f"{self.monitor.name} — {state} since {self.started_at}"

    @property
    def is_ongoing(self):
        return self.resolved_at is None

    @property
    def duration_seconds(self):
        end = self.resolved_at or timezone.now()
        return (end - self.started_at).total_seconds()


class ServerMetricSnapshot(models.Model):
    """
    One point-in-time system-metrics reading, written by
    `manage.py record_server_metrics`. This is what makes
    api_server_history real — before Phase 13 that endpoint returned
    synthetic random.randint() data because there was no persistent
    time-series store; this is that store.

    disk_io_*_bytes and network_*_bytes are stored as the raw
    cumulative counters psutil reports (bytes since boot), same as
    psutil.disk_io_counters()/net_io_counters() themselves — the
    history API computes deltas between consecutive snapshots at read
    time, not here, so any future consumer of this table can choose
    its own window rather than being stuck with whatever delta was
    computed at write time.
    """
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    cpu_percent = models.FloatField()
    memory_percent = models.FloatField()
    disk_io_read_bytes = models.BigIntegerField(default=0)
    disk_io_write_bytes = models.BigIntegerField(default=0)
    network_in_bytes = models.BigIntegerField(default=0)
    network_out_bytes = models.BigIntegerField(default=0)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"snapshot @ {self.recorded_at}"


class SlowQuery(models.Model):
    """
    A single database query that took longer than
    SLOW_QUERY_THRESHOLD_MS (default 100ms), captured by
    SlowQueryMiddleware via Django's connection.execute_wrapper() —
    portable across any DB backend Django supports, since it
    instruments Django's own query execution rather than trying to
    parse a database engine's native slow-query log file (which would
    need a different parser and a different, environment-specific log
    file path per engine). Opt-in: SlowQueryMiddleware has to be added
    to MIDDLEWARE, same as AnalyticsMiddleware itself.
    """
    sql = models.TextField()
    duration_ms = models.FloatField(db_index=True)
    path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Slow Query'
        verbose_name_plural = 'Slow Queries'

    def __str__(self):
        return f"{self.duration_ms:.0f}ms: {self.sql[:80]}"


class Deployment(models.Model):
    """
    Recorded via `manage.py record_deployment`, meant to be called
    from CI/CD right after a successful deploy. Auto-creates a
    matching ChartAnnotation (see that model's docstring) at the same
    date, so a deploy shows up on the Overview traffic chart with zero
    extra configuration — the whole point of pairing this with an
    existing feature rather than building a separate timeline view.
    """
    version = models.CharField(max_length=100, blank=True, help_text="Git SHA, tag, or version string — whatever CI passes.")
    notes = models.TextField(blank=True)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='deployments')
    deployed_at = models.DateTimeField(default=timezone.now, db_index=True)
    annotation = models.OneToOneField(
        ChartAnnotation, on_delete=models.SET_NULL, null=True, blank=True, related_name='deployment'
    )

    class Meta:
        ordering = ['-deployed_at']

    def __str__(self):
        return self.version or f"deployment @ {self.deployed_at}"


