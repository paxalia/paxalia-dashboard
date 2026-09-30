---

# Contributing

Contributions are welcome.

The goal is to preserve Paxalia's existing architecture rather than accumulating independent feature-specific systems.

### Development setup

```bash
git clone https://github.com/paxalia/paxalia-dashboard.git
cd paxalia-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run the appropriate checks.

### Baseline checks

```bash
python manage.py check
python manage.py paxalia_admin_test
python manage.py paxalia_logs_test --keep
python manage.py paxalia_dashboard_test --keep --no-ui
```

Focused Admin tests:

```bash
python manage.py test paxalia.test_admin_center -v 2
```

When working on logging:

```bash
python manage.py test paxalia.test_logging -v 2
python manage.py paxalia_logs_test --keep
```

When working on package functionality, also run:

```bash
python manage.py paxalia_package_validate path/to/test-package.paxalia
python manage.py paxalia_package_inspect path/to/test-package.paxalia
```

### Diagnostic expectations

Do not claim a subsystem is healthy merely because a single page loads.

When a change touches Admin, verify:

- registry discovery
- permissions
- model browsing
- CRUD
- relationships
- inline support
- package operations
- localization
- diagnostics

When a change touches logging, verify:

- stdlib capture
- direct `paxalia.log()`
- request context
- request-less events
- exception persistence
- redaction
- grouping/fingerprints
- dashboard visibility
- retention/pruning
- non-fatal failure behavior

### Developer conventions

Paxalia uses:

- Django-native patterns
- token-driven CSS
- reusable components
- external JavaScript modules
- defensive progressive enhancement
- explicit security boundaries
- generic configuration instead of host-model assumptions

Do not introduce an external UI framework merely to build an Admin page.

Do not move host-specific business logic into Paxalia.

Do not silently swallow operational failures merely to keep the UI looking successful.

### Commit message format

Use Conventional Commit style:

```text
type(scope): short summary
```

Common types:

```text
feat(scope): ...
fix(scope): ...
refactor(scope): ...
style(scope): ...
docs(scope): ...
chore(scope): ...
perf(scope): ...
polish(scope): ...
test(scope): ...
```

For substantial changes, use a structured body:

```text
feat(admin): improve generic model discovery

Scope:
- paxalia/admin_center/registry.py
- paxalia/templates/paxalia/admin/models.html
- paxalia/static/paxalia/scripts/admin-center.js

Changes:
- Added searchable application grouping
- Preserved Django ModelAdmin registration semantics
- Improved responsive presentation

Behavior:
- Administrators can locate models without scanning the entire registry

Impact:
- Large host projects remain easier to administer
```

### Branching

A typical repository policy is:

```text
main
feat/<name>
feat/<scope>/<name>
fix/<issue>
hotfix/<issue>
refactor/<name>
docs/<description>
```

Keep changes focused.

Avoid mixing an unrelated backend migration, dashboard redesign, and Admin change into one commit.

---


---

## Ideas for contribution

The previous roadmap contained several items that are now implemented. The remaining ideas should therefore focus on
capabilities that genuinely extend the current platform.

| Feature                               | Description                                                                                             | Effort |
|---------------------------------------|---------------------------------------------------------------------------------------------------------|--------|
| City bubbles on the world map         | Add a richer country-to-city visualization on the geography surface                                     | Medium |
| Session replay / user journey         | Show a controlled sequence of anonymous session events without introducing fingerprinting               | Large  |
| Custom dashboards                     | Let administrators assemble selected cards/charts into personalized dashboard views                     | Large  |
| Behavior flow diagram                 | Visualize supported page/event transitions                                                              | Large  |
| Additional languages                  | Add complete translation catalogs for more locales                                                      | Small  |
| Section-specific theme preference     | Allow selected dashboard sections to use controlled presentation modes                                  | Medium |
| Admin dashboard widgets               | Surface selected analytics indicators alongside the generic Admin workspace                             | Medium |
| Advanced retention/cohort exploration | Add deeper cohort comparisons and retention views                                                       | Medium |
| More alert policies                   | Add configurable thresholds for selected operational/security conditions                                | Medium |
| A/B testing integration               | Add first-party experiment measurement while keeping the data model explicit                            | Large  |
| Anonymous heatmap tooling             | Capture privacy-safe click-density data without browser fingerprinting                                  | Large  |
| Expanded export formats               | Add carefully scoped machine-oriented logical package profiles                                          | Medium |
| Package dependency planner            | Show explicit dependency ordering before larger package imports                                         | Medium |
| Admin saved views                     | Allow administrators to save safe model list/filter configurations                                      | Medium |
| Admin bulk workflow queue             | Move very large administrative operations into an explicit queued workflow                              | Large  |
| Plugin / extension system             | Allow controlled registration of additional dashboard sections and Admin capabilities                   | Large  |
| Local AI incident summaries           | Generate optional summaries from sanitized log context without sending raw logs to a hosted AI provider | Large  |

New contributions should preserve Paxalia's central principles:

```text
privacy-first
self-hosted
Django-native
security-aware
generic
auditable
maintainable
```

---
