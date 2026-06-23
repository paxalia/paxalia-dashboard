"""
Resolves upload-feature settings from the project's ZAYDANY_ANALYTICS
dict, following the exact same getattr(settings, 'ZAYDANY_ANALYTICS', {})
pattern documented in the README for every other configurable value
(API_PATH_PREFIX, GEOIP_PATH, BILLING_INVOICE_MODEL, etc.).

If a project doesn't set these keys, sane defaults apply automatically —
same behavior as billing: if not configured, related UI doesn't appear
or falls back gracefully.
"""
import os
from django.conf import settings


def _config():
    return getattr(settings, 'ZAYDANY_ANALYTICS', {})


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