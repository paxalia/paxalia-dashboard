# Paxalia API

## Overview

Paxalia exposes two distinct API families:

1. the browser-facing analytics ingestion endpoints, and
2. the authenticated Paxalia API under `/paxalia-api/v1/`.

These must not be treated as the same trust boundary.

## Browser-facing analytics event API

The existing browser event endpoint is intentionally usable without embedding a secret API key in client JavaScript. A browser-delivered secret is not a secret credential.

Current browser-facing endpoints include:

```text
/event/
/js-error/
/browser-log/
/realtime/data/
```

These endpoints are subject to the package's existing CSRF/rate-limit/payload-bound behavior appropriate to each endpoint.

## Paxalia API keys

The authenticated server-to-server API uses `PaxaliaAPIKey` records.

A generated key has the conceptual form:

```text
pxa_<random-secret>
```

The full raw key is shown once at creation time. The database stores a SHA-256 hash and a short display prefix rather than the raw secret.

Example authorization header:

```http
Authorization: Bearer pxa_<your-key>
```

## API scopes

The current key model supports two explicit scopes:

| Scope | Purpose |
|---|---|
| `ingest` | Post server-to-server analytics events |
| `read` | Read analytics through the Paxalia API |

A key can optionally be bound to one configured `Site`. A site-bound key only reads/writes the associated site context.

The service checks `is_active` and the required scope on every request.

## Server-to-server ingestion

Endpoint:

```text
POST /paxalia-api/v1/ingest/
```

Required scope:

```text
ingest
```

Example JSON:

```json
{
  "category": "billing",
  "action": "invoice_paid",
  "label": "pro-plan",
  "path": "/billing/",
  "session_id": "optional-session-id"
}
```

The endpoint requires a JSON object and requires non-empty `category` and `action` values.

The body is bounded to 256 KiB and requests are rate-limited per API key.

A successful event ingestion returns HTTP `201`.

## Read API

### Summary

```text
GET /paxalia-api/v1/stats/summary/
```

Required scope:

```text
read
```

Supported date parameters:

```text
start_date=YYYY-MM-DD
end_date=YYYY-MM-DD
```

The end date is inclusive at the calendar-day level.

The summary excludes bot traffic and API traffic from the ordinary page-view count.

Returned metrics include:

- `total_views`
- `unique_sessions`
- `unique_visitors`

`unique_visitors` is retained as a backward-compatible field name but currently represents distinct session IDs, not a person/device identity.

### Page views

```text
GET /paxalia-api/v1/pageviews/
```

Parameters:

```text
limit
offset
start_date
end_date
```

The default limit is 100 and the maximum is 500.

Results include fields such as:

- path
- method
- status code
- referrer
- country code
- UTM source/medium/campaign
- creation timestamp

### Events

```text
GET /paxalia-api/v1/events/
```

Parameters:

```text
limit
offset
start_date
end_date
category
```

Results include:

- category
- action
- label
- value
- path
- creation timestamp

## Rate limiting

Authenticated Paxalia API keys are still rate-limited. A valid key is not an unlimited trust token.

The current implementation uses a bounded per-key request budget for the `/paxalia-api/v1/` endpoints.

## Authentication failures

Invalid/missing credentials return HTTP `401`.

Rate-limited requests return HTTP `429`.

Oversized ingestion payloads return HTTP `413`.

Invalid JSON or required-field failures return HTTP `400`.

The public response must not expose internal exception details or filesystem/database paths.

## API documentation surface

The dashboard also exposes an authenticated API documentation page through:

```text
/api-docs/
```

The host project's DRF/OpenAPI configuration is separate from the minimal no-framework Paxalia API described above. The package keeps these surfaces distinct rather than requiring one API mechanism for every integration.

## API traffic analytics

The analytics dashboard can also separate API traffic from ordinary page-view analytics through the package's API-path configuration and request classification.

This allows a host application to keep:

```text
browser/page traffic
```

separate from:

```text
programmatic/API traffic
```

without requiring separate analytics storage products.

## Key management

API keys should be:

- scoped to the minimum required capability
- site-bound where appropriate
- revoked when no longer needed
- treated as server-side secrets
- never embedded in public browser JavaScript

The management UI provides create/revoke/delete workflows according to the dashboard permission model.

## Related documentation

- [Analytics](analytics.md)
- [Security](security.md)
- [Configuration](configuration.md)
- [Authentication](authentication.md)
