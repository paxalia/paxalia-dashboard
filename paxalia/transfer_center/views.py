"""Paxalia Transfer Center browser endpoints."""
from __future__ import annotations

import logging
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from honeypot.decorators import honeypot_exempt

from ..admin_security import admin_security_required, admin_security_preflight
from ..models import PaxaliaTransfer
from ..permissions import require_section_permission
from ..security_audit import log_action
from ..server_files.policy import (has_capability, ServerFilesConfigurationError, ServerFilesDisabled)
from ..server_files.exceptions import ServerFilesError
from .policy import max_concurrent_transfers, max_retries, retry_delay_seconds, staging_roots, transfer_enabled
from ..settings import get_config
from ..security_rate_limit import allowed as rate_allowed
logger = logging.getLogger(__name__)


def _log_unexpected(operation, exc, *, transfer_id=None):
    """Record an unexpected transfer error without persisting internal details."""
    extra = {"error_class": type(exc).__name__}
    if transfer_id:
        extra["transfer_id"] = str(transfer_id)
    logger.error("Paxalia Transfer Center %s failed", operation, extra=extra)


def _service_error(exc, *, default="Transfer operation could not be completed safely."):
    """Return an operator-authored error for expected failures without leaking internals."""
    if isinstance(exc, ServerFilesError):
        return str(getattr(exc, "public_message", None) or exc), int(getattr(exc, "http_status", 400) or 400)
    if isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this transfer operation.", 403
    if isinstance(exc, ValueError):
        return str(exc), 400
    return default, 500


def _transfer_error_code(exc):
    """Map expected transfer failures to a stable, non-sensitive diagnostic code."""
    explicit = getattr(exc, "transfer_error_code", None)
    if explicit:
        return str(explicit)[:80]
    if isinstance(exc, PermissionDenied):
        return "permission_denied"
    if isinstance(exc, ServerFilesError):
        code = str(getattr(exc, "code", "") or "")
        if code == "already_exists":
            return "destination_exists"
        return code[:80] or "server_files_error"
    message = str(exc)
    mappings = (
        ("This transfer cannot be resumed.", "transfer_not_resumable"),
        ("Transfer was not found.", "transfer_not_found"),
        ("The transfer upload session has failed", "upload_session_failed"),
        ("Completed transfer staging data is missing or inconsistent.", "completed_staging_missing"),
        ("Completed transfer staging data is inconsistent.", "completed_staging_inconsistent"),
        ("Resumable transfer staging data is missing or inconsistent", "resume_staging_missing"),
        ("The resumable upload session is missing", "upload_session_missing"),
        ("The receive transfer is incomplete", "receive_incomplete"),
        ("Transfer is not active.", "transfer_not_active"),
        ("Transfer is paused.", "transfer_paused"),
        ("The source file changed during transfer.", "source_changed"),
        ("Chunk out of range.", "chunk_out_of_range"),
        ("Invalid chunk index.", "invalid_chunk_index"),
    )
    for phrase, code in mappings:
        if phrase in message:
            return code
    return "service_rejection"


def _transfer_model_error_code(transfer):
    """Return a stable public diagnostic code for a terminal transfer failure."""
    if getattr(transfer, "status", "") != "failed":
        return None
    message = str(getattr(transfer, "error_message", "") or "")
    if "already exists in the transfer exchange" in message:
        return "destination_exists"
    if "SHA-256 checksums do not match" in message:
        return "verification_failed"
    if "staging file is missing" in message:
        return "staging_missing"
    if "staging data is inconsistent" in message:
        return "staging_inconsistent"
    if "upload session" in message and "complete" in message:
        return "upload_incomplete"
    return "transfer_failed"


from .service import (
    cancel_transfer,
    complete_receive,
    create_receive_transfer,
    create_send_transfer,
    read_receive_chunk,
    resume_receive_transfer,
    sync_finalize_send,
    resume_send_transfer,
    pause_transfer,
    retry_transfer,
    list_transfer_exchange_files,
    validate_transfer_exchange,
)


def _owned_transfer(request, transfer_id):
    qs = PaxaliaTransfer.objects.select_related("actor", "upload_session").filter(pk=transfer_id)
    if not request.user.is_superuser:
        qs = qs.filter(actor=request.user)
    return qs.first()


def _serialize_transfer(transfer):
    return {
        "id": str(transfer.id),
        "filename": transfer.filename,
        "direction": transfer.direction,
        "status": transfer.status,
        "status_label": transfer.get_status_display(),
        "size": transfer.size,
        "bytes_transferred": transfer.bytes_transferred,
        "progress_percent": transfer.progress_percent,
        "duration_seconds": transfer.duration_seconds,
        "average_speed_bytes_per_second": transfer.average_speed_bytes_per_second,
        "chunk_size": transfer.chunk_size,
        "total_chunks": transfer.total_chunks,
        # Keep the legacy storage fields for API compatibility while also
        # exposing direction-neutral integrity fields for the UI.
        "source_checksum": transfer.source_checksum,
        "destination_checksum": transfer.destination_checksum,
        "app_checksum": transfer.app_checksum,
        "server_checksum": transfer.server_checksum,
        "app_checksum_scope": transfer.app_checksum_scope,
        "client_checksum": transfer.client_checksum,
        "client_checksum_scope": transfer.client_checksum_scope,
        "server_checksum_scope": transfer.server_checksum_scope,
        "checksum_status": transfer.checksum_status,
        "retry_count": transfer.retry_count,
        "max_retries": transfer.max_retries,
        "error_message": transfer.error_message,
        "error_code": _transfer_model_error_code(transfer),
        "created_at": transfer.created_at.isoformat(),
        "started_at": transfer.started_at.isoformat() if transfer.started_at else None,
        "completed_at": transfer.completed_at.isoformat() if transfer.completed_at else None,
        "expires_at": transfer.expires_at.isoformat() if transfer.expires_at else None,
    }



def _safe_int_config(key, default, minimum, maximum):
    try:
        value = int(get_config().get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _transfer_rate_limit(request):
    cfg = get_config()
    try:
        max_requests = max(1, int(cfg.get("TRANSFER_MAX_REQUESTS_PER_MINUTE", 120)))
    except (TypeError, ValueError):
        max_requests = 120
    try:
        window_seconds = max(1, int(cfg.get("TRANSFER_RATE_LIMIT_WINDOW_SECONDS", 60)))
    except (TypeError, ValueError):
        window_seconds = 60
    allowed, _remaining = rate_allowed(
        "transfer", max_requests, window_seconds, getattr(request.user, "pk", ""),
    )
    if not allowed:
        return JsonResponse({"error": "Transfer request rate limit exceeded."}, status=429)
    return None


def _send_preflight(request, *args, **kwargs):
    if request.method != "POST":
        return None
    try:
        int(request.POST.get("total_size", "0"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "total_size must be an integer"}, status=400)
    return None


@require_section_permission("transfers")
def transfer_center(request):
    configuration_error = ""
    exchange_files = []
    exchange_path_display = ""
    enabled = transfer_enabled()
    can_send = enabled and (request.user.is_superuser or (
        has_capability(request.user, "create_transfers")
        and has_capability(request.user, "upload_server_files")
    ))
    can_receive = enabled and (request.user.is_superuser or (
        has_capability(request.user, "create_transfers")
        and has_capability(request.user, "download_server_files")
    ))

    if not enabled:
        configuration_error = _("Transfer Center is disabled by deployment configuration.")
    else:
        try:
            staging_roots()
            if can_send or can_receive:
                exchange_root, exchange_parts = validate_transfer_exchange(request.user, write=can_send)
                exchange_path_display = str(Path(exchange_root.path).joinpath(*exchange_parts))
            if can_receive:
                exchange_files = list_transfer_exchange_files(request.user)
        except (ServerFilesDisabled, ServerFilesConfigurationError, ValueError, ServerFilesError):
            configuration_error = _(
                "Transfer Center requires a valid private staging directory and a configured Paxalia transfer exchange folder."
            )

    active = PaxaliaTransfer.objects.filter(
        status__in=["queued", "preparing", "transferring", "paused", "interrupted", "verifying"]
    )
    history = PaxaliaTransfer.objects.exclude(
        status__in=["queued", "preparing", "transferring", "paused", "interrupted", "verifying"]
    ).order_by("-created_at")

    if not request.user.is_superuser:
        active = active.filter(actor=request.user)
        history = history.filter(actor=request.user)

    history = history[:50]

    return render(request, "paxalia/transfer_center.html", {
        "active_page": "transfer_center",
        "page_title": _("Paxalia Transfer Center"),
        "page_subtitle": _("Private file exchange, resumable delivery, and verified transfer history"),
        "configuration_error": configuration_error,
        "transfer_enabled": enabled,
        "transfer_concurrency_limit": max_concurrent_transfers(),
        "can_send_transfer": can_send,
        "can_receive_transfer": can_receive,
        "active_transfers": active,
        "history": history,
        "exchange_files": exchange_files,
        "exchange_file_count": len(exchange_files),
        "exchange_name": "paxalia_transfer",
        "exchange_path_display": exchange_path_display,
        "chunk_size": _safe_int_config("TRANSFER_CHUNK_SIZE_MB", 5, 1, 64) * 1024 * 1024,
        "max_transfer_bytes": _safe_int_config("TRANSFER_MAX_FILE_SIZE_MB", 2048, 1, 1024 * 1024) * 1024 * 1024,
        "browser_max_receive_mb": _safe_int_config("TRANSFER_BROWSER_MAX_RECEIVE_MB", 512, 1, 1024 * 1024),
        "retry_delay_ms": retry_delay_seconds() * 1000,
        "transfer_max_retries": max_retries(),
        "logging_enabled": bool(get_config().get("LOGGING_ENABLED", True)),
        "init_send_url": reverse("paxalia:transfer_send_init"),
        "receive_init_url": reverse("paxalia:transfer_receive_init"),
        "pause_base": reverse("paxalia:transfer_pause", kwargs={"transfer_id": "00000000-0000-0000-0000-000000000000"}).replace("00000000-0000-0000-0000-000000000000", "TRANSFER_ID"),
        "retry_base": reverse("paxalia:transfer_retry", kwargs={"transfer_id": "00000000-0000-0000-0000-000000000000"}).replace("00000000-0000-0000-0000-000000000000", "TRANSFER_ID"),
    })


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
@admin_security_preflight(_send_preflight)
def transfer_send_init(request):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    try:
        transfer, upload = create_send_transfer(
            user=request.user,
            filename=request.POST.get("filename", ""),
            total_size=request.POST.get("total_size", "0"),
            destination_root_id=request.POST.get("server_root", ""),
            destination_path=request.POST.get("server_path", ""),
            source_checksum=request.POST.get("source_checksum", ""),
            request_id=getattr(request, "paxalia_request_id", ""),
        )
        log_action(request, "transfer.created", detail=f"direction=send filename={transfer.filename}")
        return JsonResponse({
            "transfer": _serialize_transfer(transfer),
            "upload_id": str(upload.id),
            "resume_chunk_index": upload.chunks_received,
            "upload_chunk_url": reverse("paxalia:upload_chunk", kwargs={"upload_id": upload.id}),
            "upload_complete_url": reverse("paxalia:upload_complete", kwargs={"upload_id": upload.id}),
            "finalize_url": reverse("paxalia:transfer_send_finalize", kwargs={"transfer_id": transfer.id}),
        })
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        message, status = _service_error(exc)
        _log_unexpected("send init", exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_send_resume(request):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    try:
        transfer, upload = resume_send_transfer(transfer_id=request.POST.get("transfer_id", ""), user=request.user)
        return JsonResponse({
            "transfer": _serialize_transfer(transfer),
            "upload_id": str(upload.id),
            "resume_chunk_index": upload.chunks_received,
            "upload_chunk_url": reverse("paxalia:upload_chunk", kwargs={"upload_id": upload.id}),
            "upload_complete_url": reverse("paxalia:upload_complete", kwargs={"upload_id": upload.id}),
            "finalize_url": reverse("paxalia:transfer_send_finalize", kwargs={"transfer_id": transfer.id}),
        })
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        message, status = _service_error(exc)
        _log_unexpected("send resume", exc, transfer_id=request.POST.get("transfer_id", ""))
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_send_finalize(request, transfer_id):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404
    if transfer.upload_session is None:
        return JsonResponse({"error": "Transfer upload session is missing.", "error_code": "missing_upload_session"}, status=409)
    submitted_checksum = str(request.POST.get("source_checksum", "")).strip().lower()
    if submitted_checksum and (len(submitted_checksum) != 64 or any(ch not in "0123456789abcdef" for ch in submitted_checksum)):
        return JsonResponse({"error": "source_checksum must be a SHA-256 hexadecimal digest.", "error_code": "invalid_checksum"}, status=400)
    try:
        updated = sync_finalize_send(transfer, request.user, source_checksum=submitted_checksum or None)
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        message, status = _service_error(exc)
        _log_unexpected("send finalization", exc, transfer_id=transfer_id)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    if updated.status == "completed":
        log_action(request, "transfer.completed", detail=f"direction=send filename={updated.filename}")
    return JsonResponse({"transfer": _serialize_transfer(updated)})


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_receive_init(request):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    try:
        transfer = create_receive_transfer(
            user=request.user,
            filename=request.POST.get("filename", ""),
        )
        log_action(request, "transfer.created", detail=f"direction=receive filename={transfer.filename}")
        return JsonResponse({
            "transfer": _serialize_transfer(transfer),
            "chunk_url_template": reverse("paxalia:transfer_receive_chunk", kwargs={"transfer_id": transfer.id, "chunk_index": 0}).replace("/0/", "/CHUNK_INDEX/"),
            "complete_url": reverse("paxalia:transfer_receive_complete", kwargs={"transfer_id": transfer.id}),
        })
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        message, status = _service_error(exc)
        _log_unexpected("receive init", exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_receive_resume(request):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    try:
        transfer = resume_receive_transfer(transfer_id=request.POST.get("transfer_id", ""), user=request.user)
        return JsonResponse({
            "transfer": _serialize_transfer(transfer),
            "chunk_url_template": reverse(
                "paxalia:transfer_receive_chunk",
                kwargs={"transfer_id": transfer.id, "chunk_index": 0},
            ).replace("/0/", "/CHUNK_INDEX/"),
            "complete_url": reverse(
                "paxalia:transfer_receive_complete",
                kwargs={"transfer_id": transfer.id},
            ),
        })
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        message, status = _service_error(exc)
        _log_unexpected("receive resume", exc, transfer_id=request.POST.get("transfer_id", ""))
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_receive_chunk(request, transfer_id, chunk_index):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404
    try:
        data = read_receive_chunk(transfer, request.user, chunk_index)
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        _log_unexpected("receive chunk", exc, transfer_id=transfer_id)
        return JsonResponse({"error": "The transfer chunk could not be read safely."}, status=500)
    response = HttpResponse(data, content_type="application/octet-stream")
    response["Cache-Control"] = "no-store"
    response["X-Paxalia-Transfer-ID"] = str(transfer.id)
    response["X-Paxalia-Chunk-Index"] = str(chunk_index)
    return response


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_receive_complete(request, transfer_id):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404
    try:
        transfer = complete_receive(transfer, request.user, request.POST.get("destination_checksum", ""))
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        message, status = _service_error(exc)
        _log_unexpected("receive verification", exc, transfer_id=transfer_id)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    if transfer.status == "completed":
        log_action(request, "transfer.completed", detail=f"direction=receive filename={transfer.filename}")
    return JsonResponse({"transfer": _serialize_transfer(transfer)})


@require_section_permission("transfers")
@require_GET
def transfer_status(request, transfer_id):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404

    # Status polling is intentionally read-only. Derive the latest browser-send
    # progress from FileUpload without turning a GET into a database mutation.
    payload = _serialize_transfer(transfer)
    if transfer.upload_session_id:
        upload = transfer.upload_session
        new_bytes = min(transfer.size, max(0, int(upload.bytes_received or 0)))
        payload["bytes_transferred"] = new_bytes
        payload["progress_percent"] = min(100, round((new_bytes / transfer.size) * 100, 1)) if transfer.size else 0
        if upload.status == "uploading" and transfer.status in {"preparing", "queued"}:
            payload["status"] = "transferring"
            payload["status_label"] = "Transferring"
    return JsonResponse({"transfer": payload})


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_cancel(request, transfer_id):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404
    try:
        transfer = cancel_transfer(transfer, request.user)
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        _log_unexpected("cancellation", exc, transfer_id=transfer_id)
        return JsonResponse({"error": "The transfer could not be cancelled safely."}, status=500)
    log_action(request, "transfer.cancelled", detail=f"filename={transfer.filename}")
    return JsonResponse({"transfer": _serialize_transfer(transfer)})


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_pause(request, transfer_id):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404
    try:
        transfer = pause_transfer(transfer, request.user)
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        _log_unexpected("pause", exc, transfer_id=transfer_id)
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    log_action(request, "transfer.paused", detail=f"filename={transfer.filename}")
    return JsonResponse({"transfer": _serialize_transfer(transfer)})


@require_section_permission("transfers")
@honeypot_exempt
@require_POST
def transfer_retry(request, transfer_id):
    limited = _transfer_rate_limit(request)
    if limited is not None:
        return limited
    transfer = _owned_transfer(request, transfer_id)
    if transfer is None:
        raise Http404
    try:
        transfer = retry_transfer(transfer, request.user)
    except (ServerFilesError, PermissionDenied, ValueError) as exc:
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    except Exception as exc:
        _log_unexpected("retry", exc, transfer_id=transfer_id)
        message, status = _service_error(exc)
        return JsonResponse({"error": message, "error_code": _transfer_error_code(exc)}, status=status)
    log_action(request, "transfer.retried", detail=f"filename={transfer.filename} retry={transfer.retry_count}")
    return JsonResponse({"transfer": _serialize_transfer(transfer)})

