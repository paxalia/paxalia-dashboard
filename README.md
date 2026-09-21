# paxalia-dashboard

![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Django](https://img.shields.io/badge/django-5.0+-green.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A **complete, self‑hosted analytics platform** for Django, from [Paxalia](https://paxalia.com).
Drop it into any Django project and get a beautiful, full‑featured analytics dashboard with zero third‑party services.

---

## Table of Contents

- [Why paxalia-dashboard?](#why-paxalia-dashboard)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Dashboard Pages](#dashboard-pages)
- [Server Monitoring](#server-monitoring)
- [Bot Traffic](#bot-traffic)
- [Backup Management](#backup-management)
- [Admin Overview](#admin-overview)
- [Custom Event Tracking](#custom-event-tracking)
- [Real User Monitoring](#real-user-monitoring)
- [Uptime Monitoring](#uptime-monitoring)
- [Compliance](#compliance)
- [Data Import](#data-import)
- [Slack/Discord App](#slackdiscord-app)
- [Internationalization](#internationalization)
- [Themes](#themes)
- [Exporting Data](#exporting-data)
- [Billing Integration](#billing-integration)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Security Center](#security-center)
- [Advanced Analytics](#advanced-analytics)
- [Reporting & Sharing](#reporting--sharing)
- [Paxalia API](#paxalia-api)
- [Dependency Health](#dependency-health)
- [Notifications & Alerts](#notifications--alerts)
- [Multi-Site Analytics](#multi-site-analytics)
- [Release Center](#release-center)
- [Operational Commands](#operational-commands)
- [Security & Privacy Model](#security--privacy-model)
- [Credits](#credits)

---

## Why paxalia-dashboard

`paxalia-dashboard` is designed as a privacy-first, self-hosted analytics and operational observability layer for Django
applications. It is broader than a simple page-view counter: the v3 platform combines product analytics, behavioral
analysis, security visibility, server/runtime monitoring, uptime checks, release/deployment context, compliance tooling,
reporting, sharing, API access, and operational utilities in one Django-native package.

The comparison below keeps the original high-level positioning while making the breadth of the current platform
explicit. Availability of features from competing products varies by product tier, plan, add-on, or deployment
configuration.

| Capability                                  | Google Analytics | Typical lightweight Django analytics package | **paxalia-dashboard** |
|---------------------------------------------|-----------------:|---------------------------------------------:|----------------------:|
| Self-hosted                                 |                ❌ |                                            ✅ |                     ✅ |
| First-party data storage                    |                ❌ |                                            ✅ |                     ✅ |
| No required third-party analytics collector |                ❌ |                                            ✅ |                     ✅ |
| Django-native integration                   |                ❌ |                                            ✅ |                     ✅ |
| Page views & sessions                       |                ✅ |                                            ✅ |                     ✅ |
| Date-range analysis                         |                ✅ |                                            ✅ |                     ✅ |
| Previous-period comparison                  |                ✅ |                                       Varies |                     ✅ |
| Traffic sources / referrers                 |                ✅ |                                       Varies |                     ✅ |
| Browser / OS / device breakdown             |                ✅ |                                       Varies |                     ✅ |
| Offline GeoIP world map                     |                ❌ |                                         Rare |                     ✅ |
| Country and city drill-down                 |                ✅ |                                         Rare |                     ✅ |
| Custom events                               |                ✅ |                                       Varies |                     ✅ |
| API traffic separation                      |           Varies |                                         Rare |                     ✅ |
| API endpoint analytics                      |           Varies |                                         Rare |                     ✅ |
| Real-time visitor monitoring                |                ✅ |                                         Rare |                     ✅ |
| Broken-link analysis                        |           Varies |                                         Rare |                     ✅ |
| Bot traffic classification                  |           Varies |                                         Rare |                     ✅ |
| Search-engine crawler classification        |           Varies |                                         Rare |                     ✅ |
| AI crawler classification                   |           Varies |                                         Rare |                     ✅ |
| Social-preview bot classification           |           Varies |                                         Rare |                     ✅ |
| Malicious/scanner classification            |           Varies |                                         Rare |                     ✅ |
| Goals                                       |                ✅ |                                         Rare |                     ✅ |
| Funnel analysis                             |                ✅ |                                         Rare |                     ✅ |
| Behavioral segments                         |                ✅ |                                         Rare |                     ✅ |
| Campaign / UTM analysis                     |                ✅ |                                         Rare |                     ✅ |
| Cohort retention                            |                ✅ |                                         Rare |                     ✅ |
| Chart annotations                           |           Varies |                                         Rare |                     ✅ |
| Core Web Vitals / RUM                       |                ✅ |                                         Rare |                     ✅ |
| JavaScript error tracking                   |                ✅ |                                         Rare |                     ✅ |
| Scheduled uptime checks                     |           Varies |                                         Rare |                     ✅ |
| Incident history                            |           Varies |                                         Rare |                     ✅ |
| Server CPU monitoring                       |                ❌ |                                            ❌ |                     ✅ |
| Server memory monitoring                    |                ❌ |                                            ❌ |                     ✅ |
| Server disk monitoring                      |                ❌ |                                            ❌ |                     ✅ |
| Server network monitoring                   |                ❌ |                                            ❌ |                     ✅ |
| System service monitoring                   |                ❌ |                                            ❌ |                     ✅ |
| Process monitoring                          |                ❌ |                                            ❌ |                     ✅ |
| Slow-query monitoring                       |                ❌ |                                            ❌ |                     ✅ |
| Celery queue monitoring                     |                ❌ |                                            ❌ |                     ✅ |
| Deployment tracking                         |                ❌ |                                            ❌ |                     ✅ |
| Security Center                             |                ❌ |                                         Rare |                     ✅ |
| Login activity monitoring                   |           Varies |                                         Rare |                     ✅ |
| Active-session visibility                   |           Varies |                                         Rare |                     ✅ |
| IP blocklist                                |                ❌ |                                            ❌ |                     ✅ |
| CSP violation reporting                     |                ❌ |                                         Rare |                     ✅ |
| Security scorecard                          |                ❌ |                                            ❌ |                     ✅ |
| Dependency health                           |                ❌ |                                            ❌ |                     ✅ |
| MFA / 2FA dashboard integration             |           Varies |                                         Rare |                     ✅ |
| Consent mode                                |           Varies |                                         Rare |                     ✅ |
| Data-retention controls                     |           Varies |                                         Rare |                     ✅ |
| Forget-this-visitor deletion                |           Varies |                                         Rare |                     ✅ |
| Historical GA/Plausible import              |           Varies |                                         Rare |                     ✅ |
| Scheduled email reports                     |           Varies |                                         Rare |                     ✅ |
| PDF report delivery                         |           Varies |                                         Rare |                     ✅ |
| Public read-only share links                |           Varies |                                         Rare |                     ✅ |
| Scoped read API keys                        |                ✅ |                                         Rare |                     ✅ |
| Documented API reference                    |                ✅ |                                         Rare |                     ✅ |
| Slack / Discord command surface             |           Varies |                                         Rare |                     ✅ |
| Backup management                           |                ❌ |                                            ❌ |                     ✅ |
| Chunked upload/download support             |                ❌ |                                            ❌ |                     ✅ |
| Multi-site analytics                        |           Varies |                                         Rare |                     ✅ |
| Five-language UI + RTL support              |           Varies |                                         Rare |                     ✅ |
| Bundled/offline charts and map assets       |                ❌ |                                         Rare |                     ✅ |

The goal is not to replace every capability of a large analytics suite. The goal is to give a Django team a **single,
inspectable, self-hosted operational analytics surface** where product analytics and application/server context can live
together without making third-party analytics infrastructure mandatory.

---

## Features

- **Page Views & Sessions** – track every page visit, session duration, bounce rate, pages per session, all anonymised.
- **Traffic Sources** – see referrers, browsers, operating systems, and device types.
- **IP Geolocation** – a beautiful offline world map with drill‑down to cities; uses the free GeoLite2 database.
- **Custom Events** – add a one‑line JavaScript snippet to your site and track any user interaction (button clicks, form
  submits, video plays, downloads).
- **Billing Dashboard** – (optional) plug into your billing app to see daily revenue, top plans, and recent
  transactions.
- **Real‑time Monitoring** – watch visitors arrive live with a configurable refresh interval.
- **Server Monitoring** – real‑time system metrics: CPU, memory, disk, network, services, processes – all directly from
  your server, no external agents.
- **Bot Traffic Detection** – automatically identify and separate scanner/malicious traffic *and* known crawlers (search
  engines, AI crawlers, social-preview bots, SEO tools) from real user visits; view them broken out by category on a
  dedicated
  Bots page with its own analytics.
- **Backup Management** – configure paths to back up, set a schedule, and create/restore backups from the dashboard.
  Chunked download for large archives.
- **Admin Overview** – a dedicated dashboard for administrators showing user registrations, content creation, and login
  activity.
- **About Page** – learn the story behind the project and support its development.
- **Date Range Filter** – any chart or table can be filtered by a custom date range with one‑click presets.
- **Compare to Previous Period** – overlay the previous period on any line chart with a single checkbox.
- **CSV / JSON Export** – every table has a download button; data respects the current date filter.
- **12 Luxury Themes** – from Dark Gold to Onyx Pearl; switch themes instantly, no page reload.
- **Multi‑language & RTL** – English, Spanish, Arabic, Simplified Chinese, Brazilian Portuguese; Arabic flips the
  dashboard to right‑to‑left.
- **Fully Responsive** – works on desktop, tablet, and mobile; sidebar collapses to an overlay on small screens.
- **Configurable** – enable only the sections you need, change API paths, swap billing models, all from a single
  `PAXALIA_DASHBOARD` dict.
- **Configurable Data Handling** – IP address storage (raw by default, or SHA256-hashed if you turn on anonymization),
  and the anonymous session cookie, are both configurable in Settings; all data stays on your server regardless.
- **Goals, Funnels & Segments** – define conversion goals, multi-step funnels, and reusable behavioral segments for
  deeper product analysis.
- **Campaign & UTM Analysis** – capture campaign parameters and compare traffic and conversion behavior by campaign
  source, medium, and campaign.
- **Cohort Retention** – analyze visitor retention cohorts over time instead of looking only at aggregate traffic.
- **Chart Annotations** – mark deployments, campaigns, incidents, and other important dates directly on the analytics
  timeline.
- **Broken Links** – identify paths returning 404 responses, their frequency, and referring pages when available.
- **Real User Monitoring (RUM)** – collect LCP, CLS, and INP field data plus browser-side JavaScript errors without a
  separate tracking product.
- **Uptime Monitoring** – schedule HTTP checks, track status history, and keep transition-based incident records.
- **Security Center** – inspect login activity, active sessions, IP blocklists, audit/security signals, CSP violations,
  and security posture.
- **Security Scorecard** – surface security findings and configuration posture in one dashboard.
- **Dependency Health** – inspect the package's direct/transitive runtime dependency closure and progressively compare
  installed versions with upstream releases.
- **Compliance Controls** – optional consent gating, configurable retention periods, and visitor-deletion tooling.
- **Reporting & Sharing** – schedule report delivery and create protected public share links for selected dashboard
  views.
- **Paxalia API** – use scoped API keys for ingestion and read access to summaries, page views, and events.
- **Slack / Discord Commands** – query high-level analytics summaries from supported chat platforms.
- **Historical Data Import** – import aggregate GA/Plausible CSV history without requiring OAuth credentials or
  vendor-specific API clients.
- **Multi-site Analytics** – track multiple configured domains/sites within one dashboard and filter analytics by site.
- **Release Center** – manage release artifacts and connect deployment activity with analytics annotations.
- **Server Operations** – monitor CPU, memory, disk, network, services, processes, slow queries, Celery queues, and
  deployments directly from the host.
- **Operational Automation** – management commands cover aggregation, anomaly detection, backups, cleanup, retention,
  deployment tracking, server snapshots, uptime checks, and scheduled reports.
- **Self‑Contained** – no external CDN calls for maps, charts, or fonts – everything is bundled.

---

## Tech Stack

| Component          | Technology                                         |
|--------------------|----------------------------------------------------|
| Backend            | Django 5.0+, Python 3.10+                          |
| Database           | Any Django‑supported database (SQLite, PostgreSQL) |
| Charts             | Chart.js (bundled, no CDN)                         |
| World Map          | Datamaps + D3.js + TopoJSON (bundled, offline)     |
| GeoIP              | MaxMind GeoLite2‑City (offline database) + geoip2  |
| User‑Agent Parsing | user‑agents (optional, bundled fallback)           |
| Country Codes      | pycountry                                          |
| Server Metrics     | psutil                                             |

---

## Installation

### 1. Install the package

```bash
pip install paxalia-dashboard
```

### 2. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ...
    'paxalia',
]
```

### 3. Include the URLs

The dashboard is mounted at a secret path of your choice. The event API is mounted at a fixed public path (hardcoded in
JavaScript). This keeps your dashboard URL hidden while allowing the event tracking to work.

In your project’s root `urls.py`:

```python
from django.urls import path, include
from django.views.i18n import set_language
from paxalia.views.events import analytics_event_api

# Choose a secret path for your dashboard
DASHBOARD_URL = 'insights/'  # or a random string

urlpatterns = [
    # ...
    # Public event API (hardcoded path, matches JavaScript)
    path('api/paxalia/event/', analytics_event_api, name='event_api'),

    # Secret dashboard (everything else)
    path(DASHBOARD_URL, include('paxalia.urls')),

    # Required for language switching
    path('i18n/setlang/', set_language, name='set_language'),
]
```

### 4. Add the analytics middleware

In `settings.py`, add `paxalia.middleware.AnalyticsMiddleware` to the bottom of `MIDDLEWARE`:

```python
MIDDLEWARE = [
    # ...
    'paxalia.middleware.AnalyticsMiddleware',
]
```

This middleware automatically logs every page visit.
Without it, no data will appear in the dashboard.

### 5. Run migrations

```bash
python manage.py migrate paxalia
```

> **Note:** The package includes a clean `0001_initial.py` migration. If you're upgrading from an older version,
> you should run `python manage.py migrate paxalia` to apply the latest schema. The migration is
> database-agnostic and works with SQLite, PostgreSQL, MySQL, and others.

### 6. Update your base.html for CSP compliance

The package uses `nonce` attributes on all `<script>` tags to comply with strict Content Security Policies. To enable
this:

1. **Add the CSP context processors** to your `settings.py`:

```python
TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                # ...
                'paxalia.context_processors.analytics_config',
                'csp.context_processors.nonce',
            ],
        },
    },
]
```

2. **Add the CSP middleware** (if not already present):

```python
MIDDLEWARE = [
    # ...
    'csp.middleware.CSPMiddleware',
]
```

3. **Configure CSP** in `settings.py` with `NONCE` and `'strict-dynamic'`:

```python
from csp.constants import NONCE

CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            NONCE,
            "'strict-dynamic'",
        ),
        # ... other directives
    }
}
```

4. **Add the nonce to external scripts** in your own templates:

```python
< script
nonce = "{{ request.csp_nonce }}"
src = "{% static 'paxalia/scripts/paxalia-events.js' %}" > < / script >
```

### 7. Compile translations (optional)

```bash
python manage.py compilemessages -l es -l ar -l zh-hans -l pt-br
```

### 8. Download the GeoIP database (required for the geography page)

Download GeoLite2‑City.mmdb (free) from MaxMind
and place it in the directory specified by GEOIP_PATH (default: paxalia/geoip/ inside the package).

### 9. Start the server

```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/insights/ – your analytics dashboard is live.

### Additional management commands

The package includes several management commands to help with daily operations:

```bash
# Aggregate yesterday's stats (run daily via cron)
python manage.py aggregate_daily_stats

# Seed the database with dummy data for testing
python manage.py seed_analytics

# Import a list of bot paths from a text file
python manage.py import_bot_paths /path/to/bot_paths.txt

# Create a backup (called by the backup system or cron)
python manage.py create_backup
```

---

## Configuration

All dashboard behavior is configured through a single `PAXALIA_DASHBOARD` dictionary in the host project's
`settings.py`. The package reads this dictionary, merges it with its built-in defaults, and keeps optional integrations
disabled unless you explicitly enable/configure them.

The complete current configuration surface is:

```python
PAXALIA_DASHBOARD = {
    # ── Navigation ───────────────────────────────────────────────
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime', 'bots',
        'geography', 'events', 'billing', 'releases', 'backups', 'security',
        'sites', 'broken_links', 'goals', 'funnels', 'segments', 'campaigns',
        'annotations', 'cohorts', 'api_keys', 'reports', 'share_links',
        'notifications', 'rum', 'uptime', 'compliance', 'data_import', 'settings',
    ],

    # ── Analytics / GeoIP ───────────────────────────────────────
    'API_PATH_PREFIX': '/api/',
    'GEOIP_PATH': None,
    'DEFAULT_ANONYMIZE_IP': False,
    'DEFAULT_IGNORED_PREFIXES': ['/admin/', '/static/', '/media/'],
    'DEFAULT_IGNORED_EXTENSIONS': [
        '.css', '.js', '.png', '.jpg', '.svg', '.ico', '.woff2',
    ],
    'DEFAULT_REALTIME_REFRESH': 30,
    'DEFAULT_SEARCH_QUERY_PARAMS': ['q', 'search', 'query'],

    # ── Billing integration ────────────────────────────────────
    'BILLING_INVOICE_MODEL': 'billing.BillingInvoice',
    'BILLING_USER_PLAN_MODEL': 'billing.UserBilling',
    'BILLING_DONATION_MODEL': 'billing.Donation',

    # ── Uploads / imports ───────────────────────────────────────
    'UPLOADS_INCOMING_ROOT': None,
    'UPLOAD_CHUNK_SIZE_MB': 5,
    'UPLOAD_MAX_FILE_SIZE_MB': 2048,
    'DATA_IMPORT_MAX_FILE_SIZE_MB': 100,
    'UPLOAD_SESSION_TTL_HOURS': 24,

    # ── Security / IP resolution ───────────────────────────────
    'TRUST_X_FORWARDED_FOR': False,
    'TRUSTED_PROXY_COUNT': 1,

    # ── Security Center ────────────────────────────────────────
    'SECURITY_TRACK_ONLY_STAFF': True,
    'SECURITY_LOG_RETENTION_DAYS': 180,
    'SECURITY_FAILED_LOGIN_THRESHOLD': 5,
    'SECURITY_FAILED_LOGIN_WINDOW_MINUTES': 15,
    'SECURITY_ALERT_EMAILS': [],
    'SECURITY_ALERT_WEBHOOK_URL': None,
    'BACKUP_REAUTH_MINUTES': 15,

    # ── Server / operations ─────────────────────────────────────
    'SERVER_METRIC_RETENTION_DAYS': 7,
    'SLOW_QUERY_THRESHOLD_MS': 100,
    'CELERY_APP_PATH': None,

    # ── Compliance ──────────────────────────────────────────────
    'CONSENT_MODE_ENABLED': False,
    'CONSENT_COOKIE_NAME': 'analytics_consent',
    'CONSENT_COOKIE_GRANTED_VALUE': 'granted',
    'DATA_RETENTION_DAYS': {},

    # ── Slack / Discord ────────────────────────────────────────
    'SLACK_SIGNING_SECRET': None,
    'DISCORD_PUBLIC_KEY': None,

    # ── Multi-site ──────────────────────────────────────────────
    'AUTO_CREATE_SITES': False,

    # ── Anomaly detection ──────────────────────────────────────
    'ANOMALY_ALERT_THRESHOLD_PERCENT': 30,
}
```

### Configuration groups

**Navigation:** `SIDEBAR_SECTIONS` controls which dashboard areas are exposed and in what order. Keep a section disabled
when the corresponding integration is not configured, especially optional billing.

**Analytics:** `API_PATH_PREFIX` identifies API traffic, `GEOIP_PATH` points to the MaxMind GeoLite2-City database, the
default ignored prefixes/extensions prevent static/admin traffic from polluting analytics, `DEFAULT_REALTIME_REFRESH`
controls the live page refresh interval, and `DEFAULT_SEARCH_QUERY_PARAMS` controls common search-query parameter names.

**Billing:** `BILLING_INVOICE_MODEL`, `BILLING_USER_PLAN_MODEL`, and `BILLING_DONATION_MODEL` point to models in the
host project. The dashboard does not own your billing data model.

**Uploads/imports:** `UPLOADS_INCOMING_ROOT` controls the staging location; `UPLOAD_CHUNK_SIZE_MB` and
`UPLOAD_MAX_FILE_SIZE_MB` control upload behavior; `DATA_IMPORT_MAX_FILE_SIZE_MB` limits historical CSV imports;
`UPLOAD_SESSION_TTL_HOURS` controls how long incomplete upload sessions are retained.

**Proxy/IP trust:** only enable `TRUST_X_FORWARDED_FOR` when a reverse proxy you control sets `X-Forwarded-For`.
`TRUSTED_PROXY_COUNT` controls the trusted hop count. Do not blindly trust client-supplied forwarding headers.

**Security:** login tracking defaults to privileged accounts only; failed-login thresholds, retention, security alert
destinations, and backup re-authentication are configurable.

**Operations:** `SERVER_METRIC_RETENTION_DAYS` controls historical server snapshots, `SLOW_QUERY_THRESHOLD_MS` controls
slow-query capture, and `CELERY_APP_PATH` points to the host application's Celery instance when queue monitoring is
enabled.

**Compliance:** consent mode is disabled by default. When enabled, tracking waits for the configured consent cookie.
`DATA_RETENTION_DAYS` is empty by default; specify only the data types you explicitly want automatically pruned.

**Chat integrations:** Slack signing secrets and the Discord public key are optional. Endpoints remain unavailable until
their credentials are configured.

**Multi-site:** `AUTO_CREATE_SITES` is disabled by default so unknown hostnames do not silently create database rows.

**Anomaly detection:** a traffic change larger than `ANOMALY_ALERT_THRESHOLD_PERCENT` versus the comparable prior-week
day produces an anomaly alert.

### Host-project settings beyond `PAXALIA_DASHBOARD`

The package also integrates with standard Django settings for: `INSTALLED_APPS`, `MIDDLEWARE`, `TEMPLATES`,
database/cache configuration, email delivery, `CSRF_TRUSTED_ORIGINS`, CORS, CSP, session/cookie security, and ASGI/WSGI.
Those settings belong to the host project rather than the package's `PAXALIA_DASHBOARD` dict.

---

### Event API Path

The event API is hardcoded in JavaScript at `/api/paxalia/event/`. This is intentional:

- **The dashboard URL stays secret** – never exposed in client code.
- **The event API is public** – accepts anonymous data only.
- **No inline scripts needed** – all CSP rules are satisfied with `nonce`.

If you want to change the event API path, you must update:

1. The URL pattern in your project's `urls.py`
2. The `EVENT_URL` variable in `paxalia/static/paxalia/scripts/analytics-events.js`

---

## Middleware Integration

The package provides three middleware classes. They are deliberately split by responsibility so you can enable the
minimum set required by your deployment.

### Required: AnalyticsMiddleware

```python
MIDDLEWARE = [
    # ...
    'paxalia.middleware.AnalyticsMiddleware',
]
```

`AnalyticsMiddleware` records page views, resolves sites, classifies bot/API traffic, applies configured ignore rules,
and feeds the dashboard's daily and session analytics.

### Optional: SecurityBlockMiddleware

Place this **before** `AnalyticsMiddleware` if you want blocked IPs rejected before they are recorded as analytics
traffic:

```python
MIDDLEWARE = [
    # ...
    'paxalia.middleware.SecurityBlockMiddleware',
    'paxalia.middleware.AnalyticsMiddleware',
]
```

Blocked-IP lookups are briefly cached so the blocklist does not add an uncached database query to every request.

### Optional: SlowQueryMiddleware

```python
MIDDLEWARE = [
    # ...
    'paxalia.middleware.SlowQueryMiddleware',
    'paxalia.middleware.AnalyticsMiddleware',
]
```

Queries at or above `SLOW_QUERY_THRESHOLD_MS` are recorded in `SlowQuery`. The middleware uses Django's query execution
wrapper and guards its own insert so it does not recursively record itself.

### Recommended ordering

When both optional middleware classes are enabled, the package's intended ordering is:

```python
MIDDLEWARE = [
    # security / proxy / Django middleware ...
    'paxalia.middleware.SecurityBlockMiddleware',
    'paxalia.middleware.SlowQueryMiddleware',
    'paxalia.middleware.AnalyticsMiddleware',
]
```

`SecurityBlockMiddleware` should run before analytics so denied traffic never becomes a page-view record.
`SlowQueryMiddleware` can wrap the request independently of analytics tracking.

---

## Dashboard Pages

| Page                 | URL                     | What it shows                                                                                                                                                                     |
|----------------------|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Overview             | `/`                     | Today/yesterday views, unique visitors, sessions, bounce rate, pages/session, API calls, top page, 30‑day trend chart, top‑10 bar chart, top pages table                          |
| Pages                | `/pages/`               | All tracked pages with view counts, search by path, pagination, links to per‑page detail                                                                                          |
| Page Detail          | `/pages/…/`             | 30‑day view chart for a single page with compare toggle                                                                                                                           |
| API                  | `/api/`                 | API call counts today/yesterday, 30‑day API chart, top endpoints, status‑code distribution                                                                                        |
| Traffic              | `/traffic/`             | Top referrers, browsers, operating systems, device types                                                                                                                          |
| Geography            | `/geography/`           | Offline world map with drill‑down, country table, top cities (click a country to filter cities)                                                                                   |
| Events               | `/events/`              | Custom events: today/yesterday counts, daily chart, top categories, top actions, top labels, events by page, recent events feed                                                   |
| Real User Monitoring | `/rum/`                 | Core Web Vitals (LCP/CLS/INP) at the 75th percentile with good/needs-improvement/poor breakdown, top JavaScript errors                                                            |
| Uptime Monitoring    | `/uptime/`              | Monitor list with current status and uptime %, add/pause/delete monitors, recent incident log                                                                                     |
| Compliance           | `/compliance/`          | Consent-mode and retention status, "forget this visitor" deletion tool                                                                                                            |
| Data Import          | `/import/`              | Upload a GA/Plausible CSV export to backfill DailySiteStats for dates before you started tracking                                                                                 |
| Billing              | `/billing/`             | (optional) Total revenue, today/month revenue, active subscriptions, donations, daily income chart, top plans, recent transactions, MRR/ARR trend, churn, failed-payment tracking |
| Real‑time            | `/realtime/`            | Live visitor count (last 5 min), unique IPs, recent page views table with configurable refresh                                                                                    |
| Server Overview      | `/server/overview/`     | System health snapshot: CPU, memory, disk, network usage with live charts                                                                                                         |
| Server CPU           | `/server/cpu/`          | Detailed CPU usage per core, historical chart, load average                                                                                                                       |
| Server Memory        | `/server/memory/`       | RAM and swap usage with doughnut chart                                                                                                                                            |
| Server Disk          | `/server/disk/`         | Partition usage bars and I/O history                                                                                                                                              |
| Server Network       | `/server/network/`      | Interface statistics and network traffic chart                                                                                                                                    |
| Server Services      | `/server/services/`     | List of running systemd services                                                                                                                                                  |
| Server Processes     | `/server/processes/`    | Active process list sorted by CPU usage                                                                                                                                           |
| Server Slow Queries  | `/server/slow-queries/` | Queries recorded by the opt-in SlowQueryMiddleware, over a configurable threshold                                                                                                 |
| Server Queues        | `/server/queues/`       | Celery worker and task status (if CELERY_APP_PATH is configured)                                                                                                                  |
| Server Deployments   | `/server/deployments/`  | Log of recorded deployments (manage.py record_deployment), each creating a matching Overview chart annotation                                                                     |
| Settings             | `/settings/`            | IP anonymisation, ignored paths/extensions, refresh interval, theme selector, language selector                                                                                   |
| Admin Overview       | `/admin-overview/`      | User registrations, content creation, and login activity charts                                                                                                                   |
| Bot Traffic          | `/bots/`                | Total bot requests, daily bot charts, top bot paths, bot requests by country, bot category breakdown (search engine/AI crawler/social preview/SEO tool/unknown/malicious)         |
| Backups              | `/backups/`             | Configure backup paths, storage, schedule, and retention; create, download, and delete backups                                                                                    |
| About                | `/about/`               | The story behind the project, the developer, and support options                                                                                                                  |

All pages support date‑range filtering with one‑click presets (Today, Yesterday, Last 7 days, Last 30 days, This
month).  
Every line chart includes a “Compare to previous period” toggle.  
Every data table has CSV and JSON export buttons.

---

## Custom Event Tracking

Track any user interaction — button clicks, form submissions, video plays, downloads — with a single JavaScript snippet.

### Quick start

The package includes a lightweight event tracking script. You can either include it via Django's static tag, or copy the
code directly into your project.

**Option 1: Using Django's static tag (recommended for Django projects)**

```html

<script src="{% static 'paxalia/scripts/analytics-events.js' %}"></script>
```

**Note:** The default prefix is `/insights/`. If you changed it in your `urls.py`, replace `YOUR_PREFIX` in the script
above.

### Tracking events

Once the script is loaded, you can track events in two ways:

**Using data attributes (no JavaScript required):**

```html

<button data-analytics-category="download" data-analytics-action="click" data-analytics-label="windows">
    Download for Windows
</button>

<form data-analytics-category="form" data-analytics-action="submit" data-analytics-label="contact-form">
    ...
</form>
```

**Using JavaScript directly:**

```javascript
window.opAnalytics('video', 'play', 'intro-tutorial', 1);
```

All events appear in the Events dashboard with full date‑range filtering, comparison toggle, and CSV/JSON export.

### Available event properties

| Property | Required | Description                                             |
|----------|----------|---------------------------------------------------------|
| category | Yes      | Grouping name, e.g. `button`, `video`, `form`           |
| action   | Yes      | What happened, e.g. `click`, `play`, `submit`           |
| label    | No       | Extra detail, e.g. `signup-hero`, `linux-download`      |
| value    | No       | Numeric value (optional)                                |
| path     | No       | Page path – auto‑filled from `window.location.pathname` |

### Event API Path

The event tracking script uses **hardcoded** URLs: `/api/paxalia/event/` and (since Real User Monitoring, below)
`/api/paxalia/js-error/`. This is intentional:

- It keeps the dashboard URL secret.
- It makes the JavaScript simple and fast.
- It allows you to mount the dashboard at any secret path.

If you need to change these paths, update:

1. The URL patterns in your project's `urls.py`
2. The `EVENT_URL` and `JS_ERROR_URL` variables in `paxalia/static/paxalia/scripts/analytics-events.js`

---

## Real User Monitoring

Core Web Vitals and JavaScript error tracking, collected by the same `analytics-events.js` script used for custom
events — no separate tracker file, no third-party `web-vitals` library dependency.

### What's collected

- **LCP** (Largest Contentful Paint) and **INP** (Interaction to Next Paint) — measured natively via the browser's
  `PerformanceObserver` API.
- **CLS** (Cumulative Layout Shift) — computed with the standard session-window algorithm (shifts less than 1s apart,
  capped at a 5s session, largest session wins), not a naive lifetime sum.
- **JavaScript errors** — via `window.onerror` and `unhandledrejection`, including message, filename, line/column,
  and a truncated stack trace. Capped at 10 reports per page load (with per-error dedup) so a runaway error loop
  can't flood the endpoint.

All of it is sent right before the page is hidden/unloaded (Web Vitals, via `sendBeacon`, same lifecycle as the
existing time-on-page tracking) or immediately (JS errors, via `fetch(..., {keepalive: true})`, since a page may
keep running long after an error and you want to know sooner).

### Where it's stored

- Web Vitals ride on the existing `AnalyticsEvent` model (`category='web_vitals'`, `action` is the metric name,
  `value` the metric value) — no new table for these.
- JS errors get their own `JSError` model, since a useful report needs filename/line/column and a stack trace,
  which `AnalyticsEvent`'s generic 255-character label has no room for.

### The `/insights/rum/` page

- Three Web Vitals cards (LCP/CLS/INP), each showing the **75th percentile** for the selected period — the
  industry-standard way to aggregate field data, not an average — plus a good/needs-improvement/poor breakdown bar
  and the sample count. A metric with no samples yet shows an empty state rather than a misleading zero.
- A **Top JavaScript Errors** table, grouped by error message (count, first seen, last seen, a sample file:line).

### Accuracy notes (read before treating these as lab-grade metrics)

- **INP** here is the single worst interaction duration observed on the page, not the full percentile-ranking
  algorithm the spec uses for pages with dozens of interactions. This converges to the same number on a typical
  page and runs slightly pessimistic on a highly-interactive single-page app.
- **User-Agent-based** classification doesn't apply here, but the same "field data, not lab data" caveat as any
  RUM tool applies: these numbers reflect whatever devices/connections your real visitors actually have.
- JS error **grouping** is by message text only (not filename/line too) — grouping in a build-specific location
  would split the same error across every minified-bundle hash your deploys produce.

---

## Uptime Monitoring

Scheduled HTTP checks against URLs you configure, with status history and an incident log — a new subsystem, not
an extension of an existing page.

### How it works

1. Add a monitor on `/uptime/`: name, URL, HTTP method (GET/HEAD/POST), expected status code, timeout, and check
   interval.
2. Schedule the check command via cron or Celery beat — this package already assumes cron/Celery beat access for
   `aggregate_daily_stats`, `send_scheduled_reports`, and `detect_anomalies`, so this isn't a new operational
   requirement:

    ```bash
    # Run every minute; each monitor is only actually pinged once its own
    # check_interval_minutes has elapsed since its last check.
    * * * * * cd /path/to/project && python manage.py check_uptime >> /var/log/uptime.log 2>&1
    ```

3. The `/uptime/` page shows each monitor's current status, uptime % for the selected date range, and a combined
   recent-incidents table across all monitors.

### Design notes

- **No new dependency.** The HTTP check uses only `urllib.request` from the standard library — a GET/HEAD with a
  timeout and a status-code check doesn't need anything the `requests` library provides over urllib, and this
  package already goes out of its way to keep optional features from forcing new dependencies (`django-otp` and
  `weasyprint` are both guarded, optional imports).
- **Incidents are transition-based, not one row per failed check.** An incident opens on an up→down transition (or
  a monitor's very first check coming back down) and resolves on the next down→up transition — a monitor that's
  down for an hour with a check every minute is one incident with a ~60-minute duration, not sixty rows.
- **Alerts** go through the same `send_alert()` used by security and anomaly alerts (`category='uptime'`) — every
  down/recovery transition creates an in-dashboard notification and, if configured, an email/webhook alert, exactly
  like every other alert category.
- **Uptime %** for a period with zero checks is shown as "—", not 0% or 100% — nothing to compute yet is different
  from "always down" or "always up".

---

## Compliance

Consent-mode gating, per-data-type retention policies, and a "forget this visitor" deletion tool — independent of
any other section.

### Consent Mode

Off by default — every deployment tracks exactly as it did before this feature existed. To require consent before
tracking anything:

```python
PAXALIA_DASHBOARD = {
    ...
    'CONSENT_MODE_ENABLED': True,
    'CONSENT_COOKIE_NAME': 'analytics_consent',       # defaults shown
    'CONSENT_COOKIE_GRANTED_VALUE': 'granted',
}
```

Then, on the pages you track, include the new template tag immediately before the `analytics-events.js` script tag:

```html
{% load analytics_tags %}
{% analytics_consent_config %}
<script src="{% static 'paxalia/scripts/analytics-events.js' %}"></script>
```

Your own consent-banner/CMP JavaScript is responsible for setting the cookie once a visitor accepts — this package
doesn't provide a banner UI, only the gate that reads the cookie it sets. Until that cookie is present with the
configured value:

- No `PageView` row is written, and no session cookie is set — `AnalyticsMiddleware` returns early, before any
  tracking state is created.
- The public event/JS-error API endpoints skip the write and return `{"status": "skipped"}` rather than an error.
- `analytics-events.js` doesn't attach any listeners or send any beacons — `window.opAnalytics` becomes a no-op so
  existing `onclick="opAnalytics(...)"` call sites on your pages don't throw.

The server-side checks (middleware and the API endpoints) are the actual compliance guarantee; the client-side
check is about not even trying, and can't be relied on alone since a request could be sent directly to the API.

### Data Retention

Per-data-type retention, separate from `SECURITY_LOG_RETENTION_DAYS` (which only covers `LoginEvent`/
`SecurityAuditLog`) and `SERVER_METRIC_RETENTION_DAYS` (pruned inline by `record_server_metrics`, not by this):

```python
PAXALIA_DASHBOARD = {
    ...
    'DATA_RETENTION_DAYS': {
        'pageview': 400,
        'analytics_event': 400,
        'js_error': 90,
        'uptime_check': 90,
        'slow_query': 30,
    },
}
```

Empty by default — nothing is deleted unless you explicitly opt a data type in. Schedule the command like the
others:

```bash
0 3 * * * cd /path/to/project && python manage.py prune_analytics_data >> /var/log/prune-paxalia.log 2>&1
```

### Forget This Visitor

On `/compliance/`, delete every stored row for a given session ID or IP address — real, immediate deletion (since
`anonymize_ip` defaults off, IP addresses are typically stored raw, so this is a real capability, not a symbolic
one). Matches both a raw IP and its SHA-256 hash, since a deployment that toggled `anonymize_ip` partway through
its history could have stored a visitor's IP either way at different times.

**Known gap:** JS errors can only be deleted by session ID — the `JSError` model doesn't store an IP address, so an
IP-based deletion request won't reach it. Documented here rather than silently leaving rows behind.

The audit log records that a deletion happened and how much was deleted, but not the raw identifier that was
requested to be forgotten — logging the exact thing someone asked to have forgotten, in a different table, would
defeat the point.

---

## Data Import

Import historical daily stats from a Google Analytics or Plausible CSV export, for people migrating in — on
`/import/`.

### Why CSV, not the GA4 API

A real GA4 API integration needs OAuth credentials, a Google API client library dependency, and per-property
configuration this package has no way to own — the same category of problem as billing or Celery (it isn't this
package's data or credentials to hold). A CSV export needs nothing but a file you already have:

- **Google Analytics:** Reports → export any report as CSV.
- **Plausible:** Settings → Imports & Export → export CSV.

This is a deliberate scope decision, not a shortcut: it trades "fully automated" for "works today, no credentials,
no new dependency."

### One parser for both sources

A GA4 daily-metrics export and a Plausible export are both, underneath the different UIs, a table with a date
column and a handful of aggregate metric columns — they don't need two bespoke parsers, just column-name
recognition across both vocabularies (GA says "Views"/"Sessions"/"Users"; Plausible says
"pageviews"/"visitors"). GA's exports also carry a few leading title/date-range lines before the real header row —
the parser skips anything before the first row that looks like a real header, and skips (with a warning, not an
error) any data row whose date column doesn't parse, which also quietly handles a trailing "Totals" summary row.

### Scope

Only **date + aggregate-metric** CSVs are supported — one row per day. A page-level or dimension-broken-down
export (e.g. GA's "Pages and screens" report, one row per URL) won't import usefully: historical data lands in
daily aggregate stats, not individual page-view rows, since there's no way to reconstruct individual historical
hits from an aggregate export.

Metric mapping (documented, not guessed silently):

| Export column     | Lands in                                                                           |
|-------------------|------------------------------------------------------------------------------------|
| views / pageviews | `total_views`                                                                      |
| visitors / users  | `unique_ips` (closest available field — not literally an IP count, see below)      |
| sessions          | `total_sessions`                                                                   |
| bounce rate (%)   | `bounces`, computed as `round(bounce_rate / 100 * sessions)` when both are present |

Anything this package can't derive from a generic aggregate export — `unique_users` as distinct from `unique_ips`,
`api_calls`, `top_pages`, `bot_views` — is left at 0/empty on imported rows rather than guessed.

A date that already has a `DailySiteStats` row for the target site is **skipped by default** — import is meant to
fill in history from before you started tracking with this package, not to silently overwrite real tracked data
that happens to overlap. Check "Overwrite" on the import form if you do want to replace it. Imported rows are
tagged (`imported_from`: `ga`/`plausible`/`csv`) so they're distinguishable from live-tracked days in the Django
admin.

---

## Slack/Discord App

`alerts.py` has been able to *send* alerts to a Slack/Discord incoming webhook since v2.2.0. This is the other
direction: a slash command that *asks* for data on demand — `/analytics today`, `/analytics week`, etc.

### Slack setup

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps) and add a **Slash Command** (e.g.
   `/analytics`) pointing at `https://yourdomain.com/api/paxalia/slack/command/`.
2. Copy the app's **Signing Secret** into your settings:
   ```python
   PAXALIA_DASHBOARD = {
       ...
       'SLACK_SIGNING_SECRET': 'your-signing-secret',
   }
   ```
3. No new dependency — Slack verification is HMAC-SHA256 over the request body, using only `hmac`/`hashlib` from
   the standard library.

### Discord setup

1. Create a Discord application at [discord.com/developers/applications](https://discord.com/developers/applications),
   register a slash command (e.g. `/analytics` with an optional `period` choice: today/yesterday/week/month), and
   set the **Interactions Endpoint URL** to `https://yourdomain.com/api/paxalia/discord/interactions/`.
2. Copy the application's **Public Key** into your settings:
   ```python
   PAXALIA_DASHBOARD = {
       ...
       'DISCORD_PUBLIC_KEY': 'your-public-key',
   }
   ```
3. Discord requires Ed25519 signature verification, which the standard library doesn't provide — install
   [PyNaCl](https://pynacl.readthedocs.io/) (`pip install pynacl`) to enable it. This is an **optional** dependency,
   the same pattern as `django-otp`/`weasyprint`: without it installed, the Discord endpoint responds "not
   configured" (and, notably, Discord won't even let you save the Interactions Endpoint URL, since it requires the
   initial verification ping to pass). Slack support needs no such dependency either way.

### Scope

One command surface, reusing the exact same `compute_overview_snapshot()` the scheduled email/PDF report and
public share links already use: total views, unique visitors, top 5 pages, top 5 referrers, for
today/yesterday/this week/this month — answered against combined (all-sites) traffic; there's no per-site argument
in this version. Both platforms get the same plain-text response format rather than either platform's richer
formatting (Slack Block Kit / Discord embeds) — a single shared format that renders reasonably on both was worth
more here than a prettier response on only one of them.

---

## Admin Overview

The **Admin Overview** page provides a high‑level summary of site activity for administrators. It shows:

- **User statistics** – total users, new users today, new users this week, active users (last 7 days).
- **Content statistics** – total content items (articles, pages, etc.), configurable via `CONTENT_MODELS` in the view.
- **Charts** – user registrations over the last 30 days, content creation, and user logins.
- **Recent activity** – a table of recent actions from `django-auditlog` (if installed) or recent user logins.

This page is designed to give you a quick glance at the health of your site without diving into the Django admin or raw
database tables.

---

## Server Monitoring

The dashboard includes a full server monitoring suite that reads metrics directly from your system using the `psutil`
library. No agents, no external services – all data is collected locally.

### Available Pages

- **Overview** – a real‑time dashboard showing CPU, memory, disk, and network usage with live‑updating charts.
- **CPU** – per‑core usage, historical chart, and load average.
- **Memory** – RAM and swap usage with a doughnut chart.
- **Disk** – partition usage bars and I/O history.
- **Network** – interface statistics and traffic history.
- **Services** – list of running systemd services (Linux) with status.
- **Processes** – active process list sorted by CPU usage, updated every 5 seconds.
- **Slow Queries** – database queries that took longer than a configurable threshold, recorded by the opt-in
  `SlowQueryMiddleware` (see below).
- **Queues** – Celery worker and task status, if `CELERY_APP_PATH` is configured (see below).
- **Deployments** – a log of recorded deployments, each one also creating a matching annotation on the Overview
  traffic chart.

### History charts are now backed by real data

`api_server_history` used to generate synthetic `random.randint()` data as a placeholder — that's fixed. History
now comes from `ServerMetricSnapshot`, written by a new scheduled command:

```bash
# Run every minute; also prunes snapshots older than
# SERVER_METRIC_RETENTION_DAYS (default 7) on every run.
* * * * * cd /path/to/project && python manage.py record_server_metrics >> /var/log/server-metrics.log 2>&1
```

Without this scheduled, the history charts show an empty state rather than fabricated numbers.

### Slow query tracking (opt-in)

Add the middleware to your project's `MIDDLEWARE`, the same way `AnalyticsMiddleware` itself is added:

```python
MIDDLEWARE = [
    ...
    'paxalia.middleware.SlowQueryMiddleware',
]
```

Any query slower than `SLOW_QUERY_THRESHOLD_MS` (default 100ms, configurable in your `PAXALIA_DASHBOARD` dict) gets
recorded. This instruments Django's own query execution via `connection.execute_wrapper()`, so it works identically
across every database backend Django supports — no per-engine slow-query-log file to locate or parse.

### Queue monitoring (Celery)

Point `CELERY_APP_PATH` at your project's Celery `Application` instance:

```python
PAXALIA_DASHBOARD = {
    ...
    'CELERY_APP_PATH': 'myproject.celery.app',
}
```

This package doesn't add `celery` as a dependency — if it's not installed, or `CELERY_APP_PATH` isn't configured, the
Queues page just shows an empty state. RQ isn't implemented yet; it would follow the same dotted-path pattern.

### Deployment tracking

Call this from CI/CD right after a successful deploy:

```bash
python manage.py record_deployment --version "$(git rev-parse --short HEAD)" --notes "Deploy from main"
```

This records a `Deployment` row and auto-creates a matching `ChartAnnotation` at the same date, so the deploy shows
up on the Overview traffic chart with no extra configuration.

### Privacy and Security

All metrics are read locally; no data is sent to any third‑party service. The server views are protected by the same
`@staff_member_required` decorator as the rest of the admin pages, so only logged‑in staff can access them.

### Configuration

No additional configuration is required for the server section – it works out of the box on Linux, macOS, and Windows.
The only dependency is `psutil`, which is automatically installed with the package.

---

## Bot Traffic

The dashboard can automatically detect and separate bot/scanner traffic from real user visits. This keeps your main
analytics clean and provides a dedicated view for security monitoring.

### How it works

- You define a list of **bot paths** (one per line) in the Settings page, e.g.:

```text
/robots.txt
/.env
/wp-admin/
/xmlrpc.php
```

- The middleware checks each incoming request: if the path matches any bot path, it:
    - Marks the `PageView` with `is_bot=True` and `bot_category='malicious'`
    - Increments `DailySiteStats.bot_views` (not `total_views`)
- **In addition**, every request's User-Agent is checked against a maintained pattern list (
  `paxalia/bot_classification.py`) for known search engines (Googlebot, Bingbot, ...), AI crawlers (GPTBot, ClaudeBot,
  CCBot, ...), social-preview bots (facebookexternalhit, Twitterbot, Slackbot, ...), and SEO tools (AhrefsBot,
  SemrushBot, ...) — any match also sets `is_bot=True`, with `bot_category` set to the matching category. A generic
  bot-like User-Agent that doesn't match a known list (`curl/...`, `python-requests/...`, a bare "bot"/"crawler"/"
  spider" token, or no User-Agent at all) is categorized `'unknown'`.

> **⚠️ Breaking change:** `is_bot` used to be set *only* from the path match above — a real crawler (Googlebot, a
> social-media link-preview fetch, etc.) visiting an ordinary page was previously counted as regular human traffic in
> Overview/Traffic/Cohorts/Funnels/Goals and everywhere else that filters `is_bot=False`. That was never actually correct,
> but it means upgrading will change your numbers: "human" page-view counts will drop and Bot Traffic counts will rise on
> any site that gets real crawler traffic (which is nearly every public site). Existing rows are **not** reclassified
> automatically — run `python manage.py backfill_pageview_bot_category` once after upgrading to apply the new
> classification to history (safe to re-run any time `bot_paths` changes or the pattern list is extended). Add `--dry-run`
> to preview the counts first.
>
> User-Agent is exactly what the request claims to be — nothing here verifies it against the crawler's published IP
> ranges (that would require a network call this package doesn't make). A path match on a known attack-probe path always
> overrides a UA claim, precisely because scanners sometimes spoof "Googlebot" to bypass filtering — but a spoofed UA
> hitting an ordinary page will be misclassified as the real thing.

- Bot requests are **excluded** from all main analytics (overview, pages, geography, traffic, real‑time, events, API).
- They are **only** visible on the dedicated **Bot Traffic** page, which shows:
    - Total bot requests, today's bot requests, unique bot IPs
    - Daily bot requests chart (last 30 days)
    - Top 20 bot paths (horizontal bar chart)
    - Bot requests by country (doughnut chart)
    - **Bot category breakdown** (search engine / AI crawler / social preview / SEO tool / unknown / malicious), last 30
      days

### Importing a large bot path list

If you have a large file of known bot paths (e.g., from server logs), you can import it using the management command:

```bash
python manage.py import_bot_paths /path/to/bot_paths.txt
```

The file should contain one path per line. The command automatically merges new paths with existing ones and supports
--replace to overwrite.

This is useful for blocking common scanners (e.g., WordPress exploit attempts, .env file probes, wlwmanifest.xml scans).
A pre‑populated bots_paths.txt file is included in the package with over 3,400 known malicious paths.

--- 

## Backup Management

The dashboard includes a full backup management system that lets you create, download, and delete server backups
directly from the web interface.

### Features

- **Configurable paths** – specify which directories or files to back up (one per line).
- **Storage location** – choose an absolute path on your server where backups are stored.
- **Scheduled backups** – set a schedule (manual, daily, weekly, monthly) and run via cron.
- **Retention** – keep the last N backups; older ones are automatically deleted.
- **On‑demand backup creation** – click a button to create a backup immediately (runs in the background so the page
  doesn't block).
- **Chunked download** – large backup files are downloaded in 5 MB chunks for reliability.
- **Status tracking** – see if a backup is pending, creating, completed, or failed.

### Configuration

1. Go to `/insights/backups/` (the Settings card is at the top of the page).
2. Fill in:
    - **Paths to backup** – one per line (absolute or relative to project root).
    - **Storage directory** – absolute path (must be writable by the web server).
    - **Enable automatic backups** – check to allow scheduled backups.
    - **Schedule** – how often to run.
    - **Retention** – number of backups to keep.
3. Click **Save Settings**.
4. To create a backup, click **Create Backup** in the Archives card.

### Management command for scheduled backups

Add a cron job to run the backup command at your chosen schedule. For daily backups at 2 AM:

```bash
0 2 * * * cd /path/to/project && python manage.py create_backup >> /var/log/backup.log 2>&1
```

The command reads the configuration from the database and prunes old backups automatically.

---

## Internationalization

The dashboard ships with complete translations for five languages:

| Language             | Code      | RTL |
|----------------------|-----------|-----|
| English              | `en`      | No  |
| Spanish              | `es`      | No  |
| Arabic               | `ar`      | Yes |
| Simplified Chinese   | `zh-hans` | No  |
| Brazilian Portuguese | `pt-br`   | No  |

Arabic automatically flips the entire dashboard to right‑to‑left layout using the `dir="rtl"` attribute.

The language switcher is available in **Settings → Language**. It uses Django's standard `set_language` view — no extra
middleware or configuration is required.

### Adding a new language

1. Copy `paxalia/locale/en/LC_MESSAGES/django.po` to `paxalia/locale/<code>/LC_MESSAGES/`.
2. Translate every `msgstr` line.
3. Run `python manage.py compilemessages -l <code>`.
4. Add the language to the `languages` list in `paxalia/views/settings.py` (or override the view).

All translatable strings use Django's `{% trans %}` and `{% blocktrans %}` tags, so the dashboard can scale to any
number of languages without template changes.

---

## Themes

Twelve complete dashboard themes are included, each defining the full `--analytics-*` palette: background, surface,
border, text, dim text, accent, accent‑hover, and comparison colour.

| Theme            | Slug       | Style                                    |
|------------------|------------|------------------------------------------|
| Dark Gold        | `dark`     | Warm gold on deep charcoal — the default |
| Skybound Silk    | `default`  | Soft lavender accent, the OP brand theme |
| Golden Dusk      | `golden`   | Cream & classic gold, warm and inviting  |
| Azure Drift      | `azure`    | Cool ice‑blue, crisp and modern          |
| Sunlit Meadow    | `sunlit`   | Fresh lime green, bright and energetic   |
| Indigo Spectrum  | `indigo`   | Deep violet night, bold and creative     |
| Arctic Horizon   | `arctic`   | Icy blue & steel, calm and focused       |
| Ocean Breeze     | `ocean`    | Teal & navy, serene and deep             |
| Twilight Reverie | `twilight` | Mysterious violet, elegant and moody     |
| Velvet Noir      | `velvet`   | Dramatic crimson, luxurious and bold     |
| Citrine Prestige | `citrine`  | True gold, refined and prestigious       |
| Onyx Pearl       | `onyx`     | Minimal silver on black, ultra‑modern    |

### Switching themes

1. Go to **Settings**.
2. Open the **Theme** dropdown.
3. Select any theme — the entire dashboard recolours instantly, no page reload.
4. Your choice is saved to `localStorage` and persists across sessions.

### Creating a custom theme

Add a new `[data-analytics-theme="your-slug"]` block in `paxalia/static/paxalia/styles/themes.css`:

```css
[data-analytics-theme="your-slug"] {
    --analytics-bg: #…;
    --analytics-surface: #…;
    --analytics-border: #…;
    --analytics-text: #…;
    --analytics-text-dim: #…;
    --analytics-gold: #…;
    --analytics-gold-dim: rgba(…, 0.12);
    --analytics-gold-hover: #…;
    --analytics-compare: #…;
}
```

Then add {'slug': 'your-slug', 'label': 'Your Theme'} to the themes list in paxalia/views/settings.py. The theme will
appear in the dropdown automatically.




---

## Exporting Data

Every data table in the dashboard has two download buttons:

- **CSV** — opens immediately as a `.csv` file, compatible with Excel, Google Sheets, and any spreadsheet tool.
- **JSON** — downloads a `.json` file with an array of objects, ideal for scripts and APIs.

The export respects:

- The current **date range** (start and end dates).
- The current **path search** (on the Pages list).
- The current **country filter** (on the Geography page).

No additional configuration is needed. The export buttons appear automatically on every table card.

### Available exports

| Export                    | What it contains                                                                         |
|---------------------------|------------------------------------------------------------------------------------------|
| Top Pages                 | Top 10 pages with view counts                                                            |
| All Pages                 | Every tracked page with view counts                                                      |
| Top API Endpoints         | Endpoint paths with call counts                                                          |
| API Status Codes          | Status code distribution                                                                 |
| Top Referrers             | Referring URLs with visit counts                                                         |
| Browsers                  | Browser names with view counts                                                           |
| Operating Systems         | OS names with view counts                                                                |
| Device Types              | Device categories with view counts                                                       |
| Countries                 | Country names with visitor counts                                                        |
| Top Cities                | City, country, and visitor counts                                                        |
| Events Categories         | Category names with event counts                                                         |
| Events Actions            | Category, action, and event counts                                                       |
| Events Labels             | Label values with event counts                                                           |
| Events by Page            | Page paths with event counts                                                             |
| Recent Events             | Last 50 events with timestamps                                                           |
| Billing Plans             | Plan slugs with user counts                                                              |
| Recent Transactions       | Invoice number, user, amount, and date                                                   |
| Failed Payments (Dunning) | Invoice number, user, amount, date, and status for non-paid invoices in the last 90 days |

---

## Billing Integration

If your project has billing models (invoices, user plans, donations), the analytics dashboard can display revenue and
subscription data automatically.

### Requirements

Your project must have three models that follow this approximate structure:

| Model     | Expected fields                                                                                                                          |
|-----------|------------------------------------------------------------------------------------------------------------------------------------------|
| Invoice   | `date` (DateField), `amount` (DecimalField), `status` (CharField with 'paid'), `user` (ForeignKey to User), `invoice_number` (CharField) |
| User Plan | `current_plan` (ForeignKey to a Plan model with a `slug` field), `user` (OneToOneField to User)                                          |
| Donation  | `amount` (DecimalField)                                                                                                                  |

### Setup

1. Add `'billing'` to `SIDEBAR_SECTIONS` in your `PAXALIA_DASHBOARD` config.
2. Set the model paths to match your project:

```python
PAXALIA_DASHBOARD = {
    'SIDEBAR_SECTIONS': [..., 'billing', ...],
    'BILLING_INVOICE_MODEL': 'myapp.Invoice',
    'BILLING_USER_PLAN_MODEL': 'myapp.UserPlan',
    'BILLING_DONATION_MODEL': 'myapp.Donation',
}
```

3. Restart the server. The **Billing** link will appear in the sidebar, and `/insights/billing/` will show:

- Total revenue (all‑time)
- Revenue today and this month
- Active subscriptions count
- Total donations
- Daily income chart with compare toggle
- Plan distribution table
- Recent transactions table
- **Monthly revenue trend, last 12 months, plus a projected ARR run-rate** (an invoice-based proxy for MRR — see the
  note below)
- **Churn** (customer and revenue), computed from the last two fully-completed calendar months of invoice history
- **Failed/pending payments** ("dunning"), grouped by whatever status values your `Invoice.status` field actually uses,
  with CSV/JSON export

If the models don't exist or aren't configured, the billing section simply doesn't appear — no errors, no broken pages.

> **Why "MRR proxy" and not MRR:** this package doesn't require a Plan/price field in its documented contract above,
> only `current_plan.slug`. So "MRR" here is the sum of `'paid'` invoices in a calendar month — a reasonable stand-in when
> there's genuine month-to-month billing, but it will differ from true subscription MRR if your billing cycles aren't
> monthly, or if a Plan's price ever changed after an invoice was cut. Likewise, churn is computed from invoice history (
> paid last month, not paid this month) since there's no subscription start/cancel timestamp in the documented contract —
> it won't catch a customer who churns and resubscribes within the same window, and works best for regular (e.g. monthly)
> billing cycles.

---

## Security Center

The Security Center is a first-class dashboard surface for privileged operational visibility. It is designed to
complement, not replace, your host operating system's security controls.

### Login and session visibility

The package records authentication activity through Django's authentication signals. By default, successful-login
tracking is limited to staff/superuser accounts to preserve the privacy-first posture; failed-login attempts remain
visible for brute-force detection.

The Security Center can show login results, location/device context, active sessions, session revocation, and logout
information when the host application exposes the required Django authentication/session data.

### IP blocklist

Staff can add an IP to the dashboard blocklist. When `SecurityBlockMiddleware` is installed, subsequent requests from
active blocked addresses are rejected before the analytics middleware records them.

### Brute-force alerting

`SECURITY_FAILED_LOGIN_THRESHOLD` and `SECURITY_FAILED_LOGIN_WINDOW_MINUTES` define the threshold used to surface
repeated failed logins as a possible brute-force event. Alerts can be sent through configured email/webhook
destinations.

### CSP violation reporting

The dashboard can collect Content Security Policy violations and surface them for investigation. This is especially
useful during deployment hardening because blocked resources, inline-script violations, and unexpected origins can be
examined from the same operational interface.

### Security scorecard

The scorecard summarizes selected security findings and hardening checks so operational teams can identify outstanding
configuration issues without inspecting several Django settings modules manually.

### MFA / 2FA

The package includes a dashboard enrollment surface for authenticator-based two-factor authentication when the host
project has the required `django-otp` / two-factor stack installed and configured.

### Backup re-authentication

Backup downloads can require recent password authentication through `BACKUP_REAUTH_MINUTES`, reducing the risk of an
already-authenticated staff browser becoming an unattended archive download point.

---

## Advanced Analytics

### Goals

Goals let a deployment define meaningful conversion targets rather than only tracking traffic volume. Goals can be used
as reusable inputs to conversion-oriented analysis.

### Funnels

Funnels model ordered steps and expose drop-off between stages. A typical flow is landing page → signup → activation →
checkout.

### Segments

Segments provide reusable behavioral filters so the same audience definition can be applied across analytics views
rather than rebuilding filters manually each time.

### Campaigns

Campaign tracking captures UTM-style campaign context and exposes traffic performance by source, medium, and campaign.

### Cohorts

Cohort retention groups visitors by an initial activity period and follows subsequent activity over time, making repeat
engagement visible rather than hiding it inside aggregate counts.

### Annotations

Annotations place contextual markers on charts for deployments, campaigns, incidents, migrations, and other events that
may explain traffic changes.

---

## Reporting & Sharing

### Scheduled reports

Reports can be generated from the same analytics snapshot used by the dashboard and other integrations. Scheduled
delivery can use the host project's email configuration and optional PDF support.

### Public share links

Share links provide a controlled, read-only presentation of selected dashboard information for external stakeholders.
Password-protected links use a one-way password hash rather than storing the clear-text password, with the current
migration represented by `0019_sharelink_password_hash`.

### Exports

The dashboard provides CSV/JSON exports for supported tables, respecting applicable filters such as date range, path
search, and geography selection.

---

## Paxalia API

The package exposes a versioned, key-authenticated API surface in addition to its browser event endpoint. Scoped API
keys can be used for ingestion and read access without exposing staff dashboard credentials.

Current API capabilities include:

- event/data ingestion
- summary statistics
- page-view reads
- analytics-event reads
- API documentation through the dashboard's API Reference surface

The host application is responsible for securely storing API keys and selecting the appropriate scope.

### Browser event API

The public browser event endpoint is intentionally separate from the secret dashboard URL. This allows the tracking
script to remain functional without embedding the dashboard's private route in client-side code.

---

## Dependency Health

The Dependency Health page is intended for runtime maintenance rather than package installation. It starts from the
installed `paxalia-dashboard` distribution and resolves its runtime dependency closure, while also recognizing direct
requirements declared by the package.

The page can progressively check upstream package releases after the local inventory is rendered, so opening the page
does not need to wait for every external version lookup.

Dependency states distinguish current packages, packages with a newer upstream release, missing packages, and packages
whose upstream check could not be completed. The page does not automatically upgrade packages.

Decorative README separators such as `---`, `===`, and other non-requirement lines are ignored by the requirement parser
rather than treated as package names.

---

## Notifications & Alerts

Notifications provide an in-dashboard event surface for security, anomaly, uptime, and other supported alert categories.

Optional alert destinations include email and webhook delivery, while the in-dashboard notification center provides the
local operational history without requiring an external notification platform.

Alerting is intentionally best-effort: a notification delivery failure should not turn the underlying analytics or
security event into an application failure.

---

## Multi-Site Analytics

Multiple domains can be represented by `Site` records and tracked through the same dashboard. Requests are resolved by
hostname, cached briefly, and associated with the matching active site.

`AUTO_CREATE_SITES` is disabled by default. Enable it only when automatically registering unknown hostnames is an
explicit part of your deployment model.

---

## Release Center

The Release Center provides a dashboard surface for release artifacts and release context. Deployment tracking is
separate from artifact storage: CI/CD can call `record_deployment` after a successful deploy, which records the
deployment and creates a corresponding chart annotation so traffic changes can be interpreted against release events.

Example:

```bash
python manage.py record_deployment \
    --version "$(git rev-parse --short HEAD)" \
    --notes "Deploy from main"
```

---

## Operational Commands

The v3 package includes management commands for ongoing operations:

```bash
python manage.py aggregate_daily_stats
python manage.py backfill_pageview_bot_category
python manage.py backfill_pageview_is_api
python manage.py check_uptime
python manage.py cleanup_uploads
python manage.py create_backup
python manage.py detect_anomalies
python manage.py import_bot_paths /path/to/bot_paths.txt
python manage.py prune_analytics_data
python manage.py prune_security_logs
python manage.py record_deployment --version "$(git rev-parse --short HEAD)"
python manage.py record_server_metrics
python manage.py seed_analytics
python manage.py send_scheduled_reports
```

Typical scheduled jobs are:

```cron
# Daily analytics aggregation
0 0 * * * cd /path/to/project && python manage.py aggregate_daily_stats

# Server history snapshot
* * * * * cd /path/to/project && python manage.py record_server_metrics

# Uptime checks
* * * * * cd /path/to/project && python manage.py check_uptime

# Anomaly detection
10 * * * * cd /path/to/project && python manage.py detect_anomalies

# Analytics data retention
0 3 * * * cd /path/to/project && python manage.py prune_analytics_data

# Security log retention
20 3 * * * cd /path/to/project && python manage.py prune_security_logs
```

Adapt schedules and log destinations to the host operating system.

---

## Security & Privacy Model

The package is designed around keeping analytics data on the host server. IP storage/anonymization behavior is
configurable, consent mode can prevent tracking until a visitor has consented, and data-retention commands allow a
deployment to define how long different categories are retained.

### What the package does not do

- It does not provide a cookie-consent banner; your CMP/banner is responsible for collecting consent and setting the
  configured cookie.
- It does not verify crawler identity against published crawler IP ranges; bot classification is based on request path
  and user-agent patterns.
- It does not automatically rotate credentials or install OS firewall rules.
- It does not automatically upgrade Python packages from the Dependency Health page.
- It does not make the host project's Celery, billing, Redis, PostgreSQL, SMTP, or reverse-proxy configuration on your
  behalf.

### Production principle

Use the dashboard as an observability and application-level security layer alongside normal OS, database, reverse-proxy,
backup, network, and identity controls.

---

## Project Structure

```text
paxalia-dashboard
├── paxalia
│   ├── admin.py
│   ├── alerts.py
│   ├── anomalies.py
│   ├── api_keys.py
│   ├── apps.py
│   ├── bot_classification.py
│   ├── bots_paths.txt
│   ├── chat_ops.py
│   ├── cohorts.py
│   ├── compliance.py
│   ├── conf_uploads.py
│   ├── context_processors.py
│   ├── conversions.py
│   ├── data_import.py
│   ├── geoip
│   ├── __init__.py
│   ├── locale
│   │   ├── ar
│   │   │   └── LC_MESSAGES
│   │   │       ├── django.mo
│   │   │       └── django.po
│   │   ├── en
│   │   │   └── LC_MESSAGES
│   │   │       └── django.po
│   │   ├── es
│   │   │   └── LC_MESSAGES
│   │   │       ├── django.mo
│   │   │       └── django.po
│   │   ├── pt-br
│   │   │   └── LC_MESSAGES
│   │   │       ├── django.mo
│   │   │       └── django.po
│   │   └── zh-hans
│   │       └── LC_MESSAGES
│   │           ├── django.mo
│   │           └── django.po
│   ├── management
│   │   └── commands
│   │       ├── aggregate_daily_stats.py
│   │       ├── backfill_pageview_bot_category.py
│   │       ├── backfill_pageview_is_api.py
│   │       ├── check_uptime.py
│   │       ├── cleanup_uploads.py
│   │       ├── create_backup.py
│   │       ├── detect_anomalies.py
│   │       ├── import_bot_paths.py
│   │       ├── prune_analytics_data.py
│   │       ├── prune_security_logs.py
│   │       ├── record_deployment.py
│   │       ├── record_server_metrics.py
│   │       ├── seed_analytics.py
│   │       └── send_scheduled_reports.py
│   ├── middleware.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   ├── 0002_security_center.py
│   │   ├── 0003_csp_violations.py
│   │   ├── 0004_pageview_is_api.py
│   │   ├── 0005_flip_anonymize_ip_default.py
│   │   ├── 0006_multisite.py
│   │   ├── 0007_goals_funnels_segments_annotations.py
│   │   ├── 0008_dashboard_access_permissions.py
│   │   ├── 0009_paxalia_api_key.py
│   │   ├── 0010_reporting_sharing.py
│   │   ├── 0011_notifications.py
│   │   ├── 0012_bot_category.py
│   │   ├── 0013_js_error.py
│   │   ├── 0014_uptime_monitoring.py
│   │   ├── 0015_ops_monitoring.py
│   │   ├── 0016_compliance_permission.py
│   │   ├── 0017_data_import.py
│   │   ├── 0018_fix_dailysitestats_duplicates.py
│   │   ├── 0019_sharelink_password_hash.py
│   │   └── __init__.py
│   ├── models.py
│   ├── permissions.py
│   ├── queue_monitor.py
│   ├── report_delivery.py
│   ├── reporting.py
│   ├── requirements.txt
│   ├── revenue.py
│   ├── rum.py
│   ├── security_audit.py
│   ├── security_scorecard.py
│   ├── segments.py
│   ├── settings.py
│   ├── signals.py
│   ├── static
│   │   └── paxalia
│   │       ├── icons
│   │       │   ├── archive
│   │       │   │   ├── icon-file-text.svg
│   │       │   │   ├── icon-global.svg
│   │       │   │   └── icon-time-spendin.svg
│   │       │   ├── brand
│   │       │   │   ├── icon-brand.png
│   │       │   │   └── icon-brand.svg
│   │       │   ├── ui
│   │       │   │   ├── icon-bar-chart.svg
│   │       │   │   ├── icon-bot.svg
│   │       │   │   ├── icon-cpu.svg
│   │       │   │   ├── icon-download.svg
│   │       │   │   ├── icon-harddisk.svg
│   │       │   │   ├── icon-key.svg
│   │       │   │   ├── icon-layers.svg
│   │       │   │   ├── icon-memory.svg
│   │       │   │   ├── icon-network.svg
│   │       │   │   ├── icon-overview.svg
│   │       │   │   └── icon-server.svg
│   │       │   └── ui-multi
│   │       │       ├── icon-cloud-uploading.svg
│   │       │       └── icon-setting.svg
│   │       ├── scripts
│   │       │   ├── admin-overview.js
│   │       │   ├── analytics-events.js
│   │       │   ├── api.js
│   │       │   ├── backups.js
│   │       │   ├── billing-chart.js
│   │       │   ├── bots.js
│   │       │   ├── chart.umd.js
│   │       │   ├── d3.v3.min.js
│   │       │   ├── datamaps.world.min.js
│   │       │   ├── dependencies.js
│   │       │   ├── events-chart.js
│   │       │   ├── filter-bar.js
│   │       │   ├── geography-map.js
│   │       │   ├── language-manager.js
│   │       │   ├── overview.js
│   │       │   ├── page-detail.js
│   │       │   ├── realtime.js
│   │       │   ├── security.js
│   │       │   ├── server
│   │       │   │   ├── cpu.js
│   │       │   │   ├── disk.js
│   │       │   │   ├── memory.js
│   │       │   │   ├── network.js
│   │       │   │   ├── overview.js
│   │       │   │   ├── processes.js
│   │       │   │   └── services.js
│   │       │   ├── sidebar.js
│   │       │   ├── theme-manager.js
│   │       │   ├── topojson.v1.min.js
│   │       │   └── upload-widget.js
│   │       └── styles
│   │           ├── base.css
│   │           ├── components
│   │           │   ├── about.css
│   │           │   ├── backup.css
│   │           │   ├── buttons.css
│   │           │   ├── charts.css
│   │           │   ├── dependencies.css
│   │           │   ├── export-btn.css
│   │           │   ├── filter-bar.css
│   │           │   ├── icon.css
│   │           │   ├── menu.css
│   │           │   ├── notifications.css
│   │           │   ├── release-center.css
│   │           │   ├── rum.css
│   │           │   ├── security.css
│   │           │   ├── server.css
│   │           │   ├── settings-form.css
│   │           │   ├── sidebar.css
│   │           │   ├── stat-cards.css
│   │           │   ├── tables.css
│   │           │   ├── topbar.css
│   │           │   ├── typography.css
│   │           │   └── upload.css
│   │           ├── dashboard-refinements.css
│   │           ├── layout.css
│   │           ├── themes.css
│   │           └── tokens.css
│   ├── templates
│   │   └── paxalia
│   │       ├── about.html
│   │       ├── admin_overview.html
│   │       ├── annotations.html
│   │       ├── api_docs.html
│   │       ├── api.html
│   │       ├── api_keys.html
│   │       ├── backup_reauth.html
│   │       ├── backups.html
│   │       ├── base.html
│   │       ├── billing.html
│   │       ├── bots.html
│   │       ├── broken_links.html
│   │       ├── campaigns.html
│   │       ├── cohorts.html
│   │       ├── compliance.html
│   │       ├── dashboard.html
│   │       ├── data_import.html
│   │       ├── dependencies.html
│   │       ├── email
│   │       │   └── report_digest.html
│   │       ├── events.html
│   │       ├── funnels.html
│   │       ├── geography.html
│   │       ├── goals.html
│   │       ├── includes
│   │       │   └── filter_bar.html
│   │       ├── mfa_enroll.html
│   │       ├── notifications.html
│   │       ├── page_detail.html
│   │       ├── pages.html
│   │       ├── realtime.html
│   │       ├── releases.html
│   │       ├── reports.html
│   │       ├── rum.html
│   │       ├── security.html
│   │       ├── segments.html
│   │       ├── server_cpu.html
│   │       ├── server_deployments.html
│   │       ├── server_disk.html
│   │       ├── server_memory.html
│   │       ├── server_network.html
│   │       ├── server_overview.html
│   │       ├── server_processes.html
│   │       ├── server_queues.html
│   │       ├── server_services.html
│   │       ├── server_slow_queries.html
│   │       ├── settings.html
│   │       ├── shared_dashboard.html
│   │       ├── share_links.html
│   │       ├── sites.html
│   │       ├── traffic.html
│   │       └── uptime.html
│   ├── templatetags
│   │   ├── analytics_tags.py
│   │   └── __init__.py
│   ├── tests.py
│   ├── uptime.py
│   ├── urls.py
│   └── views
│       ├── about.py
│       ├── admin_overview.py
│       ├── annotations.py
│       ├── api_docs.py
│       ├── api_keys.py
│       ├── api.py
│       ├── backup.py
│       ├── billing.py
│       ├── bots.py
│       ├── broken_links.py
│       ├── campaigns.py
│       ├── chat_ops.py
│       ├── cohorts.py
│       ├── compliance.py
│       ├── csp_reports.py
│       ├── dashboard.py
│       ├── data_import.py
│       ├── dependencies.py
│       ├── events.py
│       ├── export.py
│       ├── geography.py
│       ├── goals.py
│       ├── __init__.py
│       ├── mfa.py
│       ├── notifications.py
│       ├── page_detail.py
│       ├── pages.py
│       ├── paxalia_api.py
│       ├── realtime.py
│       ├── releases.py
│       ├── reports.py
│       ├── rum.py
│       ├── security.py
│       ├── segments.py
│       ├── server.py
│       ├── settings.py
│       ├── share_links.py
│       ├── sites.py
│       ├── traffic.py
│       ├── uploads.py
│       ├── uptime.py
│       └── utils.py
├── LICENSE
├── MANIFEST.in
├── package-lock.json
├── pyproject.toml
├── README.md
├── setup.cfg
└── setup.py
```

> **Note:** The `.mmdb` GeoIP database files are **not** included in the Git repository because of their size.  
> Download them separately from [MaxMind](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) and place them
> in `paxalia/geoip/`.

---

## Contributing

Contributions are welcome!  
If you'd like to improve the dashboard, fix a bug, or add a new language, please open an issue first to discuss your
idea.

### Development setup

1. Clone the repository.
2. Install the package in editable mode: `pip install -e .`
3. Make your changes.
4. Run the test suite: `python manage.py test analytics`
5. Submit a pull request.

Please follow the existing code style: token‑driven CSS, external JavaScript with `window.__analytics_*` data injection,
and Django's standard patterns.

### Developer conventions

This project follows a small set of conventions to keep code readable, consistent, and easy to maintain. Please follow
these rules when contributing.

#### Commit message format

Use conventional commits with the form `type(scope): short summary`. Keep bodies short and informative.  
Common types:

- **feat(scope):** new feature  
  Example: `feat(auth): add remember-me option for login`
- **fix(scope):** bug fix  
  Example: `fix(download): correct checksum copy function`
- **refactor(scope):** non‑behavioral refactor  
  Example: `refactor(scripts): move page scripts to components/pages`
- **style(scope):** visual‑only / CSS changes  
  Example: `style(home): refine hero spacing`
- **docs(scope):** README or documentation updates  
  Example: `docs(readme): add developer conventions`
- **chore(scope):** tooling, build, or cleanup  
  Example: `chore(assets): add archive/assets-archive/`
- **perf(scope):** performance improvements
- **polish(scope):** UI/UX refinements, empty states, success messages  
  Example: `polish(analytics): add empty states to all charts`

When a change touches many files, include a short `Added / Modified / Fixed` list in the commit body.

#### Commit body structure

For non‑trivial commits, include a structured body with these sections:

```text
type(scope): short summary

Scope:
- file paths (modified/new)

Changes:
- bullet list of what changed

Behavior:
- how the system behaves now

Impact:
- why it matters
```

example:

```text
feat(analytics): add world map with drill‑down to cities

Scope:
- paxalia/views/geography.py (modified)
- paxalia/static/paxalia/scripts/geography-map.js (new)
- paxalia/templates/paxalia/geography.html (new)

Changes:
- Created a geography page with an offline Datamaps world map
- Added country‑level visitor counts with quintile‑based coloring
- Implemented click‑to‑filter on the map to show cities for a selected country

Behavior:
- Staff can see visitor distribution across countries on a world map
- Clicking a country filters the cities table to that country
- The map is fully offline; no external API calls are made

Impact:
- The dashboard now provides geographic insights comparable to Google Analytics
while remaining fully privacy‑first and self‑hosted
```

#### Branching rules

- `main` — protected, always deployable
- Feature & refactor branches (short‑lived):
    - `feat/<name>` or `feat/<scope>/<name>`
    - `refactor/<name>` or `refactor/<scope>/<name>`
- Docs branches:
    - `docs/<short‑description>`
- Hotfixes:
    - `fix/<issue>` or `hotfix/<issue>`
- When merging: prefer small focused PRs; squash or keep history tidy.

---

### Ideas for contribution

> The table below is retained as a forward-looking roadmap. Several items that were originally future ideas have since
> been implemented in v3; the list remains useful for potential extensions and contributors.

If you’re looking for a bigger feature to build, here are some ideas that would make the analytics dashboard even
better.  
All of them respect the privacy‑first philosophy and fit the existing architecture.

| Feature                                | Description                                                                                                             | Effort |
|----------------------------------------|-------------------------------------------------------------------------------------------------------------------------|--------|
| **City bubbles on the world map**      | When a country is clicked, zoom in and show city circles sized by visitor count                                         | Medium |
| **Session replay / user journey**      | Show the sequence of pages a single anonymous session visited, with timestamps                                          | Medium |
| **Funnel analysis**                    | Define a series of pages or events and see drop‑off between each step (e.g., landing → signup → checkout)               | Medium |
| **Goal completions**                   | Let users define a goal (e.g., `/signup/`, event `form:submit`) and track completions over time with conversion rates   | Medium |
| **Annotations on charts**              | Allow staff to add notes to specific dates (“new feature launched”) visible as markers on every chart                   | Small  |
| **Scheduled email reports**            | A management command that emails a weekly summary PDF/CSV to configured recipients                                      | Small  |
| **Page‑load time tracking**            | A tiny JS snippet addition to measure and display average page load times (Performance API)                             | Small  |
| **Custom dashboards**                  | Let users pin their favourite charts and tables to a custom overview page, drag‑and‑drop layout                         | Large  |
| **More languages**                     | Contribute a complete `.po` file for a new language (German, French, Japanese, Italian, Korean, etc.)                   | Small  |
| **Dark/Light theme per section**       | Allow some dashboard sections to be light while others stay dark, or schedule theme changes                             | Medium |
| **Admin dashboard widgets**            | Show today’s key metrics directly on the Django admin index page as custom admin widgets                                | Small  |
| **Audience retention / cohort table**  | Show what percentage of visitors return after N days, based on anonymous session IDs                                    | Medium |
| **Behavior flow diagram**              | A Sankey or flow chart showing how visitors move between pages (e.g., home → pricing → signup)                          | Large  |
| **Campaign / UTM tracking**            | Automatically extract `utm_source`, `utm_medium`, `utm_campaign` from URLs and show campaign performance                | Medium |
| **Alerts / thresholds**                | Let staff set thresholds (e.g., “notify me if bounce rate > 80%”) and receive Django signals or email alerts            | Medium |
| **A/B testing integration**            | Track variants of a page and show which version performs better on a chosen metric                                      | Large  |
| **Heatmap generation**                 | Record click coordinates (anonymously) and generate a heatmap overlay for any page                                      | Large  |
| **GDPR / cookie‑less mode**            | Add a fully cookie‑less mode that uses fingerprinting‑free session detection for even stricter privacy                  | Medium |
| **Custom event schema**                | Let users define a schema for their events (allowed categories, actions, labels) and validate incoming events           | Small  |
| **Video / audio engagement tracking**  | Pre‑built watchers for `<video>` and `<audio>` elements that automatically send play, pause, complete events            | Small  |
| **PDF export of the entire dashboard** | Generate a multi‑page PDF report of the current view (charts + tables) with one click                                   | Medium |
| **Public sharing links**               | Generate a secret, read‑only link to share a dashboard view with external stakeholders                                  | Medium |
| **Multi‑site / tenant support**        | Track multiple domains or sites in a single analytics installation, with per‑site filtering                             | Large  |
| **AI‑powered insights**                | Use a local LLM to generate natural‑language summaries of traffic changes (“Traffic spiked 40% on Tuesday, driven by…”) | Large  |
| **Plugin / extension system**          | Allow developers to register custom charts, tables, or pages that plug into the analytics dashboard                     | Large  |

If you’d like to work on any of these, please open an issue to discuss the approach first — I’ll be happy to help guide
the implementation.

---

## License

This project is licensed under the **Apache License 2.0**.  
See the [LICENSE](LICENSE) file for the full text.

You are free to:

- Use, copy, modify, and distribute the software
- Use it for personal, commercial, and open‑source projects
- Build and sell products that include this software

Under the following terms:

- You must include a copy of the license and copyright notice
- You must state significant changes made to the original code
- You may not use the author’s name to endorse derived products without permission

This license also includes an express **grant of patent rights** from contributors to users.

---

## Credits

Built entirely by **Parsa Zaydany** — solo, offline, during difficult circumstances – and published under the **Paxalia
** brand.

### The Story

This dashboard exists because the analytics landscape is broken. Most tools track your users, expose their IPs, and send
data to third‑party servers. They're insecure by design, and they don't respect privacy.

**paxalia-dashboard** is different:

- It's completely open source.
- It runs entirely on your own server – no external calls, no tracking pixels.
- Data handling (including IP anonymization) is yours to configure in Settings.

The world map database is only 60MB. Downloading it took **over four hours** over an unreliable connection. Pushing this
first release to GitHub required buying a small amount of bandwidth — a purchase that came from savings I had set aside
over two years for my main project. For someone in my situation, even this single push was expensive.

But developers exist because we help each other. Every language we use, every framework, every open‑source package —
someone built it and shared it. This is my contribution back.

### About Paxalia

[Paxalia](https://paxalia.com) is a workspace, timer, planner, and team-tools platform — one app covering deep-focus
timers, notes, goals, an infinite canvas board, a Life OS, live shareable pages, events and alarms, and team chat —
built and maintained by a single developer. This analytics dashboard is part of the same ecosystem.

### Full Story

To learn more about the project, the developer, and how to support its continued development, visit the **About** page
inside the dashboard at `/insights/about/`.

### Support

If this package helps your project, consider:

- Giving it a star on GitHub
- Sharing it with the Django community
- Contributing a translation or feature
- Supporting via [Paxalia](https://paxalia.com/donation/)

Thank you for using **paxalia-dashboard**.

## Paxalia Logging / Observability

The v4 logging branch adds a canonical observability layer without replacing the existing RUM, Security Center, analytics, or server-monitoring systems. Standard Python/Django loggers are captured through a safe handler after the Paxalia app loads. Add `paxalia.logging.middleware.PaxaliaLoggingMiddleware` after session/auth middleware when you want request IDs, duration, and explicit response-status events for requests that are not already logged by Django.

```python
MIDDLEWARE = [
    # Django session/auth middleware first ...
    'paxalia.logging.middleware.PaxaliaLoggingMiddleware',
    'paxalia.middleware.AnalyticsMiddleware',
]
```

Structured application events can use the branded helper:

```python
import paxalia

paxalia.log(
    'Workspace synchronization failed',
    level='ERROR',
    category='application.sync',
    action='sync_failed',
    metadata={'workspace_id': '...'},
)
```

The helper uses the standard logging infrastructure underneath and redacts common credential fields before storage. The same canonical store powers the Paxalia Logs dashboard, grouping/fingerprints, correlation IDs, filtered exports, browser error ingestion, authentication activity, and retention pruning.

Relevant `PAXALIA_DASHBOARD` settings:

```python
PAXALIA_DASHBOARD = {
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
    'SECURITY_STORE_FAILED_USERNAME': False,
    'SECURITY_ADMIN_USER_CHECK': None,
    'APPLICATION_LOGS': [],
}
```

Run `python manage.py paxalia_logs_prune --dry-run` before scheduling `python manage.py paxalia_logs_prune`. Failed login identifiers are stored as a SHA-256 fingerprint by default; set `SECURITY_STORE_FAILED_USERNAME=True` only when the host application's privacy requirements explicitly permit raw identifiers. For projects where `is_staff`/`is_superuser` is not the administrator definition, `SECURITY_ADMIN_USER_CHECK` may be set to a trusted callable accepting a user and returning a boolean.
