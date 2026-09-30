# Paxalia Error Pages

## Overview

Paxalia Dashboard provides packaged error-page presentation for common production failures, including 404 and 500 responses.

The goal is a branded, self-contained failure surface that still respects the host application's routing, security middleware, and CSP configuration.

## Error handlers

The package exposes its error handling through `paxalia.error_handlers` and branded Paxalia templates.

Error-page rendering should remain deliberately simple and resilient because the application may already be in a degraded state when the page is being rendered.

## 404 behavior

The Paxalia 404 surface is intended for not-found responses where the host configuration chooses to use Paxalia's packaged presentation.

It should not leak:

- filesystem paths
- internal stack traces
- secret settings
- database connection details
- authentication/session material

## 500 behavior

The Paxalia 500 surface is production-oriented. It presents a controlled failure message rather than exposing debugging details.

Development deployments can still use Django's own debug tooling when `DEBUG=True`; the package should not force production-style masking onto a developer workflow that intentionally enables Django debugging.

## CSP and assets

The packaged error pages follow the same self-contained frontend philosophy as the rest of the dashboard. Host applications should not need to weaken CSP or add an unrestricted public CDN dependency merely to render an error page.

## Host customization

Host projects may override the packaged templates with their own template hierarchy while preserving the package's security expectations.

Custom templates should retain the same rule:

```text
failure page
≠
secret disclosure
```

## Related documentation

- [Security](security.md)
- [Authentication](authentication.md)
- [Themes](themes.md)
- [Dashboard](dashboard.md)
