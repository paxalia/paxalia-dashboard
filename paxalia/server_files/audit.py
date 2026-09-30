"""Server Files operation auditing.

The structured operation history is authoritative for this feature. The
existing SecurityAuditLog is also notified through log_action(), which is
intentionally non-fatal in the existing security architecture.
"""
from __future__ import annotations

import logging
import re

from django.utils import timezone

from ..security_audit import log_action
from .models import ServerFileOperation
from .policy import is_sensitive, split_relative_path

logger = logging.getLogger("paxalia.server_files.audit")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _audit_path(root_id, path, *, force_redact=False):
    if force_redact:
        return "[protected]"
    try:
        parts = split_relative_path(path)
    except Exception:
        return "[invalid]"
    if is_sensitive(parts):
        return "[protected]"
    # Root IDs and canonical relative paths only; never persist absolute paths.
    return "/".join(parts)[:1024]


def _request_id(request):
    value = getattr(request, "paxalia_request_id", None)
    if not value:
        value = getattr(request, "request_id", None)
    value = str(value or "").strip()
    return value if _REQUEST_ID_RE.fullmatch(value) else ""


def begin_operation(request, operation, *, root_id="", path="", target_root_id="", target_path="", force_redact=False, required=True):
    actor = getattr(request, "user", None)
    actor = actor if actor is not None and getattr(actor, "is_authenticated", False) else None
    try:
        return ServerFileOperation.objects.create(
            actor=actor,
            operation=operation,
            root_id=str(root_id or "")[:64],
            path=_audit_path(root_id, path, force_redact=force_redact),
            target_root_id=str(target_root_id or "")[:64],
            target_path=_audit_path(target_root_id, target_path, force_redact=force_redact),
            status="started",
            request_id=_request_id(request),
        )
    except Exception:
        # Do not include exception text/traceback; a database error can contain
        # SQL parameters or paths. Mutations and sensitive reads fail closed.
        logger.error("Unable to create Server Files audit row (operation=%s)", operation)
        if required:
            from .exceptions import ServerFilesAuditUnavailable
            raise ServerFilesAuditUnavailable() from None
        return None


def finish_operation(request, record, status, *, error_code=""):
    if record is None:
        return
    try:
        record.status = status
        record.error_code = str(error_code or "")[:64]
        record.finished_at = timezone.now()
        record.save(update_fields=["status", "error_code", "finished_at"])
    except Exception:
        # The pre-created row remains in 'started' for maintenance to surface.
        logger.error("Unable to finalize Server Files audit row (operation=%s)", record.operation)
    try:
        suffix = f"root={record.root_id or '-'} path={record.path or '-'} status={status}"
        if record.target_root_id or record.target_path:
            suffix += f" target={record.target_root_id or '-'}:{record.target_path or '-'}"
        if error_code:
            suffix += f" error={str(error_code)[:64]}"
        log_action(request, f"server_files.{record.operation}", detail=suffix[:1900])
    except Exception:
        # log_action is non-fatal; this guard also protects alternate adapters.
        logger.error("Unable to mirror Server Files operation to SecurityAuditLog")
