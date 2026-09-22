# paxalia-dashboard

![PyPI Version](https://img.shields.io/pypi/v/paxalia-dashboard.svg)
![Python](https://img.shields.io/pypi/pyversions/paxalia-dashboard.svg)
![Django](https://img.shields.io/badge/django-5.0%2B%20%7C%206.0%2B-green.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A **privacy-first, self-hosted analytics, observability, security, and administration platform for Django**,
from [Paxalia](https://paxalia.com).

`paxalia-dashboard` brings product analytics, runtime/server visibility, security monitoring, persistent structured
logging, release context, reporting, data utilities, and a full Django-native administrative workspace into one package
that runs inside your own Django application.

There is no required third-party analytics SaaS, tracking pixel, hosted collector, or cloud dashboard.

Optional integrations such as billing models, Celery, Slack, Discord, email delivery, or webhooks are enabled only when
your host project configures them.

---

## Table of Contents

- [Why paxalia-dashboard?](#why-paxalia-dashboard)
- [Comparison at a glance](#comparison-at-a-glance)
- [The real value: features you notice later](#the-real-value-features-you-notice-later)
- [What Paxalia Dashboard is — and is not](#what-paxalia-dashboard-is--and-is-not)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Middleware Integration](#middleware-integration)
- [Dashboard Pages](#dashboard-pages)
- [Custom Event Tracking](#custom-event-tracking)
- [Real User Monitoring](#real-user-monitoring)
- [Uptime Monitoring](#uptime-monitoring)
- [Compliance](#compliance)
- [Data Import](#data-import)
- [Slack/Discord App](#slackdiscord-app)
- [Admin Overview](#admin-overview)
- [Server Monitoring](#server-monitoring)
- [Bot Traffic](#bot-traffic)
- [Backup Management](#backup-management)
- [Internationalization](#internationalization)
- [Themes](#themes)
- [Exporting Data](#exporting-data)
- [Billing Integration](#billing-integration)
- [Security Center](#security-center)
- [Advanced Analytics](#advanced-analytics)
- [Reporting & Sharing](#reporting--sharing)
- [Paxalia API](#paxalia-api)
- [Dependency Health](#dependency-health)
- [Notifications & Alerts](#notifications--alerts)
- [Multi-Site Analytics](#multi-site-analytics)
- [Release Center](#release-center)
- [Paxalia Logging / Observability](#paxalia-logging--observability)
- [Paxalia Admin & Packages](#paxalia-admin--packages)
- [Paxalia Package Format](#paxalia-package-format)
- [Operational Commands](#operational-commands)
- [Security & Privacy Model](#security--privacy-model)
- [Architecture & Extensibility](#architecture--extensibility)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Ideas for contribution](#ideas-for-contribution)
- [License](#license)
- [Credits](#credits)

---

## Why paxalia-dashboard

`paxalia-dashboard` is a **Django-native operational intelligence and administration layer** for real applications.

It started from the practical need to understand what an application is doing, but a real product eventually needs much
more
than page-view analytics. It needs a way to observe behavior, investigate failures, understand infrastructure, review
security,
administer application data, move structured data between environments, and keep important operational context close to
the
application itself.

Paxalia Dashboard brings those concerns together inside the Django project that owns the data.

The platform combines:

- product and traffic analytics
- behavioral analytics
- bot and crawler classification
- real user monitoring
- JavaScript error visibility
- server/runtime monitoring
- slow-query and queue visibility
- uptime checks and incident history
- release and deployment context
- security monitoring
- persistent structured logging
- reporting and protected sharing
- API access and scoped keys
- backup utilities
- historical data import
- multi-site analytics
- compliance controls
- a generic Django-native Admin
- localization-aware administration
- model-aware `.paxalia` package import/export
- operational diagnostics and maintenance commands

The central design goal is:

> **Keep operational data close to the application that produced it, make the data inspectable, and let Django remain
the source of truth.**

That means Paxalia Dashboard is deliberately broad, but it is still a **Django application package**. It is not an
alternative to
Django and it does not attempt to replace Django's core responsibilities.

Your Django application continues to own:

- models and the ORM
- authentication
- permissions
- URL routing
- forms and business rules
- migrations
- database infrastructure
- deployment
- the operating system
- the reverse proxy
- physical backup/disaster-recovery systems

Paxalia adds the operational, analytical, security, administrative, and data-workflow layer around that application.

---

### Comparison at a glance

The following comparison is intentionally broad. Paxalia Dashboard is not just an analytics counter; its scope reaches
from product
measurement and browser telemetry through server operations, security, persistent logging, administration, localization,
and logical
data portability.

This is a directional capability comparison rather than a procurement benchmark. Third-party products vary by product,
edition,
plan, integration, and deployment. `N/A` means the capability is outside the primary purpose of that category. `Varies`
means
support depends substantially on the specific product or deployment.

| Area             | Capability                                       | Google Analytics | Typical lightweight Django analytics package | **paxalia-dashboard** |
|------------------|--------------------------------------------------|-----------------:|---------------------------------------------:|----------------------:|
| Foundation       | Self-hosted application                          |                ❌ |                                            ✅ |                     ✅ |
| Foundation       | First-party storage in host infrastructure       |                ❌ |                                            ✅ |                     ✅ |
| Foundation       | Django-native integration                        |                ❌ |                                            ✅ |                     ✅ |
| Foundation       | Required hosted analytics collector              |                ✅ |                                   Usually no |                     ❌ |
| Foundation       | No mandatory analytics SaaS dependency           |                ❌ |                                  Usually yes |                     ✅ |
| Foundation       | Bundled chart assets                             |                ❌ |                                       Varies |                     ✅ |
| Foundation       | Bundled map assets                               |                ❌ |                                         Rare |                     ✅ |
| Foundation       | No public CDN required for core dashboard assets |                ❌ |                                       Varies |                     ✅ |
| Foundation       | Single configurable package surface              |                ❌ |                                       Varies |                     ✅ |
| Foundation       | Host-project configuration namespace             |                ❌ |                                       Varies |                     ✅ |
| Foundation       | Optional external integrations                   |           Varies |                                       Varies |                     ✅ |
| Analytics        | Page views                                       |                ✅ |                                            ✅ |                     ✅ |
| Analytics        | Sessions                                         |                ✅ |                                            ✅ |                     ✅ |
| Analytics        | Session duration                                 |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Bounce-related metrics                           |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Pages per session                                |                ✅ |                                       Varies |                     ✅ |
| Analytics        | One-click date presets                           |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Arbitrary date ranges                            |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Previous-period comparison                       |                ✅ |                                         Rare |                     ✅ |
| Analytics        | Searchable page tables                           |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Paginated page tables                            |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Traffic-source analysis                          |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Referrer analysis                                |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Browser breakdown                                |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Operating-system breakdown                       |                ✅ |                                       Varies |                     ✅ |
| Analytics        | Device breakdown                                 |                ✅ |                                       Varies |                     ✅ |
| Analytics        | API traffic separation                           |           Varies |                                         Rare |                     ✅ |
| Analytics        | API endpoint analytics                           |           Varies |                                         Rare |                     ✅ |
| Analytics        | Status-code distribution                         |           Varies |                                         Rare |                     ✅ |
| Analytics        | Real-time visitor monitoring                     |                ✅ |                                         Rare |                     ✅ |
| Analytics        | Recent activity feed                             |           Varies |                                         Rare |                     ✅ |
| Analytics        | Search-query parameter analysis                  |           Varies |                                         Rare |                     ✅ |
| Geography        | Offline GeoIP database support                   |                ❌ |                                         Rare |                     ✅ |
| Geography        | Country analysis                                 |                ✅ |                                         Rare |                     ✅ |
| Geography        | City analysis                                    |                ✅ |                                         Rare |                     ✅ |
| Geography        | Offline world-map presentation                   |                ❌ |                                         Rare |                     ✅ |
| Geography        | Country-to-city drill-down                       |           Varies |                                         Rare |                     ✅ |
| Behavioral       | Custom event tracking                            |                ✅ |                                       Varies |                     ✅ |
| Behavioral       | Event categories/actions/labels                  |                ✅ |                                       Varies |                     ✅ |
| Behavioral       | Event numeric values                             |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Goal definitions                                 |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Funnel definitions                               |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Funnel drop-off analysis                         |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Reusable behavioral segments                     |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Campaign/UTM analysis                            |                ✅ |                                       Varies |                     ✅ |
| Behavioral       | Campaign-source analysis                         |                ✅ |                                       Varies |                     ✅ |
| Behavioral       | Campaign-medium analysis                         |                ✅ |                                       Varies |                     ✅ |
| Behavioral       | Campaign-name analysis                           |                ✅ |                                       Varies |                     ✅ |
| Behavioral       | Cohort analysis                                  |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Retention analysis                               |                ✅ |                                         Rare |                     ✅ |
| Behavioral       | Chart annotations                                |           Varies |                                         Rare |                     ✅ |
| Behavioral       | Deployment-linked annotations                    |                ❌ |                                         Rare |                     ✅ |
| Web quality      | Broken-link / 404 analysis                       |           Varies |                                         Rare |                     ✅ |
| RUM              | Core Web Vitals                                  |                ✅ |                                         Rare |                     ✅ |
| RUM              | LCP collection                                   |                ✅ |                                         Rare |                     ✅ |
| RUM              | CLS collection                                   |                ✅ |                                         Rare |                     ✅ |
| RUM              | INP collection                                   |                ✅ |                                         Rare |                     ✅ |
| RUM              | 75th-percentile presentation                     |                ✅ |                                         Rare |                     ✅ |
| RUM              | Good/needs-improvement/poor breakdown            |                ✅ |                                         Rare |                     ✅ |
| RUM              | Browser JavaScript error capture                 |                ✅ |                                         Rare |                     ✅ |
| RUM              | `window.onerror` capture                         |           Varies |                                         Rare |                     ✅ |
| RUM              | Unhandled rejection capture                      |           Varies |                                         Rare |                     ✅ |
| RUM              | Browser error deduplication                      |           Varies |                                         Rare |                     ✅ |
| RUM              | Bounded browser error ingestion                  |           Varies |                                         Rare |                     ✅ |
| Uptime           | Scheduled HTTP checks                            |           Varies |                                         Rare |                     ✅ |
| Uptime           | GET monitoring                                   |           Varies |                                         Rare |                     ✅ |
| Uptime           | HEAD monitoring                                  |           Varies |                                         Rare |                     ✅ |
| Uptime           | POST monitoring                                  |           Varies |                                         Rare |                     ✅ |
| Uptime           | Expected status-code validation                  |           Varies |                                         Rare |                     ✅ |
| Uptime           | Configurable timeout                             |           Varies |                                         Rare |                     ✅ |
| Uptime           | Per-monitor intervals                            |           Varies |                                         Rare |                     ✅ |
| Uptime           | Status history                                   |           Varies |                                         Rare |                     ✅ |
| Uptime           | Transition-based incidents                       |           Varies |                                         Rare |                     ✅ |
| Uptime           | Recovery detection                               |           Varies |                                         Rare |                     ✅ |
| Uptime           | Uptime percentage                                |           Varies |                                         Rare |                     ✅ |
| Uptime           | Uptime alert integration                         |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Bot-path classification                          |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Search-engine crawler classification             |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | AI crawler classification                        |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Social-preview classification                    |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | SEO-tool classification                          |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Generic bot classification                       |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Malicious/scanner classification                 |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Dedicated Bot Traffic dashboard                  |           Varies |                                         Rare |                     ✅ |
| Bot intelligence | Historical bot-category backfill                 |           Varies |                                         Rare |                     ✅ |
| Server           | CPU monitoring                                   |                ❌ |                                            ❌ |                     ✅ |
| Server           | Per-core CPU history                             |                ❌ |                                            ❌ |                     ✅ |
| Server           | Load-average monitoring                          |                ❌ |                                            ❌ |                     ✅ |
| Server           | Memory monitoring                                |                ❌ |                                            ❌ |                     ✅ |
| Server           | Swap monitoring                                  |                ❌ |                                            ❌ |                     ✅ |
| Server           | Disk usage                                       |                ❌ |                                            ❌ |                     ✅ |
| Server           | Disk I/O history                                 |                ❌ |                                            ❌ |                     ✅ |
| Server           | Network-interface statistics                     |                ❌ |                                            ❌ |                     ✅ |
| Server           | Network traffic history                          |                ❌ |                                            ❌ |                     ✅ |
| Server           | System-service visibility                        |                ❌ |                                            ❌ |                     ✅ |
| Server           | Process monitoring                               |                ❌ |                                            ❌ |                     ✅ |
| Server           | Slow-query capture                               |                ❌ |                                            ❌ |                     ✅ |
| Server           | Configurable slow-query threshold                |                ❌ |                                            ❌ |                     ✅ |
| Server           | Celery queue visibility                          |                ❌ |                                            ❌ |                     ✅ |
| Server           | Deployment recording                             |                ❌ |                                            ❌ |                     ✅ |
| Server           | Deployment-to-chart correlation                  |                ❌ |                                            ❌ |                     ✅ |
| Security         | Security Center                                  |                ❌ |                                         Rare |                     ✅ |
| Security         | Login activity visibility                        |           Varies |                                         Rare |                     ✅ |
| Security         | Failed-login monitoring                          |           Varies |                                         Rare |                     ✅ |
| Security         | Active-session visibility                        |           Varies |                                         Rare |                     ✅ |
| Security         | Session-revocation visibility                    |           Varies |                                         Rare |                     ✅ |
| Security         | IP blocklist controls                            |                ❌ |                                         Rare |                     ✅ |
| Security         | Optional blocking middleware                     |                ❌ |                                         Rare |                     ✅ |
| Security         | CSP violation reporting                          |                ❌ |                                         Rare |                     ✅ |
| Security         | Security scorecard                               |                ❌ |                                         Rare |                     ✅ |
| Security         | MFA / 2FA integration                            |           Varies |                                         Rare |                     ✅ |
| Security         | Backup-download re-authentication                |                ❌ |                                         Rare |                     ✅ |
| Security         | Failed-login threshold detection                 |           Varies |                                         Rare |                     ✅ |
| Security         | Security email alerts                            |           Varies |                                         Rare |                     ✅ |
| Security         | Security webhook alerts                          |           Varies |                                         Rare |                     ✅ |
| Security         | In-dashboard alert history                       |           Varies |                                         Rare |                     ✅ |
| Security         | Security audit events                            |                ❌ |                                         Rare |                     ✅ |
| Logging          | Persistent structured application logging        |                ❌ |                                         Rare |                     ✅ |
| Logging          | Standard Python logging capture                  |                ❌ |                                         Rare |                     ✅ |
| Logging          | Django logger capture                            |                ❌ |                                         Rare |                     ✅ |
| Logging          | Direct `paxalia.log()` API                       |                ❌ |                                            ❌ |                     ✅ |
| Logging          | Request lifecycle logging                        |                ❌ |                                            ❌ |                     ✅ |
| Logging          | Request ID context                               |                ❌ |                                         Rare |                     ✅ |
| Logging          | Correlation ID context                           |                ❌ |                                         Rare |                     ✅ |
| Logging          | Trace ID context                                 |                ❌ |                                         Rare |                     ✅ |
| Logging          | Session context                                  |                ❌ |                                         Rare |                     ✅ |
| Logging          | User context                                     |                ❌ |                                         Rare |                     ✅ |
| Logging          | Site context                                     |                ❌ |                                         Rare |                     ✅ |
| Logging          | Traffic context                                  |                ❌ |                                         Rare |                     ✅ |
| Logging          | Browser-error integration                        |                ❌ |                                         Rare |                     ✅ |
| Logging          | Exception-type storage                           |                ❌ |                                         Rare |                     ✅ |
| Logging          | Stack-trace storage                              |                ❌ |                                         Rare |                     ✅ |
| Logging          | Stable event fingerprints                        |                ❌ |                                         Rare |                     ✅ |
| Logging          | Event grouping                                   |                ❌ |                                         Rare |                     ✅ |
| Logging          | Occurrence counting                              |                ❌ |                                         Rare |                     ✅ |
| Logging          | Suppression counting                             |                ❌ |                                         Rare |                     ✅ |
| Logging          | Representative samples                           |                ❌ |                                         Rare |                     ✅ |
| Logging          | Grouping windows                                 |                ❌ |                                         Rare |                     ✅ |
| Logging          | Handler-topology deduplication                   |                ❌ |                                         Rare |                     ✅ |
| Logging          | Configurable sensitive-key redaction             |                ❌ |                                         Rare |                     ✅ |
| Logging          | Bounded log-message sizes                        |                ❌ |                                         Rare |                     ✅ |
| Logging          | Bounded stack sizes                              |                ❌ |                                         Rare |                     ✅ |
| Logging          | Bounded structured metadata                      |                ❌ |                                         Rare |                     ✅ |
| Logging          | Bounded browser event rate                       |                ❌ |                                         Rare |                     ✅ |
| Logging          | Category-specific retention                      |                ❌ |                                         Rare |                     ✅ |
| Logging          | Request-less/background logging                  |                ❌ |                                         Rare |                     ✅ |
| Logging          | Detailed incident investigation                  |                ❌ |                                         Rare |                     ✅ |
| Logging          | Related-event discovery                          |                ❌ |                                         Rare |                     ✅ |
| Logging          | Sanitized “Copy for AI” context                  |                ❌ |                                         Rare |                     ✅ |
| Administration   | Generic Django-native Admin workspace            |                ❌ |                                       Varies |                     ✅ |
| Administration   | Django Admin registry as source of truth         |                ❌ |                                         Rare |                     ✅ |
| Administration   | Application grouping                             |                ❌ |                                         Rare |                     ✅ |
| Administration   | Dynamic model discovery                          |                ❌ |                                       Varies |                     ✅ |
| Administration   | Capability discovery                             |                ❌ |                                         Rare |                     ✅ |
| Administration   | Searchable model catalog                         |                ❌ |                                         Rare |                     ✅ |
| Administration   | Application collapse/expand                      |                ❌ |                                         Rare |                     ✅ |
| Administration   | Metadata-aware model search                      |                ❌ |                                         Rare |                     ✅ |
| Administration   | `list_display` compatibility                     |                ❌ |                                       Varies |                     ✅ |
| Administration   | Search compatibility                             |                ❌ |                                       Varies |                     ✅ |
| Administration   | Filter compatibility                             |                ❌ |                                       Varies |                     ✅ |
| Administration   | Ordering compatibility                           |                ❌ |                                       Varies |                     ✅ |
| Administration   | Pagination                                       |                ❌ |                                       Varies |                     ✅ |
| Administration   | Date hierarchy support                           |                ❌ |                                         Rare |                     ✅ |
| Administration   | `list_editable` compatibility                    |                ❌ |                                         Rare |                     ✅ |
| Administration   | Query-state preservation                         |                ❌ |                                         Rare |                     ✅ |
| Administration   | Django ModelForm integration                     |                ❌ |                                       Varies |                     ✅ |
| Administration   | Fieldsets                                        |                ❌ |                                       Varies |                     ✅ |
| Administration   | Read-only fields                                 |                ❌ |                                       Varies |                     ✅ |
| Administration   | Object-level permission hooks                    |                ❌ |                                         Rare |                     ✅ |
| Administration   | Safe create/read/update/delete                   |                ❌ |                                       Varies |                     ✅ |
| Administration   | Deletion preview                                 |                ❌ |                                         Rare |                     ✅ |
| Administration   | Protected/dependent deletion handling            |                ❌ |                                         Rare |                     ✅ |
| Administration   | Safe bulk deletion                               |                ❌ |                                         Rare |                     ✅ |
| Administration   | Django custom actions                            |                ❌ |                                         Rare |                     ✅ |
| Administration   | ForeignKey inspection                            |                ❌ |                                         Rare |                     ✅ |
| Administration   | OneToOne inspection                              |                ❌ |                                         Rare |                     ✅ |
| Administration   | ManyToMany inspection                            |                ❌ |                                         Rare |                     ✅ |
| Administration   | Reverse-relation inspection                      |                ❌ |                                         Rare |                     ✅ |
| Administration   | Self-reference handling                          |                ❌ |                                         Rare |                     ✅ |
| Administration   | `TabularInline` support where representable      |                ❌ |                                         Rare |                     ✅ |
| Administration   | `StackedInline` support where representable      |                ❌ |                                         Rare |                     ✅ |
| Administration   | Model statistics                                 |                ❌ |                                         Rare |                     ✅ |
| Administration   | Choice distributions                             |                ❌ |                                         Rare |                     ✅ |
| Administration   | Created/updated counts where detectable          |                ❌ |                                         Rare |                     ✅ |
| Administration   | History view                                     |                ❌ |                                         Rare |                     ✅ |
| Administration   | Audit context                                    |                ❌ |                                         Rare |                     ✅ |
| Administration   | Sensitive-field masking                          |                ❌ |                                         Rare |                     ✅ |
| Administration   | Django Admin fallback for exotic behavior        |                ❌ |                                          N/A |                     ✅ |
| Localization     | Configured-language discovery                    |                ❌ |                                         Rare |                     ✅ |
| Localization     | Translation-system discovery                     |                ❌ |                                         Rare |                     ✅ |
| Localization     | django-parler-style support                      |                ❌ |                                         Rare |                     ✅ |
| Localization     | Translation completeness                         |                ❌ |                                         Rare |                     ✅ |
| Localization     | Missing-translation inspection                   |                ❌ |                                         Rare |                     ✅ |
| Localization     | Language-aware editing                           |                ❌ |                                         Rare |                     ✅ |
| Localization     | RTL-compatible presentation                      |                ❌ |                                         Rare |                     ✅ |
| Localization     | Translation-aware exports                        |                ❌ |                                         Rare |                     ✅ |
| Localization     | Translation-aware imports                        |                ❌ |                                         Rare |                     ✅ |
| Packages         | Logical `.paxalia` package format                |                ❌ |                                         Rare |                     ✅ |
| Packages         | Versioned package metadata                       |                ❌ |                                         Rare |                     ✅ |
| Packages         | ZIP package container                            |                ❌ |                                         Rare |                     ✅ |
| Packages         | Manifest validation                              |                ❌ |                                         Rare |                     ✅ |
| Packages         | SHA-256 integrity validation                     |                ❌ |                                         Rare |                     ✅ |
| Packages         | Duplicate ZIP-member protection                  |                ❌ |                                         Rare |                     ✅ |
| Packages         | Archive path-traversal protection                |                ❌ |                                         Rare |                     ✅ |
| Packages         | Size/count safety limits                         |                ❌ |                                         Rare |                     ✅ |
| Packages         | Selected-model export                            |                ❌ |                                         Rare |                     ✅ |
| Packages         | Filtered-model export                            |                ❌ |                                         Rare |                     ✅ |
| Packages         | Multi-model export                               |                ❌ |                                         Rare |                     ✅ |
| Packages         | Identity-aware export/import                     |                ❌ |                                         Rare |                     ✅ |
| Packages         | Configurable identity fields                     |                ❌ |                                         Rare |                     ✅ |
| Packages         | ForeignKey preservation                          |                ❌ |                                         Rare |                     ✅ |
| Packages         | OneToOne preservation                            |                ❌ |                                         Rare |                     ✅ |
| Packages         | ManyToMany preservation                          |                ❌ |                                         Rare |                     ✅ |
| Packages         | Self-reference preservation                      |                ❌ |                                         Rare |                     ✅ |
| Packages         | Translation preservation                         |                ❌ |                                         Rare |                     ✅ |
| Packages         | UUID serialization                               |                ❌ |                                         Rare |                     ✅ |
| Packages         | Decimal/date/time serialization                  |                ❌ |                                         Rare |                     ✅ |
| Packages         | File-field logical-path serialization            |                ❌ |                                         Rare |                     ✅ |
| Packages         | Lazy-translation serialization                   |                ❌ |                                         Rare |                     ✅ |
| Packages         | Configurable conflict strategies                 |                ❌ |                                         Rare |                     ✅ |
| Packages         | Import preview                                   |                ❌ |                                         Rare |                     ✅ |
| Packages         | Dry-run import                                   |                ❌ |                                         Rare |                     ✅ |
| Packages         | Atomic import                                    |                ❌ |                                         Rare |                     ✅ |
| Packages         | Partial-success import                           |                ❌ |                                         Rare |                     ✅ |
| Packages         | Structured failure reporting                     |                ❌ |                                         Rare |                     ✅ |
| Packages         | Failed-subset retry packages                     |                ❌ |                                         Rare |                     ✅ |
| Packages         | Protected-model encryption requirements          |                ❌ |                                         Rare |                     ✅ |
| Packages         | Authenticated package encryption                 |                ❌ |                                         Rare |                     ✅ |
| Packages         | Wrong-password handling                          |                ❌ |                                         Rare |                     ✅ |
| Packages         | Tamper detection                                 |                ❌ |                                         Rare |                     ✅ |
| Packages         | Permission-aware package operations              |                ❌ |                                         Rare |                     ✅ |
| Packages         | Package operation auditability                   |                ❌ |                                         Rare |                     ✅ |
| Packages         | CLI package validation                           |                ❌ |                                         Rare |                     ✅ |
| Packages         | CLI package inspection                           |                ❌ |                                         Rare |                     ✅ |
| Operations       | Backup path configuration                        |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Backup storage management                        |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Scheduled backup support                         |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Backup retention                                 |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Background backup creation                       |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Chunked large-file download                      |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Chunked upload workflow                          |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Historical GA aggregate CSV import               |           Varies |                                         Rare |                     ✅ |
| Operations       | Historical Plausible aggregate CSV import        |           Varies |                                         Rare |                     ✅ |
| Operations       | Per-data-type retention                          |           Varies |                                         Rare |                     ✅ |
| Operations       | Visitor-deletion tooling                         |           Varies |                                         Rare |                     ✅ |
| Operations       | Scheduled email reports                          |           Varies |                                         Rare |                     ✅ |
| Operations       | PDF reports                                      |           Varies |                                         Rare |                     ✅ |
| Operations       | Protected dashboard sharing                      |           Varies |                                         Rare |                     ✅ |
| Operations       | Scoped API keys                                  |                ✅ |                                         Rare |                     ✅ |
| Operations       | API documentation surface                        |                ✅ |                                         Rare |                     ✅ |
| Operations       | Slack command surface                            |           Varies |                                         Rare |                     ✅ |
| Operations       | Discord command surface                          |           Varies |                                         Rare |                     ✅ |
| Operations       | Multi-site analytics                             |           Varies |                                         Rare |                     ✅ |
| Operations       | Dependency-closure inspection                    |                ❌ |                                            ❌ |                     ✅ |
| Operations       | Release-artifact context                         |                ❌ |                                         Rare |                     ✅ |
| Operations       | In-dashboard notifications                       |           Varies |                                         Rare |                     ✅ |
| Operations       | Email alert destinations                         |           Varies |                                         Rare |                     ✅ |
| Operations       | Webhook alert destinations                       |           Varies |                                         Rare |                     ✅ |
| Diagnostics      | Dashboard-wide diagnostics                       |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Admin-specific diagnostics                       |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Logging-specific diagnostics                     |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Package inspection CLI                           |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Package validation CLI                           |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Focused Admin test suite                         |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Logging test suite                               |                ❌ |                                         Rare |                     ✅ |
| Diagnostics      | Scheduled maintenance commands                   |                ❌ |                                         Rare |                     ✅ |
| Presentation     | Internationalized UI                             |           Varies |                                         Rare |                     ✅ |
| Presentation     | RTL dashboard support                            |           Varies |                                         Rare |                     ✅ |
| Presentation     | Responsive desktop/tablet/mobile UI              |           Varies |                                       Varies |                     ✅ |
| Presentation     | Theme system                                     |           Varies |                                         Rare |                     ✅ |
| Presentation     | Multiple built-in themes                         |           Varies |                                         Rare |                     ✅ |
| Presentation     | Shared design-token styling                      |                ❌ |                                         Rare |                     ✅ |
| Presentation     | Offline chart/map assets                         |                ❌ |                                         Rare |                     ✅ |

The important difference is not simply the number of checkmarks. It is the **co-location of these capabilities**: the
same Django
application can own the analytics data, runtime context, logs, security signals, administrative workflows, and logical
package
operations without creating another independent operational data plane.

---

### The real value: features you notice later

Not every feature has the same visibility.

Some capabilities are immediately attractive because their value is visible at a glance:

- analytics charts
- real-time visitors
- geography
- RUM
- security scorecards
- server dashboards
- elegant reports

Other capabilities are quieter. They are often the features a team does not think about while building a prototype, but
they can
become unusually important once the application is a real product with real data, real users, real incidents, and real
operational
history.

A useful way to understand Paxalia is:

```text
WHAT ATTRACTS YOU FIRST
        ↓
analytics
RUM
security
server visibility
reports
        ↓
WHAT BECOMES IMPORTANT LATER
        ↓
persistent logging
request correlation
generic administration
permissions
safe CRUD
relationships
localization
package export/import
identity resolution
translation preservation
failure reporting
retry workflows
retention
diagnostics
auditability
```

### The production gap

During early development, a team can often work with:

```text
database
+
Django Admin
+
a few logs
+
a few analytics charts
```

As the product grows, the operational questions become more demanding.

You start needing to know:

```text
What failed?
Where?
For which request?
For which user/session?
Was it one failure or thousands?
Is there a common fingerprint?
Did it begin after a deployment?
Is the problem in the browser, application, API, or server?
What related events happened around it?
```

You also start needing to answer administrative questions:

```text
Which models exist?
Which applications own them?
Which permissions apply?
Which fields are sensitive?
Which records can this administrator change?
Which relationships exist?
Which translations are missing?
Which actions are available?
How can a subset of application data be moved safely?
```

And eventually data portability becomes practical:

```text
Can I export selected models?
Can I preserve relationships?
Can I preserve translations?
Can I resolve identities without blindly restoring primary keys?
Can I preview the result before changing the database?
Can I dry-run it?
Can I choose update/skip behavior?
Can I perform an atomic import?
Can I isolate independent failures?
Can I retry only the failed subset?
Can protected data require encryption?
Can I validate the package before importing it?
```

Those are not always "shining" features.

They are the kind of features that become valuable because the application exists in the first place.

### Why the package is intentionally large

Paxalia Dashboard is large because it covers a wide operational surface **around Django**, not because it tries to
replace Django.

The package is best understood as a set of connected layers:

```text
                 Django application
                        │
       ┌────────────────┼────────────────┐
       │                │                │
       ▼                ▼                ▼
   Analytics         Security         Application
       │                │              operations
       │                │                │
       ├───────┬────────┴───────┬────────┤
       │       │                │        │
       ▼       ▼                ▼        ▼
      RUM    Logging          Admin   Packages
       │       │                │        │
       └───────┴────────────────┴────────┘
                        │
                        ▼
              one Django-native view
```

The point is not that every team needs every feature every day.

The point is that a production product eventually crosses multiple concerns, and Paxalia provides a coherent place to
handle
those concerns without forcing each one into a completely separate system.

### A deliberate balance

Paxalia Dashboard therefore has two kinds of value:

```text
VISIBLE VALUE
    dashboards
    analytics
    RUM
    security
    reports

QUIET VALUE
    logs
    context
    admin
    permissions
    portability
    package integrity
    localization
    diagnostics
    retention
    audit
```

The first group may get someone interested.

The second group can be what makes the package difficult to replace once it becomes part of the application's operating
workflow.

That balance is intentional.

---

### What Paxalia Dashboard is — and is not

Paxalia Dashboard is a **large Django application package**, but it does not attempt to become a second Django.

It does not replace:

- Django's ORM
- Django models
- Django authentication
- Django permissions
- Django URL routing
- Django forms
- Django migrations
- Django Admin
- your database
- your reverse proxy
- your operating system
- your deployment system
- your infrastructure
- your physical disaster-recovery strategy

Instead, it integrates with Django's existing architecture.

The administrative data flow is deliberately:

```text
Django Admin registry
        ↓
Paxalia Admin registry/adapter
        ↓
permissions
        ↓
query + services + forms
        ↓
Paxalia Admin views
        ↓
Paxalia UI
```

The generic package workflow is similarly additive:

```text
registered Django models
        ↓
permission-aware selection
        ↓
logical serialization
        ↓
identity / relationships / translations
        ↓
integrity + security
        ↓
.paxalia package
```

And the logging workflow is another layer around normal application execution:

```text
Python / Django logging
        +
paxalia.log()
        ↓
normalization
        ↓
request/runtime context
        ↓
redaction
        ↓
fingerprint/grouping
        ↓
persistent observability
```

Django remains the authority.

Paxalia supplies additional operational intelligence around it.

---

### Paxalia Dashboard and the wider Paxalia ecosystem

`paxalia-dashboard` is the open-source Django-focused project in the broader Paxalia product ecosystem.

The main Paxalia application is a much larger systemizing app built around Workspaces and connected systems for
organizing
work, time, goals, information, visual thinking, collaboration, portability, synchronization, and offline continuity.

The relationship is best understood as:

```text
Paxalia
    ↓
systemize
connect
organize
operate
    ↓
Paxalia Dashboard
    ↓
help Django applications
observe
understand
protect
administer
and move their application data
```

The dashboard is useful independently. It does not require the main Paxalia application to run.

At the same time, it shares the broader Paxalia philosophy of building systems that become more useful when the parts
connect.

Paxalia is still evolving, and the dashboard is intended as a strong foundation rather than a claim that the ecosystem
has reached its final
form. Future releases can add deeper integrations, more automation, more intelligent operational tooling, and other
capabilities as
the product and its community grow.

---

## Features

Paxalia is intentionally a platform rather than a single dashboard widget. Features are modular: a host project can use
the
analytics layer, observability layer, security layer, Admin layer, package workflows, or operational utilities according
to its
needs.

### Analytics

- **Page Views & Sessions** — page visits, sessions, duration, bounce-related metrics, and pages-per-session reporting.
- **Traffic Sources** — referrers, browsers, operating systems, devices, and source breakdowns.
- **Date Range Analysis** — reusable presets plus explicit start/end ranges.
- **Period Comparison** — compare the selected period with its corresponding previous period.
- **Interactive Tables** — searchable, paginated operational tables with CSV/JSON export where supported.
- **API Traffic Analytics** — separate API activity from normal page traffic using configurable rules.
- **Real-Time Monitoring** — live visitor and recent-request views with configurable refresh intervals.
- **Geography** — offline GeoIP-backed country and city analysis with a bundled map asset workflow.

### Behavioral analytics

- **Custom Events** — track product interactions such as clicks, form submissions, video engagement, and downloads.
- **Goals** — define conversion targets and measure completion behavior.
- **Funnels** — inspect multi-step conversion paths and drop-off.
- **Segments** — build reusable behavioral audience definitions.
- **Campaign / UTM Analytics** — compare campaign source, medium, and campaign performance.
- **Cohorts** — analyze return/retention behavior across visitor cohorts.
- **Annotations** — connect important operational dates such as deployments, incidents, or launches to analytics charts.
- **Broken Links** — identify paths returning 404 responses and inspect their referring context.

### Runtime observability

- **Real User Monitoring** — LCP, CLS, INP and field-performance breakdowns.
- **JavaScript Error Tracking** — browser exceptions and unhandled rejections with bounded ingestion.
- **Uptime Monitoring** — scheduled HTTP checks, status history, and transition-based incidents.
- **Server Monitoring** — CPU, memory, disk, network, services, and processes.
- **Slow Query Monitoring** — opt-in database query timing.
- **Celery Monitoring** — worker/task visibility when the host Celery application is configured.
- **Deployment Tracking** — release/deployment records connected to chart annotations.
- **Persistent Logs** — application and request observability in the same operational dashboard.

### Security

- **Security Center** — authentication activity, active sessions, IP blocklists, security events, and posture.
- **Security Scorecard** — security configuration findings in one operational view.
- **CSP Violation Reporting** — application-level visibility into browser policy violations.
- **MFA / 2FA Integration** — dashboard visibility and enrollment support where the host project provides compatible
  MFA.
- **Backup Re-authentication** — recent authentication can be required before sensitive backup downloads.
- **Sensitive Data Redaction** — common credential and secret fields are sanitized before persistent
  presentation/storage where the package policy applies.
- **Auditability** — privileged dashboard/admin/package operations can be connected to the existing audit/security
  architecture.

### Administration and data portability

- **Generic Paxalia Admin** — a Django-native model administration layer.
- **Model Search and Discovery** — searchable application/model catalog with collapse/expand behavior.
- **Django Permission Reuse** — registered `ModelAdmin` permission hooks remain authoritative.
- **CRUD and Actions** — normal administrative workflows without host-model hard-coding.
- **Relationships and Inlines** — inspect and manage supported Django relationship structures.
- **Localization Workspace** — discover and edit supported translation systems using configured project languages.
- **Package Center** — model-aware `.paxalia` import/export.
- **Package Validation** — structural and integrity validation before package mutation.
- **Encrypted Packages** — authenticated encryption for protected/sensitive package flows.
- **Retry Packages** — retry failed subsets without reconstructing them manually.

### Operations and utilities

- **Backup Management** — configurable paths, storage, retention, scheduled backups, and chunked transfer.
- **Historical Data Import** — GA/Plausible aggregate CSV import without vendor OAuth credentials.
- **Reporting** — scheduled email/PDF reports where configured.
- **Protected Sharing** — read-only sharing for selected dashboard views.
- **Scoped API Keys** — explicit read/ingestion scopes instead of an all-purpose secret.
- **Dependency Health** — inspect runtime dependency state and progressively compare installed versions with available
  releases.
- **Notifications & Alerts** — in-dashboard history plus optional email/webhook delivery.
- **Multi-Site Analytics** — multiple configured domains represented through `Site` records.
- **Release Center** — release artifacts and deployment context.

### Localization and presentation

- **Internationalization** — bundled dashboard translations for five languages in the package distribution.
- **RTL** — Arabic support and direction-aware dashboard behavior.
- **Themes** — twelve built-in themes using shared design tokens.
- **Responsive UI** — desktop, tablet, and mobile layouts.
- **Offline Assets** — charts, maps, and fonts do not require a public CDN at runtime.

---

## Tech Stack

The package is intentionally substantial because it covers several application-lifecycle concerns around Django. The
dependency
footprint remains focused on Django and the subsystems this dashboard actually provides; optional integrations are not
required
unless the host project enables them.

| Component                  | Technology                                                                    |
|----------------------------|-------------------------------------------------------------------------------|
| Backend                    | Django 5.0+ / Django 6.0 compatible                                           |
| Python                     | Python 3.10+                                                                  |
| Database                   | Any Django-supported database; PostgreSQL is a supported production target    |
| Charts                     | Chart.js, bundled                                                             |
| World Map                  | Datamaps + D3.js + TopoJSON, bundled                                          |
| GeoIP                      | MaxMind GeoLite2-City + `geoip2`                                              |
| User-Agent Parsing         | `user-agents`                                                                 |
| Country Codes              | `pycountry`                                                                   |
| Server Metrics             | `psutil`                                                                      |
| Package Encryption         | `cryptography`                                                                |
| Administrative Integration | `django.contrib.admin` / `ModelAdmin`                                         |
| Authentication boundaries  | Django authentication, staff permissions, and existing host security controls |

The current package metadata declares Python `>=3.10`, Django `>=5.0`, and includes Django 5.0 and Django 6.0
classifiers. fileciteturn29file2L1-L34

---

## Installation

### 1. Install the package

```bash
pip install paxalia-dashboard
```

For local development:

```bash
pip install -e .
```

### 2. Add `paxalia` to `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    # ...
    "paxalia",
]
```

### 3. Include the dashboard URLs

The dashboard is designed to live under a private path chosen by the host project.

A minimal installation can mount:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("insights/", include("paxalia.urls")),
]
```

In a hardened production installation, many projects also mount Django Admin itself under a separate secret path.

For example:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("insights/", include("paxalia.urls")),
    path("private-admin/", admin.site.urls),
]
```

The exact dashboard/admin paths are host-project decisions.

### 4. Add the analytics middleware

```python
MIDDLEWARE = [
    # Django/security/session middleware ...
    "paxalia.middleware.AnalyticsMiddleware",
]
```

`AnalyticsMiddleware` resolves sites, classifies requests, records page-view/session information, and feeds the
analytics subsystem.

### 5. Run migrations

```bash
python manage.py migrate paxalia
```

The platform includes a deterministic migration chain for the analytics, security, compliance, operations, reporting,
notification, and observability models.

### 6. Enable strict CSP correctly

The packaged dashboard is designed for CSP-safe script delivery.

A host project using a strict CSP should expose the existing Paxalia analytics configuration context processor and the
CSP nonce context processor:

```python
TEMPLATES = [
    {
        "OPTIONS": {
            "context_processors": [
                # ...
                "paxalia.context_processors.analytics_config",
                "csp.context_processors.nonce",
            ],
        },
    },
]
```

When using `django-csp`, configure its middleware and nonce policy according to the version installed by the host
project.

Example:

```python
from csp.constants import NONCE

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "script-src": (
            "'self'",
            NONCE,
            "'strict-dynamic'",
        ),
    }
}
```

Do not weaken your CSP merely to make Paxalia run.

### 7. Compile translations

```bash
python manage.py compilemessages -l es -l ar -l zh-hans -l pt-br
```

Use the actual language codes present in the host deployment.

### 8. Install the GeoIP database

The GeoIP database is intentionally not bundled into the repository because of its size.

Download GeoLite2-City from MaxMind and point `GEOIP_PATH` at the `.mmdb` file:

```python
PAXALIA_DASHBOARD = {
    "GEOIP_PATH": "/srv/paxalia/GeoLite2-City.mmdb",
}
```

The geography page can otherwise present an empty/limited state rather than fabricating location data.

### 9. Start the server

```bash
python manage.py runserver
```

Open the dashboard at the path you configured, for example:

```text
http://127.0.0.1:8000/insights/
```

---

## Configuration

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

## Dashboard Pages

| Page                | URL                     | Purpose                                                               |
|---------------------|-------------------------|-----------------------------------------------------------------------|
| Overview            | `/`                     | Core traffic summary, trends, top pages, API activity, and comparison |
| Pages               | `/pages/`               | Tracked paths, search, pagination, and page-level drill-down          |
| Page Detail         | `/pages/…/`             | Detailed historical traffic for an individual path                    |
| API                 | `/api/`                 | API traffic, endpoint activity, and status-code distribution          |
| Traffic             | `/traffic/`             | Referrers, browsers, operating systems, and device types              |
| Geography           | `/geography/`           | Offline world map, countries, and cities                              |
| Events              | `/events/`              | Custom events and event breakdowns                                    |
| Real-time           | `/realtime/`            | Current live visitor activity                                         |
| RUM                 | `/rum/`                 | Core Web Vitals and browser errors                                    |
| Uptime              | `/uptime/`              | Monitors, uptime history, and incidents                               |
| Compliance          | `/compliance/`          | Consent, retention, and visitor-deletion controls                     |
| Data Import         | `/import/`              | Historical aggregate CSV import                                       |
| Billing             | `/billing/`             | Optional billing and revenue integration                              |
| Server Overview     | `/server/overview/`     | CPU, memory, disk, network and host health                            |
| Server CPU          | `/server/cpu/`          | CPU detail and history                                                |
| Server Memory       | `/server/memory/`       | RAM and swap                                                          |
| Server Disk         | `/server/disk/`         | Storage and I/O                                                       |
| Server Network      | `/server/network/`      | Interface traffic and network statistics                              |
| Server Services     | `/server/services/`     | Running system services                                               |
| Server Processes    | `/server/processes/`    | Active process information                                            |
| Server Slow Queries | `/server/slow-queries/` | Queries crossing the configured latency threshold                     |
| Server Queues       | `/server/queues/`       | Celery state where configured                                         |
| Server Deployments  | `/server/deployments/`  | Deployment history and chart context                                  |
| Security            | `/security/`            | Application security posture and security events                      |
| Admin Overview      | `/admin-overview/`      | High-level user/content/login activity                                |
| Bot Traffic         | `/bots/`                | Bot volume, categories, paths and geography                           |
| Backups             | `/backups/`             | Backup configuration, creation and downloads                          |
| Reports             | `/reports/`             | Scheduled reporting                                                   |
| Share Links         | `/share-links/`         | Protected read-only sharing                                           |
| Notifications       | `/notifications/`       | Dashboard notifications and alerts                                    |
| Sites               | `/sites/`               | Multi-site configuration                                              |
| Dependencies        | `/dependencies/`        | Runtime dependency health                                             |
| Settings            | `/settings/`            | Dashboard preferences and operational settings                        |
| Logs                | `/logs/`                | Canonical persistent Paxalia Logs dashboard                           |
| Application Logs    | `/application-logs/`    | Application-oriented log view                                         |
| Login Activity      | `/login-activity/`      | Authentication/login observability                                    |
| Log Detail          | `/logs/<id>/`           | Full structured event investigation                                   |
| Paxalia Admin       | `/admin/.../`           | Generic Django-native Admin under the dashboard's protected mount     |

Exact route prefixes depend on the host project's dashboard mounting configuration.

### Cross-dashboard behavior

Where supported:

- date ranges are shared through the standard dashboard filtering language
- common presets include Today, Yesterday, Last 7 days, Last 30 days, and current month
- charts provide previous-period comparison
- tables provide export actions
- responsive layouts adapt to desktop, tablet, and mobile
- Arabic layouts operate in RTL

---

## Custom Event Tracking

Track product interactions without adding another analytics provider.

### Quick start

Use the bundled event script:

```html

<script src="{% static 'paxalia/scripts/analytics-events.js' %}"></script>
```

The host project should ensure the script receives the appropriate CSP nonce when a strict CSP requires one.

### Data attributes

```html

<button
        data-analytics-category="download"
        data-analytics-action="click"
        data-analytics-label="windows">
    Download for Windows
</button>
```

Forms can use the same mechanism:

```html

<form
        data-analytics-category="form"
        data-analytics-action="submit"
        data-analytics-label="contact-form">
    ...
</form>
```

### JavaScript API

```javascript
window.opAnalytics(
    "video",
    "play",
    "intro-tutorial",
    1
);
```

### Event fields

| Field      | Required | Description                                           |
|------------|----------|-------------------------------------------------------|
| `category` | Yes      | Broad grouping such as `button`, `video`, or `form`   |
| `action`   | Yes      | Event action such as `click`, `play`, or `submit`     |
| `label`    | No       | Additional event context                              |
| `value`    | No       | Optional numeric value                                |
| `path`     | No       | Page path, normally derived from the browser location |

---

## Real User Monitoring

RUM is integrated into the existing browser event system.

### Web Vitals

Paxalia collects:

- **LCP** — Largest Contentful Paint
- **CLS** — Cumulative Layout Shift
- **INP** — Interaction to Next Paint

The dashboard presents field-data summaries and percentile-oriented reporting instead of pretending these measurements
are laboratory benchmarks.

### JavaScript errors

Browser-side errors are collected through:

- `window.onerror`
- `unhandledrejection`

The client limits event volume and deduplicates repeated failures to avoid runaway error loops.

Captured data can include:

- message
- filename
- line/column
- stack
- page context

### Storage

Web Vitals reuse the existing event model.

JavaScript errors use the dedicated `JSError` model because useful browser failure diagnostics need more room and
structure than the generic event label field.

### RUM caveats

RUM represents real visitor environments.

It varies with:

- device
- network
- browser
- workload
- application architecture

INP is captured using the package's supported browser-side measurement approach and should be interpreted as field
telemetry rather than a promise of full laboratory conformance for every application architecture.

---

## Uptime Monitoring

Uptime monitoring performs scheduled HTTP checks against configured endpoints.

### Monitor configuration

A monitor can specify:

- name
- URL
- HTTP method
- expected status code
- timeout
- check interval

### Scheduling

Run the check command from cron or Celery beat.

Example:

```cron
* * * * * cd /path/to/project && python manage.py check_uptime >> /var/log/paxalia-uptime.log 2>&1
```

### Incident model

Incidents are transition-based.

A continuously failing service is represented as one incident rather than one incident row per check.

A recovery closes the incident.

### Alerts

Uptime transitions reuse the package's alert/notification infrastructure and can optionally produce dashboard
notifications plus configured email/webhook delivery.

A period with zero checks is represented as an empty/unknown state rather than falsely reported as 0% or 100%.

---

## Compliance

Paxalia's compliance tooling is application-level and intentionally separate from a legal compliance certification.

### Consent mode

Consent mode is disabled by default.

To require consent:

```python
PAXALIA_DASHBOARD = {
    "CONSENT_MODE_ENABLED": True,
    "CONSENT_COOKIE_NAME": "analytics_consent",
    "CONSENT_COOKIE_GRANTED_VALUE": "granted",
}
```

The host project's consent banner/CMP remains responsible for obtaining consent and setting the cookie.

The server-side gate is authoritative.

Without the required consent:

- page-view tracking is skipped
- anonymous session state is not created
- event endpoints can return a skipped response
- client tracking becomes a no-op

### Data retention

Retention is configurable by data type:

```python
PAXALIA_DASHBOARD = {
    "DATA_RETENTION_DAYS": {
        "pageview": 400,
        "analytics_event": 400,
        "js_error": 90,
        "uptime_check": 90,
        "slow_query": 30,
    },
}
```

Nothing is pruned unless you explicitly configure a retention policy.

### Forget this visitor

The compliance surface can delete stored analytics rows associated with a visitor identifier.

Because different observability models contain different identifiers, not every subsystem can necessarily be matched by
every identifier type.

The current implementation documents those limitations rather than pretending a deletion request reached data that
cannot be identified through the same field.

### Privacy principle

Deletion is recorded as an audit action without reintroducing the exact raw identifier into the audit trail.

---

## Data Import

Historical aggregate imports are supported for Google Analytics and Plausible CSV exports.

### Why CSV

Paxalia deliberately avoids requiring:

- Google OAuth credentials
- vendor API clients
- vendor-specific long-lived secrets

A CSV export is already an artifact under the site's control.

### Supported scope

The historical importer is designed for **daily aggregate statistics**.

It does not attempt to reconstruct individual page-view rows from aggregate exports.

### Common metric mapping

| External column   | Paxalia field                                                   |
|-------------------|-----------------------------------------------------------------|
| views / pageviews | `total_views`                                                   |
| visitors / users  | closest supported unique-visitor field                          |
| sessions          | `total_sessions`                                                |
| bounce rate       | derived bounce count where both rate and sessions are available |

Metrics that cannot be derived safely remain empty/zero rather than being fabricated.

### Existing dates

Existing daily rows are skipped by default so a historical import does not silently overwrite live analytics.

An explicit overwrite mode is available for deployments that intentionally want replacement behavior.

---

## Slack/Discord App

Paxalia supports both outgoing alert delivery and signed incoming command surfaces.

### Slack

Configure:

```python
PAXALIA_DASHBOARD = {
    "SLACK_SIGNING_SECRET": "your-secret",
}
```

The Slack endpoint verifies request signatures with HMAC-SHA256.

### Discord

Configure:

```python
PAXALIA_DASHBOARD = {
    "DISCORD_PUBLIC_KEY": "your-public-key",
}
```

Discord signature verification requires a compatible Ed25519 implementation; PyNaCl can be installed when that feature
is required.

### Scope

The command surface reuses the same high-level analytics snapshot logic used by reporting and sharing.

Typical periods include:

- today
- yesterday
- this week
- this month

The command response is deliberately plain text so it behaves consistently across supported chat platforms.

---

## Admin Overview

The existing Admin Overview gives administrators a high-level summary of application activity.

It includes:

- total users
- recent registrations
- active-user-oriented metrics
- content totals
- content creation history
- login activity
- recent administrative/security context where available

This is intentionally different from Paxalia Admin.

```text
Admin Overview
    = operational summary

Paxalia Admin
    = generic model administration
```

---

## Server Monitoring

Server monitoring reads metrics directly from the host using `psutil`.

No external monitoring agent is required.

### Available views

- Overview
- CPU
- Memory
- Disk
- Network
- Services
- Processes
- Slow Queries
- Queues
- Deployments

### History snapshots

Historical server charts are backed by persisted `ServerMetricSnapshot` data.

Schedule:

```cron
* * * * * cd /path/to/project && python manage.py record_server_metrics >> /var/log/paxalia-server.log 2>&1
```

The command also prunes data older than `SERVER_METRIC_RETENTION_DAYS`.

If no snapshots have been collected, the dashboard displays an empty state instead of synthetic values.

### Slow queries

Enable:

```python
MIDDLEWARE = [
    # ...
    "paxalia.middleware.SlowQueryMiddleware",
]
```

Then configure:

```python
PAXALIA_DASHBOARD = {
    "SLOW_QUERY_THRESHOLD_MS": 100,
}
```

The middleware uses Django's query execution instrumentation and guards its own persistence from recursive capture.

### Celery queues

Configure:

```python
PAXALIA_DASHBOARD = {
    "CELERY_APP_PATH": "myproject.celery.app",
}
```

Celery remains optional.

If it is not installed or not configured, the queue view returns an empty state rather than failing the dashboard.

### Deployments

After deployment:

```bash
python manage.py record_deployment \
    --version "$(git rev-parse --short HEAD)" \
    --notes "Deploy from main"
```

A deployment record is stored and linked to a chart annotation.

---

## Bot Traffic

Paxalia separates crawler/scanner traffic from normal analytics.

### Path classification

You can configure known bot/scanner paths such as:

```text
/robots.txt
/.env
/wp-admin/
/xmlrpc.php
```

A path match can classify a request as malicious/bot traffic.

### User-Agent classification

The classifier also recognizes categories such as:

- search engines
- AI crawlers
- social preview bots
- SEO tools
- generic bot-like clients
- malicious/scanner traffic

### Important limitation

User-Agent strings are claims made by the client.

Paxalia does not perform live crawler-IP verification.

A client that spoofs a legitimate crawler User-Agent can therefore be misclassified when visiting an ordinary page.

Attack-probe paths can still override those claims because a request for a known malicious path is meaningful evidence
of scanner activity regardless of the reported User-Agent.

### Backfilling existing traffic

When bot classification rules change, existing `PageView` rows are not silently rewritten.

Run:

```bash
python manage.py backfill_pageview_bot_category --dry-run
```

Then run the command without `--dry-run` when the results are understood.

### Importing large path lists

```bash
python manage.py import_bot_paths /path/to/bot_paths.txt
```

Use `--replace` when you intentionally want to replace the configured list rather than merge it.

---

## Backup Management

Backup Management is a **physical/system backup facility** and should not be confused with `.paxalia` logical packages.

### Features

- configurable source paths
- configurable storage directory
- scheduled backups
- retention settings
- on-demand creation
- background processing
- chunked large-file download
- archive status
- restore/delete workflows where supported
- recent-authentication checks for sensitive downloads

### Re-authentication

The host can require recent staff authentication before a backup download:

```python
PAXALIA_DASHBOARD = {
    "BACKUP_REAUTH_MINUTES": 15,
}
```

This check is applied to every download request.

### Scheduled backups

Example:

```cron
0 2 * * * cd /path/to/project && python manage.py create_backup >> /var/log/paxalia-backup.log 2>&1
```

Backup policy remains a deployment responsibility.

---

## Internationalization

The current distribution includes translations for:

| Language             | Code      | RTL |
|----------------------|-----------|-----|
| English              | `en`      | No  |
| Spanish              | `es`      | No  |
| Arabic               | `ar`      | Yes |
| Simplified Chinese   | `zh-hans` | No  |
| Brazilian Portuguese | `pt-br`   | No  |

Arabic uses RTL layout direction.

The language system is based on Django's standard internationalization workflow.

### Adding another language

A normal workflow is:

```bash
mkdir -p paxalia/locale/<code>/LC_MESSAGES
```

Then add/translate the corresponding `.po` file and compile:

```bash
python manage.py compilemessages -l <code>
```

The generic dashboard uses Django translation tags rather than hard-coded per-language template branches.

### Admin localization

Paxalia Admin's model localization workspace is different from the dashboard UI translation catalog.

For model translation data:

- supported languages are discovered from Django configuration
- translation systems are discovered from model metadata
- supported translation APIs are reused
- missing translations are identified
- translations can be edited where the model exposes a supported editing surface
- package import/export can carry multilingual translation data

There is no six-language hard-coded Admin branch.

---

## Themes

The current dashboard ships with twelve themes.

| Theme            | Slug       | Character                   |
|------------------|------------|-----------------------------|
| Dark Gold        | `dark`     | Deep charcoal and warm gold |
| Skybound Silk    | `default`  | Soft light presentation     |
| Golden Dusk      | `golden`   | Cream and gold              |
| Azure Drift      | `azure`    | Cool blue                   |
| Sunlit Meadow    | `sunlit`   | Bright green                |
| Indigo Spectrum  | `indigo`   | Violet night                |
| Arctic Horizon   | `arctic`   | Icy blue                    |
| Ocean Breeze     | `ocean`    | Teal and navy               |
| Twilight Reverie | `twilight` | Deep violet                 |
| Velvet Noir      | `velvet`   | Crimson / dark              |
| Citrine Prestige | `citrine`  | Gold-forward                |
| Onyx Pearl       | `onyx`     | Minimal dark / silver       |

### Theme contract

Themes are applied using the existing:

```html
data-analytics-theme="..."
```

contract and the shared `--analytics-*` token vocabulary.

### Persistence

The selected theme is persisted in browser storage.

### Custom themes

Add a new theme selector to the existing theme stylesheet:

```css
[data-analytics-theme="your-slug"] {
    --analytics-bg: # . . .;
    --analytics-surface: # . . .;
    --analytics-border: # . . .;
    --analytics-text: # . . .;
    --analytics-text-dim: # . . .;
    --analytics-gold: # . . .;
    --analytics-gold-dim: rgba(...);
    --analytics-gold-hover: # . . .;
    --analytics-compare: # . . .;
}
```

Then expose it through the settings theme list.

Do not introduce a second theme system.

---

## Exporting Data

Paxalia provides normal table exports throughout the dashboard.

### CSV

CSV is suitable for:

- Excel
- Google Sheets
- scripts
- operational review

### JSON

JSON is intended for:

- scripts
- integrations
- data inspection
- programmatic use

### Export context

Dashboard exports respect relevant filters such as:

- selected date range
- page/path search
- country selection
- current table/query context

Exports must not be interpreted as unrestricted database dumps.

### Spreadsheet safety

Administrative/logging exports are expected to use safe serialization for values that might otherwise be interpreted as
spreadsheet formulas.

---

## Billing Integration

Billing is intentionally model-configurable.

Paxalia does not own or replace your billing system.

### Configuration

```python
PAXALIA_DASHBOARD = {
    "BILLING_INVOICE_MODEL": "billing.BillingInvoice",
    "BILLING_USER_PLAN_MODEL": "billing.UserBilling",
    "BILLING_DONATION_MODEL": "billing.Donation",
}
```

### Dashboard capabilities

Where the host project exposes compatible models, the Billing page can provide:

- total revenue
- recent revenue
- active subscriptions/plans
- donation information
- plan breakdowns
- daily income
- MRR/ARR-oriented reporting
- churn/failed-payment context where the host model exposes it

The integration is intentionally generic rather than hard-coded to a single billing application.

---

## Security Center

Security Center brings application-facing security visibility into the same operational environment as analytics.

### Login activity

The security layer can surface:

- successful logins
- failed login patterns
- staff/privileged activity
- login locations where available
- authentication context
- related security events

### Active sessions

Where the host authentication/session model provides the required data, administrators can inspect active sessions and
revoke them through the appropriate workflow.

### IP blocklist

Security Center can maintain blocked IPs.

When `SecurityBlockMiddleware` is enabled, requests from blocked addresses can be denied before analytics recording.

### Brute-force alerting

Configure:

```python
PAXALIA_DASHBOARD = {
    "SECURITY_FAILED_LOGIN_THRESHOLD": 5,
    "SECURITY_FAILED_LOGIN_WINDOW_MINUTES": 15,
}
```

Crossing the configured threshold can generate a security alert.

### CSP violation reporting

Browser CSP violations can be fed into the Security Center so policy failures can be investigated alongside application
observability.

### Security scorecard

The Security Scorecard presents configuration/posture findings from the package's supported security checks.

It is a visibility tool, not a replacement for an external security assessment.

### MFA / 2FA

The dashboard integrates with compatible host-project MFA/2FA configuration and can expose enrollment/status workflows
where the host application implements the required support.

### Backup re-authentication

Sensitive backup downloads can require a recent password-authentication timestamp.

---

## Advanced Analytics

### Goals

Goals represent target behaviors such as:

```text
/signup/
purchase
form:submit
```

and can be used to measure completion.

### Funnels

Funnels describe ordered steps such as:

```text
landing page
    ↓
pricing
    ↓
signup
    ↓
checkout
```

### Segments

Segments provide reusable audience definitions.

They can combine supported behavioral dimensions instead of forcing administrators to reproduce the same filters
manually.

### Campaigns

Campaign analysis works with campaign parameters and provides source/medium/campaign-oriented breakdowns.

### Cohorts

Cohort analysis focuses on return behavior over time rather than one aggregate visitor total.

### Annotations

Annotations connect events such as:

- deployments
- campaigns
- incidents
- launches
- operational changes

to the analytics timeline.

---

## Reporting & Sharing

### Scheduled reports

The reporting subsystem can schedule high-level dashboard summaries and deliver them through configured email workflows.

The package can also generate PDF output where the optional PDF dependency is available.

### Public share links

Protected read-only share links allow external stakeholders to view a selected dashboard surface without receiving staff
credentials.

These links are intended to be narrowly scoped and protected.

### Exports

Reporting workflows can generate:

- CSV
- JSON
- PDF, where configured

The reporting path reuses existing dashboard computation rather than maintaining a separate analytics calculation
engine.

---

## Paxalia API

Paxalia provides an application-level API surface for supported analytics data.

### API keys

API access uses scoped keys rather than one universal secret.

Scopes can distinguish ingestion/read behavior.

### Browser event ingestion

The browser event collector uses the public event endpoint:

```text
/api/paxalia/event/
```

The event path is intentionally separate from the private dashboard mount.

### JS error ingestion

Real User Monitoring uses a corresponding public endpoint for browser JavaScript errors.

### API documentation

The host deployment can expose protected API documentation/schema routes through its normal Django URL configuration.

---

## Dependency Health

Dependency Health provides an operational view of the installed dependency closure.

It can help identify:

- installed versions
- direct dependencies
- transitive dependencies
- available release information where the configured environment permits comparison

The dashboard does **not** silently upgrade dependencies.

Dependency changes remain an explicit deployment decision.

---

## Notifications & Alerts

Paxalia supports in-dashboard notifications plus optional external destinations.

Alert categories can include:

- security
- anomaly
- uptime
- deployment/operational events
- supported system alerts

Optional delivery destinations include:

- email
- webhook endpoints
- supported chat integrations

Alert delivery is deliberately best-effort.

A notification delivery failure should not turn the underlying application event into an application failure.

---

## Multi-Site Analytics

Multiple domains can be represented by `Site` records.

Requests are resolved by hostname and associated with active sites.

Configure:

```python
PAXALIA_DASHBOARD = {
    "AUTO_CREATE_SITES": False,
}
```

Automatic site creation is disabled by default.

This avoids silently creating database rows for unexpected hostnames.

---

## Release Center

The Release Center provides release and deployment context.

Deployment tracking can connect application releases to analytics annotations.

Example:

```bash
python manage.py record_deployment \
    --version "$(git rev-parse --short HEAD)" \
    --notes "the deployed release"
```

The result is a deployment record plus a matching chart annotation.

Release artifact management remains separate from deployment event tracking.

---

## Paxalia Logging / Observability

The platform adds a canonical persistent logging and observability subsystem under `paxalia.logging`.

This is one of the major differences between the earlier analytics-only architecture and the platform.

The logging system does **not** replace:

- analytics
- RUM
- Security Center
- server metrics
- existing application logging

Instead it creates a shared structured observability layer that can connect those sources when appropriate.

### Core architecture

```text
Python / Django loggers
        │
        ├── Paxalia logging handler
        │
        └── paxalia.log(...)
                 │
                 ▼
        normalized event context
                 │
                 ├── redaction
                 ├── fingerprinting
                 ├── grouping
                 ├── deduplication
                 └── bounded persistence
                 │
                 ▼
         PaxaliaLogEvent
                 │
                 ├── PaxaliaLogGroup
                 ├── Logs dashboard
                 ├── Application Logs
                 ├── Login Activity
                 ├── Log Detail
                 └── exports / retention
```

### Direct application logging

The package exposes a simple application-facing entry point:

```python
import paxalia

paxalia.log(
    "Workspace synchronization failed",
    level="ERROR",
    category="application.sync",
    action="sync_failed",
    metadata={
        "workspace_id": "...",
    },
)
```

The helper uses the same canonical logging pipeline as standard Python/Django logs.

### Standard logging capture

When enabled, ordinary logger calls can be captured without changing application code:

```python
import logging

logger = logging.getLogger(__name__)

logger.error(
    "Synchronization failed",
    extra={
        "category": "application.sync",
        "action": "sync_failed",
    },
)
```

Paxalia normalizes the record before persistence.

### Request lifecycle logging

`PaxaliaLoggingMiddleware` can provide:

- request IDs
- response-status events
- duration
- request path
- method
- site
- session context
- authenticated user context
- correlation/trace identifiers

Configure:

```python
MIDDLEWARE = [
    # ...
    "paxalia.logging.middleware.PaxaliaLoggingMiddleware",
]
```

The middleware is designed for request context.

Paxalia logging also supports request-less events from:

- background jobs
- startup code
- CLI commands
- scheduled management commands
- direct application logging

### Event context

A stored event can contain structured fields for:

- severity
- source
- category
- action
- logger name
- message
- exception type
- stack trace
- module
- file
- line number
- function
- session ID
- request ID
- correlation ID
- trace ID
- request method
- request path
- response status
- duration
- site
- traffic type
- bot category
- user ID
- user display information
- admin marker
- IP context where configured
- User-Agent
- browser
- operating system
- device
- process ID
- thread name
- host
- environment
- release
- structured metadata
- sensitive-data state

Not every event has every value.

### Fingerprints and grouping

Paxalia can calculate a stable fingerprint from structural event characteristics.

Related events can be grouped and summarized through:

- first-seen time
- last-seen time
- occurrence count
- suppressed count
- sample count
- grouping window
- representative metadata

This lets an administrator see:

```text
1 underlying problem
    ↓
4,812 occurrences
    ↓
5 retained representative samples
```

instead of manually opening thousands of duplicate log rows.

### Deduplication

Handler-topology duplication is guarded so the same record is not persisted repeatedly simply because it passed through
multiple supported logging paths.

### Exception capture

The logging layer records:

- exception type
- normalized message
- stack trace

Stack/message lengths are bounded through configuration.

### Redaction

Sensitive values are sanitized before persistent presentation/storage according to the package's redaction policy.

Common credential classes include:

```text
password
token
access_token
refresh_token
secret
api_key
private_key
authorization
cookie
credential
session key
encryption key
```

Host projects can extend the sensitive-key configuration.

The objective is:

```text
useful debugging context
        +
low probability of credential persistence
```

not simply deleting every form of structured metadata.

### Browser observability

The browser-side RUM/error system can feed relevant errors into the canonical logging/investigation workflow.

### Log dashboard

The Logs page supports investigation through:

- date filtering
- severity filtering
- source/result filters
- search
- structured event rows
- pagination
- auto-refresh
- detail navigation
- related-event discovery

Less frequently used controls are kept behind secondary filtering so the main operational surface stays calm.

### Log detail

The detailed event surface is built for incident investigation rather than only showing a single message.

It can expose:

- event identity
- request/network context
- client/browser context
- runtime context
- grouping information
- structured metadata
- exception details
- stack traces
- related events

A sanitized **Copy for AI** workflow can prepare structured incident context for external debugging or AI-assisted
analysis.

The copied context is intentionally sanitized rather than treating the raw event database as a safe prompt source.

### Login activity

Authentication-related observability can be inspected independently through the Login Activity dashboard.

Failed-login identifiers can be privacy-controlled.

### Retention

Current logging retention configuration is category-specific:

```python
PAXALIA_DASHBOARD = {
    "LOG_RETENTION_DAYS": {
        "system": 30,
        "request": 30,
        "browser": 30,
        "application": 30,
        "login": 180,
        "security": 180,
        "group": 90,
    },
}
```

Run a dry run first:

```bash
python manage.py paxalia_logs_prune --dry-run
```

Then schedule pruning:

```bash
python manage.py paxalia_logs_prune
```

### Logging-specific safety properties

The observability system is designed so that:

- sensitive values are redacted
- payload sizes are bounded
- browser event rates are bounded
- metadata sizes are bounded
- identifiers are normalized
- grouping state is bounded
- logging failures do not break the primary application request path
- request-less logging remains supported

---

## Paxalia Admin & Packages

The platform includes a full **Paxalia Admin** and the **Paxalia Package Center**.

Detailed implementation notes also live in:

[`docs/PAXALIA_ADMIN_PACKAGES.md`](docs/PAXALIA_ADMIN_PACKAGES.md)

### Paxalia Admin philosophy

Paxalia Admin is not a replacement for Django Admin architecture.

Its model flow is:

```text
Django Admin registry
        ↓
PaxaliaAdminRegistry
        ↓
model definition / adapter / capabilities
        ↓
query / services / forms
        ↓
Paxalia Admin views
        ↓
Paxalia dashboard UI
```

Django remains the source of truth for:

- model registration
- ModelAdmin configuration
- permissions
- model forms
- supported custom actions
- inline definitions

Django Admin remains the fallback for exotic behavior that cannot safely be rendered by Paxalia Admin.

### Model discovery

The Admin workspace discovers models from Django's registered ModelAdmin registry.

It can expose metadata such as:

- application label
- model label
- verbose name
- verbose plural name
- capabilities
- search support
- filter support
- ordering
- list display
- list editable
- actions
- relationship fields
- inline definitions
- localization capability
- identity fields
- sensitive fields
- protected behavior

The registry is dynamic.

Host model names are not hard-coded into Paxalia.

### Models browser

The Models page is intentionally catalog-oriented.

It provides:

- application groups
- searchable models
- application collapse/expand
- compact model cards
- capability metadata
- responsive layouts
- meaningful empty states

Application groups expose accessible toggle controls with `aria-expanded` and `aria-controls`.

Model search can match:

- verbose model name
- model label
- application label
- application verbose name
- visible model metadata

### Changelists

Paxalia Admin supports normal record browsing with:

- list display
- sorting
- search
- filters
- pagination
- date hierarchy where supported
- query-string state preservation
- record selection
- supported list-editable formsets
- CSV/JSON data workflows where exposed
- optimized relationship loading where possible

### List editable

When the registered ModelAdmin uses Django's `list_editable`, Paxalia Admin can reuse the corresponding formset
behavior.

The Django management-form prefix semantics are preserved so editable formsets behave like Django expects.

### CRUD

The generic Admin surface supports:

```text
Create
  ↓
Django ModelForm
  ↓
validate
  ↓
save
  ↓
audit

Read
  ↓
safe presentation
  ↓
sensitive masking
  ↓
relationship inspection

Update
  ↓
permission check
  ↓
ModelForm
  ↓
validate
  ↓
save
  ↓
audit

Delete
  ↓
permission check
  ↓
deletion collector
  ↓
preview
  ↓
confirm
  ↓
delete
  ↓
audit
```

### Permissions

Paxalia Admin uses Django permission semantics.

Access is not granted simply because a model is registered.

The current architecture checks:

- staff access
- model-level permissions
- object-level permission hooks where available
- add/change/delete capabilities
- action permissions
- localization permissions
- package permissions

### Sensitive fields

Sensitive-field configuration is applied at the display layer and package layer where applicable.

Examples:

```text
password
token
access_token
refresh_token
client_secret
api_key
private_key
authorization
cookie
secret_key
encryption_key
```

Sensitive values should not appear as normal list/detail values.

Protected workflows can require stronger controls rather than simply showing the value.

### Relationships

Paxalia Admin recognizes Django relationship structures including:

- ForeignKey
- OneToOneField
- ManyToManyField
- reverse relations
- self-references
- supported inline relations

The query layer can optimize common relationship loading.

### Inline admins

The Admin diagnostics inspect registered inline definitions.

Supported inline presentation uses Django's existing `TabularInline`/`StackedInline` concepts where the generic Paxalia
surface can safely reproduce them.

Exotic inline behavior remains eligible for Django Admin fallback.

### Actions

Normal Django custom actions can be surfaced through the Paxalia action workflow.

Permission checks remain enforced before execution.

Action failures are surfaced rather than silently treated as success.

### Statistics

Model statistics can include, where the model makes them detectable:

- record totals
- created counts
- updated counts
- related counts
- choice distributions
- localization completeness

The exact statistics are model-dependent and are never hard-coded around a particular host application.

### History and audit

Paxalia Admin can show:

- history
- recent changes
- actor context
- timestamps
- object context
- Django admin log entries
- Paxalia security audit events

Sensitive values remain redacted.

### Localization workspace

Translatable models can expose a localization workspace.

The workflow is:

```text
discover translation system
        ↓
discover configured languages
        ↓
inspect completeness
        ↓
choose language
        ↓
edit supported translation fields
        ↓
save through model translation API
```

Languages come from Django configuration.

The Admin does not hard-code a fixed number of language tabs.

### Package Center

The package UI is available from Paxalia Admin and is divided into deliberate workflows:

```text
Package Center
    ├── Export
    ├── Import
    └── History
```

Export and import screens intentionally separate:

```text
Scope
Models
Filters
Options
Security
Action
```

rather than presenting every control as one giant form.

---

## Paxalia Package Format

`.paxalia` is a model-aware logical package format.

It is **not** a raw database dump.

Conceptually:

```text
ordinary package

package.paxalia
├── manifest.json
├── integrity.json
└── data.json
```

and an encrypted package can use the encrypted data member:

```text
package.paxalia
├── manifest.json
├── integrity.json
└── data.enc
```

The exact package internals are versioned by the package format itself.

### Manifest

The manifest records package metadata required for validation and compatibility.

It allows the reader to establish:

- package format version
- logical package metadata
- model scope
- object/relationship context
- translation information where included
- encryption state

### Integrity

Package contents are integrity-checked with SHA-256 hashes.

Tampered package data must fail validation.

### Archive safety

The package reader validates archive structure before database mutation.

Security checks include defenses for:

- duplicate ZIP members
- path traversal
- invalid archive structure
- unsupported versions
- invalid encryption metadata
- size/count limits
- malformed records
- malformed relationships

The package file extension itself is not treated as a security boundary.

### Serialization

The exporter handles supported Django/Python values such as:

- UUID
- datetime
- date
- time
- Decimal
- timedelta
- Path
- bytes
- JSON-compatible structures
- Django `FieldFile` logical paths
- lazy translation values
- relationship identities

The serializer does not blindly call `json.dumps()` on arbitrary model values.

Unsupported or unexpected data is treated as an explicit export problem where required rather than silently presented as
a complete successful package.

### Identity resolution

Imports use configured identity fields where appropriate.

Examples include:

- primary key
- unique field
- slug
- username
- email
- configured field combinations

Identity resolution occurs before relationship restoration.

New records normally receive new Django IDs unless the package strategy explicitly requires identity restoration.

### Relationships

Paxalia packages can preserve supported:

- ForeignKey relationships
- OneToOne relationships
- ManyToMany relationships
- self-references
- supported translation relationships

Relationship restoration is identity-aware and does not depend on archive row order.

### Conflicts

The current default allowed strategies are:

```text
update
skip
```

The package engine validates the selected conflict strategy against configured policy.

### Import preview

The Import workflow can preview:

- model count
- record count
- creates
- updates
- skips
- potential failures
- relationships
- translations
- encryption state
- validation state

The preview is generated from actual package validation and planning.

It is not an illustrative hard-coded result.

### Dry run

A dry run validates and plans without permanent database mutation.

It can detect:

- malformed records
- identity conflicts
- missing relationships
- incompatible fields
- translation problems
- permissions
- size/count limits
- encryption requirements

### Atomic imports

Atomic import uses Django transactions according to the configured scope.

If required work fails, the configured transaction boundary can roll back mutations.

### Partial imports

Partial import allows independent valid work to remain committed while failed work is isolated and reported.

A relationship-dependent operation should not be called a successful partial import when the dependency graph makes the
resulting data invalid.

### Failure reporting

Failures are structured around:

- model
- object identity
- field
- relationship
- translation
- exception category
- safe failure reason

Secret material should not be included.

### Retry packages

Failed subsets can be packaged for retry where practical.

The retry package preserves the relevant operation context without forcing an administrator to reconstruct the failed
data manually.

### Protected models

Configured protected models can require encryption:

```python
PAXALIA_DASHBOARD = {
    "PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED": True,
}
```

This policy is enforced by the package engine, not only by the UI.

### Encryption

Paxalia package encryption uses authenticated encryption via the optional `cryptography` dependency.

The current security module uses:

```text
AES-256-GCM
PBKDF2-HMAC-SHA256
```

with bounded/validated KDF parameters.

Wrong passwords and tampering produce package-security failures rather than partial plaintext processing.

### Package limits

Current defaults include:

```python
PAXALIA_DASHBOARD = {
    "PACKAGE_MAX_FILE_SIZE_MB": 100,
    "PACKAGE_MAX_OBJECTS": 10000,
    "PACKAGE_MAX_RELATIONS": 50000,
}
```

These limits are intended to keep administrative package operations predictable.

### CLI validation

Validate:

```bash
python manage.py paxalia_package_validate export.paxalia
```

Inspect:

```bash
python manage.py paxalia_package_inspect export.paxalia
```

Encrypted package inspection requires the appropriate password input according to the command's options.

### Important distinction: package vs backup

Use **physical backups** for:

- disaster recovery
- database restoration
- server recovery
- infrastructure migration
- full system restore

Use **`.paxalia` packages** for:

- logical application-data transfer
- selected model migration
- model-aware export/import
- translation transfer
- environment-to-environment content movement
- controlled administrative data exchange

Do not use a logical package as your only disaster-recovery mechanism.

---

## Operational Commands

Paxalia contains management commands for analytics, operations, logging, Admin diagnostics, package validation, and
maintenance.

### Analytics and operational commands

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

### Logging diagnostics and retention

```bash
python manage.py paxalia_logs_test --keep
python manage.py paxalia_logs_prune --dry-run
python manage.py paxalia_logs_prune
```

### Dashboard diagnostics

```bash
python manage.py paxalia_dashboard_test --keep --no-ui
python manage.py paxalia_dashboard_test --keep
```

### Paxalia Admin diagnostics

```bash
python manage.py paxalia_admin_test
```

The Admin diagnostics check areas such as:

- Django Admin registry
- Admin enabled state
- registered model discovery
- model configuration
- ModelAdmin compatibility
- list-editable support
- deletion preview compatibility
- relationship and inline discovery
- history routes
- sensitive-field policy
- hardening settings

Diagnostic model counts are intentionally dynamic.

Do not hard-code values from one host environment into the package.

### Package inspection

```bash
python manage.py paxalia_package_validate export.paxalia
python manage.py paxalia_package_inspect export.paxalia
```

### Suggested schedules

Daily aggregation:

```cron
0 0 * * * cd /path/to/project && python manage.py aggregate_daily_stats
```

Server history:

```cron
* * * * * cd /path/to/project && python manage.py record_server_metrics
```

Uptime checks:

```cron
* * * * * cd /path/to/project && python manage.py check_uptime
```

Anomaly detection:

```cron
10 * * * * cd /path/to/project && python manage.py detect_anomalies
```

Analytics retention:

```cron
0 3 * * * cd /path/to/project && python manage.py prune_analytics_data
```

Security log retention:

```cron
20 3 * * * cd /path/to/project && python manage.py prune_security_logs
```

Paxalia log retention:

```cron
30 3 * * * cd /path/to/project && python manage.py paxalia_logs_prune
```

---

## Security & Privacy Model

Paxalia is designed to keep data on the host application.

That does not mean "privacy automatically solved."

The host project still controls:

- database access
- operating system security
- reverse proxy
- authentication
- administrator accounts
- backups
- network policy
- retention choices
- proxy trust
- email/webhook destinations
- access to exported files

### Application-level security principles

Paxalia uses:

- Django authentication
- staff checks
- Django permissions
- object-level ModelAdmin permission hooks where available
- CSRF protection
- sensitive-field redaction
- no-store handling for protected responses where configured
- package structural validation
- package integrity checks
- package encryption requirements
- ZIP archive safety controls
- bounded upload/package limits
- audit/security events

### Secret dashboard paths

The dashboard can be mounted at a private path.

This is useful as a defense-in-depth measure.

It must not be treated as an authentication mechanism by itself.

### Public ingestion endpoints

Browser event ingestion is intentionally public because visitors send anonymous telemetry to it.

Public ingestion endpoints must therefore validate and bound input on the server.

### Proxy trust

Only enable forwarded-IP trust behind a controlled proxy infrastructure.

### Logging privacy

Persistent observability makes debugging easier, but it also creates another sensitive data store.

The logging system therefore:

- redacts credential-like fields
- bounds message and stack sizes
- bounds metadata
- bounds browser event rates
- supports retention policies
- distinguishes diagnostic context from secrets
- supports privacy-aware failed-login identifier handling

### Admin privacy

Paxalia Admin is designed to avoid displaying configured sensitive fields as normal values.

Protected values should not be exposed simply because an administrator can browse the model.

### Package privacy

Normal exports omit configured sensitive fields.

Protected-model export can require encryption.

Package failure reports must not expose secret material.

### Backups

Physical backups contain whatever the configured backup scope includes.

Treat them as highly sensitive infrastructure artifacts and protect their storage and transport accordingly.

### What Paxalia does not do

Paxalia does not:

- replace your OS firewall
- rotate all application credentials for you
- verify crawler identity through a live IP-range lookup
- replace a dedicated WAF
- replace a dedicated SIEM
- automatically upgrade dependencies
- provision your Redis/Celery/PostgreSQL infrastructure
- operate your mail server
- replace a physical disaster-recovery strategy
- certify legal compliance

### Production principle

Use Paxalia as an **application-level observability, analytics, administration, and security layer** alongside your
normal infrastructure controls.

---

## Paxalia and Django

Paxalia Dashboard is an application package **for Django**, not a replacement for Django.

| Responsibility                 | Django / host project    | Paxalia Dashboard                                             |
|--------------------------------|--------------------------|---------------------------------------------------------------|
| ORM and database models        | Authoritative            | Integrates with them                                          |
| Authentication                 | Authoritative            | Reuses the host authentication/session context                |
| Model permissions              | Authoritative            | Reuses Django permission and ModelAdmin hooks                 |
| URL routing                    | Authoritative            | Adds dashboard/package routes                                 |
| Business logic                 | Authoritative            | Observes and administrates without owning host business rules |
| Django Admin registry          | Authoritative            | Uses it as the source of truth for generic Admin              |
| Analytics                      | Host/application data    | Provides the analytics layer                                  |
| Structured application logging | Host/Python logging APIs | Provides persistent observability and investigation           |
| Server/runtime telemetry       | Host environment         | Provides application-facing monitoring                        |
| Logical data portability       | Host data                | Provides `.paxalia` package workflows                         |
| Physical backups               | Host infrastructure      | Provides complementary backup-management utilities            |
| Deployment                     | Host infrastructure/CI   | Records deployment context                                    |
| Final operational authority    | Host project             | Remains with the host project                                 |

This separation is deliberate. Paxalia becomes powerful by integrating with Django rather than by trying to replace the
framework it
runs inside.

## Architecture & Extensibility

Paxalia is intentionally modular.

### Analytics architecture

```text
HTTP request
    ↓
middleware
    ↓
classification / site resolution
    ↓
persistent analytics models
    ↓
aggregation / reporting
    ↓
dashboard views
    ↓
browser UI
```

### Logging architecture

```text
stdlib / Django logging
        +
paxalia.log()
        ↓
normalization
        ↓
context
        ↓
redaction
        ↓
fingerprint / grouping
        ↓
persistent observability
        ↓
logs / audit / investigation
```

### Admin architecture

```text
django.contrib.admin registry
        ↓
PaxaliaAdminRegistry
        ↓
adapter / definition / capabilities
        ↓
permissions
        ↓
query + services + forms
        ↓
views
        ↓
Paxalia Admin UI
```

### Package architecture

```text
selection / queryset
        ↓
generic serializer
        ↓
identity map
        ↓
relationship data
        ↓
translation data
        ↓
manifest + integrity
        ↓
optional authenticated encryption
        ↓
.paxalia archive
```

### Extension philosophy

Host applications can extend Paxalia through configuration and their existing Django architecture.

Good extension points include:

- ModelAdmin registration
- model-specific identity fields
- sensitive-field configuration
- dashboard section configuration
- application log adapters
- billing models
- Celery app path
- site records
- translation models
- theme configuration

Avoid hard-coding host application models into Paxalia itself.

---

## Project Structure

A representative source tree looks like:

```text
paxalia-dashboard/
├── paxalia
│   ├── admin_center
│   │   ├── adapter.py
│   │   ├── __init__.py
│   │   ├── package_views.py
│   │   ├── permissions.py
│   │   ├── query.py
│   │   ├── registry.py
│   │   ├── services.py
│   │   ├── urls.py
│   │   ├── utils.py
│   │   └── views.py
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
│   ├── logging
│   │   ├── application.py
│   │   ├── context.py
│   │   ├── fingerprint.py
│   │   ├── handler.py
│   │   ├── __init__.py
│   │   ├── middleware.py
│   │   ├── redaction.py
│   │   └── services.py
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
│   │       ├── paxalia_admin_test.py
│   │       ├── paxalia_dashboard_test.py
│   │       ├── paxalia_logs_prune.py
│   │       ├── paxalia_logs_test.py
│   │       ├── paxalia_package_inspect.py
│   │       ├── paxalia_package_validate.py
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
│   │   ├── 0020_paxalia_observability.py
│   │   ├── 0021_remove_loginevent_paxalia_log_is_ad_8ef5a0_idx_and_more.py
│   │   └── __init__.py
│   ├── models.py
│   ├── packages
│   │   ├── engine.py
│   │   ├── format.py
│   │   ├── __init__.py
│   │   ├── localization.py
│   │   └── security.py
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
│   │       │   ├── dependencies.js
│   │       │   ├── realtime.js
│   │       │   ├── sidebar.js
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
│   │       │   ├── admin-center.js
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
│   │       │   ├── logging-filter.js
│   │       │   ├── logs.js
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
│   │           │   ├── admin.css
│   │           │   ├── backup.css
│   │           │   ├── buttons.css
│   │           │   ├── charts.css
│   │           │   ├── dependencies.css
│   │           │   ├── export-btn.css
│   │           │   ├── filter-bar.css
│   │           │   ├── icon.css
│   │           │   ├── logging.css
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
│   │       ├── admin
│   │       │   ├── audit.html
│   │       │   ├── bulk_delete.html
│   │       │   ├── delete_confirmation.html
│   │       │   ├── history.html
│   │       │   ├── home.html
│   │       │   ├── model_list.html
│   │       │   ├── model_localization.html
│   │       │   ├── model_overview.html
│   │       │   ├── models.html
│   │       │   ├── model_stats.html
│   │       │   ├── object_detail.html
│   │       │   ├── object_form.html
│   │       │   ├── package_center.html
│   │       │   ├── package_export_center.html
│   │       │   ├── package_export.html
│   │       │   ├── package_history.html
│   │       │   ├── package_import_center.html
│   │       │   ├── package_import.html
│   │       │   └── package_result.html
│   │       ├── admin_overview.html
│   │       ├── annotations.html
│   │       ├── api_docs.html
│   │       ├── api.html
│   │       ├── api_keys.html
│   │       ├── application_logs.html
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
│   │       │   ├── filter_bar.html
│   │       │   └── pagination.html
│   │       ├── log_detail.html
│   │       ├── login_activity.html
│   │       ├── logs.html
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
│   ├── test_admin_center.py
│   ├── test_logging.py
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
│       ├── login_activity.py
│       ├── logs.py
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
├── pyproject.toml
├── README.md
├── setup.cfg
├── setup.py
├── .gitignore
└── .gitattributes
```

The `.mmdb` GeoIP database is intentionally excluded from Git because of its size.

---

## Contributing

Contributions are welcome.

The goal is to preserve Paxalia's existing architecture rather than accumulating independent feature-specific systems.

### Development setup

```bash
git clone https://github.com/paxalia/paxalia-dashboard.git
cd paxalia-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run the appropriate checks.

### Baseline checks

```bash
python manage.py check
python manage.py paxalia_admin_test
python manage.py paxalia_logs_test --keep
python manage.py paxalia_dashboard_test --keep --no-ui
```

Focused Admin tests:

```bash
python manage.py test paxalia.test_admin_center -v 2
```

When working on logging:

```bash
python manage.py test paxalia.test_logging -v 2
python manage.py paxalia_logs_test --keep
```

When working on package functionality, also run:

```bash
python manage.py paxalia_package_validate path/to/test-package.paxalia
python manage.py paxalia_package_inspect path/to/test-package.paxalia
```

### Diagnostic expectations

Do not claim a subsystem is healthy merely because a single page loads.

When a change touches Admin, verify:

- registry discovery
- permissions
- model browsing
- CRUD
- relationships
- inline support
- package operations
- localization
- diagnostics

When a change touches logging, verify:

- stdlib capture
- direct `paxalia.log()`
- request context
- request-less events
- exception persistence
- redaction
- grouping/fingerprints
- dashboard visibility
- retention/pruning
- non-fatal failure behavior

### Developer conventions

Paxalia uses:

- Django-native patterns
- token-driven CSS
- reusable components
- external JavaScript modules
- defensive progressive enhancement
- explicit security boundaries
- generic configuration instead of host-model assumptions

Do not introduce an external UI framework merely to build an Admin page.

Do not move host-specific business logic into Paxalia.

Do not silently swallow operational failures merely to keep the UI looking successful.

### Commit message format

Use Conventional Commit style:

```text
type(scope): short summary
```

Common types:

```text
feat(scope): ...
fix(scope): ...
refactor(scope): ...
style(scope): ...
docs(scope): ...
chore(scope): ...
perf(scope): ...
polish(scope): ...
test(scope): ...
```

For substantial changes, use a structured body:

```text
feat(admin): improve generic model discovery

Scope:
- paxalia/admin_center/registry.py
- paxalia/templates/paxalia/admin/models.html
- paxalia/static/paxalia/scripts/admin-center.js

Changes:
- Added searchable application grouping
- Preserved Django ModelAdmin registration semantics
- Improved responsive presentation

Behavior:
- Administrators can locate models without scanning the entire registry

Impact:
- Large host projects remain easier to administer
```

### Branching

A typical repository policy is:

```text
main
feat/<name>
feat/<scope>/<name>
fix/<issue>
hotfix/<issue>
refactor/<name>
docs/<description>
```

Keep changes focused.

Avoid mixing an unrelated backend migration, dashboard redesign, and Admin change into one commit.

---

## Ideas for contribution

The previous roadmap contained several items that are now implemented. The remaining ideas should therefore focus on
capabilities that genuinely extend the current platform.

| Feature                               | Description                                                                                             | Effort |
|---------------------------------------|---------------------------------------------------------------------------------------------------------|--------|
| City bubbles on the world map         | Add a richer country-to-city visualization on the geography surface                                     | Medium |
| Session replay / user journey         | Show a controlled sequence of anonymous session events without introducing fingerprinting               | Large  |
| Custom dashboards                     | Let administrators assemble selected cards/charts into personalized dashboard views                     | Large  |
| Behavior flow diagram                 | Visualize supported page/event transitions                                                              | Large  |
| Additional languages                  | Add complete translation catalogs for more locales                                                      | Small  |
| Section-specific theme preference     | Allow selected dashboard sections to use controlled presentation modes                                  | Medium |
| Admin dashboard widgets               | Surface selected analytics indicators alongside the generic Admin workspace                             | Medium |
| Advanced retention/cohort exploration | Add deeper cohort comparisons and retention views                                                       | Medium |
| More alert policies                   | Add configurable thresholds for selected operational/security conditions                                | Medium |
| A/B testing integration               | Add first-party experiment measurement while keeping the data model explicit                            | Large  |
| Anonymous heatmap tooling             | Capture privacy-safe click-density data without browser fingerprinting                                  | Large  |
| Expanded export formats               | Add carefully scoped machine-oriented logical package profiles                                          | Medium |
| Package dependency planner            | Show explicit dependency ordering before larger package imports                                         | Medium |
| Admin saved views                     | Allow administrators to save safe model list/filter configurations                                      | Medium |
| Admin bulk workflow queue             | Move very large administrative operations into an explicit queued workflow                              | Large  |
| Plugin / extension system             | Allow controlled registration of additional dashboard sections and Admin capabilities                   | Large  |
| Local AI incident summaries           | Generate optional summaries from sanitized log context without sending raw logs to a hosted AI provider | Large  |

New contributions should preserve Paxalia's central principles:

```text
privacy-first
self-hosted
Django-native
security-aware
generic
auditable
maintainable
```

---

## License

This project is licensed under the **Apache License 2.0**.

See [`LICENSE`](LICENSE) for the complete license text.

In practical terms, the Apache 2.0 license permits:

- use
- reproduction
- modification
- distribution
- commercial use
- derivative works

subject to the license conditions.

---

## Credits

Built by **Parsa Zaydany** and published under the **Paxalia** brand.

### The Story

Paxalia was built around a simple idea:

> software should help people work with time, information, and collaboration without requiring every piece of their
> operational data to leave their own environment.

The dashboard reflects the same philosophy.

Instead of depending on a third-party analytics collector, it keeps application analytics and operational telemetry
inside the Django project that owns the data.

### About Paxalia

[Paxalia](https://paxalia.com) is a workspace, timer, planner, and team-tools platform covering areas such as:

- focused time tracking
- notes
- goals
- an infinite canvas/board
- Life OS workflows
- live shareable pages
- events and alarms
- team communication

The Paxalia Dashboard is the open-source Paxalia project focused on Django applications and is part of the same
ecosystem.

### Support

If Paxalia helps your project, useful forms of support include:

- starring the repository
- sharing it with the Django community
- contributing a language
- contributing tests
- contributing documentation
- contributing a feature
- supporting Paxalia through the project's official support/donation channels

Thank you for using **paxalia-dashboard**.
