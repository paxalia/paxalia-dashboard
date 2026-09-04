# analytics/settings.py
from django.conf import settings

DEFAULTS = {
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime', 'bots',
        'geography', 'events', 'billing', 'releases', 'backups', 'settings'
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
}


def get_config():
    """Return the ZAYDANY_ANALYTICS dict merged with defaults."""
    user_config = getattr(settings, 'ZAYDANY_ANALYTICS', {})
    config = DEFAULTS.copy()
    config.update(user_config)
    return config
