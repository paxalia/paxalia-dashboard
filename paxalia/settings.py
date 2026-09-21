# paxalia/settings.py
from django.conf import settings

DEFAULTS = {
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime', 'bots',
        'geography', 'events', 'logs', 'billing', 'releases', 'backups', 'security',
        'sites', 'broken_links', 'goals', 'funnels', 'segments', 'campaigns',
        'annotations', 'cohorts', 'api_keys', 'reports', 'share_links', 'notifications', 'rum', 'uptime', 'compliance', 'data_import', 'settings'
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
    'UPLOADS_INCOMING_ROOT': None,
    'UPLOAD_CHUNK_SIZE_MB': 5,                                # optional, default 5
    'UPLOAD_MAX_FILE_SIZE_MB': 2048,
    'DATA_IMPORT_MAX_FILE_SIZE_MB': 100,
    'UPLOAD_SESSION_TTL_HOURS': 24,                          # optional, default 2048 (2GB)

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
    'LOG_REQUEST_ID_RESPONSE_HEADER': 'X-Paxalia-Request-ID',
    'LOG_MAX_MESSAGE_LENGTH': 4000,
    'LOG_MAX_STACK_LENGTH': 12000,
    'LOG_MAX_METADATA_BYTES': 16384,
    'LOG_DEDUPE_WINDOW_SECONDS': 60,
    'LOG_MAX_SAMPLES_PER_GROUP': 5,
    'LOG_BROWSER_MAX_EVENTS_PER_PAGE': 50,
    'LOG_BROWSER_MAX_REQUESTS_PER_MINUTE': 120,
    'LOG_BROWSER_MAX_PAYLOAD_BYTES': 32768,
    'LOG_BROWSER_CAPTURE_CONSOLE': False,
    'LOG_BROWSER_CAPTURE_RESOURCE_ERRORS': True,
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

    # ── Ops/server monitoring (Phase 13) ──
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

    # ── Compliance tooling (Phase 14) ──
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

    # ── Slack/Discord app (Phase 16) ──
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
