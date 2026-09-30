# Billing Integration

## Overview

Billing Analytics is an optional integration point for host applications that already contain their own billing models.

Paxalia does not require a specific billing application to be installed. Instead, the dashboard accepts configurable host-model references.

## Model adapters

The default package configuration expects model paths conceptually like:

```python
PAXALIA_DASHBOARD = {
    "BILLING_INVOICE_MODEL": "billing.BillingInvoice",
    "BILLING_USER_PLAN_MODEL": "billing.UserBilling",
    "BILLING_DONATION_MODEL": "billing.Donation",
}
```

A host application can change these paths to match its own models.

## Optional integration

Billing is optional. A project that does not expose compatible billing models should not be expected to provide billing pages/data.

This follows the package's general integration rule:

```text
Paxalia owns the dashboard surface.
Host application owns the domain models.
```

## Revenue analytics

The v3 feature line added revenue analytics including:

- MRR/ARR trend
- churn tracking
- dunning-related analytics

The exact available calculations depend on the host billing models and data that the configured adapters can observe.

## Safety

Billing integrations must not silently assume that unrelated host fields have a universal meaning.

Model adapters should inspect actual model structure and fail clearly when expected fields are unavailable.

## Related documentation

- [Analytics](analytics.md)
- [Configuration](configuration.md)
- [Administration](administration.md)
- [Releases](releases.md)
