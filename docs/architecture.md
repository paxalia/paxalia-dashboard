---

# Paxalia and Django

Paxalia Dashboard is an application package **for Django**, not a replacement for Django.

| Responsibility                 | Django / host project    | Paxalia Dashboard                                                           |
|--------------------------------|--------------------------|-----------------------------------------------------------------------------|
| ORM and database models        | Authoritative            | Integrates with them                                                        |
| Authentication                 | Authoritative            | Reuses host authentication and adds the mandatory admin verification layers |
| Model permissions              | Authoritative            | Reuses Django permission and ModelAdmin hooks                               |
| URL routing                    | Authoritative            | Adds dashboard/package routes                                               |
| Business logic                 | Authoritative            | Observes and administrates without owning host business rules               |
| Django Admin registry          | Authoritative            | Uses it as the source of truth for generic Admin                            |
| Analytics                      | Host/application data    | Provides the analytics layer                                                |
| Structured application logging | Host/Python logging APIs | Provides persistent observability and investigation                         |
| Server/runtime telemetry       | Host environment         | Provides application-facing monitoring                                      |
| Logical data portability       | Host data                | Provides `.paxalia` package workflows                                       |
| Physical backups               | Host infrastructure      | Provides complementary backup-management utilities                          |
| Deployment                     | Host infrastructure/CI   | Records deployment context                                                  |
| Final operational authority    | Host project             | Remains with the host project                                               |

This separation is deliberate. Paxalia becomes powerful by integrating with Django rather than by trying to replace the
framework it
runs inside.


## Architecture & Extensibility

Paxalia is intentionally modular.

### Analytics architecture

```text
HTTP request
    ↓
middleware
    ↓
classification / site resolution
    ↓
persistent analytics models
    ↓
aggregation / reporting
    ↓
dashboard views
    ↓
browser UI
```

### Logging architecture

```text
stdlib / Django logging
        +
paxalia.log()
        ↓
normalization
        ↓
context
        ↓
redaction
        ↓
fingerprint / grouping
        ↓
persistent observability
        ↓
logs / audit / investigation
```

### Admin architecture

```text
django.contrib.admin registry
        ↓
PaxaliaAdminRegistry
        ↓
adapter / definition / capabilities
        ↓
permissions
        ↓
query + services + forms
        ↓
views
        ↓
Paxalia Admin UI
```

### Package architecture

```text
selection / queryset
        ↓
generic serializer
        ↓
identity map
        ↓
relationship data
        ↓
translation data
        ↓
manifest + integrity
        ↓
optional authenticated encryption
        ↓
.paxalia archive
```

### Extension philosophy

Host applications can extend Paxalia through configuration and their existing Django architecture.

Good extension points include:

- ModelAdmin registration
- model-specific identity fields
- sensitive-field configuration
- dashboard section configuration
- application log adapters
- billing models
- Celery app path
- site records
- translation models
- theme configuration

Avoid hard-coding host application models into Paxalia itself.

---
