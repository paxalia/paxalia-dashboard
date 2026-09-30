# Paxalia Bot Traffic

## Overview

Paxalia Bot Traffic separates automated traffic from ordinary human-facing analytics and provides a management workflow for scanner/crawler paths.

The current classification system recognizes categories such as:

- generic bots
- search-engine crawlers
- AI crawlers
- social-preview crawlers
- SEO tools
- malicious/scanner patterns

Bot classification is based on both request context and configured/path rules where supported.

## Why separation matters

A production website can receive a large automated traffic volume that would distort ordinary analytics if it were treated like human browsing.

Paxalia therefore keeps bot classification available as a distinct analytical dimension.

## Bot paths

The package contains a managed bot-path rules workflow. The rules can be imported from the package's bot-path list and amended by privileged dashboard operators.

The core management helper normalizes a path prefix before storing it.

The root prefix `/` is intentionally rejected as a destructive/over-broad bot rule because it would classify the entire website.

## Management permissions

Bot-path management is protected by the dedicated dashboard access permission defined by the migration/model state.

The management service checks the capability rather than trusting the view layer alone.

## Bounded management

Relevant safety settings include:

```python
PAXALIA_DASHBOARD = {
    "BOT_PATH_MAX_PREFIX_LENGTH": 255,
    "BOT_PATH_MAX_DELETE_PER_ACTION": 10000,
    "BOT_PATH_MAX_MUTATIONS_PER_MINUTE": 30,
}
```

Traffic tables are also bounded when grouping client IPs, paths, scanner rows, and crawler rows.

## Historical reclassification

When a path rule is added, the package can reclassify matching historical normal page views into bot traffic. The management workflow is deliberately bounded so a single browser action cannot become an unbounded full-table rewrite.

## Bot traffic dashboard

The dashboard route is:

```text
/bots/
```

Path management uses:

```text
/bots/path-mark/
```

Related broken-link and page views workflows can also expose or act on bot/scanner paths according to their section permissions.

## Importing bot paths

The package includes:

```bash
python manage.py import_bot_paths
```

This imports normalized bot path rules from the packaged rules file.

Historical bot-category backfill remains available through:

```bash
python manage.py backfill_pageview_bot_category
```

## Privacy and safety

Bot traffic is operational analytics, not an excuse to collect unlimited visitor identifiers.

The package continues to use its normal IP-privacy configuration and bounded traffic tables.

## Related documentation

- [Analytics](analytics.md)
- [Monitoring](monitoring.md)
- [Operations](operations.md)
- [Security](security.md)
