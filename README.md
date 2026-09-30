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

## Documentation

The README keeps the product overview, feature surface, technology stack, and installation path. Detailed operational
and technical reference material is organized under [`docs/`](docs/).

### Product and release context

- [v4.1.0 Release Notes](docs/releases.md)

- [Configuration](docs/configuration.md)

- [Dashboard Pages](docs/dashboard.md)

### Analytics and monitoring

- [Analytics](docs/analytics.md)

- [Monitoring](docs/monitoring.md)

- [Compliance](docs/compliance.md)

### Security

- [Security](docs/security.md)

- [Administrator Authentication](docs/authentication.md)

### Administration and operations

- [Administration](docs/administration.md)

- [Package Format](docs/package-format.md)

- [Operations](docs/operations.md)

- [Transfer / Release Center](docs/transfers.md)

- [Server Files](docs/server-files.md)

- [Backup Management](docs/backup-management.md)

### Integrations and platform

- [Integrations](docs/integrations.md)

- [Paxalia API](docs/api.md)

- [Internationalization](docs/internationalization.md)

- [Themes](docs/themes.md)

### Internal architecture and development

- [Logging / Observability](docs/logging.md)

- [Architecture](docs/architecture.md)

- [Project Structure](docs/project-structure.md)

- [Contributing](docs/contributing.md)

- [Legal and Credits](docs/legal.md)

---

# Paxalia Dashboard v4.1.0 — Security, Stability & Administration Update

Paxalia Dashboard v4.1.0 is a complete Django-native operational workspace: analytics, runtime observability, persistent
logging, security monitoring, administration, data portability, reporting, integrations, localization, and a dedicated
administrator authentication boundary all live inside the Django application that owns the data.

The v4 administrator security model is intentionally layered. The dashboard does not rely on a single password, a hidden
URL, or a browser fingerprint as its only protection.

```text
Paxalia Administrator Access

1. Password
      ↓
2. Mandatory 2FA
      ↓
3. Authorized Device
      ↓
4. Authentication Rate Limits
      ↓
5. CSRF Protection
      ↓
6. Isolated Administrator Authentication
      ↓
7. Secret Dashboard Path
      ↓
Protected Paxalia Dashboard
```

The first three layers are the required authentication chain. The remaining layers are defense-in-depth controls around
that
chain:

```text
Password → TOTP / recovery → WebAuthn device
             │
             ├── login / 2FA / device rate limits
             ├── Django CSRF enforcement
             ├── dedicated Paxalia SessionStore + cookie
             └── deployment-specific private dashboard path
```

The default administrator mode is isolated:

```text
Host Website Authentication
        │
        └── host session / host cookies
                 │
                 │   completely separate
                 ▼
Paxalia Administrator Authentication
        │
        ├── password
        ├── Paxalia TOTP
        ├── authorized WebAuthn credential
        └── paxalia_admin_session
```

The two systems can use the same Django user model and the same Django session backend without sharing the same session
state.
This keeps the package independently usable while preventing ordinary host login, host 2FA, host session rotation, or
host
logout behavior from becoming the Paxalia administrator session.

The complete v4 presentation layer also includes twelve built-in themes built on shared design tokens, responsive
desktop,
tablet, and mobile layouts, RTL support, bundled chart/map assets, and reusable component styling.

---

---

# Why paxalia-dashboard

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
| Security         | Mandatory administrator TOTP 2FA                 |                ❌ |                                         Rare |                     ✅ |
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

---

# Features

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

- **Mandatory Administrator Authentication** — privileged dashboard access requires password authentication, confirmed
  TOTP/recovery verification, and an authorized WebAuthn device credential.
- **Administrator Authentication Isolation** — the default mode stores the final Paxalia administrator session in a
  dedicated Django `SessionStore` and a separate `paxalia_admin_session` cookie scoped to the dashboard path.
- **Authentication Rate Limiting** — login, 2FA, and device ceremonies have independent configurable attempt/window
  limits; failed-login thresholds also feed Security Center alerting.
- **CSRF Protection** — authentication and state-changing browser operations are designed to remain behind Django's CSRF
  middleware; the bundled WebAuthn JSON helper sends the current CSRF token with POST requests.
- **Secret Dashboard Path** — the full administrator surface can be mounted below a deployment-specific private path;
  production configuration requires a high-entropy URL-safe segment.
- **Security Center** — authentication activity, active sessions, IP blocklists, security events, and posture.
- **Security Scorecard** — security configuration findings in one operational view.
- **CSP Violation Reporting** — application-level visibility into browser policy violations.
- **Mandatory Administrator 2FA** — every privileged Paxalia Dashboard administrator must complete the configured
  TOTP second-factor enrollment and verification before administrative access is established.
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

---

# Tech Stack

The package is intentionally substantial because it covers several application-lifecycle concerns around Django. The
dependency
footprint remains focused on Django and the subsystems this dashboard actually provides; optional integrations are not
required
unless the host project enables them.

| Component                  | Technology                                                                 |
|----------------------------|----------------------------------------------------------------------------|
| Backend                    | Django 5.0+ / Django 6.0 compatible                                        |
| Python                     | Python 3.10+                                                               |
| Database                   | Any Django-supported database; PostgreSQL is a supported production target |
| Charts                     | Chart.js, bundled                                                          |
| World Map                  | Datamaps + D3.js + TopoJSON, bundled                                       |
| GeoIP                      | MaxMind GeoLite2-City + `geoip2`                                           |
| User-Agent Parsing         | `user-agents`                                                              |
| Country Codes              | `pycountry`                                                                |
| Server Metrics             | `psutil`                                                                   |
| Package Encryption         | `cryptography`                                                             |
| TOTP / Administrator 2FA   | `django-otp`                                                               |
| WebAuthn / Device Auth     | `webauthn`                                                                 |
| Administrative Integration | `django.contrib.admin` / `ModelAdmin`                                      |
| Authentication boundaries  | Host Django authentication + mandatory 2FA + authorized WebAuthn device    |

The current package metadata declares Python `>=3.10`, Django `>=5.0`, and includes Django 5.0 and Django 6.0
classifiers.

### Runtime dependency set

The current package declares the following runtime dependencies. This is the package dependency set rather than a list
of optional dependencies from a particular host application:

| Package           | Declared requirement | Used for                                                                     |
|-------------------|----------------------|------------------------------------------------------------------------------|
| `Django`          | `>=5.0`              | Core framework, ORM, sessions, authentication, forms, middleware, migrations |
| `user-agents`     | `>=2.2.0`            | Browser, operating-system, and device classification                         |
| `geoip2`          | `>=4.8.0`            | Offline GeoIP lookup support                                                 |
| `psutil`          | `>=5.9.0`            | Server CPU, memory, disk, network, process, and service metrics              |
| `pycountry`       | `>=22.3.5`           | Country-code and country-name support                                        |
| `django-honeypot` | `>=1.2.1`            | Honeypot integration used by hardened host deployments                       |
| `cryptography`    | `>=46.0.0`           | Authenticated package/data encryption primitives                             |
| `django-otp`      | `>=1.7.0,<2.0`       | Mandatory administrator TOTP authentication                                  |
| `qrcode`          | `>=8.0,<9.0`         | QR presentation for TOTP enrollment                                          |
| `webauthn`        | `>=3.0.0,<4.0`       | Layer 3 WebAuthn registration and authentication                             |

A host project can have additional dependencies such as its own Redis, Celery, Sentry, REST framework, or authentication
packages. Those belong to the host application and are not silently counted as Paxalia Dashboard runtime requirements.
fileciteturn29file2L1-L34

---

---

# Installation

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

### 4a. Mount the dashboard under a deployment-specific secret path

The administrator surface should live under a private, non-predictable route chosen by the host project.

For development, a simple route such as `/insights/` is acceptable. Production deployments should use a dedicated
32–128 character URL-safe random segment:

```bash
export ENVIRONMENT=production
export DASHBOARD_URL="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Expose that value through the host settings:

```python
import os

DASHBOARD_URL = os.environ["DASHBOARD_URL"]

PAXALIA_DASHBOARD = {
    # ...
    "DASHBOARD_URL": DASHBOARD_URL,
}
```

Then mount Paxalia below that path:

```python
from django.conf import settings
from django.urls import include, path

urlpatterns = [
    path(
        settings.DASHBOARD_URL.lstrip("/"),
        include("paxalia.urls"),
    ),
]
```

Every administrator authentication route then lives below the same private mount:

```text
<secret-dashboard-path>/auth/login/
<secret-dashboard-path>/auth/2fa/setup/
<secret-dashboard-path>/auth/2fa/verify/
<secret-dashboard-path>/auth/device/
<secret-dashboard-path>/security/
<secret-dashboard-path>/admin/...
```

The secret path is defense in depth, not authentication. The password, 2FA, device, rate-limit, CSRF, and session
boundaries
remain mandatory.

### 4b. Enable the isolated Paxalia administrator session

In the default mode, place the dedicated Paxalia session middleware immediately after Django's normal
`SessionMiddleware`, and place the isolated administrator authentication middleware after Django's
`AuthenticationMiddleware`:

```python
MIDDLEWARE = [
    # ...
    "django.contrib.sessions.middleware.SessionMiddleware",

    "paxalia.auth_middleware.PaxaliaIsolatedSessionMiddleware",

    # ...
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "paxalia.auth_middleware.PaxaliaIsolatedAdminAuthenticationMiddleware",

    # ...
    "paxalia.middleware.SecurityBlockMiddleware",
    "paxalia.logging.middleware.PaxaliaLoggingMiddleware",
    "paxalia.middleware.SlowQueryMiddleware",
    "paxalia.middleware.AnalyticsMiddleware",
]
```

The default isolated mode is:

```python
PAXALIA_DASHBOARD = {
    # ...
    "AUTH_USE_HOST_LOGIN": False,
    "AUTH_ISOLATED_SESSION_COOKIE_NAME": "paxalia_admin_session",
    "AUTH_ISOLATED_SESSION_COOKIE_SAMESITE": "Lax",
    "ADMIN_SESSION_MAX_AGE_SECONDS": 8 * 60 * 60,
}
```

The resulting administrator cookie is scoped to the dashboard path. Paxalia logout deletes the isolated administrator
session without flushing the host website session.

### 4c. Optional host-authentication compatibility mode

Projects that deliberately want Paxalia to participate in an existing host login/2FA flow can opt in:

```python
PAXALIA_DASHBOARD = {
    # ...
    "AUTH_USE_HOST_LOGIN": True,
    "AUTH_LOGIN_URL": None,
    "AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",),
    "AUTH_HOST_2FA_INTENT_TTL_SECONDS": 600,
}
```

When this compatibility mode is enabled, the host project's successful second-factor route can hand the administrator
back
to the protected Paxalia destination through the signed, short-lived handoff implemented by
`PaxaliaAdminHost2FARedirectMiddleware`.

The middleware does not grant dashboard access by itself and does not change ordinary host login redirects when there is
no
active Paxalia administrator intent.

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
python manage.py runserver localhost:8000
```

Open the dashboard at the path you configured, for example:

```text
http://localhost:8000/<secret-dashboard-path>/
```

### 10. Create or authorize a dashboard administrator

By default, the package recognizes Django users that are `is_staff` or `is_superuser` as administrators. Projects with a
custom administrator role can supply `SECURITY_ADMIN_USER_CHECK`.

For a fresh local project, Django's standard command is sufficient:

```bash
python manage.py createsuperuser
```

Then use the Paxalia login route beneath the secret dashboard mount:

```text
http://localhost:8000/<secret-dashboard-path>/auth/login/
```

The final administrator session is created only after the full required authentication chain completes:

```text
password
  ↓
confirmed TOTP / recovery code
  ↓
authorized WebAuthn device
  ↓
Paxalia administrator session
```

```text
http://localhost:8000/<secret-dashboard-path>/
```

---

## Detailed Documentation

The documentation files above contain the complete reference material that was previously embedded in this README. No
feature area, implementation detail, command reference, code sample, security checklist, or project-structure material
was intentionally removed during the split.

For licensing and attribution, see [`docs/legal.md`](docs/legal.md).
