# Paxalia Broken Links

## Overview

The Broken Links dashboard provides operational visibility into 404 activity rather than pretending every 404 is automatically an application defect.

Dashboard route:

```text
/broken-links/
```

## What is recorded

The view can summarize:

- requested path
- occurrence information
- referring context
- client grouping where configured
- whether the request was classified as bot/scanner traffic

The dashboard uses bounded result sizes to avoid turning a high-volume 404 stream into an unbounded page query.

## Bot-aware handling

Bot traffic and ordinary human-facing broken links are intentionally distinguishable.

This matters because scanners can generate large numbers of requests for unrelated paths that should not be interpreted like ordinary user-facing navigation failures.

## Path limits

Relevant defaults include:

```python
PAXALIA_DASHBOARD = {
    "BROKEN_LINKS_MAX_PATHS": 50,
    "BROKEN_LINKS_MAX_IPS": 25,
}
```

The dashboard should remain responsive even when a large volume of broken-link traffic exists.

## Relationship to Availability

Broken Links answers:

> Which paths are returning 404 responses?

Availability answers:

> Is a selected website/API/endpoint currently reachable and healthy under its configured monitor criteria?

They are complementary signals, not one combined model.

## Management

Bot/scanner paths identified through Broken Links can feed the dedicated bot-path management workflow where the operator has the required permission.

The destructive root prefix `/` remains rejected by the bot management service.

## Related documentation

- [Bot Traffic](bot-traffic.md)
- [Availability](availability.md)
- [Analytics](analytics.md)
