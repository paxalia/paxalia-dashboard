# analytics/settings.py
from django.conf import settings

DEFAULTS = {
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime', 'bots',
        'geography', 'events', 'billing', 'releases', 'backups', 'security', 'settings'
    ],
    'API_PATH_PREFIX': '/api/',
    'GEOIP_PATH': None,  # None → use analytics/geoip/ inside the package
    'BILLING_INVOICE_MODEL': 'billing.BillingInvoice',
    'BILLING_USER_PLAN_MODEL': 'billing.UserBilling',
    'BILLING_DONATION_MODEL': 'billing.Donation',
    'DEFAULT_ANONYMIZE_IP': True,
    'DEFAULT_IGNORED_PREFIXES': ['/admin/', '/static/', '/media/'],
    'DEFAULT_IGNORED_EXTENSIONS': ['.css', '.js', '.png', '.jpg', '.svg', '.ico', '.woff2'],
    'DEFAULT_REALTIME_REFRESH': 30,
    'UPLOADS_INCOMING_ROOT': None,
    'UPLOAD_CHUNK_SIZE_MB': 5,                                # optional, default 5
    'UPLOAD_MAX_FILE_SIZE_MB': 2048,                          # optional, default 2048 (2GB)

    # ── Security: IP resolution ──
    'TRUST_X_FORWARDED_FOR': False,
    'TRUSTED_PROXY_COUNT': 1,

    # ── Security Center ──
    'SECURITY_TRACK_ONLY_STAFF': True,
    'SECURITY_LOG_RETENTION_DAYS': 180,
    'SECURITY_FAILED_LOGIN_THRESHOLD': 5,
    'SECURITY_FAILED_LOGIN_WINDOW_MINUTES': 15,
    'SECURITY_ALERT_EMAILS': [],
    'SECURITY_ALERT_WEBHOOK_URL': None,
}


def get_config():
    """Return the ZAYDANY_ANALYTICS dict merged with defaults."""
    user_config = getattr(settings, 'ZAYDANY_ANALYTICS', {})
    config = DEFAULTS.copy()
    config.update(user_config)
    return config
