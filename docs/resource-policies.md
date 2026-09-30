# Paxalia Resource & Retention Policies

## Purpose

Paxalia Dashboard stores operational data that can grow continuously: logs, browser events, server metrics, uptime checks, incidents, transfer history, and related records.

The v5 resource-policy layer exists to keep those systems bounded without turning maintenance into one giant destructive transaction.

The primary principles are:

```text
Bound
→
Retain intentionally
→
Clean incrementally
→
Protect critical records
→
Observe maintenance
```

## Log capacity controls

The package defaults include:

```python
PAXALIA_DASHBOARD = {
    "LOG_MAX_RECORDS": 500000,
    "LOG_MAX_STORAGE_MB": 2048,
    "LOG_CLEANUP_BATCH_SIZE": 500,
}
```

`LOG_MAX_RECORDS` is a record-count safety cap. `LOG_MAX_STORAGE_MB` is a storage-pressure threshold used by the resource policy layer where storage accounting is available.

## Storage warnings

The default warning thresholds are:

```python
"LOG_STORAGE_WARNING_THRESHOLDS": (80, 90, 95)
```

The warning system can emit notifications when configured storage usage crosses a threshold. Cooldown is controlled by:

```python
"LOG_STORAGE_WARNING_COOLDOWN_SECONDS": 21600
```

Notifications can be disabled without disabling logging itself.

## Severity retention

Default severity-based retention is:

| Severity | Days |
|---|---:|
| DEBUG | 7 |
| INFO | 30 |
| WARNING | 60 |
| ERROR | 180 |
| CRITICAL | 365 |

Configure with:

```python
"LOG_SEVERITY_RETENTION_DAYS": {
    "DEBUG": 7,
    "INFO": 30,
    "WARNING": 60,
    "ERROR": 180,
    "CRITICAL": 365,
}
```

Category-specific retention remains available through the existing `LOG_RETENTION_DAYS` map and can override severity defaults for configured categories.

## Protected log records

The cleanup layer protects critical/security information from being treated like disposable low-value diagnostics.

The package exposes explicit controls:

```python
"LOG_RETAIN_CRITICAL": True,
"LOG_RETAIN_SECURITY": True,
```

Critical records and security-category records are therefore protected from the ordinary cleanup path according to the configured policy.

## Cleanup order

When retention/capacity cleanup must remove data, the policy favors low-value expired data before higher-value records.

The intent is:

```text
expired data
↓
old low-severity operational data
↓
redundant/repetitive data where policy permits
↓
old normal application events
```

Protected records remain excluded from ordinary deletion.

## Category retention

Legacy category retention remains supported for compatibility:

```python
"LOG_RETENTION_DAYS": {
    "system": 30,
    "request": 30,
    "browser": 30,
    "application": 30,
    "login": 180,
    "security": 180,
    "group": 90,
}
```

Existing per-category settings remain authoritative where configured, so the new severity-aware policy does not silently discard the package's earlier retention model.

## Realtime browser bounds

The live log interface has separate browser-side safety limits:

| Setting | Default |
|---|---:|
| `LOG_BROWSER_MAX_REALTIME_EVENTS` | 2000 |
| `LOG_BROWSER_MAX_REALTIME_BUFFER` | 5000 |
| `LOG_REALTIME_BATCH_SIZE` | 200 |
| `LOG_REALTIME_AUTO_PAUSE_THRESHOLD` | 1000 |

This creates two boundaries:

1. how many events the UI will display, and
2. how many it can keep in its local buffer.

At high event rates the client can throttle/auto-pause instead of rendering an unlimited stream.

## Browser ingestion bounds

Separate browser event ingestion remains bounded through:

```python
"LOG_BROWSER_MAX_EVENTS_PER_PAGE": 50,
"LOG_BROWSER_MAX_REQUESTS_PER_MINUTE": 120,
"LOG_BROWSER_MAX_PAYLOAD_BYTES": 32768,
```

These limits are independent of how many events the live UI chooses to display.

## Cross-subsystem policies

The current default `RESOURCE_POLICIES` mapping includes:

```python
"RESOURCE_POLICIES": {
    "transfer": {
        "retention_days": 90,
        "max_records": 100000,
    },
    "uptime_check": {
        "retention_days": 90,
        "max_records": 500000,
    },
    "uptime_incident": {
        "retention_days": 365,
        "max_records": 10000,
    },
    "server_metric": {
        "retention_days": 7,
        "max_records": 100000,
    },
}
```

These policies complement subsystem-specific settings rather than silently replacing them.

## Global maintenance budget

The `paxalia_resource_prune` command uses a single processing budget for a maintenance invocation.

The design goal is important:

```text
one maintenance invocation
        ↓
shared bounded budget
        ↓
transfer cleanup
availability cleanup
server metrics cleanup
log cleanup
staging cleanup
        ↓
stop when budget is consumed
```

This prevents one especially large subsystem from consuming the entire maintenance window.

## Dry run

Use:

```bash
python manage.py paxalia_resource_prune --dry-run
```

The dry-run reports what the command would process while leaving data unchanged.

## Transfer staging cleanup

Transfer staging has an additional safety requirement: a file is not an orphan merely because it is old.

Cleanup checks whether staging is still referenced by active upload/transfer metadata before removing it.

The filesystem scan itself is bounded by the configured staging scan limit.

## Maintenance failure behavior

Cleanup operations should be:

- bounded
- incremental
- retry-safe
- observable
- explicit about protected rows

Avoid one enormous delete that can hold a database lock for an extended period.

## Maintenance commands

Primary commands include:

```bash
python manage.py paxalia_logs_prune --dry-run
python manage.py paxalia_resource_prune --dry-run
python manage.py paxalia_transfer_maintenance --dry-run
python manage.py paxalia_server_files_prune --dry-run
```

The exact available options should be checked with `--help` in the installed package because hosts can tune retention and cleanup values.

## Security and policy changes

Retention and capacity changes alter how long operational evidence survives. They should therefore be treated as privileged configuration changes and should preserve auditability where the surrounding subsystem provides it.

Do not configure aggressive retention merely to reduce storage without considering incident/security/audit requirements.

## Related documentation

- [Logging](logging.md)
- [Operations](operations.md)
- [Availability](availability.md)
- [Transfers](transfers.md)
- [Server Files](server-files.md)
