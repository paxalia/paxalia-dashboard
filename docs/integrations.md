---

# Data Import

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
