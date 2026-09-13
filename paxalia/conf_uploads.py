"""
Resolves upload-feature settings from the project's PAXALIA_DASHBOARD
dict, following the exact same getattr(settings, 'PAXALIA_DASHBOARD', {})
pattern documented in the README for every other configurable value
(API_PATH_PREFIX, GEOIP_PATH, BILLING_INVOICE_MODEL, etc.).

If a project doesn't set these keys, sane defaults apply automatically —
same behavior as billing: if not configured, related UI doesn't appear
or falls back gracefully.

NOTE: this module read the pre-rebrand ZAYDANY_ANALYTICS key until
Phase 8 — a leftover the Phase 0 rebrand missed since this file wasn't
touched in that phase. Anything set under UPLOADS_INCOMING_ROOT /
UPLOAD_CHUNK_SIZE_MB / UPLOAD_MAX_FILE_SIZE_MB in a project's
PAXALIA_DASHBOARD dict was silently ignored until now — those keys
were effectively unconfigurable. Fixed here as part of the Phase 8
audit pass; flagging in case any deployment was relying on the old
key name (unlikely, since it never worked).
"""
import os
from django.conf import settings

# Server-executable / script extensions that are essentially never a
# legitimate release artifact and are dangerous if a misconfigured
# deployment ever serves the uploads directory directly (e.g. a
# accidentally-public /uploads_incoming/ under a PHP-capable vhost).
# Enforced regardless of UPLOAD_ALLOWED_EXTENSIONS — this is a floor,
# not the only line of defense.
_DEFAULT_BLOCKED_EXTENSIONS = {
    '.php', '.php3', '.php4', '.php5', '.php7', '.phtml', '.phar',
    '.py', '.pyc', '.pyo', '.pyw', '.rb', '.pl', '.cgi',
    '.jsp', '.jspx', '.asp', '.aspx', '.ashx',
    '.sh', '.bash', '.bat', '.cmd',
    '.htaccess', '.htpasswd',
}


def _config():
    return getattr(settings, 'PAXALIA_DASHBOARD', {})


def is_releases_enabled():
    """True only if 'releases' is listed in SIDEBAR_SECTIONS — same
    pattern as how billing is gated by SIDEBAR_SECTIONS containing
    'billing'."""
    sections = _config().get('SIDEBAR_SECTIONS', [])
    return 'releases' in sections


def get_uploads_incoming_root():
    """
    Directory where completed uploads are stored.
    Config key: UPLOADS_INCOMING_ROOT
    Default: BASE_DIR/uploads_incoming/
    """
    configured = _config().get('UPLOADS_INCOMING_ROOT')
    if configured:
        root = str(configured)
    else:
        root = os.path.join(str(settings.BASE_DIR), 'uploads_incoming')
    os.makedirs(root, exist_ok=True)
    return root


def get_upload_chunk_size_bytes():
    """
    Chunk size used by the client-side widget, in bytes.
    Config key: UPLOAD_CHUNK_SIZE_MB (megabytes)
    Default: 5 MB
    """
    mb = _config().get('UPLOAD_CHUNK_SIZE_MB', 5)
    return int(mb) * 1024 * 1024


def get_upload_max_file_size_bytes():
    """
    Maximum allowed total file size for a single upload session.
    Config key: UPLOAD_MAX_FILE_SIZE_MB (megabytes)
    Default: 2048 MB (2 GB). Set to None / 0 in config for "no limit"
    (not recommended — disk usage is otherwise unbounded).
    """
    mb = _config().get('UPLOAD_MAX_FILE_SIZE_MB', 2048)
    if not mb:
        return None
    return int(mb) * 1024 * 1024


def get_upload_blocked_extensions():
    """
    Extensions that are always rejected on upload, regardless of
    UPLOAD_ALLOWED_EXTENSIONS. Config key: UPLOAD_BLOCKED_EXTENSIONS
    (list of extensions, dot-prefixed, e.g. ['.php', '.sh']).
    Default: _DEFAULT_BLOCKED_EXTENSIONS above. Pass an empty list to
    disable this floor entirely (not recommended).
    """
    configured = _config().get('UPLOAD_BLOCKED_EXTENSIONS')
    if configured is not None:
        return {str(e).lower() for e in configured}
    return set(_DEFAULT_BLOCKED_EXTENSIONS)


def get_upload_allowed_extensions():
    """
    Optional strict allowlist. Config key: UPLOAD_ALLOWED_EXTENSIONS
    (list of extensions, dot-prefixed, e.g. ['.zip', '.tar.gz']).
    Default: None — no additional restriction beyond the blocklist
    above, since this package doesn't know what a given project's
    release artifacts look like.
    """
    configured = _config().get('UPLOAD_ALLOWED_EXTENSIONS')
    if configured is None:
        return None
    return {str(e).lower() for e in configured}