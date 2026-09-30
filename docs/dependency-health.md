# Paxalia Dependency Health

## Overview

Dependency Health is the security/operations page for inspecting the installed runtime package set and comparing it with declared requirements and available release metadata.

It is intentionally diagnostic rather than a package installer.

## What it inspects

The current dependency service:

- parses declared requirements
- normalizes distribution names
- reads installed package metadata
- compares installed versions against available release metadata where accessible
- exposes per-package status information

The dashboard routes are:

```text
/security/dependencies/
/security/dependencies/status/<package_name>/
```

## Runtime versus host dependencies

Paxalia distinguishes its own declared runtime requirements from arbitrary dependencies belonging to the host Django project.

The current package runtime set includes:

- Django
- geoip2
- user-agents
- pycountry
- psutil
- django-honeypot
- cryptography
- django-otp
- qrcode
- webauthn

The host application may additionally use Redis, Celery, DRF, Sentry, or other packages. Those are not silently treated as Paxalia runtime requirements merely because the host happens to install them.

## Status semantics

Dependency status should distinguish conditions such as:

```text
installed and compatible
update available
missing
unreadable/unknown
```

The exact UI wording can evolve, but the implementation should not invent a version that was not observed.

## Safe external metadata

Checking for available releases is external metadata access. The dashboard should treat it as optional diagnostics.

Failure to retrieve package-index information must not make the local dependency inspection fail.

## Configuration and operational use

Dependency Health is useful during:

- deployment validation
- upgrade planning
- security reviews
- incident investigation
- support diagnostics

It should be read as an advisory inspection surface, not a replacement for host-level dependency management tools such as pip/uv/poetry or a deployment image lock file.

## Package baseline

The current package metadata uses:

```text
Python >= 3.10
Django >= 5.0
```

and declares Django 5.0 and 6.0 classifiers.

## Related documentation

- [Configuration](configuration.md)
- [Security](security.md)
- [Operations](operations.md)
- [Releases](releases.md)
