"""Bounded, descriptor-relative filesystem operations for Paxalia Server Files.

No shell is invoked. User paths are relative to explicitly configured roots.
All directory and file opens reject symlinks and are performed relative to an
already-open directory descriptor (POSIX platforms with dir_fd support only).
"""
from __future__ import annotations

import codecs
import ctypes
import errno
import json
import mimetypes
from functools import lru_cache
import re
import os
try:
    import pwd
    import grp
except ImportError:  # pragma: no cover - non-POSIX hosts
    pwd = None
    grp = None
import stat
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime

from django.utils import timezone

from .exceptions import (
    ServerFilesAlreadyExists,
    ServerFilesBinaryFile,
    ServerFilesDenied,
    ServerFilesInvalidPath,
    ServerFilesNotDirectory,
    ServerFilesNotFound,
    ServerFilesNotRegularFile,
    ServerFilesTooLarge,
    ServerFilesUnsupportedPreview,
)
from .policy import (
    ServerFilesRoot,
    assert_path_allowed,
    config_value,
    get_root,
    get_roots,
    limits,
    require_secure_platform,
    split_relative_path,
    validate_name,
    has_capability,
)
from ..logging.redaction import redact_text

_FLAG_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_FLAG_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_FLAG_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_READ_CHUNK = 1024 * 1024
_PREVIEW_SECRET_KEYS = (
    "api_token", "access_key", "secret_access_key", "database_url", "db_url",
    "connection_string", "django_secret_key", "signing_key", "webhook_secret",
)
_PREVIEW_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(?P<prefix>^[ \t]*(?:[\"']?(?:[A-Z0-9_.-]*(?:AUTHORIZATION|PASSWORD|PASSWD|SECRET|TOKEN|API[_-]?KEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET|CREDENTIAL|DATABASE[_-]?URL|DB[_-]?URL|CONNECTION[_-]?STRING)[A-Z0-9_.-]*)[\"']?)\s*[:=]\s*)"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;#}\]]+)"
)


@contextmanager
def _open_root(root: ServerFilesRoot):
    require_secure_platform()
    flags = os.O_RDONLY | _FLAG_DIRECTORY | _FLAG_NOFOLLOW | _FLAG_CLOEXEC
    try:
        fd = os.open(root.path, flags)
    except OSError as error:
        _raise_filesystem_error(error)
    try:
        current = os.fstat(fd)
        if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (root.device, root.inode):
            raise ServerFilesDenied("The configured filesystem root changed after validation.")
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _open_directory(root: ServerFilesRoot, parts: tuple[str, ...]):
    with _open_root(root) as root_fd:
        fd = os.dup(root_fd)
    try:
        for component in parts:
            try:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | _FLAG_DIRECTORY | _FLAG_NOFOLLOW | _FLAG_CLOEXEC,
                    dir_fd=fd,
                )
            except OSError as error:
                if error.errno == errno.ENOTDIR:
                    # Linux can report ENOTDIR for O_NOFOLLOW|O_DIRECTORY when
                    # an intermediate component is a symlink to a directory.
                    # Distinguish that security violation from an ordinary file
                    # encountered where a directory was required. The actual
                    # open remains protected by O_NOFOLLOW, so this check is
                    # only for stable error classification, not path safety.
                    try:
                        entry_stat = os.stat(component, dir_fd=fd, follow_symlinks=False)
                    except OSError:
                        _raise_filesystem_error(error)
                    if stat.S_ISLNK(entry_stat.st_mode):
                        raise ServerFilesDenied(
                            "Symbolic links are not available through Server Files."
                        ) from None
                _raise_filesystem_error(error)
            os.close(fd)
            fd = next_fd
        current = os.fstat(fd)
        if not stat.S_ISDIR(current.st_mode):
            raise ServerFilesNotDirectory()
        yield fd
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


@contextmanager
def _open_parent(root: ServerFilesRoot, parts: tuple[str, ...]):
    if not parts:
        raise ServerFilesInvalidPath("A filename is required for this operation.")
    with _open_directory(root, parts[:-1]) as parent_fd:
        yield parent_fd, parts[-1]


def _raise_filesystem_error(error: OSError):
    if error.errno in (errno.ENOENT, errno.ENOTDIR):
        if error.errno == errno.ENOTDIR:
            raise ServerFilesNotDirectory() from None
        raise ServerFilesNotFound() from None
    if error.errno == errno.EEXIST:
        raise ServerFilesAlreadyExists() from None
    if error.errno in (errno.ELOOP, errno.EACCES, errno.EPERM):
        raise ServerFilesDenied() from None
    if error.errno in (errno.EISDIR, errno.ENXIO):
        raise ServerFilesNotRegularFile() from None
    raise ServerFilesDenied("The filesystem rejected this operation.") from None


def _safe_stat(parent_fd, name):
    try:
        result = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        _raise_filesystem_error(error)
    if stat.S_ISLNK(result.st_mode):
        raise ServerFilesDenied("Symbolic links are not available through Server Files.")
    return result


@contextmanager
def _open_regular_file(root, parts, *, write=False, exclusive=False):
    with _open_parent(root, parts) as (parent_fd, name):
        flags = (os.O_WRONLY if write else os.O_RDONLY) | _FLAG_NOFOLLOW | _FLAG_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
        if exclusive:
            flags |= os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(name, flags, 0o640, dir_fd=parent_fd)
        except OSError as error:
            _raise_filesystem_error(error)
        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ServerFilesNotRegularFile()
            yield fd, file_stat
        finally:
            os.close(fd)


@lru_cache(maxsize=2048)
def _owner_name(uid):
    try:
        return pwd.getpwuid(uid).pw_name if pwd is not None else str(uid)
    except (KeyError, ImportError, AttributeError, OSError):
        return str(uid)


@lru_cache(maxsize=2048)
def _group_name(gid):
    try:
        return grp.getgrgid(gid).gr_name if grp is not None else str(gid)
    except (KeyError, ImportError, AttributeError, OSError):
        return str(gid)


def _entry_record(name, file_stat, root_id, parts):
    mode = file_stat.st_mode
    if stat.S_ISDIR(mode):
        kind = "directory"
    elif stat.S_ISREG(mode):
        kind = "file"
    elif stat.S_ISLNK(mode):
        kind = "symlink"
    else:
        kind = "special"
    content_type, _encoding = mimetypes.guess_type(name, strict=False)
    return {
        "name": name,
        "path": "/".join((*parts, name)),
        "kind": kind,
        "is_directory": kind == "directory",
        "is_regular_file": kind == "file",
        "can_preview": kind == "file" and _preview_extension_allowed(name),
        "size": file_stat.st_size if kind == "file" else None,
        "modified": datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.get_current_timezone()),
        "permissions": format(stat.S_IMODE(mode), "04o"),
        "owner": _owner_name(file_stat.st_uid),
        "group": _group_name(file_stat.st_gid),
        "content_type": content_type or "application/octet-stream",
        "root_id": root_id,
    }


def _preview_extension_allowed(name):
    configured = config_value("FILE_MANAGER_PREVIEW_EXTENSIONS", None)
    if configured is None:
        configured = (".txt", ".json", ".csv", ".md", ".yaml", ".yml", ".log", ".py", ".html", ".htm", ".xml", ".toml", ".ini", ".cfg", ".conf", ".sql", ".css", ".js")
    if not isinstance(configured, (list, tuple)):
        return False
    suffix = os.path.splitext(name.casefold())[1]
    allowed = {str(ext).casefold() for ext in configured if isinstance(ext, str)}
    return suffix in allowed


def _entry_sort_key(item, sort_by):
    if sort_by == "size":
        value = item["size"] if item["size"] is not None else -1
    elif sort_by == "modified":
        value = item["modified"].timestamp()
    elif sort_by == "type":
        value = (item["content_type"], item["kind"])
    else:
        value = item["name"].casefold()
    return (not item["is_directory"], value, item["name"].casefold())


def list_directory(root_id, path, user, *, page=1, search="", sort_by="name", direction="asc", show_hidden=False, show_sensitive=False):
    if not has_capability(user, "view_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to view Paxalia Server Files.")
    roots = get_roots()
    root = get_root(root_id, roots)
    parts = split_relative_path(path)
    assert_path_allowed(root, parts, user)
    search = str(search or "")[:128].strip().casefold()
    sort_by = sort_by if sort_by in {"name", "type", "size", "modified"} else "name"
    reverse = direction == "desc"
    limit_config = limits()
    page_size = limit_config["page_size"]
    scan_limit = limit_config["scan_limit"]
    allow_hidden = bool(config_value("FILE_MANAGER_ALLOW_HIDDEN", False))
    show_hidden = bool(show_hidden and allow_hidden)

    items = []
    truncated = False
    with _open_directory(root, parts) as directory_fd:
        try:
            with os.scandir(directory_fd) as entries:
                scanned = 0
                for entry in entries:
                    scanned += 1
                    if scanned > scan_limit:
                        truncated = True
                        break
                    name = entry.name
                    if not isinstance(name, str) or name in (".", ".."):
                        continue
                    if name.startswith(".") and not show_hidden:
                        continue
                    if search and search not in name.casefold():
                        continue
                    child_parts = (*parts, name)
                    # Denied entries are omitted rather than disclosed in the listing.
                    from .policy import is_denied, is_sensitive
                    if is_denied(root, child_parts):
                        continue
                    sensitive = is_sensitive(child_parts)
                    if sensitive and (
                        not show_sensitive
                        or not has_capability(user, "view_sensitive_files")
                    ):
                        continue
                    try:
                        entry_stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        # A concurrently removed entry is not a fatal listing error.
                        continue
                    items.append(_entry_record(name, entry_stat, root.id, parts))
        except OSError as error:
            _raise_filesystem_error(error)

    items.sort(key=lambda item: _entry_sort_key(item, sort_by), reverse=reverse)
    try:
        page = max(1, int(page))
    except (TypeError, ValueError, OverflowError):
        page = 1
    total = len(items)
    page_count = max(1, (total + page_size - 1) // page_size)
    page = min(page, page_count)
    start = (page - 1) * page_size
    return {
        "root": root,
        "path": "/".join(parts),
        "parts": parts,
        "items": items[start:start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": page_count,
        "truncated": truncated,
        "search": search,
        "sort_by": sort_by,
        "direction": "desc" if reverse else "asc",
        "show_hidden": show_hidden,
        "hidden_allowed": allow_hidden,
        "show_sensitive": bool(show_sensitive),
    }


def get_metadata(root_id, path, user):
    if not has_capability(user, "view_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to view Paxalia Server Files.")
    roots = get_roots()
    root = get_root(root_id, roots)
    parts = split_relative_path(path, allow_empty=False)
    assert_path_allowed(root, parts, user)
    with _open_parent(root, parts) as (parent_fd, name):
        file_stat = _safe_stat(parent_fd, name)
        return _entry_record(name, file_stat, root.id, parts[:-1])


class _BoundedFileReader:
    """File-like wrapper that never streams beyond the authorized byte count."""
    def __init__(self, wrapped, byte_limit):
        self._wrapped = wrapped
        self._remaining = max(0, int(byte_limit))

    def read(self, size=-1):
        if self._remaining <= 0:
            return b""
        if size is None or size < 0 or size > self._remaining:
            size = self._remaining
        chunk = self._wrapped.read(size)
        self._remaining -= len(chunk)
        return chunk

    def close(self):
        self._wrapped.close()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def open_download(root_id, path, user):
    if not has_capability(user, "download_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to download Server Files.")
    roots = get_roots()
    root = get_root(root_id, roots)
    parts = split_relative_path(path, allow_empty=False)
    assert_path_allowed(root, parts, user)
    with _open_regular_file(root, parts) as (fd, file_stat):
        if file_stat.st_size > limits()["download_bytes"]:
            raise ServerFilesTooLarge()
        # Return a separately-owned descriptor so the caller can stream it.
        stream = os.fdopen(os.dup(fd), "rb")
        return _BoundedFileReader(stream, file_stat.st_size), file_stat, parts[-1], root


def _normalised_secret_key(value):
    key = re.sub(r"[^a-z0-9]", "", str(value).casefold())
    markers = (
        "authorization", "proxyauthorization", "cookie", "setcookie", "password",
        "passwd", "secret", "token", "apikey", "accesskey", "privatekey",
        "clientsecret", "credential", "databaseurl", "dburl", "connectionstring",
        "signingkey", "sessionkey", "csrf",
    )
    return any(marker in key for marker in markers)


def _redact_json_value(value, *, depth=0, budget=None):
    """Boundedly redact JSON objects without dropping long ordinary values."""
    if budget is None:
        budget = [10000]
    if depth > 20:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            budget[0] -= 1
            if budget[0] < 0:
                result["_paxalia_truncated"] = True
                break
            key_text = str(key)[:200]
            if _normalised_secret_key(key_text):
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = _redact_json_value(item, depth=depth + 1, budget=budget)
        return result
    if isinstance(value, list):
        result = []
        for item in value[:10000]:
            budget[0] -= 1
            if budget[0] < 0:
                result.append("[TRUNCATED_ITEMS]")
                break
            result.append(_redact_json_value(item, depth=depth + 1, budget=budget))
        if len(value) > len(result):
            result.append("[TRUNCATED_ITEMS]")
        return result
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return "[UNSUPPORTED_VALUE]"


def _redact_preview(content, filename):
    """Redact credential-shaped content before it reaches the browser.

    Valid JSON receives structural key-based redaction. Other supported text
    receives the shared Paxalia inline-secret redaction plus conservative
    line-based assignment and YAML block redaction. The caller has already
    bounded bytes before this function is called.
    """
    suffix = os.path.splitext(filename.casefold())[1]
    if suffix == ".json":
        try:
            parsed = json.loads(content)
        except RecursionError:
            return "[Preview withheld because the JSON structure is too deeply nested.]"
        except (TypeError, ValueError):
            # A malformed or truncated JSON document cannot be safely
            # structurally redacted. Withhold it rather than falling back to
            # displaying a possibly unredacted one-line object.
            return "[Preview withheld because the JSON document is incomplete or invalid.]"
        else:
            try:
                cleaned = _redact_json_value(parsed)
                return json.dumps(cleaned, ensure_ascii=False, indent=2)
            except Exception:
                # Never fall back to showing an unredacted JSON document when
                # structural sanitization unexpectedly fails.
                return "[Preview withheld because safe redaction failed.]"

    content = redact_text(content)
    safe_lines = []
    block_indent = None
    for line in content.splitlines(keepends=True):
        ending = ""
        body = line
        if body.endswith("\r\n"):
            body, ending = body[:-2], "\r\n"
        elif body.endswith(("\n", "\r")):
            body, ending = body[:-1], body[-1:]

        indent = len(body) - len(body.lstrip(" \t"))
        if block_indent is not None:
            if not body.strip() or indent > block_indent:
                safe_lines.append((body[:indent] + "[REDACTED]" if body.strip() else body) + ending)
                continue
            block_indent = None

        match = _PREVIEW_SECRET_ASSIGNMENT_RE.match(body)
        if match:
            value = match.group("value")
            if value in ("|", ">", "|-", ">-", "|+", ">+"):
                block_indent = indent
                value = "[REDACTED]"
            elif value.startswith("\"") and value.endswith("\""):
                value = '"[REDACTED]"'
            elif value.startswith("'") and value.endswith("'"):
                value = "'[REDACTED]'"
            else:
                value = "[REDACTED]"
            body = match.group("prefix") + value
        safe_lines.append(body + ending)
    return "".join(safe_lines)


def preview_file(root_id, path, user):
    if not has_capability(user, "view_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to view Paxalia Server Files.")
    roots = get_roots()
    root = get_root(root_id, roots)
    parts = split_relative_path(path, allow_empty=False)
    assert_path_allowed(root, parts, user)
    name = parts[-1]
    if not _preview_extension_allowed(name):
        raise ServerFilesUnsupportedPreview()
    max_bytes = limits()["preview_bytes"]
    with _open_regular_file(root, parts) as (fd, file_stat):
        sample = os.read(fd, min(max_bytes + 1, max(file_stat.st_size, 1)))
    utf16_bom = sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))
    if not utf16_bom:
        if b"\x00" in sample[:8192]:
            raise ServerFilesBinaryFile()
        controls = sum(1 for value in sample[:8192] if value < 9 or 13 < value < 32)
        if sample[:8192] and controls / min(len(sample), 8192) > 0.10:
            raise ServerFilesBinaryFile()
    truncated = file_stat.st_size > max_bytes or len(sample) > max_bytes
    sample = sample[:max_bytes]
    if utf16_bom:
        content = sample.decode("utf-16", errors="replace")
        encoding = "UTF-16"
    else:
        try:
            content = sample.decode("utf-8-sig")
            encoding = "UTF-8"
        except UnicodeDecodeError:
            content = sample.decode("latin-1", errors="replace")
            encoding = "Latin-1 fallback"
    content = _redact_preview(content, name)
    return {
        "root": root,
        "path": "/".join(parts),
        "filename": name,
        "content": content,
        "encoding": encoding,
        "truncated": truncated,
        "size": file_stat.st_size,
        "preview_limit": max_bytes,
    }


def create_directory(root_id, path, name, user):
    if not has_capability(user, "modify_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to modify Server Files.")
    root = get_root(root_id)
    parts = split_relative_path(path)
    name = validate_name(name)
    assert_path_allowed(root, (*parts, name), user, write=True)
    with _open_directory(root, parts) as parent_fd:
        try:
            os.mkdir(name, mode=0o750, dir_fd=parent_fd)
        except OSError as error:
            _raise_filesystem_error(error)
        os.fsync(parent_fd)
    return {"root": root, "path": "/".join((*parts, name))}


def upload_file(root_id, path, name, uploaded_file, user):
    if not has_capability(user, "upload_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to upload Server Files.")
    root = get_root(root_id)
    parts = split_relative_path(path)
    name = validate_name(name)
    target_parts = (*parts, name)
    assert_path_allowed(root, target_parts, user, write=True)
    max_bytes = limits()["upload_bytes"]
    declared_size = getattr(uploaded_file, "size", None)
    if declared_size is None or declared_size < 0 or declared_size > max_bytes:
        raise ServerFilesTooLarge()

    temp_name = f".paxalia-upload-{uuid.uuid4().hex}.part"
    created = False
    with _open_directory(root, parts) as parent_fd:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAG_NOFOLLOW | _FLAG_CLOEXEC
        try:
            fd = os.open(temp_name, flags, 0o640, dir_fd=parent_fd)
            created = True
            written = 0
            try:
                for chunk in uploaded_file.chunks(chunk_size=_READ_CHUNK):
                    written += len(chunk)
                    if written > max_bytes or written > declared_size:
                        raise ServerFilesTooLarge()
                    view = memoryview(chunk)
                    while view:
                        count = os.write(fd, view)
                        if count <= 0:
                            raise OSError(errno.EIO, "write failed")
                        view = view[count:]
                if written != declared_size:
                    raise ServerFilesInvalidPath("The uploaded file size did not match its declared size.")
                os.fsync(fd)
                os.fchmod(fd, 0o640)
            finally:
                os.close(fd)
            try:
                os.link(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
            except OSError as error:
                _raise_filesystem_error(error)
            os.unlink(temp_name, dir_fd=parent_fd)
            created = False
            os.fsync(parent_fd)
        finally:
            if created:
                try:
                    os.unlink(temp_name, dir_fd=parent_fd)
                except OSError:
                    pass
    return {"root": root, "path": "/".join(target_parts), "size": written}


def _rename_noreplace(src_fd, src_name, dst_fd, dst_name):
    """Use Linux renameat2(RENAME_NOREPLACE); fail closed if unavailable."""
    if not sys.platform.startswith("linux"):
        raise ServerFilesDenied("Safe no-overwrite rename is unavailable on this platform.")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise ServerFilesDenied("Safe no-overwrite rename is unavailable on this platform.")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(src_fd, os.fsencode(src_name), dst_fd, os.fsencode(dst_name), 1)  # RENAME_NOREPLACE
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise ServerFilesAlreadyExists()
    if error_number in (errno.EXDEV, errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP):
        raise ServerFilesDenied("The filesystem cannot perform this safe move.")
    _raise_filesystem_error(OSError(error_number, os.strerror(error_number)))


def rename_or_move(root_id, path, destination_root_id, destination_path, name, user):
    if not has_capability(user, "modify_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to modify Server Files.")
    src_root = get_root(root_id)
    dst_root = get_root(destination_root_id)
    src_parts = split_relative_path(path, allow_empty=False)
    dst_parts = split_relative_path(destination_path)
    new_name = validate_name(name)
    assert_path_allowed(src_root, src_parts, user, write=True)
    assert_path_allowed(dst_root, (*dst_parts, new_name), user, write=True)

    with _open_parent(src_root, src_parts) as (src_fd, src_name):
        source_stat = _safe_stat(src_fd, src_name)
        if not (stat.S_ISREG(source_stat.st_mode) or stat.S_ISDIR(source_stat.st_mode)):
            raise ServerFilesNotRegularFile()
        if stat.S_ISDIR(source_stat.st_mode) and src_root.id == dst_root.id:
            if len(dst_parts) >= len(src_parts) and dst_parts[:len(src_parts)] == src_parts:
                raise ServerFilesInvalidPath("A directory cannot be moved into itself or one of its descendants.")
        with _open_directory(dst_root, dst_parts) as dst_fd:
            try:
                _rename_noreplace(src_fd, src_name, dst_fd, new_name)
                os.fsync(src_fd)
                if dst_fd != src_fd:
                    os.fsync(dst_fd)
            except OSError as error:
                _raise_filesystem_error(error)
    return {
        "root": dst_root,
        "path": "/".join((*dst_parts, new_name)),
        "source_path": "/".join(src_parts),
    }


def copy_file(root_id, path, destination_root_id, destination_path, name, user):
    if not has_capability(user, "modify_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to modify Server Files.")
    src_root = get_root(root_id)
    dst_root = get_root(destination_root_id)
    src_parts = split_relative_path(path, allow_empty=False)
    dst_parts = split_relative_path(destination_path)
    new_name = validate_name(name)
    # Copying a protected source is an effective disclosure/replication
    # operation; require the same explicit sensitive-mutation policy as writes.
    assert_path_allowed(src_root, src_parts, user, write=True)
    assert_path_allowed(dst_root, (*dst_parts, new_name), user, write=True)
    max_bytes = limits()["copy_bytes"]

    with _open_regular_file(src_root, src_parts) as (src_fd, source_stat):
        if source_stat.st_size > max_bytes:
            raise ServerFilesTooLarge("The file exceeds the configured copy size limit.")
        temp_name = f".paxalia-copy-{uuid.uuid4().hex}.part"
        created = False
        with _open_directory(dst_root, dst_parts) as dst_dir_fd:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAG_NOFOLLOW | _FLAG_CLOEXEC
            try:
                dst_fd = os.open(temp_name, flags, 0o640, dir_fd=dst_dir_fd)
                created = True
                copied = 0
                try:
                    while True:
                        chunk = os.read(src_fd, _READ_CHUNK)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > max_bytes:
                            raise ServerFilesTooLarge("The file exceeds the configured copy size limit.")
                        view = memoryview(chunk)
                        while view:
                            count = os.write(dst_fd, view)
                            if count <= 0:
                                raise OSError(errno.EIO, "write failed")
                            view = view[count:]
                    current_source = os.fstat(src_fd)
                    if (
                        copied != source_stat.st_size
                        or (current_source.st_dev, current_source.st_ino, current_source.st_size,
                            current_source.st_mtime_ns, current_source.st_ctime_ns)
                        != (source_stat.st_dev, source_stat.st_ino, source_stat.st_size,
                            source_stat.st_mtime_ns, source_stat.st_ctime_ns)
                    ):
                        raise ServerFilesInvalidPath("The source file changed while it was being copied.")
                    os.fsync(dst_fd)
                    os.fchmod(dst_fd, 0o640)
                finally:
                    os.close(dst_fd)
                try:
                    os.link(temp_name, new_name, src_dir_fd=dst_dir_fd, dst_dir_fd=dst_dir_fd, follow_symlinks=False)
                except OSError as error:
                    _raise_filesystem_error(error)
                os.unlink(temp_name, dir_fd=dst_dir_fd)
                created = False
                os.fsync(dst_dir_fd)
            finally:
                if created:
                    try:
                        os.unlink(temp_name, dir_fd=dst_dir_fd)
                    except OSError:
                        pass
    return {"root": dst_root, "path": "/".join((*dst_parts, new_name)), "size": copied}


def delete_item(root_id, path, user):
    if not has_capability(user, "delete_server_files"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to delete Server Files.")
    root = get_root(root_id)
    parts = split_relative_path(path, allow_empty=False)
    assert_path_allowed(root, parts, user, write=True)
    with _open_parent(root, parts) as (parent_fd, name):
        file_stat = _safe_stat(parent_fd, name)
        try:
            if stat.S_ISDIR(file_stat.st_mode):
                # Deliberately non-recursive: large tree deletion belongs in a
                # bounded background workflow, not an ordinary HTTP request.
                os.rmdir(name, dir_fd=parent_fd)
            elif stat.S_ISREG(file_stat.st_mode):
                os.unlink(name, dir_fd=parent_fd)
            else:
                raise ServerFilesNotRegularFile()
            os.fsync(parent_fd)
        except OSError as error:
            if error.errno == errno.ENOTEMPTY:
                raise ServerFilesDenied("Only empty directories can be deleted from Server Files.") from None
            _raise_filesystem_error(error)
    return {"root": root, "path": "/".join(parts)}
