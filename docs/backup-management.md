# Backup Management

## Overview

Paxalia Backup Management provides application-aware backup configuration and protected access to generated backup archives.

It is intentionally separate from physical disaster-recovery infrastructure. Paxalia can create/manage backup archives inside the application environment, but the host deployment remains responsible for its final disaster-recovery strategy and off-site durability requirements.

## Backup configuration

The singleton `BackupConfiguration` model supports:

- included backup paths
- backup storage path
- enabled/disabled state
- schedule
- retention count

Schedules are:

```text
manual
daily
weekly
monthly
```

A scheduled backup still requires the host to run the appropriate management command through its scheduler/cron infrastructure.

## Storage-path safety

The backup storage path must not overlap the configured backup source paths.

This protects against an unbounded self-including backup loop such as:

```text
backup source
    ↓
new archive stored inside source
    ↓
next archive includes previous archive
    ↓
archive grows
    ↓
repeat
```

The model exposes overlap detection and the backup views use it when validating configuration.

## Backup archive model

`BackupArchive` records metadata including:

- filename
- size
- storage path
- status
- creation time
- completion time
- bounded error text

Statuses include:

```text
PENDING
CREATING
COMPLETED
FAILED
```

## Manual backup creation

The management layer and dashboard can trigger backup creation when the backup feature is enabled and configured.

The dashboard route is:

```text
/backups/trigger/
```

The corresponding management command used by the operational architecture is:

```bash
python manage.py create_backup
```

## Retention

The backup configuration uses a retention count rather than an unbounded archive list.

The current model defaults to retaining the most recent five backups, with validated bounds in the management view.

Retention cleanup removes older completed archive records/files according to the configured count.

## Protected downloads

Backup downloads are treated as sensitive operations.

A recent password re-authentication is required for protected backup download workflows. The default re-authentication window is configured through:

```python
PAXALIA_DASHBOARD = {
    "BACKUP_REAUTH_MINUTES": 15,
}
```

Being logged into the dashboard is not by itself sufficient for a protected backup download when the re-authentication window has expired.

## Chunked download

Large backups use a chunked download protocol rather than requiring one giant response body.

The current dashboard implementation uses a 5 MiB chunk size for backup downloads.

Protocol endpoints include:

```text
/backups/download/init/<backup_id>/
/backups/download/chunk/<backup_id>/<chunk_index>/
/backups/download/<backup_id>/
```

The chunked path reports total size and chunk count before individual chunks are fetched.

## Download integrity and path safety

Downloads validate the stored archive record and the configured backup path before reading data.

The implementation must never trust a browser-submitted arbitrary filesystem path.

## Backup deletion

Deletion is an authenticated management operation:

```text
/backups/delete/<backup_id>/
```

The operation uses the existing dashboard section permission model and should be audited according to the host's security/audit policy.

## Backup + Transfer Center

v5 adds the Transfer Center as the controlled transport layer for large files. Backup Management remains the system that knows what a backup archive is; Transfer Center handles practical resumable movement where the two systems are integrated.

Conceptually:

```text
Backup Manager
    ↓
backup archive exists
    ↓
Transfer Center
    ↓
chunked/resumable movement
    ↓
verification
```

Do not maintain a second unrelated backup-transfer engine.

## Operational recommendations

A production deployment should define:

- explicit source paths
- an explicit non-overlapping storage path
- a bounded retention count
- a scheduler/cron invocation
- protected access rules
- an external/off-site disaster-recovery strategy

## Related documentation

- [Transfers](transfers.md)
- [Server Files](server-files.md)
- [Operations](operations.md)
- [Security](security.md)
