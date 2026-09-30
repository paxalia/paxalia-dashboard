---

# Paxalia Logging / Observability

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
