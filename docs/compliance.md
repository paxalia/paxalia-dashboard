---

# Compliance

Paxalia's compliance tooling is application-level and intentionally separate from a legal compliance certification.

### Consent mode

Consent mode is disabled by default.

To require consent:

```python
PAXALIA_DASHBOARD = {
    "CONSENT_MODE_ENABLED": True,
    "CONSENT_COOKIE_NAME": "analytics_consent",
    "CONSENT_COOKIE_GRANTED_VALUE": "granted",
}
```

The host project's consent banner/CMP remains responsible for obtaining consent and setting the cookie.

The server-side gate is authoritative.

Without the required consent:

- page-view tracking is skipped
- anonymous session state is not created
- event endpoints can return a skipped response
- client tracking becomes a no-op

### Data retention

Retention is configurable by data type:

```python
PAXALIA_DASHBOARD = {
    "DATA_RETENTION_DAYS": {
        "pageview": 400,
        "analytics_event": 400,
        "js_error": 90,
        "uptime_check": 90,
        "slow_query": 30,
    },
}
```

Nothing is pruned unless you explicitly configure a retention policy.

### Forget this visitor

The compliance surface can delete stored analytics rows associated with a visitor identifier.

Because different observability models contain different identifiers, not every subsystem can necessarily be matched by
every identifier type.

The current implementation documents those limitations rather than pretending a deletion request reached data that
cannot be identified through the same field.

### Privacy principle

Deletion is recorded as an audit action without reintroducing the exact raw identifier into the audit trail.

---
