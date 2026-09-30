---

# Configuration

All package behavior is configured through the host project's `PAXALIA_DASHBOARD` dictionary.

The package merges the supplied configuration with safe built-in defaults.

A representative configuration surface is:

```python
PAXALIA_DASHBOARD = {
    # ── Navigation ───────────────────────────────────────────────
    "SIDEBAR_SECTIONS": [
        "overview",
        "pages",
        "api",
        "traffic",
        "realtime",
        "bots",
        "geography",
        "events",
        "billing",
        "releases",
        "backups",
        "security",
        "sites",
        "broken_links",
        "goals",
        "funnels",
        "segments",
        "campaigns",
        "annotations",
        "cohorts",
        "api_keys",
        "reports",
        "share_links",
        "notifications",
        "rum",
        "uptime",
        "compliance",
        "data_import",
        "settings",
    ],

    # ── Analytics / GeoIP ───────────────────────────────────────
    "API_PATH_PREFIX": "/api/",
    "GEOIP_PATH": None,
    "DEFAULT_ANONYMIZE_IP": False,
    "DEFAULT_IGNORED_PREFIXES": ["/admin/", "/static/", "/media/"],
    "DEFAULT_IGNORED_EXTENSIONS": [
        ".css",
        ".js",
        ".png",
        ".jpg",
        ".svg",
        ".ico",
        ".woff2",
    ],
    "DEFAULT_REALTIME_REFRESH": 30,
    "DEFAULT_SEARCH_QUERY_PARAMS": ["q", "search", "query"],

    # ── Billing integration ─────────────────────────────────────
    "BILLING_INVOICE_MODEL": "billing.BillingInvoice",
    "BILLING_USER_PLAN_MODEL": "billing.UserBilling",
    "BILLING_DONATION_MODEL": "billing.Donation",

    # ── Uploads / imports ───────────────────────────────────────
    "UPLOADS_INCOMING_ROOT": None,
    "UPLOAD_CHUNK_SIZE_MB": 5,
    "UPLOAD_MAX_FILE_SIZE_MB": 2048,
    "DATA_IMPORT_MAX_FILE_SIZE_MB": 100,
    "UPLOAD_SESSION_TTL_HOURS": 24,

    # ── Proxy / IP trust ────────────────────────────────────────
    "TRUST_X_FORWARDED_FOR": False,
    "TRUSTED_PROXY_COUNT": 1,

    # ── Security Center ─────────────────────────────────────────
    "SECURITY_TRACK_ONLY_STAFF": True,
    "SECURITY_LOG_RETENTION_DAYS": 180,
    "SECURITY_FAILED_LOGIN_THRESHOLD": 5,
    "SECURITY_FAILED_LOGIN_WINDOW_MINUTES": 15,
    "SECURITY_ALERT_EMAILS": [],
    "SECURITY_ALERT_WEBHOOK_URL": None,
    "BACKUP_REAUTH_MINUTES": 15,

    # ── Server / operations ─────────────────────────────────────
    "SERVER_METRIC_RETENTION_DAYS": 7,
    "SLOW_QUERY_THRESHOLD_MS": 100,
    "CELERY_APP_PATH": None,

    # ── Compliance ──────────────────────────────────────────────
    "CONSENT_MODE_ENABLED": False,
    "CONSENT_COOKIE_NAME": "analytics_consent",
    "CONSENT_COOKIE_GRANTED_VALUE": "granted",
    "DATA_RETENTION_DAYS": {},

    # ── Integrations ───────────────────────────────────────────
    "SLACK_SIGNING_SECRET": None,
    "DISCORD_PUBLIC_KEY": None,

    # ── Multi-site ──────────────────────────────────────────────
    "AUTO_CREATE_SITES": False,

    # ── Anomaly detection ───────────────────────────────────────
    "ANOMALY_ALERT_THRESHOLD_PERCENT": 30,

    # ── Persistent Logging / Observability ──────────────────────
    "LOGGING_ENABLED": True,
    "LOG_CAPTURE_STANDARD_LOGGING": True,
    "LOG_MIN_LEVEL": "INFO",
    "LOG_REQUEST_SUCCESSES": False,
    "LOG_REQUEST_ID_RESPONSE_HEADER": "X-Paxalia-Request-ID",
    "LOG_MAX_MESSAGE_LENGTH": 4000,
    "LOG_MAX_STACK_LENGTH": 12000,
    "LOG_MAX_METADATA_BYTES": 16384,
    "LOG_DEDUPE_WINDOW_SECONDS": 60,
    "LOG_MAX_SAMPLES_PER_GROUP": 5,
    "LOG_BROWSER_MAX_EVENTS_PER_PAGE": 50,
    "LOG_BROWSER_MAX_REQUESTS_PER_MINUTE": 120,
    "LOG_BROWSER_MAX_PAYLOAD_BYTES": 32768,
    "LOG_BROWSER_CAPTURE_CONSOLE": False,
    "LOG_BROWSER_CAPTURE_RESOURCE_ERRORS": True,
    "LOG_RELEASE": None,
    "LOG_SENSITIVE_KEYS": [],
    "LOG_RETENTION_DAYS": {
        "system": 30,
        "request": 30,
        "browser": 30,
        "application": 30,
        "login": 180,
        "security": 180,
        "group": 90,
    },
    "SECURITY_STORE_FAILED_USERNAME": True,
    "SECURITY_ADMIN_USER_CHECK": None,
    "APPLICATION_LOGS": [],

    # ── Paxalia Admin ───────────────────────────────────────────
    "ADMIN_ENABLED": True,
    "ADMIN_MODEL_ALLOWLIST": [],
    "ADMIN_MODEL_DENYLIST": [],
    "ADMIN_MODELS": {},
    "ADMIN_LIST_PER_PAGE": 50,
    "ADMIN_MAX_RELATION_ITEMS": 10,
    "ADMIN_MAX_BULK_OPERATIONS": 500,
    "ADMIN_SENSITIVE_FIELDS": [
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "client_secret",
        "signing_secret",
        "api_key",
        "apikey",
        "private_key",
        "session_key",
        "csrf_token",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "secret_key",
        "encryption_key",
    ],
    "ADMIN_DJANGO_FALLBACK_ENABLED": True,
    "ADMIN_LIST_EDITABLE_ENABLED": True,
    "ADMIN_MAX_DELETE_PREVIEW": 100,
    "ADMIN_OBJECT_HISTORY_PER_PAGE": 30,
    "ADMIN_PROTECTED_NO_STORE": True,

    # ── Paxalia Packages ────────────────────────────────────────
    "PACKAGE_MAX_FILE_SIZE_MB": 100,
    "PACKAGE_MAX_OBJECTS": 10000,
    "PACKAGE_MAX_RELATIONS": 50000,
    "PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED": True,
    "PACKAGE_ALLOWED_CONFLICTS": ["update", "skip"],
}
```

The current package configuration surface include the Admin and logging sections above.

### Mandatory administrator security configuration

The administrator security controls are policy parameters rather than feature switches. The three authentication layers
cannot be disabled through normal dashboard configuration.

A complete security-focused configuration can be expressed as:

```python
PAXALIA_DASHBOARD = {
    # ── Administrator security policy ─────────────────────────────
    "ADMIN_MAX_DEVICES": 5,
    "ADMIN_SESSION_MAX_AGE_SECONDS": 8 * 60 * 60,

    # Layer 1 — password/login rate limiting
    "SECURITY_LOGIN_RATE_LIMIT_ATTEMPTS": 8,
    "SECURITY_LOGIN_RATE_LIMIT_WINDOW_SECONDS": 15 * 60,

    # Layer 2 — TOTP rate limiting
    "SECURITY_2FA_RATE_LIMIT_ATTEMPTS": 5,
    "SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS": 5 * 60,

    # Layer 3 — WebAuthn/device rate limiting
    "SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS": 5,
    "SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS": 5 * 60,

    # Layer 3 — WebAuthn ceremony
    "WEBAUTHN_CHALLENGE_TTL_SECONDS": 120,
    "WEBAUTHN_RP_NAME": "Paxalia Dashboard",
    "WEBAUTHN_RP_ID": None,
    "WEBAUTHN_ORIGIN": None,

    # Separate Paxalia administrator session
    "AUTH_USE_HOST_LOGIN": False,
    "AUTH_ISOLATED_SESSION_COOKIE_NAME": "paxalia_admin_session",
    "AUTH_ISOLATED_SESSION_COOKIE_SAMESITE": "Lax",
    "AUTH_ISOLATED_SESSION_COOKIE_DOMAIN": None,

    # Public authentication surfaces
    "AUTH_SIGNUP_ENABLED": True,
    "AUTH_PASSWORD_RESET_ENABLED": True,
    "AUTH_PASSWORD_CHANGE_ENABLED": True,

    # Recovery
    "SECURITY_RECOVERY_CODE_COUNT": 10,

    # Private destination / presentation
    "AUTH_BRAND_NAME": "Paxalia",
    "AUTH_HOME_URL": "/",
    "AUTH_ADMIN_HOME_URL": None,
    "AUTH_SUPPORT_URL": None,
}
```

Important policy details:

- `AUTH_USE_HOST_LOGIN=False` is the default and keeps Paxalia's administrator authentication separate from the host
  website authentication.
- `AUTH_ISOLATED_SESSION_COOKIE_NAME` defaults to `paxalia_admin_session`.
- The isolated cookie path follows the configured dashboard path.
- `ADMIN_MAX_DEVICES` limits the number of active administrator device credentials.
- Login, TOTP, and WebAuthn/device ceremonies each have independent rate limits.
- WebAuthn challenges are short-lived and single-use.
- `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` should be set explicitly in production when TLS terminates at a reverse proxy
  or
  when a stable deployed origin is known.
- `SECURITY_RECOVERY_CODE_COUNT` controls the number of recovery codes generated for the administrator recovery path.
- These settings tune policy values; they do not remove the mandatory authentication layers.

### Secret-path deployment policy

For production deployments, `DASHBOARD_URL` is validated as a 32–128 character URL-safe random path segment. Predictable
paths such as `/admin/`, `/dashboard/`, `/insights/`, `/paxalia/`, or `/login/` must not be used as the production
secret
mount.

A typical deployment shape is:

```text
Public application
    ├── normal website login
    ├── normal website sessions
    └── public ingestion endpoints

Private Paxalia mount
    ├── auth/login/
    ├── auth/2fa/
    ├── auth/device/
    ├── security/
    ├── admin/
    ├── logs/
    ├── packages/
    └── dashboard pages
```

The same private mount is used for the administrator UI and its authentication lifecycle, so the dashboard's privileged
surfaces are not scattered across conventional public routes.

### CSRF requirements

Keep Django CSRF middleware enabled:

```python
MIDDLEWARE = [
    # ...
    "django.middleware.csrf.CsrfViewMiddleware",
    # ...
]
```

Do not add a blanket `csrf_exempt` around Paxalia authentication or package-management views. The bundled browser
authentication helper sends the current CSRF token for JSON POST requests, including WebAuthn ceremonies.

fileciteturn28file0L1-L20

### Configuration groups

#### Navigation

`SIDEBAR_SECTIONS` controls the navigation sections displayed and their order.

A section can still require a corresponding integration or capability before it is useful. Optional areas should not be
enabled just for decoration.

#### Analytics

`API_PATH_PREFIX` determines what traffic is treated as API traffic. `DEFAULT_ANONYMIZE_IP` controls the default IP
storage behavior. Ignored prefixes and extensions help avoid polluting analytics with static and administrative
requests.

#### Uploads

`UPLOADS_INCOMING_ROOT` controls staging. Chunk size, total upload size, and session TTL are bounded so upload handling
does not become unbounded temporary storage.

#### Proxy and IP trust

`TRUST_X_FORWARDED_FOR` must only be enabled behind a reverse proxy you control.

Do not blindly trust arbitrary client-supplied `X-Forwarded-For` values.

`TRUSTED_PROXY_COUNT` describes how many trusted proxy hops should be considered when resolving the client IP.

#### Security

Security Center settings control staff-only tracking, log retention, failed-login thresholds, alert destinations, and
backup download re-authentication.

#### Logging

The logging settings control capture level, request logging, response request-ID headers, message/stack/metadata bounds,
deduplication, browser ingestion limits, retention, and redaction configuration.

#### Admin

The Admin settings control which registered models are exposed, page sizes, relationship display limits, bulk operation
limits, sensitive field policies, fallback behavior, list-editable support, deletion preview limits, history pagination,
and no-store handling.

#### Packages

Package limits protect import/export operations from unexpected scale.

`PACKAGE_ALLOWED_CONFLICTS` controls which conflict strategies may be used. The package UI and engine enforce these
settings rather than trusting arbitrary user-provided values.

### Model-specific Admin configuration

`ADMIN_MODELS` provides optional per-model configuration without making Paxalia depend on a host application's model
names.

For example:

```python
PAXALIA_DASHBOARD = {
    "ADMIN_MODELS": {
        "content.article": {
            "identity_fields": ["slug"],
            "sensitive_fields": ["private_token"],
        },
    },
}
```

This is a configuration extension point.

It does **not** replace Django registration and should not be used to build hard-coded model-specific business logic
into Paxalia.

### Host Django settings

The host project remains responsible for:

- `INSTALLED_APPS`
- `MIDDLEWARE`
- `TEMPLATES`
- database configuration
- cache configuration
- email delivery
- sessions and cookies
- CSRF settings
- CORS
- CSP
- ASGI/WSGI deployment
- reverse proxy configuration
- authentication and identity policy

---


---

## Middleware Integration

Paxalia provides multiple middleware capabilities.

### AnalyticsMiddleware

Required for page-view/session collection:

```python
MIDDLEWARE = [
    # ...
    "paxalia.middleware.AnalyticsMiddleware",
]
```

Responsibilities include:

- request classification
- site resolution
- page-view creation
- session handling
- bot/API classification
- configured ignore rules
- analytics aggregation feed

### SecurityBlockMiddleware

Optional.

Place it before analytics when you want blocked IPs rejected before analytics records are created:

```python
MIDDLEWARE = [
    # ...
    "paxalia.middleware.SecurityBlockMiddleware",
    "paxalia.middleware.AnalyticsMiddleware",
]
```

### SlowQueryMiddleware

Optional.

```python
MIDDLEWARE = [
    # ...
    "paxalia.middleware.SlowQueryMiddleware",
    "paxalia.middleware.AnalyticsMiddleware",
]
```

It observes Django database query execution and persists queries that reach the configured threshold.

### PaxaliaLoggingMiddleware

Optional.

Place it after the host's session/authentication context when you want Paxalia request IDs, request lifecycle events,
response status, and duration context:

```python
MIDDLEWARE = [
    # security/session/auth middleware ...
    "paxalia.logging.middleware.PaxaliaLoggingMiddleware",
    "paxalia.middleware.AnalyticsMiddleware",
]
```

It is intentionally separate from `AnalyticsMiddleware`.

The two systems answer different questions:

```text
Analytics
    "What happened to the site's traffic?"

Logging / Observability
    "What happened inside the application while that request was executing?"
```

### Recommended ordering

A common production arrangement is:

```python
MIDDLEWARE = [
    # Django / proxy / security / session / authentication ...

    "paxalia.middleware.SecurityBlockMiddleware",
    "paxalia.logging.middleware.PaxaliaLoggingMiddleware",
    "paxalia.middleware.SlowQueryMiddleware",
    "paxalia.middleware.AnalyticsMiddleware",
]
```

Exact ordering depends on the host application's middleware stack.

---
