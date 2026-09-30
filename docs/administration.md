---

# Admin Overview

The existing Admin Overview gives administrators a high-level summary of application activity.

It includes:

- total users
- recent registrations
- active-user-oriented metrics
- content totals
- content creation history
- login activity
- recent administrative/security context where available

This is intentionally different from Paxalia Admin.

```text
Admin Overview
    = operational summary

Paxalia Admin
    = generic model administration
```

---


---

## Paxalia Admin & Packages

The platform includes a full **Paxalia Admin** and the **Paxalia Package Center**.

Detailed implementation notes also live in:

[`docs/PAXALIA_ADMIN_PACKAGES.md`](docs/PAXALIA_ADMIN_PACKAGES.md)

### Paxalia Admin philosophy

Paxalia Admin is not a replacement for Django Admin architecture.

Its model flow is:

```text
Django Admin registry
        ↓
PaxaliaAdminRegistry
        ↓
model definition / adapter / capabilities
        ↓
query / services / forms
        ↓
Paxalia Admin views
        ↓
Paxalia dashboard UI
```

Django remains the source of truth for:

- model registration
- ModelAdmin configuration
- permissions
- model forms
- supported custom actions
- inline definitions

Django Admin remains the fallback for exotic behavior that cannot safely be rendered by Paxalia Admin.

### Model discovery

The Admin workspace discovers models from Django's registered ModelAdmin registry.

It can expose metadata such as:

- application label
- model label
- verbose name
- verbose plural name
- capabilities
- search support
- filter support
- ordering
- list display
- list editable
- actions
- relationship fields
- inline definitions
- localization capability
- identity fields
- sensitive fields
- protected behavior

The registry is dynamic.

Host model names are not hard-coded into Paxalia.

### Models browser

The Models page is intentionally catalog-oriented.

It provides:

- application groups
- searchable models
- application collapse/expand
- compact model cards
- capability metadata
- responsive layouts
- meaningful empty states

Application groups expose accessible toggle controls with `aria-expanded` and `aria-controls`.

Model search can match:

- verbose model name
- model label
- application label
- application verbose name
- visible model metadata

### Changelists

Paxalia Admin supports normal record browsing with:

- list display
- sorting
- search
- filters
- pagination
- date hierarchy where supported
- query-string state preservation
- record selection
- supported list-editable formsets
- CSV/JSON data workflows where exposed
- optimized relationship loading where possible

### List editable

When the registered ModelAdmin uses Django's `list_editable`, Paxalia Admin can reuse the corresponding formset
behavior.

The Django management-form prefix semantics are preserved so editable formsets behave like Django expects.

### CRUD

The generic Admin surface supports:

```text
Create
  ↓
Django ModelForm
  ↓
validate
  ↓
save
  ↓
audit

Read
  ↓
safe presentation
  ↓
sensitive masking
  ↓
relationship inspection

Update
  ↓
permission check
  ↓
ModelForm
  ↓
validate
  ↓
save
  ↓
audit

Delete
  ↓
permission check
  ↓
deletion collector
  ↓
preview
  ↓
confirm
  ↓
delete
  ↓
audit
```

### Permissions

Paxalia Admin uses Django permission semantics.

Access is not granted simply because a model is registered.

The current architecture checks:

- staff access
- model-level permissions
- object-level permission hooks where available
- add/change/delete capabilities
- action permissions
- localization permissions
- package permissions

### Sensitive fields

Sensitive-field configuration is applied at the display layer and package layer where applicable.

Examples:

```text
password
token
access_token
refresh_token
client_secret
api_key
private_key
authorization
cookie
secret_key
encryption_key
```

Sensitive values should not appear as normal list/detail values.

Protected workflows can require stronger controls rather than simply showing the value.

### Relationships

Paxalia Admin recognizes Django relationship structures including:

- ForeignKey
- OneToOneField
- ManyToManyField
- reverse relations
- self-references
- supported inline relations

The query layer can optimize common relationship loading.

### Inline admins

The Admin diagnostics inspect registered inline definitions.

Supported inline presentation uses Django's existing `TabularInline`/`StackedInline` concepts where the generic Paxalia
surface can safely reproduce them.

Exotic inline behavior remains eligible for Django Admin fallback.

### Actions

Normal Django custom actions can be surfaced through the Paxalia action workflow.

Permission checks remain enforced before execution.

Action failures are surfaced rather than silently treated as success.

### Statistics

Model statistics can include, where the model makes them detectable:

- record totals
- created counts
- updated counts
- related counts
- choice distributions
- localization completeness

The exact statistics are model-dependent and are never hard-coded around a particular host application.

### History and audit

Paxalia Admin can show:

- history
- recent changes
- actor context
- timestamps
- object context
- Django admin log entries
- Paxalia security audit events

Sensitive values remain redacted.

### Localization workspace

Translatable models can expose a localization workspace.

The workflow is:

```text
discover translation system
        ↓
discover configured languages
        ↓
inspect completeness
        ↓
choose language
        ↓
edit supported translation fields
        ↓
save through model translation API
```

Languages come from Django configuration.

The Admin does not hard-code a fixed number of language tabs.

### Package Center

Package operations are protected by the same administrator security boundary as the rest of Paxalia. Export/import,
protected models, encrypted packages, and retry-package workflows run only inside the privileged dashboard context.

The package UI is available from Paxalia Admin and is divided into deliberate workflows:

```text
Package Center
    ├── Export
    ├── Import
    └── History
```

Export and import screens intentionally separate:

```text
Scope
Models
Filters
Options
Security
Action
```

rather than presenting every control as one giant form.

---
