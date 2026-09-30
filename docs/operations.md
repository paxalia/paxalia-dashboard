---

# Operational Commands

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

### Administrator authentication/security tests

The security/authentication suite can be run directly:

```bash
python manage.py test paxalia.test_security_auth -v 2
python manage.py test paxalia.test_security_cleanup_fix22 -v 2
python manage.py test paxalia.test_security_ux_fix21 -v 2
```

The focused security tests cover the password/2FA/device flow, isolated-session semantics, logout behavior,
rate-limit enforcement, WebAuthn ceremony handling, and security UI contracts.

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
