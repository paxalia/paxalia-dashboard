# Paxalia Server Files

Paxalia Server Files is a restricted filesystem explorer for an authenticated Paxalia Dashboard administrator. It is disabled by default and exposes only explicitly configured, existing directories. It is not a terminal and does not execute shell commands.

## Enablement and configuration

The feature is disabled unless `FILE_MANAGER_ENABLED` is set to `True`. Even when enabled, an empty `FILE_MANAGER_ALLOWED_ROOTS` list grants no filesystem access.


## Package integration

Phase 1 registers the `ServerFileOperation` model through
`paxalia/models.py`, exposes the Server Files URL set through `paxalia/urls.py`,
and adds the Server Files entry to the existing Infrastructure navigation.
The package default is fail-closed:

```python
PAXALIA_DASHBOARD = {
    "FILE_MANAGER_ENABLED": False,
    "FILE_MANAGER_ALLOWED_ROOTS": [],
}
```

A host project that explicitly enables Server Files should add
`"server_files"` to its own `SIDEBAR_SECTIONS` because host configuration
overrides the package default sidebar list.

`0023_server_file_operations.py` must retain its `CreateModel` operation.
Do **not** add `DeleteModel(name="ServerFileOperation")` to 0023. A
DeleteModel migration would remove the history table and is exactly the schema
state that causes the prune command to fail.



## Host honeypot integration

Paxalia Server Files POST endpoints are authenticated dashboard operations, not public forms. When a host uses `django-honeypot` middleware site-wide, the Server Files operation and password reauthentication views are explicitly marked `@honeypot_exempt`. CSRF protection, the dedicated administrator security gate, request-size preflight, rate limiting, and Server Files capability checks remain enforced.


## Content Security Policy

Server Files does not require inline JavaScript. Its page behavior is provided by the static `server-files.js` asset and the template uses the request CSP nonce on that external script tag. Inline SVG is presentation markup and does not require `script-src` exceptions.
