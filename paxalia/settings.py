# paxalia/settings.py
from django.conf import settings

DEFAULTS = {
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime', 'bots',
        'geography', 'events', 'logs', 'billing', 'backups', 'server_files', 'security',
        'sites', 'broken_links', 'goals', 'funnels', 'segments', 'campaigns',
        'annotations', 'cohorts', 'api_keys', 'reports', 'share_links', 'notifications', 'rum', 'uptime', 'availability', 'transfers', 'compliance', 'data_import', 'settings'
    ],
    'API_PATH_PREFIX': '/api/',
    'GEOIP_PATH': None,  # None → use paxalia/geoip/ inside the package
    'BILLING_INVOICE_MODEL': 'billing.BillingInvoice',
    'BILLING_USER_PLAN_MODEL': 'billing.UserBilling',
    'BILLING_DONATION_MODEL': 'billing.Donation',
    'DEFAULT_ANONYMIZE_IP': False,  # matches AnalyticsSettings.anonymize_ip's model default (see models.py)
    'DEFAULT_IGNORED_PREFIXES': ['/admin/', '/static/', '/media/'],
    'DEFAULT_IGNORED_EXTENSIONS': ['.css', '.js', '.png', '.jpg', '.svg', '.ico', '.woff2'],
    'DEFAULT_REALTIME_REFRESH': 30,
    'DEFAULT_SEARCH_QUERY_PARAMS': ['q', 'search', 'query'],
    # Bot/scanner path-management safety bounds. These govern the one-click
    # cleanup actions exposed on Pages, Bot Traffic, and Broken Links.
    'BOT_PATH_MAX_PREFIX_LENGTH': 255,
    'BOT_PATH_MAX_DELETE_PER_ACTION': 10000,
    'BOT_PATH_MAX_MUTATIONS_PER_MINUTE': 30,
    'BOT_TRAFFIC_MAX_IPS': 30,
    'BOT_TRAFFIC_MAX_PATHS_PER_IP': 8,
    'BOT_TRAFFIC_MAX_SCANNER_ROWS': 40,
    'BOT_TRAFFIC_MAX_CRAWLER_ROWS': 20,
    'BROKEN_LINKS_MAX_PATHS': 50,
    'BROKEN_LINKS_MAX_IPS': 25,
    'UPLOADS_INCOMING_ROOT': None,
    'UPLOAD_CHUNK_SIZE_MB': 5,                                # optional, default 5
    'UPLOAD_MAX_FILE_SIZE_MB': 2048,
    'DATA_IMPORT_MAX_FILE_SIZE_MB': 100,
    'UPLOAD_SESSION_TTL_HOURS': 24,                          # session retention in hours
    # ── Paxalia Server Files ──
    # Disabled by default. Host projects must explicitly opt in and configure
    # one or more non-root, non-overlapping filesystem directories.
    'FILE_MANAGER_ENABLED': False,
    'FILE_MANAGER_ALLOWED_ROOTS': [],
    'FILE_MANAGER_DENIED_PATHS': [],
    'FILE_MANAGER_SENSITIVE_PATTERNS': None,
    'FILE_MANAGER_ALLOW_HIDDEN': False,
    'FILE_MANAGER_ALLOW_SENSITIVE_MUTATIONS': False,
    'FILE_MANAGER_MAX_UPLOAD_SIZE_MB': 100,
    'FILE_MANAGER_MAX_DOWNLOAD_SIZE_MB': 1024,
    'FILE_MANAGER_PREVIEW_MAX_BYTES': 262144,
    'FILE_MANAGER_DIRECTORY_PAGE_SIZE': 100,
    'FILE_MANAGER_HISTORY_PAGE_SIZE': 50,
    'FILE_MANAGER_MAX_DIRECTORY_ENTRIES': 10000,
    'FILE_MANAGER_MAX_COPY_SIZE_MB': 100,
    'FILE_MANAGER_MAX_MUTATIONS_PER_MINUTE': 30,
    'FILE_MANAGER_MAX_READS_PER_MINUTE': 120,
    'FILE_MANAGER_RATE_LIMIT_WINDOW_SECONDS': 60,
    'FILE_MANAGER_MAX_OPERATION_RECORDS': 20000,
    'FILE_MANAGER_OPERATION_RETENTION_DAYS': 90,
    'FILE_MANAGER_CLEANUP_BATCH_SIZE': 500,

    # ── Paxalia Transfer Center ──
    # Enabled by default as a UI subsystem, but no filesystem transfer is
    # possible until Server Files roots/capabilities are configured.
    'TRANSFER_CENTER_ENABLED': True,
    'TRANSFER_ROOT': None,
    'TRANSFER_EXCHANGE_ROOT': None,
    'TRANSFER_EXCHANGE_LIST_LIMIT': 200,
    'TRANSFER_MAX_FILE_SIZE_MB': 2048,
    'TRANSFER_CHUNK_SIZE_MB': 5,
    'TRANSFER_MAX_CONCURRENT': 3,
    'TRANSFER_MAX_RETRIES': 5,
    'TRANSFER_RETRY_DELAY_SECONDS': 2,
    'TRANSFER_STAGING_TTL_HOURS': 24,
    'TRANSFER_SYNC_VERIFY_MAX_MB': 50,
    'TRANSFER_ALLOW_SYNC_LARGE_PROMOTION': False,
    'TRANSFER_CLEANUP_BATCH_SIZE': 100,
    # Filesystem scan cap for stale transfer staging cleanup. This bounds the
    # number of directory entries inspected across both staging roots in one pass.
    'TRANSFER_STAGING_SCAN_LIMIT': 5000,
    'TRANSFER_BROWSER_MAX_RECEIVE_MB': 512,
    'TRANSFER_MAX_REQUESTS_PER_MINUTE': 120,
    'TRANSFER_RATE_LIMIT_WINDOW_SECONDS': 60,

    # ── Paxalia Availability ──
    'AVAILABILITY_DEFAULT_INTERVAL_SECONDS': 300,
    'AVAILABILITY_MIN_INTERVAL_SECONDS': 30,
    'AVAILABILITY_MAX_INTERVAL_SECONDS': 86400,
    'AVAILABILITY_DEFAULT_TIMEOUT_SECONDS': 10,
    'AVAILABILITY_FAILURE_THRESHOLD': 2,
    'AVAILABILITY_RECOVERY_THRESHOLD': 2,
    'AVAILABILITY_MAX_RESPONSE_BYTES': 262144,
    # Bound configured POST bodies accepted by Availability monitors.
    'AVAILABILITY_MAX_REQUEST_BODY_BYTES': 65536,
    'AVAILABILITY_LOG_CORRELATION_WINDOW_SECONDS': 300,
    'AVAILABILITY_HISTORY_RETENTION_DAYS': 90,
    'AVAILABILITY_MAX_CHECK_RECORDS': 500000,
    'AVAILABILITY_CLEANUP_BATCH_SIZE': 500,
    'AVAILABILITY_ALLOWED_METHODS': ['GET', 'HEAD', 'POST'],
    'AVAILABILITY_MAX_CHECKS_PER_RUN': 100,
    # Hard upper bound on how many active monitors a scheduler pass may scan.
    'AVAILABILITY_MAX_SCHEDULER_SCAN': 1000,

    # ── Paxalia Resource & Retention Policies ──
    'LOG_MAX_RECORDS': 500000,
    'LOG_MAX_STORAGE_MB': 2048,
    'LOG_CLEANUP_BATCH_SIZE': 500,
    'LOG_STORAGE_WARNING_THRESHOLDS': (80, 90, 95),
    'LOG_STORAGE_WARNING_NOTIFICATIONS': True,
    'LOG_STORAGE_WARNING_COOLDOWN_SECONDS': 21600,
    'ALERT_DEDUPLICATION_ENABLED': True,
    'ALERT_DEFAULT_COOLDOWN_SECONDS': 300,
    'LOG_SEVERITY_RETENTION_DAYS': {
        'DEBUG': 7,
        'INFO': 30,
        'WARNING': 60,
        'ERROR': 180,
        'CRITICAL': 365,
    },
    'LOG_BROWSER_MAX_REALTIME_EVENTS': 2000,
    'LOG_BROWSER_MAX_REALTIME_BUFFER': 5000,
    'LOG_BROWSER_MAX_EVENTS_PER_PAGE': 50,
    'LOG_BROWSER_MAX_PAYLOAD_BYTES': 32768,
    'LOG_REALTIME_BATCH_SIZE': 200,
    'LOG_REALTIME_AUTO_PAUSE_THRESHOLD': 1000,
    'LOG_RETAIN_CRITICAL': True,
    'LOG_RETAIN_SECURITY': True,

    # Cross-subsystem resource policy defaults. The existing subsystem-specific
    # settings remain authoritative for backwards compatibility.
    'RESOURCE_POLICIES': {
        'transfer': {'retention_days': 90, 'max_records': 100000},
        'uptime_check': {'retention_days': 90, 'max_records': 500000},
        'uptime_incident': {'retention_days': 365, 'max_records': 10000},
        'server_metric': {'retention_days': 7, 'max_records': 100000},
    },

    # ── Security: IP resolution ──
    # Whether this deployment sits behind a reverse proxy / load balancer
    # that sets X-Forwarded-For. Only enable this if you control that
    # proxy — otherwise any client can spoof their own tracked IP by
    # sending a fake X-Forwarded-For header directly.
    'TRUST_X_FORWARDED_FOR': False,
    # Number of trusted proxies in front of the app. With TRUST_X_FORWARDED_FOR
    # enabled, the client IP is taken as the entry that is this many hops
    # from the right-hand end of the X-Forwarded-For chain (the standard
    # "trust the last N proxies" pattern), not blindly the first entry.
    'TRUSTED_PROXY_COUNT': 1,

    # ── Security Center ──
    # Only log logins for staff/superuser accounts by default, in keeping
    # with the package's privacy-first philosophy. Set False to track
    # every user's login (make sure your privacy policy covers this).
    'SECURITY_TRACK_ONLY_STAFF': False,
    # Optional trusted callable for projects with a custom administrator role.
    # Signature: callable(user) -> bool. Defaults to is_staff/is_superuser.
    'SECURITY_ADMIN_USER_CHECK': None,
    # How many days of LoginEvent / SecurityAuditLog rows to keep.
    # Enforced by `python manage.py prune_security_logs` (run via cron).
    'SECURITY_LOG_RETENTION_DAYS': 180,

    # ── Paxalia Observability ──
    # Standard-library Python/Django logging capture is enabled by default.
    'LOGGING_ENABLED': True,
    'LOG_CAPTURE_STANDARD_LOGGING': True,
    'LOG_MIN_LEVEL': 'INFO',
    'LOG_REQUEST_SUCCESSES': False,
    # Development can optionally persist every request lifecycle record
    # at DEBUG so cross-subsystem failures can be correlated without forcing
    # verbose request logging in production.
    'LOG_DEBUG_REQUEST_LIFECYCLE': False,
    'LOG_REQUEST_ID_RESPONSE_HEADER': 'X-Paxalia-Request-ID',
    'LOG_MAX_MESSAGE_LENGTH': 4000,
    'LOG_MAX_STACK_LENGTH': 12000,
    'LOG_MAX_METADATA_BYTES': 16384,
    'LOG_DEDUPE_WINDOW_SECONDS': 60,
    'LOG_MAX_SAMPLES_PER_GROUP': 5,
    'LOG_BROWSER_MAX_REQUESTS_PER_MINUTE': 120,
    'LOG_BROWSER_CAPTURE_CONSOLE': False,
    'LOG_BROWSER_CAPTURE_RESOURCE_ERRORS': False,
    'LOG_RELEASE': None,
    'LOG_SENSITIVE_KEYS': [],
    'LOG_RETENTION_DAYS': {
        'system': 30,
        'request': 30,
        'browser': 30,
        'application': 30,
        'login': 180,
        'security': 180,
        'group': 90,
    },
    # Keep failed identifiers hashed by default. Raw attempted usernames can
    # be enabled only when the host project's privacy policy supports it.
    'SECURITY_STORE_FAILED_USERNAME': True,
    # Configurable host application log model adapters.
    'APPLICATION_LOGS': [],

    # ── Paxalia Packages ──
    'PACKAGE_MAX_FILE_SIZE_MB': 100,
    'PACKAGE_MAX_OBJECTS': 10000,
    'PACKAGE_MAX_RELATIONS': 50000,
    'PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED': True,
    'PACKAGE_ALLOWED_CONFLICTS': ['update', 'skip'],

    # ── Paxalia Admin ──
    # The Paxalia Admin UI is a Django-native presentation over models that
    # are already registered with django.contrib.admin.
    'ADMIN_ENABLED': True,
    'ADMIN_MODEL_ALLOWLIST': [],
    'ADMIN_MODEL_DENYLIST': [],
    'ADMIN_MODELS': {},
    'ADMIN_LIST_PER_PAGE': 50,
    'ADMIN_MAX_RELATION_ITEMS': 10,
    'ADMIN_MAX_BULK_OPERATIONS': 500,
    'ADMIN_SENSITIVE_FIELDS': [
        'password', 'password_hash', 'token', 'access_token', 'refresh_token',
        'secret', 'client_secret', 'signing_secret', 'api_key', 'apikey',
        'private_key', 'session_key', 'csrf_token', 'authorization', 'cookie',
        'credential', 'credentials', 'secret_key', 'encryption_key',
        'otp_secret', 'otp_key', 'code_hash', 'credential_id',
        'credential_public_key', 'webauthn_user_handle', 'challenge',
        'request_headers', 'request_body',
    ],
    'ADMIN_DJANGO_FALLBACK_ENABLED': True,
    'ADMIN_LIST_EDITABLE_ENABLED': True,
    'ADMIN_MAX_DELETE_PREVIEW': 100,
    'ADMIN_OBJECT_HISTORY_PER_PAGE': 30,
    'ADMIN_PROTECTED_NO_STORE': True,
    # Consecutive failed logins (any account) from one IP within
    # SECURITY_FAILED_LOGIN_WINDOW_MINUTES before it's surfaced as a
    # "brute force suspected" alert on the Security Center.
    'SECURITY_FAILED_LOGIN_THRESHOLD': 5,
    'SECURITY_FAILED_LOGIN_WINDOW_MINUTES': 15,
    # Optional: list of email addresses to notify on security alerts
    # (new-location login, failed-login threshold, backup downloaded).
    # Empty disables email alerting.
    'SECURITY_ALERT_EMAILS': [],
    # Optional: webhook URL (e.g. Slack/Discord incoming webhook) to POST
    # the same alerts to. None/empty disables webhook alerting.
    'SECURITY_ALERT_WEBHOOK_URL': None,
    # A staff user must have entered their password within this many
    # minutes before they can download a backup archive. Re-checked on
    # every download attempt; re-authenticating resets the window.
    'BACKUP_REAUTH_MINUTES': 15,

    # ── Mandatory Paxalia administrator security ──
    # These are policy parameters, not switches. Layers 1/2/3 cannot be
    # disabled for Paxalia Dashboard administrator access.
    'ADMIN_MAX_DEVICES': 5,
    'ADMIN_SESSION_MAX_AGE_SECONDS': 8 * 60 * 60,
    'SECURITY_LOGIN_RATE_LIMIT_ATTEMPTS': 8,
    'SECURITY_LOGIN_RATE_LIMIT_WINDOW_SECONDS': 15 * 60,
    'SECURITY_2FA_RATE_LIMIT_ATTEMPTS': 5,
    'SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS': 5 * 60,
    'SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS': 5,
    'SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS': 5 * 60,
    'WEBAUTHN_CHALLENGE_TTL_SECONDS': 120,
    'WEBAUTHN_RP_NAME': 'Paxalia Dashboard',
    # Leave unset to derive values from the current request in supported
    # deployments. Explicit values are recommended when TLS terminates at a
    # reverse proxy or when the dashboard is deployed behind a stable origin.
    'WEBAUTHN_RP_ID': None,
    'WEBAUTHN_ORIGIN': None,
    'AUTH_BRAND_NAME': 'Paxalia',
    'AUTH_HOME_URL': '/',
    # Private server-side destination for completed Paxalia administrator auth.
    # This must never be exposed through client-side configuration.
    'AUTH_ADMIN_HOME_URL': None,
    'AUTH_SUPPORT_URL': None,
    # Paxalia owns its administrator Layer-1 login by default. This keeps the
    # package's password/2FA flow independent from the host site's login and
    # custom authentication middleware. Set True only when deliberately
    # integrating Paxalia with the host login flow.
    'AUTH_USE_HOST_LOGIN': False,
    # Optional explicit URL/view name for the host login in compatibility mode.
    # When unset, the package resolves Django's global LOGIN_URL.
    'AUTH_LOGIN_URL': None,
    # Optional backend list for Paxalia's isolated password check. When unset,
    # the package deliberately uses Django's ModelBackend only, keeping host
    # authentication backends such as Axes/SSO/LDAP out of the Paxalia login
    # boundary. Set an explicit tuple/list when a host needs another credential
    # source for Paxalia administrators.
    'AUTH_ISOLATED_AUTHENTICATION_BACKENDS': None,
    # URL names for the host application's successful second-factor endpoint.
    # The package does not assume a host routing scheme; embedded projects
    # opt in by naming their own 2FA view(s).
    'AUTH_HOST_2FA_URL_NAMES': (),
    # A host-login admin intent must not survive indefinitely in an abandoned
    # browser tab and later hijack a normal login flow.
    'AUTH_HOST_2FA_INTENT_TTL_SECONDS': 600,
    # Short-lived signed cookie used to survive host auth session rotation
    # when compatibility mode is explicitly enabled.
    'AUTH_HOST_2FA_HANDOFF_COOKIE_NAME': 'paxalia_admin_handoff',
    # Final Paxalia administrator authentication is isolated from the host
    # Django authentication/session in the default mode. The package uses a
    # real Django SessionStore with a separate cookie scoped to the dashboard.
    'AUTH_ISOLATED_SESSION_COOKIE_NAME': 'paxalia_admin_session',
    'AUTH_ISOLATED_SESSION_COOKIE_SAMESITE': 'Lax',
    'AUTH_ISOLATED_SESSION_COOKIE_DOMAIN': None,
    # Public-facing Paxalia authentication surfaces are available by default
    # but can be disabled individually by a host project without editing
    # installed package files. These do not disable the mandatory admin
    # security layers.
    'AUTH_SIGNUP_ENABLED': True,
    'AUTH_PASSWORD_RESET_ENABLED': True,
    'AUTH_PASSWORD_CHANGE_ENABLED': True,
    'ERROR_BRAND_NAME': 'Paxalia',
    'ERROR_HOME_URL': '/',
    'ERROR_SUPPORT_URL': None,
    'SECURITY_RECOVERY_CODE_COUNT': 10,

    # ── Ops/server monitoring ──────────────────────────────────────
    # How long ServerMetricSnapshot rows are kept — pruned by
    # record_server_metrics on every run, since it's typically
    # scheduled every minute and would otherwise grow unbounded.
    'SERVER_METRIC_RETENTION_DAYS': 7,
    # A query slower than this (via SlowQueryMiddleware, opt-in — see
    # README) gets recorded as a SlowQuery.
    'SLOW_QUERY_THRESHOLD_MS': 100,
    # Dotted path to your project's Celery Application instance (e.g.
    # 'myproject.celery.app'), same pattern as BILLING_INVOICE_MODEL —
    # this package doesn't own that instance, only reads it if you
    # point at one. None/unset means the Queues page shows nothing.
    'CELERY_APP_PATH': None,

    # ── Compliance tooling ─────────────────────────────────────────
    # Off by default — existing deployments track exactly as before.
    # When True, nothing is tracked (no PageView row, no session
    # cookie, client-side beacons no-op) until a cookie named
    # CONSENT_COOKIE_NAME is present with value CONSENT_COOKIE_GRANTED_VALUE
    # — set that cookie from your own CMP/consent-banner JS once the
    # visitor accepts. See the README's "Consent Mode" section.
    'CONSENT_MODE_ENABLED': False,
    'CONSENT_COOKIE_NAME': 'analytics_consent',
    'CONSENT_COOKIE_GRANTED_VALUE': 'granted',
    # Per-data-type retention, read by prune_analytics_data — separate
    # from SECURITY_LOG_RETENTION_DAYS (LoginEvent/SecurityAuditLog
    # only) and SERVER_METRIC_RETENTION_DAYS (pruned inline elsewhere).
    # Empty by default: nothing is deleted unless you explicitly opt a
    # data type in, e.g. {'pageview': 400, 'js_error': 90}. Valid keys:
    # pageview, analytics_event, js_error, uptime_check, slow_query.
    'DATA_RETENTION_DAYS': {},

    # ── Slack/Discord app ──────────────────────────────────────────
    # Both None by default — each platform's endpoint responds
    # "not configured" until you set its secret/key. See the README's
    # "Slack/Discord App" section.
    'SLACK_SIGNING_SECRET': None,
    'DISCORD_PUBLIC_KEY': None,

    # ── Multi-site ──
    # If True, a request from an unrecognized hostname automatically gets
    # a new Site row created for it. Off by default — predictable behavior
    # (unmatched hosts get site=None) beats silent auto-provisioning; turn
    # this on if you'd rather not pre-register every domain by hand.
    'AUTO_CREATE_SITES': False,

    # ── Anomaly detection ──
    # A day's traffic vs. the same weekday one week earlier, beyond
    # this percent change (either direction), triggers an alert.
    'ANOMALY_ALERT_THRESHOLD_PERCENT': 30,
}


def get_config():
    """Return the PAXALIA_DASHBOARD dict merged with defaults."""
    user_config = getattr(settings, 'PAXALIA_DASHBOARD', {})
    config = DEFAULTS.copy()
    config.update(user_config)
    return config



