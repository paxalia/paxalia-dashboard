"""Configuration and safety policy for the Paxalia Transfer Center."""
from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings

from ..settings import get_config
from ..server_files.exceptions import ServerFilesConfigurationError, ServerFilesDisabled
from ..server_files.policy import get_roots


def transfer_enabled() -> bool:
    return bool(get_config().get("TRANSFER_CENTER_ENABLED", True))


def _transfer_root_overlaps_server_files(root: Path) -> bool:
    """Return True when transfer staging would be visible inside a Server Files root."""
    try:
        server_roots = get_roots()
    except ServerFilesDisabled:
        return False
    except ServerFilesConfigurationError as exc:
        # A transfer root must never bypass an invalid Server Files policy.
        # The caller can present this as a configuration error without exposing
        # the underlying path/configuration details.
        raise ValueError(
            "Server Files configuration is invalid; transfer staging could not be validated."
        ) from exc
    for server_root in server_roots:
        server_path = Path(server_root.path).resolve()
        try:
            if root == server_path or root.is_relative_to(server_path) or server_path.is_relative_to(root):
                return True
        except (ValueError, OSError, RuntimeError):
            return True
    return False


def transfer_root() -> Path:
    configured = get_config().get("TRANSFER_ROOT")
    root = Path(str(configured)) if configured else Path(settings.BASE_DIR) / "paxalia-files"
    try:
        root = Path(os.path.abspath(os.fspath(root.expanduser())))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Transfer staging root is invalid.") from exc
    if root == Path(root.anchor or os.sep):
        raise ValueError("Transfer staging root must be an explicit non-root directory.")
    _reject_existing_symlink_components(root)
    if _transfer_root_overlaps_server_files(root):
        raise ValueError("Transfer staging root must not overlap a Server Files root.")
    try:
        if root.exists() and not root.is_dir():
            raise ValueError("Transfer staging root must be a directory.")
    except OSError as exc:
        raise ValueError("Transfer staging root could not be inspected safely.") from exc
    return root




def transfer_exchange_root() -> Path:
    """Return the fixed Server Files exchange directory used by Transfer Center.

    This is deliberately separate from ``TRANSFER_ROOT``: the latter is private
    resumable staging, while this directory is the operator-visible exchange
    area where completed outbound files are placed and inbound files are
    selected from.
    """
    configured = get_config().get("TRANSFER_EXCHANGE_ROOT")
    if not configured:
        raise ValueError("Transfer exchange directory is not configured.")
    try:
        root = Path(os.path.abspath(os.fspath(Path(str(configured)).expanduser())))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Transfer exchange directory is invalid.") from exc
    if root == Path(root.anchor or os.sep):
        raise ValueError("Transfer exchange directory must be an explicit non-root directory.")
    _reject_existing_symlink_components(root)
    try:
        if not root.exists() or not root.is_dir() or root.is_symlink():
            raise ValueError("Transfer exchange directory is unavailable.")
    except OSError as exc:
        raise ValueError("Transfer exchange directory could not be inspected safely.") from exc
    return root.resolve()


def _ensure_staging_directory(root: Path) -> Path:
    """Create one staging directory without accepting symlinked components."""
    root = Path(os.path.abspath(os.fspath(root)))
    _reject_existing_symlink_components(root)
    parent = root.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        if root.exists() and root.is_symlink():
            raise ValueError("Transfer staging directory must not be a symbolic link.")
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise ValueError("Transfer staging directory must not be a symbolic link.")
        if not root.is_dir():
            raise ValueError("Transfer staging path must be a directory.")
        return root.resolve()
    except ValueError:
        raise
    except (OSError, RuntimeError) as exc:
        raise ValueError("Transfer staging directory could not be inspected safely.") from exc


def _reject_existing_symlink_components(candidate: Path) -> None:
    """Reject any existing symlink in the configured staging path chain."""
    candidate = Path(os.path.abspath(os.fspath(candidate)))
    try:
        paths = (candidate, *candidate.parents)
        for current in paths:
            if current.is_symlink():
                raise ValueError("Transfer staging paths must not traverse symbolic links.")
            if current == Path(current.anchor):
                break
    except OSError as exc:
        raise ValueError("Transfer staging path could not be inspected safely.") from exc


def _reject_symlink_components(candidate: Path, root: Path) -> None:
    """Reject any existing symlink between a trusted staging root and a file."""
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Transfer staging path escapes the configured Paxalia transfer root.") from exc
    if not relative.parts:
        raise ValueError("Transfer staging path must identify a file, not a staging directory.")

    current = root
    for component in relative.parts:
        current = current / component
        try:
            if current.is_symlink():
                raise ValueError("Transfer staging paths must not traverse symbolic links.")
        except OSError as exc:
            raise ValueError("Transfer staging path could not be inspected safely.") from exc


def send_root() -> Path:
    return _ensure_staging_directory(transfer_root() / "send")


def send_upload_temp_path(upload_id) -> Path:
    """Return the private resumable-send temp file for one upload session."""
    import uuid

    try:
        parsed = uuid.UUID(str(upload_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Transfer upload id is invalid.") from exc
    return safe_staging_path(send_root() / f".upload-{parsed}")


def receive_root() -> Path:
    return _ensure_staging_directory(transfer_root() / "receive")


def staging_roots() -> tuple[Path, Path]:
    return send_root(), receive_root()


def max_transfer_bytes() -> int:
    mb = get_config().get("TRANSFER_MAX_FILE_SIZE_MB", 2048)
    try:
        mb = int(mb)
    except (TypeError, ValueError):
        mb = 2048
    return max(1, mb) * 1024 * 1024


def chunk_size_bytes() -> int:
    mb = get_config().get("TRANSFER_CHUNK_SIZE_MB", 5)
    try:
        mb = int(mb)
    except (TypeError, ValueError):
        mb = 5
    return max(1, min(mb, 64)) * 1024 * 1024


def max_concurrent_transfers() -> int:
    try:
        return max(1, int(get_config().get("TRANSFER_MAX_CONCURRENT", 3)))
    except (TypeError, ValueError):
        return 3


def max_retries() -> int:
    try:
        return max(0, int(get_config().get("TRANSFER_MAX_RETRIES", 5)))
    except (TypeError, ValueError):
        return 5


def retry_delay_seconds() -> int:
    try:
        return max(1, min(int(get_config().get("TRANSFER_RETRY_DELAY_SECONDS", 2)), 300))
    except (TypeError, ValueError):
        return 2


def expiration_hours() -> int:
    try:
        return max(1, int(get_config().get("TRANSFER_STAGING_TTL_HOURS", 24)))
    except (TypeError, ValueError):
        return 24


def sync_verify_max_bytes() -> int:
    try:
        mb = max(0, int(get_config().get("TRANSFER_SYNC_VERIFY_MAX_MB", 50)))
    except (TypeError, ValueError):
        mb = 50
    return mb * 1024 * 1024


def safe_staging_path(path: str | os.PathLike) -> Path:
    """Return a lexical staging path only when every path component is trusted."""
    try:
        candidate = Path(os.path.abspath(os.path.expanduser(os.fspath(path))))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Transfer staging path is invalid.") from exc

    roots = staging_roots()
    for root in roots:
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        _reject_symlink_components(candidate, root)
        return candidate
    raise ValueError("Transfer staging path escapes the configured Paxalia transfer root.")


def validate_transfer_filename(name: str) -> str:
    """Validate a transfer filename against Server Files and upload policies."""
    from pathlib import PurePath
    from ..conf_uploads import get_upload_allowed_extensions, get_upload_blocked_extensions

    raw = str(name or "").strip()
    if not raw or raw in {".", ".."} or PurePath(raw).name != raw or "/" in raw or "\\" in raw:
        raise ValueError("Transfer filenames must contain a single filename, not a path.")
    blocked = {str(ext).lower() for ext in get_upload_blocked_extensions()}
    allowed = get_upload_allowed_extensions()
    allowed = {str(ext).lower() for ext in allowed} if allowed is not None else None
    lower = raw.lower()
    candidates = blocked | (allowed or set())
    matched = next((ext for ext in sorted(candidates, key=len, reverse=True) if lower.endswith(ext)), None)
    if matched in blocked:
        raise ValueError(f'Files with extension "{matched}" are not allowed.')
    if allowed is not None and matched not in allowed:
        raise ValueError('The selected file extension is not allowed by this deployment.')
    return raw
