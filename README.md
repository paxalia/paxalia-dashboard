# django‑zaydany‑analytics

![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Django](https://img.shields.io/badge/django-5.0+-green.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A **privacy‑first, self‑hosted analytics platform** for Django.  
Drop it into any Django project and get a beautiful, full‑featured analytics dashboard with zero third‑party services.

---

## Table of Contents

- [Why django‑zaydany‑analytics?](#why-django-zaydany-analytics)
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
- [Internationalization](#internationalization)
- [Themes](#themes)
- [Exporting Data](#exporting-data)
- [Billing Integration](#billing-integration)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

---

## Why django‑zaydany‑analytics

|                      | Google Analytics | Other Django packages | **django‑zaydany‑analytics** |
|----------------------|------------------|-----------------------|------------------------------|
| Self‑hosted          | ❌                | ✅                     | ✅                            |
| Privacy‑first        | ❌                | ❌ (basic)             | ✅ (no third‑party sharing)   |
| Full dashboard       | ✅                | ❌ (basic counters)    | ✅                            |
| World map            | ✅                | ❌                     | ✅                            |
| Event tracking       | ✅                | ❌                     | ✅                            |
| Billing dashboard    | ❌                | ❌                     | ✅                            |
| Server monitoring    | ❌                | ❌                     | ✅                            |
| Bot detection        | ❌                | ❌                     | ✅                            |
| Backup management    | ❌                | ❌                     | ✅                            |
| Themes               | ❌                | ❌                     | ✅ (12 luxury themes)         |
| Multi‑language + RTL | ❌                | ❌                     | ✅ (5 languages, RTL support) |
| Offline map          | ❌                | ❌                     | ✅ (no CDN calls)             |
| One‑click CSV/JSON   | ❌                | ❌                     | ✅                            |

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
- **Bot Traffic Detection** – automatically identify and separate scanner and bot requests; view them in a dedicated
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
  `ZAYDANY_ANALYTICS` dict.
- **Privacy‑First** – IP addresses are hashed; no cookies required (anonymous session cookie is optional and carries no
  personal data); all data stays on your server.
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
pip install django-zaydany-analytics
```

### 2. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ...
    'analytics',
]
```

### 3. Include the URLs

The dashboard is mounted at a secret path of your choice. The event API is mounted at a fixed public path (hardcoded in
JavaScript). This keeps your dashboard URL hidden while allowing the event tracking to work.

In your project’s root `urls.py`:

```python
from django.urls import path, include
from django.views.i18n import set_language
from analytics.views.events import analytics_event_api

# Choose a secret path for your dashboard
DASHBOARD_URL = 'insights/'  # or a random string

urlpatterns = [
    # ...
    # Public event API (hardcoded path, matches JavaScript)
    path('api/analytics/event/', analytics_event_api, name='event_api'),

    # Secret dashboard (everything else)
    path(DASHBOARD_URL, include('analytics.urls')),

    # Required for language switching
    path('i18n/setlang/', set_language, name='set_language'),
]
```

### 4. Add the analytics middleware

In `settings.py`, add `analytics.middleware.AnalyticsMiddleware` to the bottom of `MIDDLEWARE`:

```python
MIDDLEWARE = [
    # ...
    'analytics.middleware.AnalyticsMiddleware',
]
```

This middleware automatically logs every page visit.
Without it, no data will appear in the dashboard.

### 5. Run migrations

```bash
python manage.py migrate analytics
```

> **Note:** The package includes a clean `0001_initial.py` migration. If you're upgrading from an older version,
> you should run `python manage.py migrate analytics` to apply the latest schema. The migration is
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
                'analytics.context_processors.analytics_config',
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
src = "{% static 'analytics/scripts/analytics-events.js' %}" > < / script >
```

### 7. Compile translations (optional)

```bash
python manage.py compilemessages -l es -l ar -l zh-hans -l pt-br
```

### 8. Download the GeoIP database (required for the geography page)

Download GeoLite2‑City.mmdb (free) from MaxMind
and place it in the directory specified by GEOIP_PATH (default: analytics/geoip/ inside the package).

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

All settings go into your settings.py under a single ZAYDANY_ANALYTICS dictionary.

```python
ZAYDANY_ANALYTICS = {
    # Sidebar sections to show (order matters)
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime',
        'geography', 'events', 'billing', 'releases', 'settings',
        'bots', 'backups'
    ],

    # Prefix used to identify API calls (used in stats)
    'API_PATH_PREFIX': '/api/',

    # Path to the MaxMind GeoLite2‑City.mmdb file
    'GEOIP_PATH': None,  # None = use analytics/geoip/ inside the package

    # Billing models (optional – enable 'billing' in SIDEBAR_SECTIONS)
    'BILLING_INVOICE_MODEL': 'billing.BillingInvoice',
    'BILLING_USER_PLAN_MODEL': 'billing.UserBilling',
    'BILLING_DONATION_MODEL': 'billing.Donation',

    # Default middleware fallbacks (when no AnalyticsSettings row exists)
    'DEFAULT_ANONYMIZE_IP': True,
    'DEFAULT_IGNORED_PREFIXES': ['/admin/', '/static/', '/media/'],
    'DEFAULT_IGNORED_EXTENSIONS': ['.css', '.js', '.png', '.jpg', '.svg', '.ico', '.woff2'],
    'DEFAULT_REALTIME_REFRESH': 30,

    'UPLOADS_INCOMING_ROOT': None,
    'UPLOAD_CHUNK_SIZE_MB': 5,  # optional, default 5
    'UPLOAD_MAX_FILE_SIZE_MB': 2048,  # optional, default 2048 (2GB)
}
```

Important: If you enable the 'billing' section, the corresponding models must exist and be importable.

### Event API Path

The event API is hardcoded in JavaScript at `/api/analytics/event/`. This is intentional:

- **The dashboard URL stays secret** – never exposed in client code.
- **The event API is public** – accepts anonymous data only.
- **No inline scripts needed** – all CSP rules are satisfied with `nonce`.

If you want to change the event API path, you must update:

1. The URL pattern in your project's `urls.py`
2. The `EVENT_URL` variable in `analytics/static/analytics/scripts/analytics-events.js`

---

## Dashboard Pages

| Page             | URL                  | What it shows                                                                                                                                            |
|------------------|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Overview         | `/`                  | Today/yesterday views, unique visitors, sessions, bounce rate, pages/session, API calls, top page, 30‑day trend chart, top‑10 bar chart, top pages table |
| Pages            | `/pages/`            | All tracked pages with view counts, search by path, pagination, links to per‑page detail                                                                 |
| Page Detail      | `/pages/…/`          | 30‑day view chart for a single page with compare toggle                                                                                                  |
| API              | `/api/`              | API call counts today/yesterday, 30‑day API chart, top endpoints, status‑code distribution                                                               |
| Traffic          | `/traffic/`          | Top referrers, browsers, operating systems, device types                                                                                                 |
| Geography        | `/geography/`        | Offline world map with drill‑down, country table, top cities (click a country to filter cities)                                                          |
| Events           | `/events/`           | Custom events: today/yesterday counts, daily chart, top categories, top actions, top labels, events by page, recent events feed                          |
| Billing          | `/billing/`          | (optional) Total revenue, today/month revenue, active subscriptions, donations, daily income chart, top plans, recent transactions                       |
| Real‑time        | `/realtime/`         | Live visitor count (last 5 min), unique IPs, recent page views table with configurable refresh                                                           |
| Server Overview  | `/server/overview/`  | System health snapshot: CPU, memory, disk, network usage with live charts                                                                                |
| Server CPU       | `/server/cpu/`       | Detailed CPU usage per core, historical chart, load average                                                                                              |
| Server Memory    | `/server/memory/`    | RAM and swap usage with doughnut chart                                                                                                                   |
| Server Disk      | `/server/disk/`      | Partition usage bars and I/O history                                                                                                                     |
| Server Network   | `/server/network/`   | Interface statistics and network traffic chart                                                                                                           |
| Server Services  | `/server/services/`  | List of running systemd services                                                                                                                         |
| Server Processes | `/server/processes/` | Active process list sorted by CPU usage                                                                                                                  |
| Settings         | `/settings/`         | IP anonymisation, ignored paths/extensions, refresh interval, theme selector, language selector                                                          |
| Admin Overview   | `/admin-overview/`   | User registrations, content creation, and login activity charts                                                                                          |
| Bot Traffic      | `/bots/`             | Total bot requests, daily bot charts, top bot paths, bot requests by country                                                                             |
| Backups          | `/backups/`          | Configure backup paths, storage, schedule, and retention; create, download, and delete backups                                                           |
| About            | `/about/`            | The story behind the project, the developer, and support options                                                                                         |

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

<script src="{% static 'analytics/scripts/analytics-events.js' %}"></script>
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

The event tracking script uses a **hardcoded** URL: `/api/analytics/event/`. This is intentional:

- It keeps the dashboard URL secret.
- It makes the JavaScript simple and fast.
- It allows you to mount the dashboard at any secret path.

If you need to change this path, update:

1. The URL pattern in your project's `urls.py`
2. The `EVENT_URL` variable in `analytics/static/analytics/scripts/analytics-events.js`

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
    - Marks the `PageView` with `is_bot=True`
    - Increments `DailySiteStats.bot_views` (not `total_views`)
- Bot requests are **excluded** from all main analytics (overview, pages, geography, traffic, real‑time, events, API).
- They are **only** visible on the dedicated **Bot Traffic** page, which shows:
    - Total bot requests, today's bot requests, unique bot IPs
    - Daily bot requests chart (last 30 days)
    - Top 20 bot paths (horizontal bar chart)
    - Bot requests by country (doughnut chart)

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

1. Copy `analytics/locale/en/LC_MESSAGES/django.po` to `analytics/locale/<code>/LC_MESSAGES/`.
2. Translate every `msgstr` line.
3. Run `python manage.py compilemessages -l <code>`.
4. Add the language to the `languages` list in `analytics/views/settings.py` (or override the view).

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

Add a new `[data-analytics-theme="your-slug"]` block in `analytics/static/analytics/styles/themes.css`:

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

Then add {'slug': 'your-slug', 'label': 'Your Theme'} to the themes list in analytics/views/settings.py. The theme will
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

| Export              | What it contains                       |
|---------------------|----------------------------------------|
| Top Pages           | Top 10 pages with view counts          |
| All Pages           | Every tracked page with view counts    |
| Top API Endpoints   | Endpoint paths with call counts        |
| API Status Codes    | Status code distribution               |
| Top Referrers       | Referring URLs with visit counts       |
| Browsers            | Browser names with view counts         |
| Operating Systems   | OS names with view counts              |
| Device Types        | Device categories with view counts     |
| Countries           | Country names with visitor counts      |
| Top Cities          | City, country, and visitor counts      |
| Events Categories   | Category names with event counts       |
| Events Actions      | Category, action, and event counts     |
| Events Labels       | Label values with event counts         |
| Events by Page      | Page paths with event counts           |
| Recent Events       | Last 50 events with timestamps         |
| Billing Plans       | Plan slugs with user counts            |
| Recent Transactions | Invoice number, user, amount, and date |

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

1. Add `'billing'` to `SIDEBAR_SECTIONS` in your `ZAYDANY_ANALYTICS` config.
2. Set the model paths to match your project:

```python
ZAYDANY_ANALYTICS = {
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

If the models don't exist or aren't configured, the billing section simply doesn't appear — no errors, no broken pages.

---

## Project Structure

```text
├── analytics
│   ├── admin.py
│   ├── apps.py
│   ├── bots_paths.txt
│   ├── conf_uploads.py
│   ├── context_processors.py
│   ├── geoip
│   │   ├── GeoLite2-ASN.mmdb
│   │   ├── GeoLite2-City.mmdb
│   │   └── GeoLite2-Country.mmdb
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
│   │       ├── create_backup.py
│   │       ├── import_bot_paths.py
│   │       └── seed_analytics.py
│   ├── middleware.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   └── __init__.py
│   ├── models.py
│   ├── requirements.txt
│   ├── settings.py
│   ├── static
│   │   └── analytics
│   │       ├── icons
│   │       │   ├── archive
│   │       │   │   ├── icon-file-text.svg
│   │       │   │   ├── icon-global.svg
│   │       │   │   └── icon-time-spendin.svg
│   │       │   ├── brand
│   │       │   │   ├── icon-brand.png
│   │       │   │   ├── icon-brand.svg
│   │       │   │   ├── icon-brand-transparent.png
│   │       │   │   └── icon-brand-transparent.svg
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
│   │       │   ├── events-chart.js
│   │       │   ├── filter-bar.js
│   │       │   ├── geography-map.js
│   │       │   ├── language-manager.js
│   │       │   ├── overview.js
│   │       │   ├── page-detail.js
│   │       │   ├── realtime.js
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
│   │           │   ├── charts.css
│   │           │   ├── export-btn.css
│   │           │   ├── filter-bar.css
│   │           │   ├── icon.css
│   │           │   ├── menu.css
│   │           │   ├── server.css
│   │           │   ├── settings-form.css
│   │           │   ├── sidebar.css
│   │           │   ├── stat-cards.css
│   │           │   ├── tables.css
│   │           │   ├── topbar.css
│   │           │   ├── typography.css
│   │           │   └── upload.css
│   │           ├── layout.css
│   │           ├── themes.css
│   │           └── tokens.css
│   ├── templates
│   │   └── analytics
│   │       ├── about.html
│   │       ├── admin_overview.html
│   │       ├── api.html
│   │       ├── backups.html
│   │       ├── base.html
│   │       ├── billing.html
│   │       ├── bots.html
│   │       ├── dashboard.html
│   │       ├── events.html
│   │       ├── geography.html
│   │       ├── includes
│   │       │   └── filter_bar.html
│   │       ├── page_detail.html
│   │       ├── pages.html
│   │       ├── realtime.html
│   │       ├── releases.html
│   │       ├── server_cpu.html
│   │       ├── server_disk.html
│   │       ├── server_memory.html
│   │       ├── server_network.html
│   │       ├── server_overview.html
│   │       ├── server_processes.html
│   │       ├── server_services.html
│   │       ├── settings.html
│   │       └── traffic.html
│   ├── templatetags
│   │   ├── analytics_tags.py
│   │   └── __init__.py
│   ├── tests.py
│   ├── urls.py
│   └── views
│       ├── about.py
│       ├── admin_overview.py
│       ├── api.py
│       ├── backup.py
│       ├── billing.py
│       ├── bots.py
│       ├── dashboard.py
│       ├── events.py
│       ├── export.py
│       ├── geography.py
│       ├── __init__.py
│       ├── page_detail.py
│       ├── pages.py
│       ├── realtime.py
│       ├── releases.py
│       ├── server.py
│       ├── settings.py
│       ├── traffic.py
│       ├── uploads.py
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
> in `analytics/geoip/`.

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
- analytics/views/geography.py (modified)
- analytics/static/analytics/scripts/geography-map.js (new)
- analytics/templates/analytics/geography.html (new)

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

**django‑zaydany‑analytics** is different:

- It's completely open source.
- It runs entirely on your own server – no external calls, no tracking pixels.
- Your users' privacy is protected by default.

The world map database is only 60MB. Downloading it took **over four hours** over an unreliable connection. Pushing this
first release to GitHub required buying a small amount of bandwidth — a purchase that came from savings I had set aside
over two years for my main project. For someone in my situation, even this single push was expensive.

But developers exist because we help each other. Every language we use, every framework, every open‑source package —
someone built it and shared it. This is my contribution back.

### About Paxalia

[Paxalia](https://paxalia.com) is a collection of thoughtfully crafted digital tools – a planning app, an SVG design
tool, and this analytics dashboard – all built by a solo developer who believes that great software should be both
powerful and ethical.

### Full Story

To learn more about the project, the developer, and how to support its continued development, visit the **About** page
inside the dashboard at `/insights/about/`.

### Support

If this package helps your project, consider:

- Giving it a star on GitHub
- Sharing it with the Django community
- Contributing a translation or feature
- Supporting via [Paxalia](https://paxalia.com/donation/)

Thank you for using **django‑zaydany‑analytics**.