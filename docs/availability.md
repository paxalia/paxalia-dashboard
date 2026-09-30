# Paxalia Availability Center

## Overview

Paxalia Availability extends the existing v4 uptime subsystem into a broader availability-monitoring surface. It does **not** create a second monitoring engine.

Current dashboard routing exposes the same overview through:

```text
/availability/
/uptime/
```

The compatibility route remains available while the dashboard calls the section Availability.

## Monitor kinds

The current model supports:

```text
server
website
api
endpoint
```

The same underlying `UptimeMonitor` model drives all four kinds.

## Supported methods

The current implementation allows:

- GET
- HEAD
- POST

The host configuration bounds which methods are accepted through `AVAILABILITY_ALLOWED_METHODS`.

## Monitor configuration

A monitor can define:

- name
- URL
- kind
- HTTP method
- expected status code
- timeout
- interval in seconds
- failure threshold
- recovery threshold
- redirect policy
- request headers
- bounded POST request body
- expected content type
- response assertions
- active/inactive state
- optional site association

Relevant configuration defaults include:

| Setting | Default |
|---|---:|
| `AVAILABILITY_DEFAULT_INTERVAL_SECONDS` | 300 s |
| `AVAILABILITY_MIN_INTERVAL_SECONDS` | 30 s |
| `AVAILABILITY_MAX_INTERVAL_SECONDS` | 86400 s |
| `AVAILABILITY_DEFAULT_TIMEOUT_SECONDS` | 10 s |
| `AVAILABILITY_FAILURE_THRESHOLD` | 2 |
| `AVAILABILITY_RECOVERY_THRESHOLD` | 2 |
| `AVAILABILITY_MAX_RESPONSE_BYTES` | 262,144 |
| `AVAILABILITY_MAX_REQUEST_BODY_BYTES` | 65,536 |
| `AVAILABILITY_LOG_CORRELATION_WINDOW_SECONDS` | 300 s |
| `AVAILABILITY_MAX_CHECKS_PER_RUN` | 100 |
| `AVAILABILITY_MAX_SCHEDULER_SCAN` | 1000 |

Individual monitor values are also bounded server-side.

## UP, DOWN, UNKNOWN

The observation state is explicit:

```text
UP
DOWN
UNKNOWN
```

### UP

The target produced a response that satisfied the configured health criteria.

That can include:

- expected HTTP status
- expected content type
- configured response assertions

### DOWN

The target was observed failing its configured health criteria.

Examples:

- wrong HTTP status
- request timeout
- transport failure
- failed response validation
- response body exceeding the configured bound in a way that makes the observation invalid

### UNKNOWN

UNKNOWN is reserved for monitor-side uncertainty rather than a target health assertion.

Examples include:

- invalid monitor configuration
- unsafe/private DNS resolution
- invalid configured headers
- an oversized configured request body
- an unavailable/ambiguous observation condition where the system cannot safely interpret the target state

Do not turn an UNKNOWN monitor observation into a fabricated DOWN event.

## SSRF protection

Availability checks execute outbound HTTP requests from the server, so URL validation is a security boundary.

The implementation resolves and validates the destination before connecting and uses DNS-pinned request handlers so an accepted destination cannot simply be re-resolved to a different address during the request.

Private, reserved, multicast, loopback, unspecified, and other disallowed addresses are rejected according to the monitor safety policy. Mixed public/private DNS answers are not treated as safely public.

The check layer is designed to avoid turning a monitor URL into a server-side request forgery primitive.

## Redirect policy

Redirects are not blindly followed.

The monitor has an explicit redirect setting. When safe redirects are allowed, each redirect destination remains subject to the same target-safety rules.

## Request bounds

Availability monitoring is intentionally bounded before and during network I/O.

Configured POST bodies cannot exceed `AVAILABILITY_MAX_REQUEST_BODY_BYTES`.

Response bodies are read through a bounded reader using `AVAILABILITY_MAX_RESPONSE_BYTES`.

This prevents a monitor from turning a health check into an unbounded memory/CPU operation.

## Response validation

HTTP status is only one health signal.

The monitor can additionally validate:

```text
HTTP status
+
Content type
+
Response assertions
```

Response assertions can inspect selected JSON values and expected body/header conditions without requiring the entire response to be persisted.

## Failure and recovery thresholds

Incidents are transition-based.

Configured consecutive thresholds prevent a single transient failure from immediately becoming a prolonged outage state.

Example:

```text
failure threshold = 2

check 1 → DOWN
check 2 → DOWN
         ↓
       incident
```

Recovery is also thresholded:

```text
recovery threshold = 2

check 1 → UP
check 2 → UP
         ↓
      recovered
```

The current implementation bounds thresholds to safe values server-side.

## Incidents

`UptimeIncident` represents a confirmed transition rather than an exact physical outage clock.

Incident states are:

```text
OPEN
ACKNOWLEDGED
RECOVERED
```

The record retains observation-boundary timestamps including:

- last confirmed healthy time
- first confirmed failure time
- first confirmed recovery time
- resolution time

It can also record cause, status code, response time, request ID, acknowledgement actor, and acknowledgement timestamp.

## Observed availability semantics

Suppose:

```text
12:00  UP
12:10  UP
12:20  UP
12:30  DOWN
...
18:40  UP
18:50  UP
```

The system can truthfully say:

```text
Last confirmed healthy: 12:20
First confirmed failure: 12:30
First confirmed recovery: 18:40
```

It cannot truthfully claim the target failed at exactly 12:21 or recovered at exactly 18:39 unless there was an observation at that boundary.

The UI should therefore use wording such as:

> Observed interruption between the last confirmed healthy observation and the first confirmed recovery.

## Response-time statistics

The uptime service can compute bounded response-time statistics and chart points instead of scanning unlimited raw history for every dashboard request.

Current checks retain response time in milliseconds.

## Scheduling

Checks are intended to run from background scheduling/management infrastructure, not from a browser tab.

The scheduler has independent scan/check caps:

- maximum monitors scanned in a pass
- maximum checks executed in a pass

This prevents a very large monitor fleet from turning one scheduler invocation into an unbounded job.

Use:

```bash
python manage.py paxalia_availability_check --dry-run
```

for a bounded diagnostic invocation.

The command is an extension of the existing uptime check machinery.

## Availability and logs

Availability transitions are written into the canonical Paxalia logging pipeline. The system can retain request IDs and a configurable correlation window for investigation.

This is context correlation, not duplication of complete log events inside every incident.

## Notifications

Availability transitions integrate with the existing alert/notification system. Typical transitions include:

- incident opened
- incident recovered

Alert deduplication/cooldown behavior remains the responsibility of the shared notification pipeline.

## Permissions

The dashboard exposes a dedicated `view_availability` section permission. Monitor configuration and incident actions are protected by the existing administrator/security boundary and the corresponding view permissions in the package.

Incident acknowledgement is a management operation and is not exposed to view-only users.

## Retention

Availability history is bounded by:

```python
PAXALIA_DASHBOARD = {
    "AVAILABILITY_HISTORY_RETENTION_DAYS": 90,
    "AVAILABILITY_MAX_CHECK_RECORDS": 500000,
    "AVAILABILITY_CLEANUP_BATCH_SIZE": 500,
}
```

The cross-subsystem `RESOURCE_POLICIES` can further define the retention/count policy for `uptime_check` and `uptime_incident` records.

## Related documentation

- [Operations](operations.md)
- [Logging](logging.md)
- [Notifications](notifications.md)
- [Security](security.md)
- [Releases](releases.md)
