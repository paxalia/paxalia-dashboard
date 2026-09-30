"""Bounded Transfer Center orchestration built on Paxalia's existing upload engine."""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import stat
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from ..alerts import send_alert
from ..models import FileUpload, PaxaliaTransfer
from ..server_files import service as server_files_service
from ..server_files.exceptions import (
    ServerFilesAlreadyExists,
    ServerFilesConfigurationError,
    ServerFilesDenied,
    ServerFilesDisabled,
    ServerFilesInvalidPath,
    ServerFilesNotFound,
)
from ..server_files.policy import (
    assert_path_allowed,
    get_root,
    get_roots,
    has_capability,
    split_relative_path,
    validate_name,
)
from ..settings import get_config
from .models import PaxaliaTransferLock
from .policy import (
    chunk_size_bytes,
    expiration_hours,
    max_concurrent_transfers,
    max_retries,
    max_transfer_bytes,
    retry_delay_seconds,
    safe_staging_path,
    send_root,
    send_upload_temp_path,
    transfer_exchange_root,
    sync_verify_max_bytes,
    transfer_enabled,
    validate_transfer_filename,
)

_READ_SIZE = 1024 * 1024
logger = logging.getLogger(__name__)


def _log_unexpected(operation, exc, *, transfer_id=None):
    """Record an unexpected transfer error without exposing internal details."""
    extra = {"error_class": type(exc).__name__}
    if transfer_id:
        extra["transfer_id"] = str(transfer_id)
    logger.error("Paxalia Transfer Center %s failed", operation, extra=extra)


_ACTIVE_STATUSES = {"queued", "preparing", "transferring", "paused", "interrupted", "verifying"}
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "expired"}


def _notify_transfer(transfer, action):
    try:
        label = f"{transfer.filename} ({transfer.direction})"
        if action == "completed":
            send_alert(
                f"Transfer completed: {transfer.filename}",
                f"Paxalia Transfer Center completed {label} with verified integrity.",
                category="general",
                site=None,
                dedupe_key=f"transfer:{transfer.pk}:completed",
            )
        elif action == "failed":
            send_alert(
                f"Transfer failed: {transfer.filename}",
                f"Paxalia Transfer Center marked {label} as failed: {transfer.error_message[:300]}",
                category="general",
                site=None,
                dedupe_key=f"transfer:{transfer.pk}:failed",
            )
    except Exception:
        # Notification delivery must never change transfer correctness.
        pass


def ensure_enabled():
    if not transfer_enabled():
        raise PermissionDenied("Paxalia Transfer Center is disabled.")


def _check_capability(user, codename: str):
    if not has_capability(user, codename):
        raise PermissionDenied("You do not have permission to perform this transfer operation.")


def _safe_filename(name: str) -> str:
    raw = validate_transfer_filename(name)
    return validate_name(raw)


def _staging_filename(file_id: uuid.UUID, filename: str) -> Path:
    return send_root() / f"{file_id}_{_safe_filename(filename)}"


def _cleanup_staging(path):
    if not path:
        return
    try:
        safe_staging_path(path).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def _cleanup_send_upload_temp(upload_id):
    if not upload_id:
        return
    try:
        send_upload_temp_path(upload_id).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def _sync_transfer_upload_state(upload, *, status=None, error_message=None, clear_storage=False):
    """Keep a transfer-owned FileUpload row aligned with transfer lifecycle."""
    if upload is None or getattr(upload, "purpose", "release") != "transfer_send":
        return
    update_fields = []
    if status is not None and upload.status != status:
        upload.status = status
        update_fields.append("status")
    if error_message is not None:
        message = str(error_message)[:500]
        if upload.error_message != message:
            upload.error_message = message
            update_fields.append("error_message")
    if clear_storage and upload.storage_path:
        upload.storage_path = ""
        update_fields.append("storage_path")
    if status == "failed" and upload.completed_at is not None:
        upload.completed_at = None
        update_fields.append("completed_at")
    if update_fields:
        update_fields.append("updated_at")
        upload.save(update_fields=update_fields)


def _normalize_checksum(value, *, optional=True):
    checksum = str(value or "").strip().lower()
    if not checksum and optional:
        return ""
    if len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
        raise ValueError("A valid SHA-256 checksum is required.")
    return checksum


def _valid_chunk_indexes(transfer, chunk_indexes):
    valid = set()
    for raw_index in chunk_indexes or []:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 0 <= index < transfer.total_chunks:
            valid.add(index)
    return valid


def _received_bytes(transfer, chunk_indexes):
    total = 0
    for index in _valid_chunk_indexes(transfer, chunk_indexes):
        start = index * transfer.chunk_size
        total += min(transfer.chunk_size, max(0, transfer.size - start))
    return min(transfer.size, total)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags)
    try:
        with os.fdopen(fd, "rb", closefd=False) as handle:
            while True:
                chunk = handle.read(_READ_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
    finally:
        os.close(fd)
    return digest.hexdigest()



def _hash_server_file(root, parts):
    """Hash one authorized server file without loading it into memory."""
    digest = hashlib.sha256()
    with server_files_service._open_regular_file(root, parts) as (fd, _file_stat):
        while True:
            chunk = os.read(fd, _READ_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _hash_fd(fd) -> str:
    """Hash bytes from an already-open regular-file descriptor."""
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, _READ_SIZE)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _resolve_server_target(root_id: str, relative_path: str, name: str, user, *, write=True):
    """Legacy resolver retained only for non-transfer callers/tests.

    Transfer Center must never call this function: its destination/source is
    always the fixed configured exchange directory.
    """
    root = get_root(root_id)
    parts = split_relative_path(relative_path, allow_empty=True)
    name = _safe_filename(name)
    assert_path_allowed(root, (*parts, name), user, write=write)
    return root, parts, name


def _resolve_bound_transfer_path(transfer, user, *, write=False):
    """Resolve a persisted transfer path only when it is bound to the current exchange.

    New Transfer Center rows are created against the fixed exchange directory.
    Older rows can still exist after an upgrade, so resume/finalize/read paths
    must not trust their historical ``server_relative_path`` blindly.
    """
    try:
        root, folder_parts = _resolve_transfer_exchange(user, write=write)
    except (ServerFilesConfigurationError, ServerFilesDisabled, ServerFilesDenied, ValueError):
        raise PermissionDenied("The transfer path is no longer authorized by the transfer exchange policy.") from None
    try:
        stored_root = get_root(transfer.server_root_id)
        stored_parts = split_relative_path(transfer.server_relative_path, allow_empty=False)
        expected_name = _safe_filename(transfer.filename)
    except (ServerFilesInvalidPath, ServerFilesConfigurationError, ServerFilesDenied, ServerFilesDisabled, ValueError):
        raise PermissionDenied("The transfer path is no longer authorized by the transfer exchange policy.") from None

    if stored_root.id != root.id:
        raise PermissionDenied("The transfer path is no longer authorized by the transfer exchange policy.")
    if len(stored_parts) != len(folder_parts) + 1:
        raise PermissionDenied("The transfer path is no longer authorized by the transfer exchange policy.")
    if tuple(stored_parts[:-1]) != tuple(folder_parts) or stored_parts[-1] != expected_name:
        raise PermissionDenied("The transfer path is no longer authorized by the transfer exchange policy.")

    assert_path_allowed(root, stored_parts, user, write=write)
    return root, stored_parts


def _resolve_transfer_exchange(user, *, write=False):
    """Resolve the fixed operator exchange directory through Server Files policy."""
    exchange = transfer_exchange_root()
    roots = get_roots()
    matches = []
    for root in roots:
        root_path = Path(root.path).resolve()
        try:
            relative = exchange.relative_to(root_path)
        except ValueError:
            continue
        parts = tuple(relative.parts)
        if parts:
            matches.append((root, parts))
    if len(matches) != 1:
        raise ValueError("Transfer exchange directory must be inside exactly one configured Server Files root.")
    root, folder_parts = matches[0]
    assert_path_allowed(root, folder_parts, user, write=write)
    if not exchange.is_dir() or exchange.is_symlink():
        raise ValueError("Transfer exchange directory is unavailable.")
    return root, folder_parts


def _exchange_file_parts(user, filename, *, write=False):
    root, folder_parts = _resolve_transfer_exchange(user, write=write)
    name = _safe_filename(filename)
    parts = (*folder_parts, name)
    assert_path_allowed(root, parts, user, write=write)
    return root, parts, name


def validate_transfer_exchange(user, *, write=False):
    """Validate the configured exchange directory against current Server Files policy."""
    return _resolve_transfer_exchange(user, write=write)


def list_transfer_exchange_files(user):
    """Return bounded regular files available for inbound transfer selection."""
    root, folder_parts = _resolve_transfer_exchange(user, write=False)
    configured_limit = get_config().get("TRANSFER_EXCHANGE_LIST_LIMIT", 200)
    try:
        limit = max(1, min(int(configured_limit), 1000))
    except (TypeError, ValueError):
        limit = 200
    files = []
    with server_files_service._open_directory(root, folder_parts) as directory_fd:
        try:
            entries = os.scandir(directory_fd)
            try:
                for entry in entries:
                    if len(files) >= limit:
                        break
                    name = entry.name
                    if not isinstance(name, str) or name.startswith("."):
                        continue
                    try:
                        parts = (*folder_parts, name)
                        if not stat.S_ISREG(entry.stat(follow_symlinks=False).st_mode):
                            continue
                        if name in {".", ".."} or not validate_name(name):
                            continue
                        assert_path_allowed(root, parts, user, write=False)
                        file_stat = entry.stat(follow_symlinks=False)
                    except (OSError, ServerFilesDenied, ServerFilesInvalidPath):
                        continue
                    files.append({
                        "name": name,
                        "size": int(file_stat.st_size),
                        "modified": datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.get_current_timezone()).isoformat(),
                        "content_type": mimetypes.guess_type(name, strict=False)[0] or "application/octet-stream",
                    })
            finally:
                entries.close()
        except OSError as exc:
            raise ValueError("The transfer exchange directory could not be listed safely.") from exc
    files.sort(key=lambda item: item["name"].casefold())
    return files


def _acquire_transfer_slot():
    """Serialize the global concurrency check and reserve a creation slot."""
    lock, _ = PaxaliaTransferLock.objects.select_for_update().get_or_create(pk=1)
    # Touching the row is useful on backends where a newly-created row needs
    # an observable update before the surrounding transaction commits.
    lock.updated_at = timezone.now()
    lock.save(update_fields=["updated_at"])
    if PaxaliaTransfer.objects.filter(status__in=_ACTIVE_STATUSES).count() >= max_concurrent_transfers():
        raise PermissionDenied("The configured concurrent transfer limit has been reached.")
    return lock


def _active_transfer_count():
    return PaxaliaTransfer.objects.filter(status__in=_ACTIVE_STATUSES).count()


def create_send_transfer(*, user, filename, total_size, destination_root_id="", destination_path="", source_checksum="", request_id=""):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "upload_server_files")
    source_checksum = _normalize_checksum(source_checksum)
    try:
        total_size = int(total_size)
    except (TypeError, ValueError):
        raise ValueError("Transfer size must be an integer.") from None
    if total_size <= 0 or total_size > max_transfer_bytes():
        raise ValueError("Transfer size exceeds the configured limit.")

    # Transfer Center has one destination authority: the configured fixed
    # exchange directory. Browser-supplied root/path values are deliberately
    # ignored so the endpoint can never become a general filesystem writer.
    filename = _safe_filename(filename)
    request_id = str(request_id or "")[:128]
    destination_root, exchange_parts, filename = _exchange_file_parts(user, filename, write=True)

    # Never start a potentially large browser upload when the fixed exchange
    # already contains the requested name. Promotion also uses O_EXCL as the
    # race-safe final guard; this preflight simply fails early and clearly.
    try:
        with server_files_service._open_parent(destination_root, exchange_parts) as (parent_fd, destination_name):
            try:
                os.stat(destination_name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ServerFilesAlreadyExists(
                    "A file with this name already exists in the transfer exchange. Rename the local file and upload again."
                )
    except ServerFilesNotFound:
        raise ValueError("The transfer exchange directory is unavailable.") from None

    destination_root_id = destination_root.id
    destination_parts = exchange_parts[:-1]
    now = timezone.now()
    upload = None

    with transaction.atomic():
        _acquire_transfer_slot()
        transfer = PaxaliaTransfer.objects.create(
            actor=user,
            direction="send",
            filename=filename,
            size=total_size,
            chunk_size=chunk_size_bytes(),
            total_chunks=(total_size + chunk_size_bytes() - 1) // chunk_size_bytes(),
            server_root_id=str(destination_root_id)[:64],
            server_relative_path="/".join((*destination_parts, filename)),
            status="queued",
            source_checksum=source_checksum,
            checksum_algorithm="sha256",
            max_retries=max_retries(),
            request_id=request_id,
            started_at=now,
            expires_at=now + timedelta(hours=expiration_hours()),
        )
        upload = FileUpload.objects.create(
            uploaded_by=user,
            original_filename=filename,
            total_size=total_size,
            chunk_size=transfer.chunk_size,
            total_chunks=transfer.total_chunks,
            status="pending",
            purpose="transfer_send",
            transfer_id=transfer.id,
            storage_path="",
        )
        transfer.upload_session = upload
        transfer.status = "preparing"
        transfer.staging_path = str(_staging_filename(upload.id, filename))
        transfer.save(update_fields=["upload_session", "status", "staging_path", "updated_at"])

    return transfer, upload


def resume_send_transfer(*, transfer_id, user):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "upload_server_files")
    try:
        with transaction.atomic():
            transfer = PaxaliaTransfer.objects.select_for_update().get(
                pk=transfer_id, direction="send"
            )
            if not user.is_superuser and transfer.actor_id != user.pk:
                raise PermissionDenied("You do not own this transfer.")
            if transfer.status in _TERMINAL_STATUSES:
                raise ValueError("This transfer cannot be resumed.")
            if transfer.upload_session_id is None:
                raise ValueError("This transfer cannot be resumed.")
            root, parts = _resolve_bound_transfer_path(transfer, user, write=True)

            upload = FileUpload.objects.select_for_update().get(pk=transfer.upload_session_id)
            if upload.uploaded_by_id != getattr(user, "pk", None) and not user.is_superuser:
                raise PermissionDenied("You do not own this transfer upload.")
            if upload.status == "failed":
                raise ValueError("The transfer upload session has failed; a new transfer is required.")

            # upload_complete() moves transfer-send bytes to transfer.staging_path.
            # A lost browser response after that move must remain resumable.
            if upload.status == "completed":
                staging = safe_staging_path(transfer.staging_path)
                if not staging.is_file() or staging.stat().st_size != transfer.size:
                    raise ValueError("Completed transfer staging data is missing or inconsistent.")
                if upload.storage_path and Path(upload.storage_path).resolve() != staging.resolve():
                    raise ValueError("Completed transfer staging data is inconsistent.")
                transfer.status = "verifying"
                transfer.bytes_transferred = transfer.size
            else:
                temp = send_upload_temp_path(upload.id)
                if upload.chunks_received and (not temp.is_file() or temp.stat().st_size != upload.bytes_received):
                    raise ValueError("Resumable transfer staging data is missing or inconsistent.")
                transfer.status = "transferring" if upload.chunks_received else "preparing"
                transfer.bytes_transferred = min(transfer.size, max(0, upload.bytes_received))

            now = timezone.now()
            transfer.expires_at = now + timedelta(hours=expiration_hours())
            transfer.updated_at = now
            update_fields = ["status", "bytes_transferred", "expires_at", "updated_at"]
            if not transfer.started_at:
                transfer.started_at = now
                update_fields.append("started_at")
            transfer.save(update_fields=update_fields)
            return transfer, upload
    except PaxaliaTransfer.DoesNotExist:
        raise ValueError("Transfer was not found.") from None

def resume_receive_transfer(*, transfer_id, user):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "download_server_files")
    try:
        with transaction.atomic():
            transfer = PaxaliaTransfer.objects.select_for_update().get(pk=transfer_id, direction="receive")
            if not user.is_superuser and transfer.actor_id != user.pk:
                raise PermissionDenied("You do not own this transfer.")
            if transfer.status in _TERMINAL_STATUSES:
                raise ValueError("This transfer cannot be resumed.")
            root, parts = _resolve_bound_transfer_path(transfer, user, write=False)
            now = timezone.now()
            transfer.status = "transferring"
            transfer.expires_at = now + timedelta(hours=expiration_hours())
            transfer.updated_at = now
            transfer.save(update_fields=["status", "expires_at", "updated_at"])
            return transfer
    except PaxaliaTransfer.DoesNotExist:
        raise ValueError("Transfer was not found.") from None


def pause_transfer(transfer: PaxaliaTransfer, user):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    if transfer.direction == "send":
        _check_capability(user, "create_transfers")
        _check_capability(user, "upload_server_files")
    else:
        _check_capability(user, "create_transfers")
        _check_capability(user, "download_server_files")
    with transaction.atomic():
        locked = PaxaliaTransfer.objects.select_for_update().get(pk=transfer.pk)
        if locked.actor_id != getattr(user, "pk", None) and not user.is_superuser:
            raise PermissionDenied("You do not own this transfer.")
        if locked.status not in {"preparing", "transferring", "interrupted"}:
            raise ValueError("Only active transfers can be paused.")
        locked.status = "paused"
        locked.updated_at = timezone.now()
        locked.save(update_fields=["status", "updated_at"])
        return locked


def retry_transfer(transfer: PaxaliaTransfer, user):
    """Retry an interrupted/failed transfer while preserving verified progress."""
    ensure_enabled()
    _check_capability(user, "view_transfers")
    if transfer.direction == "send":
        _check_capability(user, "create_transfers")
        _check_capability(user, "upload_server_files")
    else:
        _check_capability(user, "create_transfers")
        _check_capability(user, "download_server_files")
    with transaction.atomic():
        locked = PaxaliaTransfer.objects.select_for_update().get(pk=transfer.pk)
        if locked.actor_id != getattr(user, "pk", None) and not user.is_superuser:
            raise PermissionDenied("You do not own this transfer.")
        if locked.status not in {"failed", "interrupted", "paused"}:
            raise ValueError("Only failed, interrupted, or paused transfers can be resumed.")
        is_retry = locked.status in {"failed", "interrupted", "paused"}
        needs_new_slot = locked.status in {"failed", "interrupted"}
        if is_retry and locked.retry_count >= locked.max_retries:
            raise ValueError("The configured transfer retry limit has been reached.")

        # Failed/interrupted transfers no longer consume an active slot.
        # Reserve the replacement slot before checking the upload/session
        # payload so a saturated deployment consistently rejects the retry
        # with the concurrency error rather than leaking implementation detail
        # such as a missing resumable upload.
        if needs_new_slot:
            _acquire_transfer_slot()

        if locked.direction == "send":
            _check_capability(user, "create_transfers")
            _check_capability(user, "upload_server_files")
            root, parts = _resolve_bound_transfer_path(locked, user, write=True)
            if not locked.upload_session_id:
                raise ValueError("The resumable upload session is missing.")
            upload = FileUpload.objects.select_for_update().filter(pk=locked.upload_session_id).first()
            if upload is None:
                raise ValueError("The resumable upload session is missing.")
            if upload.status == "failed":
                raise ValueError("The transfer upload session has failed; a new transfer is required.")
            if upload.status == "completed":
                staging = safe_staging_path(locked.staging_path)
                if not staging.is_file() or staging.stat().st_size != locked.size:
                    raise ValueError("Completed transfer staging data is missing or inconsistent; a new transfer is required.")
                if upload.storage_path and Path(upload.storage_path).resolve() != staging.resolve():
                    raise ValueError("Completed transfer staging data is inconsistent; a new transfer is required.")
                locked.status = "verifying"
                locked.bytes_transferred = locked.size
            else:
                temp = send_upload_temp_path(upload.id)
                if upload.chunks_received and (not temp.is_file() or temp.stat().st_size != upload.bytes_received):
                    raise ValueError("Verified transfer staging data is missing or inconsistent; a new transfer is required.")
                locked.status = "transferring" if upload.chunks_received else "preparing"
                locked.bytes_transferred = min(locked.size, max(0, upload.bytes_received))
        else:
            _resolve_bound_transfer_path(locked, user, write=False)
            locked.status = "transferring" if _valid_chunk_indexes(locked, locked.received_chunks) else "preparing"

        if is_retry:
            locked.retry_count += 1
        locked.error_message = ""
        locked.expires_at = timezone.now() + timedelta(hours=expiration_hours())
        locked.updated_at = timezone.now()
        locked.save(update_fields=["status", "retry_count", "error_message", "expires_at", "bytes_transferred", "updated_at"])
        return locked


def sync_finalize_send(transfer: PaxaliaTransfer, user, *, source_checksum=None, allow_large=False):
    """Verify a staged send and atomically claim its promotion work.

    The row lock intentionally spans the filesystem promotion.  Without it,
    two workers can race on O_EXCL, and the losing worker could otherwise
    overwrite the first worker's final database status or unlink its newly
    created destination.
    """
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "upload_server_files")

    transfer_id = transfer.pk if isinstance(transfer, PaxaliaTransfer) else transfer
    try:
        transfer_id = uuid.UUID(str(transfer_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Transfer was not found.") from None

    with transaction.atomic():
        try:
            locked = PaxaliaTransfer.objects.select_for_update().get(pk=transfer_id)
        except PaxaliaTransfer.DoesNotExist:
            raise ValueError("Transfer was not found.") from None
        if locked.direction != "send":
            raise ValueError("Not a send transfer.")
        if locked.actor_id != getattr(user, "pk", None) and not user.is_superuser:
            raise PermissionDenied("You do not own this transfer.")
        if locked.status in _TERMINAL_STATUSES:
            return locked
        if locked.status == "paused":
            raise ValueError("Transfer is paused; resume it before finalization.")
        if locked.status not in {"preparing", "transferring", "interrupted", "verifying"}:
            raise ValueError("Transfer is not ready for finalization.")
        upload = FileUpload.objects.select_for_update().filter(pk=locked.upload_session_id).first()
        if upload is None or upload.status != "completed":
            raise ValueError("The transfer upload session is not complete.")
        if upload.uploaded_by_id != locked.actor_id and not user.is_superuser:
            raise PermissionDenied("You do not own this transfer upload.")

        submitted_checksum = _normalize_checksum(source_checksum) if source_checksum is not None else ""
        if submitted_checksum:
            locked.source_checksum = submitted_checksum

        staging = safe_staging_path(locked.staging_path)
        if not upload.storage_path:
            locked.status = "failed"
            locked.error_message = "Transfer upload staging reference is missing."
            _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
            _cleanup_staging(staging)
            locked.save(update_fields=["status", "error_message", "updated_at", "source_checksum"])
            result = locked
        elif Path(upload.storage_path).resolve() != staging.resolve():
            locked.status = "failed"
            locked.error_message = "Transfer upload staging data is inconsistent."
            _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
            _cleanup_staging(staging)
            locked.save(update_fields=["status", "error_message", "updated_at", "source_checksum"])
            result = locked
        elif not staging.is_file():
            locked.status = "failed"
            locked.error_message = "Transfer staging file is missing."
            _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
            locked.save(update_fields=["status", "error_message", "updated_at", "source_checksum"])
            result = locked
        elif staging.stat().st_size != locked.size:
            locked.status = "failed"
            locked.error_message = "Transfer staging file size does not match the declared size."
            _cleanup_staging(staging)
            _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
            locked.save(update_fields=["status", "error_message", "updated_at", "source_checksum"])
            result = locked
        elif not locked.source_checksum:
            locked.status = "failed"
            locked.error_message = "A source SHA-256 checksum is required before transfer completion."
            _cleanup_staging(staging)
            _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
            locked.save(update_fields=["status", "error_message", "updated_at", "source_checksum"])
            result = locked
        else:
            locked.status = "verifying"
            locked.error_message = ""
            locked.updated_at = timezone.now()
            locked.save(update_fields=["status", "error_message", "updated_at", "source_checksum"])
            if locked.size > sync_verify_max_bytes() and not (allow_large or get_config().get("TRANSFER_ALLOW_SYNC_LARGE_PROMOTION", False)):
                result = locked
            else:
                promotion_root = None
                promotion_parts = None
                promotion_name = None
                promotion_temp_name = None
                temp_created = False
                try:
                    source_flags = os.O_RDONLY
                    if hasattr(os, "O_NOFOLLOW"):
                        source_flags |= os.O_NOFOLLOW
                    if hasattr(os, "O_CLOEXEC"):
                        source_flags |= os.O_CLOEXEC
                    source_fd = os.open(str(staging), source_flags)
                    try:
                        source_stat = os.fstat(source_fd)
                        if not stat.S_ISREG(source_stat.st_mode) or source_stat.st_size != locked.size:
                            raise ValueError("Transfer staging file changed during verification.")

                        root, parts = _resolve_bound_transfer_path(locked, user, write=True)
                        promotion_root = root
                        promotion_parts = parts
                        promotion_name = validate_name(parts[-1])

                        with server_files_service._open_parent(root, parts) as (parent_fd, name):
                            promotion_temp_name = f".paxalia-transfer-{uuid.uuid4().hex}.part"
                            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
                            if hasattr(os, "O_NOFOLLOW"):
                                flags |= os.O_NOFOLLOW
                            if hasattr(os, "O_CLOEXEC"):
                                flags |= os.O_CLOEXEC
                            fd = os.open(promotion_temp_name, flags, 0o600, dir_fd=parent_fd)
                            temp_created = True
                            try:
                                source_digest = hashlib.sha256()
                                written_total = 0
                                while written_total < locked.size:
                                    chunk = os.read(source_fd, min(_READ_SIZE, locked.size - written_total))
                                    if not chunk:
                                        raise OSError("Transfer staging file ended before the declared size.")
                                    source_digest.update(chunk)
                                    view = memoryview(chunk)
                                    while view:
                                        written = os.write(fd, view)
                                        if written <= 0:
                                            raise OSError("destination write failed")
                                        view = view[written:]
                                    written_total += len(chunk)
                                if written_total != locked.size:
                                    raise OSError("destination size mismatch")
                                current_source = os.fstat(source_fd)
                                if (
                                    (source_stat.st_dev, source_stat.st_ino, source_stat.st_size, source_stat.st_mtime_ns, source_stat.st_ctime_ns)
                                    != (current_source.st_dev, current_source.st_ino, current_source.st_size, current_source.st_mtime_ns, current_source.st_ctime_ns)
                                ):
                                    raise ValueError("Transfer staging file changed during verification.")
                                os.fsync(fd)
                                destination_hash = _hash_fd(fd)
                                source_hash = source_digest.hexdigest()
                                if source_hash != locked.source_checksum or destination_hash != source_hash:
                                    locked.destination_checksum = ""
                                    locked.status = "failed"
                                    locked.error_message = "Source and server destination SHA-256 checksums do not match."
                                    _cleanup_staging(staging)
                                    _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
                                    locked.save(update_fields=["status", "error_message", "updated_at", "destination_checksum", "source_checksum"])
                                    result = locked
                                else:
                                    try:
                                        os.link(
                                            promotion_temp_name,
                                            name,
                                            src_dir_fd=parent_fd,
                                            dst_dir_fd=parent_fd,
                                            follow_symlinks=False,
                                        )
                                    except FileExistsError:
                                        # Never infer ownership from matching bytes. An existing exchange
                                        # file may belong to another operation, so the final name is always
                                        # treated as a strict no-overwrite collision.
                                        locked.destination_checksum = ""
                                        locked.status = "failed"
                                        locked.error_message = (
                                            "A file with this name already exists in the transfer exchange. "
                                            "Rename the local file and upload again."
                                        )
                                        locked.save(update_fields=["status", "error_message", "updated_at", "destination_checksum", "source_checksum"])
                                        result = locked
                                    else:
                                        os.unlink(promotion_temp_name, dir_fd=parent_fd)
                                        temp_created = False
                                        os.fsync(parent_fd)
                                        locked.destination_checksum = destination_hash
                                        locked.status = "completed"
                                        locked.completed_at = timezone.now()
                                        locked.error_message = ""
                                        locked.bytes_transferred = locked.size
                                        _cleanup_staging(staging)
                                        _sync_transfer_upload_state(upload, status="completed", clear_storage=True)
                                        locked.save(update_fields=["status", "completed_at", "bytes_transferred", "error_message", "updated_at", "destination_checksum", "source_checksum"])
                                        result = locked
                            finally:
                                os.close(fd)
                                if temp_created:
                                    try:
                                        os.unlink(promotion_temp_name, dir_fd=parent_fd)
                                    except OSError:
                                        pass
                                    temp_created = False
                    finally:
                        os.close(source_fd)
                except (OSError, ValueError, PermissionDenied) as exc:
                    if temp_created and promotion_root is not None and promotion_name is not None and promotion_temp_name:
                        try:
                            with server_files_service._open_parent(promotion_root, promotion_parts) as (parent_fd, _name):
                                os.unlink(promotion_temp_name, dir_fd=parent_fd)
                        except Exception:
                            pass
                    if isinstance(exc, FileNotFoundError):
                        locked.status = "failed"
                        locked.error_message = "Transfer destination promotion failed; the exchange directory is unavailable."
                    elif isinstance(exc, PermissionDenied):
                        locked.status = "failed"
                        locked.error_message = "Transfer destination promotion failed; permission was denied."
                    else:
                        locked.status = "failed"
                        locked.error_message = "Transfer destination promotion failed; retry or inspect server logs."
                    locked.save(update_fields=["status", "error_message", "updated_at", "destination_checksum", "source_checksum"])
                    _log_unexpected("send promotion", exc, transfer_id=locked.pk)
                    result = locked

    if result.status == "completed":
        _notify_transfer(result, "completed")
    elif result.status == "failed":
        _notify_transfer(result, "failed")
    return result


def create_receive_transfer(*, user, source_root_id="", source_path="", filename=""):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "download_server_files")

    requested = filename or source_path
    if not requested or "/" in str(requested) or "\\" in str(requested):
        raise ValueError("Choose a file from the configured Paxalia transfer exchange.")
    root, parts, name = _exchange_file_parts(user, requested, write=False)

    with server_files_service._open_regular_file(root, parts) as (_fd, file_stat):
        size = int(file_stat.st_size)
        if size <= 0 or size > max_transfer_bytes():
            raise ValueError("File exceeds the configured transfer size limit.")

    now = timezone.now()
    with transaction.atomic():
        _acquire_transfer_slot()
        transfer = PaxaliaTransfer.objects.create(
            actor=user,
            direction="receive",
            filename=name,
            size=size,
            chunk_size=chunk_size_bytes(),
            total_chunks=(size + chunk_size_bytes() - 1) // chunk_size_bytes(),
            received_chunks=[],
            server_root_id=str(root.id)[:64],
            server_relative_path="/".join(parts),
            status="preparing",
            checksum_algorithm="sha256",
            max_retries=max_retries(),
            started_at=now,
            expires_at=now + timedelta(hours=expiration_hours()),
        )
        if size <= sync_verify_max_bytes():
            try:
                transfer.source_checksum = _hash_server_file(root, parts)
            except OSError:
                transfer.status = "failed"
                transfer.error_message = "The source file could not be hashed safely."
        transfer.save(update_fields=["source_checksum", "status", "updated_at"])
    return transfer


def read_receive_chunk(transfer: PaxaliaTransfer, user, chunk_index: int) -> bytes:
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "download_server_files")
    if transfer.direction != "receive":
        raise ValueError("Not a receive transfer.")
    if transfer.actor_id != getattr(user, "pk", None) and not getattr(user, "is_superuser", False):
        raise PermissionDenied("You do not own this transfer.")
    if transfer.status in _TERMINAL_STATUSES:
        raise ValueError("Transfer is not active.")
    if transfer.status == "paused":
        raise ValueError("Transfer is paused.")
    try:
        chunk_index = int(chunk_index)
    except (TypeError, ValueError):
        raise ValueError("Invalid chunk index.") from None
    if chunk_index < 0 or chunk_index >= transfer.total_chunks:
        raise ValueError("Chunk out of range.")

    root, parts = _resolve_bound_transfer_path(transfer, user, write=False)
    start = chunk_index * transfer.chunk_size
    length = min(transfer.chunk_size, transfer.size - start)
    with server_files_service._open_regular_file(root, parts) as (fd, file_stat):
        if file_stat.st_size != transfer.size:
            raise ValueError("The source file changed during transfer.")
        os.lseek(fd, start, os.SEEK_SET)
        buffer = bytearray()
        while len(buffer) < length:
            piece = os.read(fd, min(_READ_SIZE, length - len(buffer)))
            if not piece:
                break
            buffer.extend(piece)
    if len(buffer) != length:
        raise ValueError("The requested transfer chunk could not be read completely.")

    now = timezone.now()
    with transaction.atomic():
        locked = PaxaliaTransfer.objects.select_for_update().get(pk=transfer.pk)
        if locked.status in _TERMINAL_STATUSES or locked.status == "paused":
            raise ValueError("Transfer is not active.")
        received = {int(index) for index in (locked.received_chunks or []) if str(index).lstrip("-").isdigit()}
        received.add(chunk_index)
        locked.received_chunks = sorted(received)
        locked.bytes_transferred = _received_bytes(locked, received)
        locked.status = "transferring"
        locked.updated_at = now
        locked.save(update_fields=["received_chunks", "bytes_transferred", "status", "updated_at"])
    return bytes(buffer)


def complete_receive(transfer: PaxaliaTransfer, user, destination_checksum: str):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    _check_capability(user, "create_transfers")
    _check_capability(user, "download_server_files")
    checksum = _normalize_checksum(destination_checksum, optional=False)
    with transaction.atomic():
        locked = PaxaliaTransfer.objects.select_for_update().get(pk=transfer.pk)
        if locked.actor_id != getattr(user, "pk", None) and not user.is_superuser:
            raise PermissionDenied("You do not own this transfer.")
        # Revalidate the authoritative source path at completion time. The
        # browser may take minutes to download a large file, and Server Files
        # policy can change while the transfer is in flight.
        root, parts = _resolve_bound_transfer_path(locked, user, write=False)
        if locked.direction != "receive":
            raise ValueError("Not a receive transfer.")
        if locked.status in _TERMINAL_STATUSES:
            return locked
        received_indexes = _valid_chunk_indexes(locked, locked.received_chunks)
        if len(received_indexes) < locked.total_chunks:
            raise ValueError("The receive transfer is incomplete; not all chunks have been received.")

        locked.destination_checksum = checksum
        locked.status = "verifying"
        locked.bytes_transferred = locked.size
        locked.updated_at = timezone.now()
        # For bounded synchronous receives, hash the authoritative server
        # source again at completion time. The checksum captured at initiation
        # is useful metadata, but cannot prove the source remained unchanged
        # throughout a long browser download. Larger receives are rechecked by
        # bounded maintenance before they become completed.
        if locked.size <= sync_verify_max_bytes():
            current_source_checksum = _hash_server_file(root, parts)
            locked.source_checksum = current_source_checksum
            if current_source_checksum != checksum:
                locked.status = "failed"
                locked.error_message = "Source and client SHA-256 checksums do not match."
            else:
                locked.status = "completed"
                locked.completed_at = timezone.now()
                locked.error_message = ""
        locked.save(
            update_fields=[
                "source_checksum", "destination_checksum", "status", "completed_at", "bytes_transferred", "updated_at", "error_message"
            ]
        )
    if locked.status == "completed":
        _notify_transfer(locked, "completed")
    elif locked.status == "failed":
        _notify_transfer(locked, "failed")
    return locked


def cancel_transfer(transfer: PaxaliaTransfer, user):
    ensure_enabled()
    _check_capability(user, "view_transfers")
    if transfer.direction == "send":
        _check_capability(user, "create_transfers")
        _check_capability(user, "upload_server_files")
    else:
        _check_capability(user, "create_transfers")
        _check_capability(user, "download_server_files")
    with transaction.atomic():
        locked = PaxaliaTransfer.objects.select_for_update().get(pk=transfer.pk)
        if locked.actor_id != getattr(user, "pk", None) and not user.is_superuser:
            raise PermissionDenied("You do not own this transfer.")
        if locked.status in {"completed", "cancelled", "expired"}:
            return locked
        if locked.status == "verifying":
            raise ValueError("Transfer verification is in progress and cannot be cancelled.")
        upload = None
        if locked.upload_session_id and locked.direction == "send":
            upload = FileUpload.objects.select_for_update().filter(pk=locked.upload_session_id).first()
        locked.status = "cancelled"
        locked.updated_at = timezone.now()
        if upload is not None:
            _sync_transfer_upload_state(upload, status="failed", error_message="Transfer was cancelled.", clear_storage=True)
        locked.save(update_fields=["status", "updated_at"])
        staging_path = locked.staging_path
        upload_id = upload.id if upload is not None and upload.purpose == "transfer_send" else None
    _cleanup_staging(staging_path)
    _cleanup_send_upload_temp(upload_id)
    return locked

def maintenance(*, batch_size=None, dry_run=False):
    """Process a globally bounded maintenance pass over transfer state."""
    try:
        batch_size = max(1, min(int(batch_size or get_config().get("TRANSFER_CLEANUP_BATCH_SIZE", 100)), 1000))
    except (TypeError, ValueError, OverflowError):
        batch_size = 100

    now = timezone.now()
    processed = completed = expired = failed = 0

    if dry_run:
        expiry_count = PaxaliaTransfer.objects.filter(
            status__in=_ACTIVE_STATUSES, expires_at__lt=now
        ).count()
        verify_count = PaxaliaTransfer.objects.filter(status="verifying").count()
        return {
            "processed": min(batch_size, expiry_count + verify_count),
            "completed": 0,
            "expired": min(batch_size, expiry_count),
            "failed": 0,
            "dry_run": True,
            "eligible": expiry_count + verify_count,
        }

    expiry_ids = list(
        PaxaliaTransfer.objects.filter(status__in=_ACTIVE_STATUSES, expires_at__lt=now)
        .order_by("expires_at").values_list("pk", flat=True)[:batch_size]
    )
    for transfer_id in expiry_ids:
        with transaction.atomic():
            transfer = (
                PaxaliaTransfer.objects.select_related("upload_session")
                .select_for_update()
                .filter(pk=transfer_id, status__in=_ACTIVE_STATUSES, expires_at__lt=now)
                .first()
            )
            if transfer is None:
                continue
            transfer.status = "expired"
            transfer.error_message = "Transfer staging record expired before completion."
            transfer.updated_at = now
            transfer.save(update_fields=["status", "error_message", "updated_at"])
            upload = transfer.upload_session if transfer.direction == "send" else None
            upload_id = upload.id if upload is not None and getattr(upload, "purpose", "release") == "transfer_send" else None
            if upload is not None:
                _sync_transfer_upload_state(upload, status="failed", error_message="Transfer expired.", clear_storage=True)
            staging_path = transfer.staging_path
        _cleanup_staging(staging_path)
        _cleanup_send_upload_temp(upload_id)
        processed += 1
        expired += 1
        try:
            send_alert(
                f"Transfer expired: {transfer.filename}",
                f"Paxalia Transfer Center expired {transfer.filename} before completion.",
                category="general",
                site=None,
                dedupe_key=f"transfer:{transfer.pk}:expired",
            )
        except Exception:
            pass
        if processed >= batch_size:
            return {"processed": processed, "completed": completed, "expired": expired, "failed": failed}

    remaining = batch_size - processed
    if remaining <= 0:
        return {"processed": processed, "completed": completed, "expired": expired, "failed": failed}

    send_rows = list(
        PaxaliaTransfer.objects.filter(direction="send", status="verifying")
        .order_by("updated_at").values_list("pk", flat=True)[:remaining]
    )
    for transfer_id in send_rows:
        try:
            transfer = PaxaliaTransfer.objects.select_related("actor").get(pk=transfer_id)
            user = transfer.actor
            if user is None:
                with transaction.atomic():
                    locked = PaxaliaTransfer.objects.select_for_update().filter(pk=transfer_id, status="verifying").first()
                    if locked is None:
                        continue
                    locked.status = "failed"
                    locked.error_message = "Transfer owner is no longer available for verification."
                    locked.updated_at = timezone.now()
                    upload = locked.upload_session
                    if upload is not None:
                        _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
                    locked.save(update_fields=["status", "error_message", "updated_at"])
                    staging_path = locked.staging_path
                    upload_id = upload.id if upload is not None and getattr(upload, "purpose", "release") == "transfer_send" else None
                _cleanup_staging(staging_path)
                _cleanup_send_upload_temp(upload_id)
                failed += 1
                _notify_transfer(locked, "failed")
            else:
                try:
                    updated = sync_finalize_send(transfer, user, allow_large=True)
                except Exception:
                    with transaction.atomic():
                        locked = PaxaliaTransfer.objects.select_for_update().filter(pk=transfer_id, status="verifying").first()
                        if locked is None:
                            continue
                        locked.status = "failed"
                        locked.error_message = "Transfer verification could not be completed safely."
                        locked.updated_at = timezone.now()
                        upload = locked.upload_session
                        if upload is not None:
                            _sync_transfer_upload_state(upload, status="failed", error_message=locked.error_message, clear_storage=True)
                        locked.save(update_fields=["status", "error_message", "updated_at"])
                        staging_path = locked.staging_path
                        upload_id = upload.id if upload is not None and getattr(upload, "purpose", "release") == "transfer_send" else None
                    _cleanup_staging(staging_path)
                    _cleanup_send_upload_temp(upload_id)
                    _log_unexpected("maintenance send verification", exc, transfer_id=transfer_id)
                    failed += 1
                    _notify_transfer(locked, "failed")
                else:
                    if updated.status == "completed":
                        completed += 1
                    elif updated.status == "failed":
                        failed += 1
        except PaxaliaTransfer.DoesNotExist:
            continue
        processed += 1
        remaining -= 1
        if remaining <= 0:
            break

    if remaining <= 0:
        return {"processed": processed, "completed": completed, "expired": expired, "failed": failed}

    receive_rows = list(
        PaxaliaTransfer.objects.filter(direction="receive", status="verifying")
        .exclude(destination_checksum="")
        .order_by("updated_at").values_list("pk", flat=True)[:remaining]
    )
    for transfer_id in receive_rows:
        action = None
        try:
            with transaction.atomic():
                transfer = (
                    PaxaliaTransfer.objects.select_related("actor")
                    .select_for_update()
                    .filter(pk=transfer_id, direction="receive", status="verifying")
                    .first()
                )
                if transfer is None:
                    continue
                root, parts = _resolve_bound_transfer_path(transfer, transfer.actor, write=False)
                source_checksum = _hash_server_file(root, parts)
                transfer.source_checksum = source_checksum
                if source_checksum == transfer.destination_checksum:
                    transfer.status = "completed"
                    transfer.completed_at = timezone.now()
                    transfer.error_message = ""
                    action = "completed"
                else:
                    transfer.status = "failed"
                    transfer.error_message = "Source and client SHA-256 checksums do not match."
                    action = "failed"
                transfer.updated_at = timezone.now()
                transfer.save(update_fields=["source_checksum", "status", "completed_at", "error_message", "updated_at"])
            if action == "completed":
                completed += 1
                _notify_transfer(transfer, "completed")
            elif action == "failed":
                failed += 1
                _notify_transfer(transfer, "failed")
        except Exception:
            with transaction.atomic():
                locked = PaxaliaTransfer.objects.select_for_update().filter(pk=transfer_id, status="verifying").first()
                if locked is None:
                    continue
                locked.status = "failed"
                locked.error_message = "Transfer verification could not be completed safely."
                locked.updated_at = timezone.now()
                locked.save(update_fields=["status", "error_message", "updated_at"])
            _log_unexpected("maintenance receive verification", exc, transfer_id=transfer_id)
            failed += 1
            _notify_transfer(locked, "failed")
        processed += 1
        remaining -= 1
        if remaining <= 0:
            break

    return {"processed": processed, "completed": completed, "expired": expired, "failed": failed}

