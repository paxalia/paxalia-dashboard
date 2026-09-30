---

# Real User Monitoring

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
