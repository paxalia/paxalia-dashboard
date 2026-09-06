# analytics/settings.py
from django.conf import settings

DEFAULTS = {
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime', 'bots',
        'geography', 'events', 'billing', 'releases', 'backups', 'security',
        'sites', 'broken_links', 'settings'
    ],
    'API_PATH_PREFIX': '/api/',
    'GEOIP_PATH': None,  # None → use analytics/geoip/ inside the package
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
    'UPLOAD_MAX_FILE_SIZE_MB': 2048,                          # optional, default 2048 (2GB)

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
    'SECURITY_TRACK_ONLY_STAFF': True,
    # How many days of LoginEvent / SecurityAuditLog rows to keep.
    # Enforced by `python manage.py prune_security_logs` (run via cron).
    'SECURITY_LOG_RETENTION_DAYS': 180,
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

    # ── Multi-site ──
    # If True, a request from an unrecognized hostname automatically gets
    # a new Site row created for it. Off by default — predictable behavior
    # (unmatched hosts get site=None) beats silent auto-provisioning; turn
    # this on if you'd rather not pre-register every domain by hand.
    'AUTO_CREATE_SITES': False,
}


def get_config():
    """Return the PAXALIA_DASHBOARD dict merged with defaults."""
    user_config = getattr(settings, 'PAXALIA_DASHBOARD', {})
    config = DEFAULTS.copy()
    config.update(user_config)
    return config
