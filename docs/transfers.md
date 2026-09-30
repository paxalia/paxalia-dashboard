# Paxalia Transfer Center

## Overview

Paxalia Transfer Center provides resumable, integrity-checked movement of files between the browser/application side and a controlled server-side exchange.

It extends the existing Paxalia upload/chunk infrastructure instead of creating an unrelated transfer engine.

The two directions are:

```text
Send to Server
Browser/application payload → server exchange

Receive from Server
server exchange → browser/application download
```

## Operational states

Transfers use explicit lifecycle states:

```text
QUEUED
PREPARING
TRANSFERRING
PAUSED
INTERRUPTED
VERIFYING
COMPLETED
FAILED
CANCELLED
EXPIRED
```

A transfer is not considered complete merely because HTTP requests succeeded. Integrity verification is part of the terminal workflow.

## Transfer model

The persistent `PaxaliaTransfer` model stores:

- actor
- direction
- filename
- total size
- transferred bytes
- chunk size/count
- received chunk indexes
- transfer state
- SHA-256 source/destination checksums
- retry count and budget
- bounded error text
- request ID
- timestamps
- expiration time
- the existing `FileUpload` relationship for send operations where applicable

Server filesystem paths are internal state. They are not exposed to normal serialized browser responses.

## Staging model

The package deliberately separates:

1. **private resumable staging**, and
2. **operator-visible exchange storage**.

Configuration:

```python
PAXALIA_DASHBOARD = {
    "TRANSFER_CENTER_ENABLED": True,
    "TRANSFER_ROOT": "/private/paxalia-transfer",
    "TRANSFER_EXCHANGE_ROOT": "/srv/paxalia-transfer-exchange",
}
```

The exact paths are deployment decisions. The package defaults the two paths to `None`, so a host must configure them before actual transfer activity can occur.

The private transfer root must not overlap the configured Server Files root policy.

The exchange directory must itself be a valid explicitly configured directory and must be inside an authorized Server Files root where the Transfer Center requires that binding.

## Send workflow

The safe send path is:

```text
Choose local file
    ↓
create transfer
    ↓
existing Paxalia upload/chunk engine
    ↓
private transfer staging
    ↓
source integrity verification
    ↓
atomic hidden exchange staging
    ↓
no-overwrite promotion
    ↓
server destination verification
    ↓
COMPLETED
```

The browser's requested destination is not treated as a server filesystem instruction. The Transfer Center uses its controlled exchange destination.

## Receive workflow

The receive path is deliberately selection-based:

```text
Select filename from configured exchange
    ↓
create receive transfer
    ↓
server-side source validation
    ↓
read bounded chunks
    ↓
client checksum
    ↓
server/source verification
    ↓
COMPLETED
```

The browser cannot submit an arbitrary server path as the receive source.

## Fixed exchange selection

The operator-visible exchange is intentionally a narrow selection boundary.

The exchange listing returns only regular files and does not expose server filesystem paths. This avoids turning the Transfer Center into a general filesystem browser through a secondary API.

A persisted transfer path is revalidated against the current exchange policy before later operations use it.

If the exchange becomes unauthorized or unavailable, the operation fails closed.

## Chunking and limits

Default package settings include:

| Setting | Default |
|---|---:|
| `TRANSFER_MAX_FILE_SIZE_MB` | 2048 MB |
| `TRANSFER_CHUNK_SIZE_MB` | 5 MB |
| `TRANSFER_MAX_CONCURRENT` | 3 |
| `TRANSFER_MAX_RETRIES` | 5 |
| `TRANSFER_RETRY_DELAY_SECONDS` | 2 s |
| `TRANSFER_STAGING_TTL_HOURS` | 24 h |
| `TRANSFER_BROWSER_MAX_RECEIVE_MB` | 512 MB |
| `TRANSFER_MAX_REQUESTS_PER_MINUTE` | 120 |
| `TRANSFER_EXCHANGE_LIST_LIMIT` | 200 |

The package also limits filesystem scans performed during stale staging cleanup.

## Resume and retry

Transfers support pause, interruption, resume, retry, and cancellation where the lifecycle state allows it.

The browser maintains a stable semantic resume namespace rather than using development/version-numbered local-storage keys.

A non-404 resume failure is surfaced as the real error rather than silently creating a duplicate new transfer. A missing resume record can be treated as a resume miss and handled according to the client protocol.

## Retry behavior

Retries are bounded and should only be applied to transient failures. Terminal failures, authorization failures, collisions, and other explicit policy failures are not blindly retried.

The server persists retry count and maximum retry budget. Client backoff is bounded independently from retry budget.

## Integrity verification

The canonical checksum algorithm is SHA-256.

The model exposes direction-neutral application/server checksum concepts:

- application-side checksum
- server-side checksum
- checksum scope
- verification status

For a send:

```text
application source checksum
        ↕
server destination checksum
```

For a receive:

```text
server source checksum
        ↕
downloaded payload checksum
```

A matching checksum is required before the transfer is reported as fully verified/completed.

If a send integrity check fails, the implementation must not claim a valid server-destination hash for the incorrect payload.

## Collision safety

Transfer promotion is no-overwrite.

The system checks for an existing destination before creation and still handles race-created destination conflicts at the finalization boundary.

Two files with identical content are still considered a collision if the destination filename already exists. Matching content is not used as an implicit ownership proof.

## Verification state

Large sends may remain in `VERIFYING` while server-side integrity/promotion work completes.

The browser does not convert a background verification state into a fake success message. It waits for the server's terminal state and reports the actual result.

For receives, browser download triggering is delayed until the server reports the transfer as completed/verified.

## Status polling

Status polling is read-only. It must not mutate transfer state, create new transfer rows, or reload the dashboard page.

The current client materializes active rows and updates them in place.

## Permissions

The current transfer service enforces:

```text
view_transfers
create_transfers
```

Create/resume/retry mutations re-check the required capability at the service boundary rather than trusting the view layer alone.

The existing Server Files upload capability is also part of the send path authorization boundary where applicable.

## HTTP protocol shape

The current URL surface includes:

```text
transfer-center/
transfer-center/pause/<transfer_id>/
transfer-center/retry/<transfer_id>/
transfer-center/send/init/
transfer-center/send/resume/
transfer-center/send/<transfer_id>/finalize/
transfer-center/receive/init/
transfer-center/receive/resume/
transfer-center/receive/<transfer_id>/chunk/<chunk_index>/
transfer-center/receive/<transfer_id>/complete/
transfer-center/<transfer_id>/status/
transfer-center/<transfer_id>/cancel/
```

Receive chunk delivery is POST-backed because it updates transfer state.

## Transfer history

History exposes operational metadata rather than arbitrary internal filesystem details. Useful fields include:

- filename
- direction
- size
- bytes transferred
- status
- progress
- retry budget
- checksum state
- duration
- average speed
- timestamps
- safe failure information

The historical view filters ownership before slicing the queryset so staff users cannot infer or read another actor's transfer history by pagination tricks.

## Cleanup

Stale transfer state and staging are cleaned incrementally through:

```bash
python manage.py paxalia_transfer_maintenance --dry-run
```

The resource maintenance command can also retire stale/overflowing transfer records under the configured global processing budget.

The cleanup process is careful not to delete staging that is still referenced by an active upload/transfer.

## Security model

The Transfer Center must preserve these invariants:

```text
No arbitrary browser destination path
No arbitrary browser source path
No filesystem path leakage
No silent destination overwrite
No symlink escape
No unbounded transfer size
No unbounded concurrency
No unbounded retry loop
No false verification success
No background reload loop
No secret data in logs
```

Archives are treated as files. The Transfer Center does not provide a browser-facing arbitrary archive-extraction shell.

## Related documentation

- [Server Files](server-files.md)
- [Backups](backup-management.md)
- [Operations](operations.md)
- [Security](security.md)
