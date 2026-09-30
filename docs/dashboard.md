---

# Dashboard Pages

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

### Administrator authentication routes

The routes below are relative to the dashboard's configured mount:

| Route                                    | Purpose                                                         |
|------------------------------------------|-----------------------------------------------------------------|
| `/auth/login/`                           | Layer 1 administrator password login                            |
| `/auth/logout/`                          | End the isolated Paxalia administrator session                  |
| `/auth/signup/`                          | Public Paxalia-branded signup surface when enabled              |
| `/auth/password-reset/`                  | Start password recovery                                         |
| `/auth/password-reset/<uidb64>/<token>/` | Password-reset confirmation                                     |
| `/auth/password-change/`                 | Change the current password                                     |
| `/auth/2fa/setup/`                       | Enroll the mandatory Paxalia TOTP authenticator                 |
| `/auth/2fa/verify/`                      | Verify the Layer 2 TOTP/recovery step                           |
| `/auth/2fa/reset/`                       | Reset the Paxalia 2FA state through the supported recovery flow |
| `/auth/recovery/regenerate/`             | Regenerate administrator recovery codes                         |
| `/auth/device/`                          | Start Layer 3 authorized-device authentication                  |
| `/auth/device/options/`                  | Select an available authorized-device option                    |
| `/auth/device/verify/`                   | Complete WebAuthn authentication                                |
| `/auth/device/register/`                 | Start authorized-device registration                            |
| `/auth/device/register/verify/`          | Complete WebAuthn device registration                           |
| `/auth/session-expired/`                 | Show the expired administrator-session state                    |
| `/auth/access-denied/`                   | Show the protected access-denied state                          |

These routes are intentionally part of the private dashboard mount in the normal deployment model.

### Cross-dashboard behavior

Where supported:

- date ranges are shared through the standard dashboard filtering language
- common presets include Today, Yesterday, Last 7 days, Last 30 days, and current month
- charts provide previous-period comparison
- tables provide export actions
- responsive layouts adapt to desktop, tablet, and mobile
- Arabic layouts operate in RTL

---
