# Paxalia Diagnostics

## Overview

Paxalia includes focused management commands for checking the installed package, administration layer, logging pipeline, dashboard integration, resource maintenance, and operational subsystems.

Diagnostics are intentionally separate from ordinary application requests.

## Core checks

### Django system check

```bash
python manage.py check
```

This is the standard Django deployment check and should be part of every release validation cycle.

### Paxalia Admin diagnostics

```bash
python manage.py paxalia_admin_test
```

The command validates the Paxalia Admin environment, including discovery, configuration, ModelAdmin compatibility hooks, changelist editor support, deletion preview behavior, relationship discovery, history routing, sensitive-field policy, and hardening settings.

### Paxalia Logs diagnostics

```bash
python manage.py paxalia_logs_test --keep
```

The logging diagnostics exercise the canonical persistence and handler capture path rather than merely checking that a logger object exists.

The command intentionally emits test ERROR records. A successful run ends with a PASS statement and reports the captured diagnostic events.

### Paxalia Dashboard diagnostics

```bash
python manage.py paxalia_dashboard_test --keep --no-ui
```

This checks the installed package, settings, Django registry, database connection/transaction state, Paxalia observability tables/columns/indexes, migration state, logger topology, direct persistence, standard logging, helper logging, Django request capture, security logging, middleware capture, request context, and diagnostic state.

Some diagnostic warnings can be expected when the duplicate-capture guard reports that a record was already captured. The authoritative result is the failure count and final persistence state, not the presence of the word `WARN` in the diagnostic stream.

## Operational dry runs

Availability:

```bash
python manage.py paxalia_availability_check --dry-run
```

Transfer maintenance:

```bash
python manage.py paxalia_transfer_maintenance --dry-run
```

Resource maintenance:

```bash
python manage.py paxalia_resource_prune --dry-run
```

Log pruning:

```bash
python manage.py paxalia_logs_prune --dry-run
```

Server Files history pruning:

```bash
python manage.py paxalia_server_files_prune --dry-run
```

Dry runs should be preferred during deployment validation because they expose bounded maintenance behavior without deleting production data.

## Package inspection

The package also provides:

```bash
python manage.py paxalia_package_inspect
python manage.py paxalia_package_validate
```

These are intended for model/package integrity inspection and validation workflows.

## Diagnostic interpretation

Use the following rule when reading output:

```text
FAIL
→ a diagnostic contract did not hold

PASS
→ the checked contract held

WARN
→ additional context exists; investigate the named state

intentional ERROR log
→ may be emitted by a logging self-test and is not itself a command failure
```

Do not grep only for the literal word `ERROR` and call that a failed diagnostic. Check the test/command result and final summary.

## Release validation

A practical release validation sequence is:

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py check
python manage.py paxalia_admin_test
python manage.py paxalia_logs_test --keep
python manage.py paxalia_dashboard_test --keep --no-ui
```

Then run the focused regression suites appropriate to the release.

## Related documentation

- [Operations](operations.md)
- [Logging](logging.md)
- [Releases](releases.md)
- [Contributing](contributing.md)
