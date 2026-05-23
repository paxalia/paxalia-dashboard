# django‑zaydany‑analytics

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

In your project’s root urls.py:

```python
from django.urls import path, include

urlpatterns = [
    # ...
    path('insights/', include('analytics.urls')),
]
```

### 4. Run migrations

```bash
python manage.py migrate analytics
```

### 5. Compile translations (optional)

```bash
python manage.py compilemessages -l es -l ar -l zh-hans -l pt-br
```

### 6. Download the GeoIP database (required for the geography page)

Download GeoLite2‑City.mmdb (free) from MaxMind
and place it in the directory specified by GEOIP_PATH (default: analytics/geoip/ inside the package).

### 7. Start the server

```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/insights/ – your analytics dashboard is live.


---

## Configuration

All settings go into your settings.py under a single ZAYDANY_ANALYTICS dictionary.

```python
ZAYDANY_ANALYTICS = {
    # Sidebar sections to show (order matters)
    'SIDEBAR_SECTIONS': [
        'overview', 'pages', 'api', 'traffic', 'realtime',
        'geography', 'events', 'billing', 'settings'
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
}
```

Important: If you enable the 'billing' section, the corresponding models must exist and be importable.

---

## Dashboard Pages

| Page        | URL                    | What it shows                                                                                                                                            |
|-------------|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Overview    | `/insights/`           | Today/yesterday views, unique visitors, sessions, bounce rate, pages/session, API calls, top page, 30‑day trend chart, top‑10 bar chart, top pages table |
| Pages       | `/insights/pages/`     | All tracked pages with view counts, search by path, pagination, links to per‑page detail                                                                 |
| Page Detail | `/insights/pages/…/`   | 30‑day view chart for a single page with compare toggle                                                                                                  |
| API         | `/insights/api/`       | API call counts today/yesterday, 30‑day API chart, top endpoints, status‑code distribution                                                               |
| Traffic     | `/insights/traffic/`   | Top referrers, browsers, operating systems, device types                                                                                                 |
| Geography   | `/insights/geography/` | Offline world map with drill‑down, country table, top cities (click a country to filter cities)                                                          |
| Events      | `/insights/events/`    | Custom events: today/yesterday counts, daily chart, top categories, top actions, top labels, events by page, recent events feed                          |
| Billing     | `/insights/billing/`   | (optional) Total revenue, today/month revenue, active subscriptions, donations, daily income chart, top plans, recent transactions                       |
| Real‑time   | `/insights/realtime/`  | Live visitor count (last 5 min), unique IPs, recent page views table with configurable refresh                                                           |
| Settings    | `/insights/settings/`  | IP anonymisation, ignored paths/extensions, refresh interval, theme selector, language selector                                                          |

All pages support date‑range filtering with one‑click presets (Today, Yesterday, Last 7 days, Last 30 days, This
month).  
Every line chart includes a “Compare to previous period” toggle.  
Every data table has CSV and JSON export buttons.

---

## Custom Event Tracking

Track any user interaction — button clicks, form submissions, video plays, downloads — with a single JavaScript snippet.

### Quick start

1. Include the snippet on every page you want to track:

```html

<script src="{% static 'analytics/scripts/analytics-events.js' %}"></script>
```

2. Add `data-analytics-*` attributes to any HTML element:

```html

<button data-analytics-category="download" data-analytics-action="click" data-analytics-label="windows">
    Download for Windows
</button>

<form data-analytics-category="form" data-analytics-action="submit" data-analytics-label="contact-form">
    ...
</form>
```

3. Or call the function directly from JavaScript:

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
│   │       └── seed_analytics.py
│   ├── middleware.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   ├── 0002_analyticssettings.py
│   │   ├── 0003_dailysitestats_bounces_dailysitestats_total_sessions_and_more.py
│   │   ├── 0004_pageview_city_pageview_country_code_and_more.py
│   │   ├── 0005_analyticsevent.py
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
│   │       │   ├── ui
│   │       │   │   ├── icon-bar-chart.svg
│   │       │   │   ├── icon-cpu.svg
│   │       │   │   ├── icon-download.svg
│   │       │   │   └── icon-overview.svg
│   │       │   └── ui-multi
│   │       │       └── icon-setting.svg
│   │       ├── scripts
│   │       │   ├── analytics-events.js
│   │       │   ├── api.js
│   │       │   ├── billing-chart.js
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
│   │       │   ├── sidebar.js
│   │       │   ├── theme-manager.js
│   │       │   └── topojson.v1.min.js
│   │       └── styles
│   │           ├── base.css
│   │           ├── components
│   │           │   ├── charts.css
│   │           │   ├── export-btn.css
│   │           │   ├── filter-bar.css
│   │           │   ├── icon.css
│   │           │   ├── menu.css
│   │           │   ├── settings-form.css
│   │           │   ├── sidebar.css
│   │           │   ├── stat-cards.css
│   │           │   ├── tables.css
│   │           │   ├── topbar.css
│   │           │   └── typography.css
│   │           ├── layout.css
│   │           ├── themes.css
│   │           └── tokens.css
│   ├── templates
│   │   └── analytics
│   │       ├── api.html
│   │       ├── base.html
│   │       ├── billing.html
│   │       ├── dashboard.html
│   │       ├── events.html
│   │       ├── geography.html
│   │       ├── includes
│   │       │   └── filter_bar.html
│   │       ├── page_detail.html
│   │       ├── pages.html
│   │       ├── realtime.html
│   │       ├── settings.html
│   │       └── traffic.html
│   ├── templatetags
│   │   ├── analytics_tags.py
│   │   └── __init__.py
│   ├── tests.py
│   ├── urls.py
│   └── views
│       ├── api.py
│       ├── billing.py
│       ├── dashboard.py
│       ├── events.py
│       ├── export.py
│       ├── geography.py
│       ├── __init__.py
│       ├── page_detail.py
│       ├── pages.py
│       ├── realtime.py
│       ├── settings.py
│       ├── traffic.py
│       └── utils.py
├── .gitignore
├── .gitattributes
├── setup.cfg
├── MANIFEST.in
├── README.md
└── LICENSE
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

Built entirely by **Parsa Zaydany** — solo, offline, during difficult circumstances.

The world map database is only 60MB.  
Downloading it took **over four hours** over an unreliable connection.  

Pushing this first release to GitHub required buying a small amount of bandwidth —  
a purchase that came from savings I had set aside over two years for my main project.  
For someone in my situation, even this single push was expensive.

But developers exist because we help each other.  
Every language we use, every framework, every open‑source package —  
someone built it and shared it. This is my contribution back.

When my situation improves in the coming months, big things are on the road.

If this package helps your project, consider:

- Giving it a star on GitHub
- Sharing it with the Django community
- Contributing a translation or feature

Thank you for using **django‑zaydany‑analytics**.