"""Configuration and path policy for Paxalia Server Files.

The browser only supplies a root identifier and a relative POSIX path. Every
operation reopens path components relative to a trusted root descriptor with
O_NOFOLLOW; the path resolver is never treated as the sole security control.
"""
from __future__ import annotations

import fnmatch
import os
import re
import stat
from dataclasses import dataclass
from typing import Iterable

from ..settings import get_config
from .exceptions import (
    ServerFilesConfigurationError,
    ServerFilesDenied,
    ServerFilesDisabled,
    ServerFilesInvalidPath,
    ServerFilesUnsupportedPlatform,
)

_ROOT_ID_RE = re.compile(r"^root-[0-9]{1,3}$")
_DEFAULT_SENSITIVE_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.p7b", "*.p8",
    "*.crt", "*.cer", "*.der", "*.jks", "*.keystore", "*.secret", "*.secrets",
    "*.token", "*.credentials", "id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*",
    "authorized_keys", "known_hosts", ".netrc", ".pgpass", ".my.cnf", "credentials",
    "credentials.*", "*.sqlite", "*.sqlite3", "*.db", "local_settings.py",
    "settings_local.py", "settings.py", "settings_*.py", "secrets.json", "secret.json",
    "service-account*.json", "*.tfstate", "*.tfstate.backup",
)
_DEFAULT_SENSITIVE_DIRECTORIES = {
    ".ssh", ".aws", ".azure", ".gcloud", ".kube", ".gnupg", "secrets",
    "secret", "credentials",
}


@dataclass(frozen=True)
class ServerFilesRoot:
    id: str
    name: str
    path: str
    device: int
    inode: int


def config_value(name, default=None):
    return get_config().get(name, default)


def is_enabled() -> bool:
    return bool(config_value("FILE_MANAGER_ENABLED", False))


def _positive_int(name, default, maximum=2_147_483_647):
    value = config_value(name, default)
    if isinstance(value, bool):
        raise ServerFilesConfigurationError(f"Invalid {name} configuration.")
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ServerFilesConfigurationError(f"Invalid {name} configuration.") from None
    if value <= 0 or value > maximum:
        raise ServerFilesConfigurationError(f"Invalid {name} configuration.")
    return value


def limits():
    """Return validated, bounded limits in bytes/counts."""
    return {
        "upload_bytes": _positive_int("FILE_MANAGER_MAX_UPLOAD_SIZE_MB", 100, 1024 * 1024) * 1024 * 1024,
        "download_bytes": _positive_int("FILE_MANAGER_MAX_DOWNLOAD_SIZE_MB", 1024, 1024 * 1024) * 1024 * 1024,
        "preview_bytes": _positive_int("FILE_MANAGER_PREVIEW_MAX_BYTES", 262144, 16 * 1024 * 1024),
        "page_size": _positive_int("FILE_MANAGER_DIRECTORY_PAGE_SIZE", 100, 500),
        "scan_limit": _positive_int("FILE_MANAGER_MAX_DIRECTORY_ENTRIES", 10000, 100000),
        "copy_bytes": _positive_int("FILE_MANAGER_MAX_COPY_SIZE_MB", 100, 1024 * 1024) * 1024 * 1024,
        "rate_limit": _positive_int("FILE_MANAGER_MAX_MUTATIONS_PER_MINUTE", 30, 10000),
        "read_rate_limit": _positive_int("FILE_MANAGER_MAX_READS_PER_MINUTE", 120, 10000),
        "rate_window": _positive_int("FILE_MANAGER_RATE_LIMIT_WINDOW_SECONDS", 60, 3600),
    }


def _supported_dirfd_operations():
    required = (os.open, os.stat, os.mkdir, os.unlink, os.rmdir, os.rename, os.link)
    return (
        os.name == "posix"
        and hasattr(os, "O_NOFOLLOW")
        and hasattr(os, "O_DIRECTORY")
        and all(operation in getattr(os, "supports_dir_fd", set()) for operation in required)
    )


def require_secure_platform():
    if not _supported_dirfd_operations():
        raise ServerFilesUnsupportedPlatform()


def _is_filesystem_root(path):
    absolute = os.path.abspath(path)
    drive, tail = os.path.splitdrive(absolute)
    if drive:
        return tail in (os.sep, "")
    return absolute == os.path.abspath(os.sep)


def get_roots() -> list[ServerFilesRoot]:
    """Resolve configured roots; never invent a default root."""
    if not is_enabled():
        raise ServerFilesDisabled()
    configured = config_value("FILE_MANAGER_ALLOWED_ROOTS", [])
    if not isinstance(configured, (list, tuple)) or not configured:
        return []
    if len(configured) > 32:
        raise ServerFilesConfigurationError("At most 32 filesystem roots may be configured.")

    roots = []
    canonical_paths = []
    for index, item in enumerate(configured):
        if isinstance(item, str):
            name, raw_path = f"Root {index + 1}", item
        elif isinstance(item, dict):
            name = str(item.get("name", f"Root {index + 1}")).strip()
            raw_path = item.get("path")
        else:
            raise ServerFilesConfigurationError("Each allowed root must be a path or a {name, path} mapping.")

        if not name or len(name) > 64 or any(ord(ch) < 32 for ch in name):
            raise ServerFilesConfigurationError("A configured filesystem root has an invalid display name.")
        if not isinstance(raw_path, (str, os.PathLike)) or not os.fspath(raw_path):
            raise ServerFilesConfigurationError("A configured filesystem root must have an absolute path.")
        raw_path = os.fspath(raw_path)
        if not isinstance(raw_path, str):
            raise ServerFilesConfigurationError("Allowed roots must be configured as text paths.")
        if not os.path.isabs(raw_path) or _is_filesystem_root(raw_path):
            raise ServerFilesConfigurationError("Allowed roots must be explicit absolute non-root directories.")
        try:
            raw_absolute = os.path.abspath(raw_path)
            raw_stat = os.lstat(raw_absolute)
            if stat.S_ISLNK(raw_stat.st_mode) or not stat.S_ISDIR(raw_stat.st_mode):
                raise ServerFilesConfigurationError("Every allowed root must be an existing, non-symlink directory.")
            canonical = os.path.realpath(raw_absolute)
            root_stat = os.stat(canonical, follow_symlinks=False)
        except ServerFilesConfigurationError:
            raise
        except (OSError, RuntimeError, ValueError, TypeError):
            raise ServerFilesConfigurationError("A configured filesystem root is unavailable.") from None

        if not stat.S_ISDIR(root_stat.st_mode):
            raise ServerFilesConfigurationError("Every allowed root must be a directory.")
        if is_sensitive((os.path.basename(canonical),)):
            raise ServerFilesConfigurationError(
                "An allowed root cannot itself match the built-in sensitive-path policy."
            )
        for previous in canonical_paths:
            try:
                common = os.path.commonpath([previous, canonical])
            except ValueError:
                common = None
            if common in (previous, canonical):
                raise ServerFilesConfigurationError("Allowed filesystem roots must not overlap or contain one another.")
        canonical_paths.append(canonical)
        roots.append(ServerFilesRoot(
            id=f"root-{index}", name=name, path=canonical,
            device=root_stat.st_dev, inode=root_stat.st_ino,
        ))
    return roots


def get_root(root_id: str, roots: Iterable[ServerFilesRoot] | None = None) -> ServerFilesRoot:
    roots = list(roots if roots is not None else get_roots())
    if not isinstance(root_id, str) or not _ROOT_ID_RE.fullmatch(root_id):
        raise ServerFilesInvalidPath("The selected filesystem root is invalid.")
    for root in roots:
        if root.id == root_id:
            return root
    raise ServerFilesInvalidPath("The selected filesystem root is not configured.")


def split_relative_path(value: str | None, *, allow_empty=True) -> tuple[str, ...]:
    """Validate a canonical relative POSIX path; do not decode it here.

    Percent signs and backslashes are rejected so differently encoded or
    platform-specific path spellings cannot be interpreted as aliases.
    """
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ServerFilesInvalidPath()
    if value == "":
        if allow_empty:
            return ()
        raise ServerFilesInvalidPath()
    if len(value) > 2048 or value.startswith(("/", "\\")):
        raise ServerFilesInvalidPath()
    if "\x00" in value or "%" in value or "\\" in value or ":" in value:
        raise ServerFilesInvalidPath()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ServerFilesInvalidPath()
    parts = tuple(value.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        raise ServerFilesInvalidPath()
    for part in parts:
        _validate_name(part)
    return parts


def _validate_name(value: str) -> str:
    if not isinstance(value, str) or not value or value in (".", ".."):
        raise ServerFilesInvalidPath("A single, non-empty filename is required.")
    if len(os.fsencode(value)) > 255:
        raise ServerFilesInvalidPath("The filename is too long.")
    if any(ch in value for ch in ("/", "\\", "\x00", "%", ":")):
        raise ServerFilesInvalidPath("The filename contains an unsupported character.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ServerFilesInvalidPath("The filename contains a control character.")
    if value.endswith((".", " ")):
        raise ServerFilesInvalidPath("Filenames ending in a dot or space are not supported.")
    return value


def validate_name(value: str) -> str:
    return _validate_name(value)


def _denied_prefixes(root: ServerFilesRoot):
    denied = config_value("FILE_MANAGER_DENIED_PATHS", [])
    if not isinstance(denied, (list, tuple)):
        raise ServerFilesConfigurationError("FILE_MANAGER_DENIED_PATHS must be a list or tuple.")
    prefixes = []
    for item in denied:
        if not isinstance(item, (str, os.PathLike)):
            raise ServerFilesConfigurationError("Denied paths must be strings.")
        value = os.fspath(item)
        if not isinstance(value, str):
            raise ServerFilesConfigurationError("Denied paths must be configured as text paths.")
        if not value:
            continue
        if os.path.isabs(value):
            try:
                candidate = os.path.realpath(os.path.abspath(value))
                common = os.path.commonpath([root.path, candidate])
            except (OSError, ValueError, TypeError):
                continue
            if common != root.path:
                continue
            relative = os.path.relpath(candidate, root.path)
            if relative == ".":
                prefixes.append(())
            else:
                prefixes.append(split_relative_path(relative.replace(os.sep, "/")))
        else:
            prefixes.append(split_relative_path(value))
    return prefixes


def is_denied(root: ServerFilesRoot, parts: tuple[str, ...]) -> bool:
    for prefix in _denied_prefixes(root):
        if len(parts) >= len(prefix) and parts[:len(prefix)] == prefix:
            return True
    return False


def _sensitive_patterns():
    """Return built-in protections plus any host-specific additions.

    A host may strengthen this policy, but cannot accidentally replace the
    package's baseline secret patterns by supplying a shorter list.
    """
    configured = config_value("FILE_MANAGER_SENSITIVE_PATTERNS", None)
    if configured is None:
        return _DEFAULT_SENSITIVE_PATTERNS
    if not isinstance(configured, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in configured):
        raise ServerFilesConfigurationError("FILE_MANAGER_SENSITIVE_PATTERNS must contain non-empty strings.")
    return tuple(_DEFAULT_SENSITIVE_PATTERNS) + tuple(item.strip().casefold() for item in configured)


def is_sensitive(parts: tuple[str, ...]) -> bool:
    patterns = _sensitive_patterns()
    for component in parts:
        folded = component.casefold()
        if folded in _DEFAULT_SENSITIVE_DIRECTORIES:
            return True
        if any(fnmatch.fnmatchcase(folded, pattern) for pattern in patterns):
            return True
    return False


def has_capability(user, codename: str) -> bool:
    """Return a current Django permission result without stale user caches.

    Django's ``has_perm()`` result is cached on the User instance after the
    first check. Server Files operations can occur after permissions are
    granted/revoked on that same instance (notably in tests and long-lived
    admin request flows), so clear the permission caches before consulting
    Django's authoritative permission backend.
    """
    if getattr(user, "is_superuser", False):
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if hasattr(user, "is_active") and not user.is_active:
        return False

    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        try:
            delattr(user, cache_name)
        except AttributeError:
            pass

    try:
        return bool(user.has_perm(f"paxalia.{codename}"))
    except (AttributeError, TypeError, ValueError):
        return False


def assert_path_allowed(root: ServerFilesRoot, parts: tuple[str, ...], user, *, write=False):
    if is_denied(root, parts):
        raise ServerFilesDenied()
    sensitive = is_sensitive(parts)
    if sensitive and not has_capability(user, "view_sensitive_files"):
        raise ServerFilesDenied()
    if write and sensitive:
        if not bool(config_value("FILE_MANAGER_ALLOW_SENSITIVE_MUTATIONS", False)):
            raise ServerFilesDenied("Sensitive filesystem mutations are disabled by policy.")
        if not has_capability(user, "modify_sensitive_files"):
            raise ServerFilesDenied("You do not have permission to modify protected files.")
    return sensitive


def maximum_operation_records():
    return _positive_int("FILE_MANAGER_MAX_OPERATION_RECORDS", 20000, 10_000_000)


def operation_retention_days():
    return _positive_int("FILE_MANAGER_OPERATION_RETENTION_DAYS", 90, 36500)


def cleanup_batch_size():
    return _positive_int("FILE_MANAGER_CLEANUP_BATCH_SIZE", 500, 10000)
