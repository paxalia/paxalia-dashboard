# Paxalia Notifications & Alerts

## Overview

Paxalia notifications combine in-dashboard alert history with optional email/webhook delivery through one shared alert pipeline.

The central alert API is implemented in `paxalia.alerts`.

## Notification categories

The current `Notification` model defines:

```text
anomaly
security
report
uptime
general
```

The dashboard stores a notification record even when email/webhook delivery is not configured or fails. This keeps the in-dashboard alert history useful as the canonical local record of the alert itself.

## Shared alert path

The core flow is:

```text
subsystem event
      ↓
paxalia.alerts.send_alert()
      ↓
notification record
      ├── optional email
      └── optional webhook
```

Security alerts have a dedicated helper that classifies them as security events.

## Delivery is best effort

External notification delivery must not become an application failure.

A failed SMTP/webhook delivery should not cause the original monitored request, transfer, backup, or availability operation to fail merely because the notification channel was unavailable.

## Deduplication and cooldown

The shared alert layer supports deduplication keys and cooldowns.

Current defaults include:

```python
PAXALIA_DASHBOARD = {
    "ALERT_DEDUPLICATION_ENABLED": True,
    "ALERT_DEFAULT_COOLDOWN_SECONDS": 300,
}
```

Subsystems can supply a stable deduplication key for transitions such as:

```text
availability monitor X opened
availability monitor X recovered
security condition Y triggered
```

This avoids turning one persistent incident into an unlimited stream of duplicate notifications.

## Email delivery

Security alert recipients can be configured through:

```python
PAXALIA_DASHBOARD = {
    "SECURITY_ALERT_EMAILS": [],
}
```

An empty list disables those email alerts.

The package uses Django's email configuration for actual delivery.

## Webhook delivery

Security/alert webhooks can be configured with:

```python
PAXALIA_DASHBOARD = {
    "SECURITY_ALERT_WEBHOOK_URL": None,
}
```

The webhook URL is a secret-sensitive setting and should not be exposed in dashboard response data or logs.

## In-dashboard notifications

The dashboard exposes:

```text
/notifications/
/notifications/<notification_id>/read/
/notifications/mark-all-read/
```

The current model uses a global `is_read` state rather than a per-user read table. When one staff member marks a notification read, it becomes read for everyone.

This is a deliberate simplification of the current model rather than a hidden per-user notification system.

## Site scoping

Notifications can be associated with a `Site`. The dashboard filters site-specific notifications according to the current dashboard site context.

## Availability integration

Availability transitions use the shared alert system for incident-opened and incident-recovered notifications.

Because the same alert pipeline is used, cooldown/deduplication semantics remain centralized.

## Security integration

Security Center can emit alerts for conditions such as:

- failed-login thresholds
- security posture events
- protected operational events where configured

Sensitive details should remain inside the protected dashboard/security context rather than being copied into an external alert body unless the configured policy explicitly allows it.

## Operational rule

Use one shared alert path instead of implementing separate ad-hoc notification senders inside every subsystem.

The goal is:

```text
consistent categories
consistent deduplication
consistent cooldowns
consistent local history
best-effort external delivery
```

## Related documentation

- [Availability](availability.md)
- [Security](security.md)
- [Logging](logging.md)
- [Operations](operations.md)
