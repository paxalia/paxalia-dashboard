# Paxalia Dashboard Release History

This document is the release-history index for Paxalia Dashboard. The history is intentionally separated from the feature documentation so the main README can describe the current product without carrying the full historical implementation narrative.

## Release lineage

| Version | Release focus | Reference |
|---|---|---|
| v1.0.0 | Privacy-first analytics foundation and standalone package launch | [v1.0.0](releases/v1.0.0.md) |
| v2.0.0 | Dashboard platform expansion and packaging milestone | [v2.0.0](releases/v2.0.0.md) |
| v2.1.0 | CSP, API separation, and package cleanup | [v2.1.0](releases/v2.1.0.md) |
| v2.1.1 | Django compatibility, security, and dependency hardening | [v2.1.1](releases/v2.1.1.md) |
| v3.0.0 | Major analytics, security, monitoring, compliance, API, integrations, and reporting expansion | [v3.0.0](releases/v3.0.0.md) |
| v4.0.0 | Persistent observability, Paxalia Admin, and administrator security foundation | [v4.0.0](releases/v4.0.0.md) |
| v4.1.0 | Security, stability, administration, compatibility, diagnostics, and polish hardening | [v4.1.0](releases/v4.1.0.md) |
| v5.0.0 | Operational infrastructure: Server Files, Transfer Center, Availability, and bounded resource controls | [v5.0.0](releases/v5.0.0.md) |

## Version philosophy

Paxalia Dashboard is an evolutionary Django package. Each major version builds on the previous architecture rather than replacing it with an unrelated system.

```text
v1.0.0
Privacy-first analytics foundation
        ↓
v2.x
Platform packaging, compatibility, and security hardening
        ↓
v3.0.0
Broad analytics, security, monitoring, compliance, API, integrations, and reporting platform
        ↓
v4.0.0
Persistent observability + Paxalia Admin + administrator security
        ↓
v4.1.0
Hardening + compatibility + diagnostics + polish
        ↓
v5.0.0
Operational infrastructure + server control
```

## Current release

Paxalia Dashboard currently identifies itself as **v5.0.0**. The package metadata and `paxalia.__version__` are both part of the release state.

The v5 release line should be understood as the operational layer on top of the v4 foundation. Existing analytics, RUM, logs, security, Admin, packages, backups, reporting, notifications, multi-site support, and uptime behavior remain part of the product.

## Repository implementation lineage

The repository history supplied for this release records the following milestone commits:

```text
v4.1.0  858ebd0  merge(feat): merge feat/v4-dashboard-complete-fixes into main — complete security, stability, administration and polish
v5 HEAD f76abfe  feat(server-files): add secure Server Files management and audit system
```

The broader v5 operational source currently includes the Server Files, Transfer Center, Availability, resource/retention, and related regression infrastructure described in the v5 release document.

## Reading the history

The version documents describe historical scope, not a promise that every historical implementation detail remains identical internally. For the current implementation, prefer the feature/reference documents under `docs/` and the package source itself.
