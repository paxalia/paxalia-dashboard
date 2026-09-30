# Paxalia Server Files

## Purpose

Paxalia Server Files is a controlled filesystem-management capability for Django deployments. It is designed for structured file operations from inside the Paxalia Dashboard.

It is **not**:

- a shell
- a terminal emulator
- unrestricted root filesystem access
- arbitrary command execution
- a way to execute files through the browser

The implementation is deliberately policy-first and fail-closed.

## Enablement and safe defaults

Server Files is disabled by default:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_ENABLED": False,
    "FILE_MANAGER_ALLOWED_ROOTS": [],
}
```

The host project must explicitly enable the feature and configure one or more allowed directories.

Every configured root must be:

- an absolute path
- a directory
- an existing path when the feature is enabled
- a non-root directory
- non-symlinked
- non-overlapping with another configured root
- outside the built-in sensitive-path policy

The implementation never turns an empty root list into `/` or another implicit server root.

## Allowed roots

Roots may be configured as simple paths or named mappings:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_ENABLED": True,
    "FILE_MANAGER_ALLOWED_ROOTS": [
        "/srv/application-data",
        {
            "name": "Web data",
            "path": "/srv/web-data",
        },
    ],
}
```

The browser selects a configured root by identifier. It sends a relative path beneath that root; it does not get to redefine the root itself.

The package limits root configuration to a bounded number of entries and rejects overlapping/containing roots so that one configured root cannot accidentally grant a second root through another entry.

## Path security model

Every filesystem operation follows the same conceptual pipeline:

```text
Browser root ID + relative path
        ↓
relative-path parsing
        ↓
name / traversal validation
        ↓
root resolution
        ↓
denied-prefix check
        ↓
sensitive-path check
        ↓
canonical/symlink safety checks
        ↓
Django capability check
        ↓
operation
        ↓
audit history
```

The service rejects traversal forms including normal parent traversal and alternate encodings that would resolve outside the authorized root.

Intermediate symlink escapes are blocked. Symlinks are not treated as a safe way to reach a second filesystem tree.

## Denied paths

Host projects can add explicit denied prefixes beneath configured roots:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_DENIED_PATHS": [
        "/srv/application-data/private",
        "/srv/application-data/runtime",
    ],
}
```

A denied prefix remains unavailable even when the parent directory itself is allowed.

## Sensitive paths

Server Files has a separate sensitive-path policy. A sensitive entry requires an explicit capability to view it, and sensitive mutations require both configuration permission and a dedicated mutation capability.

The package supports project-specific sensitive patterns through:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_SENSITIVE_PATTERNS": None,
    "FILE_MANAGER_ALLOW_SENSITIVE_MUTATIONS": False,
}
```

The default mutation policy is deliberately disabled. Do not enable sensitive mutations merely because the operator is a staff user.

## Capabilities

The current migration/model state defines these Server Files capabilities:

| Capability | Purpose |
|---|---|
| `view_server_files` | View the Server Files section |
| `download_server_files` | Download files |
| `upload_server_files` | Upload files |
| `modify_server_files` | Create directories, rename, move, and copy |
| `delete_server_files` | Delete files/directories |
| `view_sensitive_files` | View sensitive files |
| `modify_sensitive_files` | Modify sensitive files when the feature is explicitly enabled |

Backend services enforce capabilities independently of whether a frontend control is visible.

## Supported operations

The operation-history model defines:

```text
list
preview
download
upload
mkdir
rename
move
copy
delete
history
```

Destructive operations are explicit and are never treated as a generic command dispatcher.

### Directory browsing

Directory browsing is paginated and bounded. The implementation does not recursively enumerate an entire filesystem for a page request.

Supported metadata can include:

- name
- type
- size
- modified time
- MIME/type information where available
- permission/ownership information where safely available

Hidden entries remain subject to the configured visibility policy.

### Preview

Preview is restricted to supported textual formats and bounded by bytes.

The preview pipeline:

- rejects binary/unsupported content
- truncates oversized output
- protects against unsafe inline HTML behavior
- redacts sensitive JSON/YAML values according to preview policy
- does not execute uploaded/source content

Configuration:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_PREVIEW_MAX_BYTES": 262144,
}
```

### Download

Downloads require the download capability. Sensitive downloads additionally require the sensitive-file capability and recent re-authentication where the view requires it.

The reader is bounded by the authorized file size observed for the operation. It does not blindly read beyond the authorized initial size.

### Upload

Uploads are size-bounded and do not overwrite existing files.

Relevant configuration:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_MAX_UPLOAD_SIZE_MB": 100,
}
```

The request-limit middleware rejects oversized upload requests before downstream middleware parses the body.

### Create directory

`mkdir` uses the modify capability and the same path-security boundary as every other operation.

### Rename / move / copy

Rename, move, and copy operations are policy checked and no-overwrite. A directory cannot be moved into itself.

Copy operations are bounded by:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_MAX_COPY_SIZE_MB": 100,
}
```

### Delete

Delete uses a dedicated delete capability and explicit operation handling. Non-empty directories are not silently removed as recursive trees.

## Hidden files

Hidden files are controlled separately:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_ALLOW_HIDDEN": False,
}
```

The default is not to expose hidden entries.

## Limits and rate controls

The package defaults include:

| Setting | Default |
|---|---:|
| `FILE_MANAGER_MAX_UPLOAD_SIZE_MB` | 100 MB |
| `FILE_MANAGER_MAX_DOWNLOAD_SIZE_MB` | 1024 MB |
| `FILE_MANAGER_PREVIEW_MAX_BYTES` | 262,144 |
| `FILE_MANAGER_DIRECTORY_PAGE_SIZE` | 100 |
| `FILE_MANAGER_MAX_DIRECTORY_ENTRIES` | 10,000 |
| `FILE_MANAGER_MAX_COPY_SIZE_MB` | 100 MB |
| `FILE_MANAGER_MAX_MUTATIONS_PER_MINUTE` | 30 |
| `FILE_MANAGER_MAX_READS_PER_MINUTE` | 120 |
| `FILE_MANAGER_RATE_LIMIT_WINDOW_SECONDS` | 60 |

These are safety bounds, not promises that every host must keep the same values.

## Request-limit middleware

`paxalia.server_files.middleware.ServerFilesRequestLimitMiddleware` exists specifically to reject oversized upload and re-authentication request bodies before downstream processing.

If the feature is disabled, the middleware does not intercept unrelated requests.

## Recent re-authentication

Sensitive filesystem workflows can require recent password re-authentication in addition to the normal administrator authentication session.

This prevents a long-lived dashboard session from automatically becoming a long-lived approval for every sensitive filesystem action.

## Operation history

The `ServerFileOperation` model stores operational metadata such as:

- actor
- operation
- selected root
- path/target context
- status
- safe error code
- request ID
- creation/finish timestamps

History must never contain file contents, secrets, or unnecessary raw sensitive paths.

## History retention

The package provides bounded operation-history retention:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_OPERATION_RETENTION_DAYS": 90,
    "FILE_MANAGER_MAX_OPERATION_RECORDS": 20000,
    "FILE_MANAGER_CLEANUP_BATCH_SIZE": 500,
}
```

Cleanup is incremental rather than one giant deletion transaction.

## Maintenance

Use the dedicated maintenance command for Server Files operation history cleanup:

```bash
python manage.py paxalia_server_files_prune
```

The command supports a dry-run path and schema guards so an installation with a missing history table gets an actionable error rather than an opaque database exception.

## Security invariants

A complete Server Files implementation must preserve all of the following:

```text
No arbitrary shell
No arbitrary root
No browser-selected raw server path
No traversal
No encoded traversal
No symlink escape
No silent overwrite
No unbounded preview
No unbounded listing
No frontend-only authorization
No secret contents in audit history
```

## Related documentation

- [Transfer Center](transfers.md)
- [Security](security.md)
- [Authentication](authentication.md)
- [Operations](operations.md)
- [Configuration](configuration.md)
