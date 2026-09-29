"""Authenticated views for Paxalia Server Files."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate
from django.db.models import Q
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from ..admin_security import admin_security_preflight
from ..permissions import require_section_permission
from ..security_audit import log_action
from ..settings import get_config
from . import service
from .audit import begin_operation, finish_operation
from .exceptions import ServerFilesError
from .models import ServerFileOperation
from .policy import get_roots, has_capability, is_sensitive, split_relative_path
from .permissions import require_capability
from honeypot.decorators import honeypot_exempt

logger = logging.getLogger("paxalia.server_files.views")
_REAUTH_SESSION_KEY = "analytics_backup_reauth_at"


def _has_recent_reauth(request):
    stamp = request.session.get(_REAUTH_SESSION_KEY)
    if not stamp:
        return False
    try:
        reauthed_at = datetime.fromisoformat(str(stamp))
        if timezone.is_naive(reauthed_at):
            reauthed_at = timezone.make_aware(reauthed_at, timezone.get_current_timezone())
        minutes = int(get_config().get("BACKUP_REAUTH_MINUTES", 15))
        if minutes <= 0 or minutes > 1440:
            return False
    except (TypeError, ValueError, OverflowError):
        return False
    return timezone.now() <= reauthed_at + timedelta(minutes=minutes)


def _safe_next(request, value):
    value = str(value or "").strip()
    if not value:
        return reverse("paxalia:server_files")
    if not url_has_allowed_host_and_scheme(
        url=value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return reverse("paxalia:server_files")
    return value


def _require_recent_reauth(request):
    if _has_recent_reauth(request):
        return None
    next_url = _safe_next(request, request.get_full_path())
    url = reverse("paxalia:server_files_reauth")
    return redirect(f"{url}?{urlencode({'next': next_url})}")


def _rate_key(request, action):
    # Ignore forwarded headers and hash identifiers so raw IP/user values are
    # not embedded in cache keys.
    actor = str(getattr(request.user, "pk", "anonymous"))
    address = str(request.META.get("REMOTE_ADDR", ""))[:128]
    raw = f"{actor}\0{address}\0{action}".encode("utf-8", "replace")
    return "paxalia:server-files:rate:" + hashlib.sha256(raw).hexdigest()


def _enforce_rate_limit(request, action):
    values = service.limits()
    key = _rate_key(request, action)
    limit = values["read_rate_limit"] if action in {"list", "preview", "download", "history"} else values["rate_limit"]
    try:
        # Initialize once, then use the backend's atomic increment. A race or
        # expired-key failure is rejected instead of allowing an unmetered op.
        cache.add(key, 0, timeout=values["rate_window"])
        count = cache.incr(key)
        if count > limit:
            from .exceptions import ServerFilesRateLimited
            raise ServerFilesRateLimited()
    except ServerFilesError:
        raise
    except Exception:
        logger.error("Server Files rate-limit backend unavailable (action=%s)", action)
        from .exceptions import ServerFilesRateLimited
        raise ServerFilesRateLimited(
            "The operation is temporarily unavailable because rate limiting could not be verified."
        ) from None


def _sensitive_path(path):
    try:
        return is_sensitive(split_relative_path(path))
    except ServerFilesError:
        return False


def _audit(request, operation, *, root_id="", path="", target_root_id="", target_path=""):
    return begin_operation(
        request,
        operation,
        root_id=root_id,
        path=path,
        target_root_id=target_root_id,
        target_path=target_path,
        force_redact=_sensitive_path(path) or _sensitive_path(target_path),
        required=True,
    )


def _require_capability_audited(
    request, codename, operation, *, root_id="", path="", target_root_id="", target_path=""
):
    """Reject a capability and retain a content-free denied-attempt record."""
    if has_capability(request.user, codename):
        return
    try:
        record = begin_operation(
            request,
            operation,
            root_id=root_id,
            path=path,
            target_root_id=target_root_id,
            target_path=target_path,
            force_redact=_sensitive_path(path) or _sensitive_path(target_path),
            required=False,
        )
        if record is not None:
            finish_operation(request, record, "denied", error_code="permission_denied")
        else:
            log_action(request, f"server_files.{operation}.denied", detail="permission_denied")
    except Exception:
        # A failed audit sink must not grant an operation or turn a denial into
        # a different response.
        logger.error("Unable to record denied Server Files permission (operation=%s)", operation)
    require_capability(request.user, codename)


def _finish_failed(request, record, exc):
    if record is not None:
        finish_operation(
            request,
            record,
            "denied" if getattr(exc, "http_status", 400) == 403 else "failed",
            error_code=getattr(exc, "code", "internal_error"),
        )


def _failure_response(request, exc):
    status = getattr(exc, "http_status", 400)
    return render(request, "paxalia/server_files_error.html", {
        "active_page": "server_files",
        "page_title": _("Server Files unavailable"),
        "error_message": _(getattr(exc, "public_message", "The filesystem operation could not be completed.")),
    }, status=status)


def _capabilities(user):
    names = (
        "download_server_files", "upload_server_files", "modify_server_files",
        "delete_server_files", "view_sensitive_files", "modify_sensitive_files",
    )
    return {name: has_capability(user, name) for name in names}


@require_section_permission("server_files")
@require_GET
def server_files(request):
    """Render a bounded single-directory listing; never walk recursively."""
    record = None
    try:
        roots = get_roots()
        if not roots:
            return render(request, "paxalia/server_files.html", {
                "active_page": "server_files",
                "page_title": _("Paxalia Server Files"),
                "roots": [],
                "listing": None,
                "capabilities": _capabilities(request.user),
                "empty_roots": True,
            })
        root_id = request.GET.get("root", roots[0].id)
        requested_path = request.GET.get("path", "")
        show_sensitive = request.GET.get("protected") == "1"
        _enforce_rate_limit(request, "list")
        if show_sensitive:
            _require_capability_audited(
                request, "view_sensitive_files", "list", root_id=root_id, path=requested_path
            )
            redirect_response = _require_recent_reauth(request)
            if redirect_response:
                return redirect_response
        record = _audit(request, "list", root_id=root_id, path=requested_path)
        listing = service.list_directory(
            root_id,
            requested_path,
            request.user,
            page=request.GET.get("page", 1),
            search=request.GET.get("q", ""),
            sort_by=request.GET.get("sort", "name"),
            direction=request.GET.get("dir", "asc"),
            show_hidden=request.GET.get("hidden") == "1",
            show_sensitive=show_sensitive,
        )
        finish_operation(request, record, "success")
        crumbs = []
        prefix = []
        for part in listing["parts"]:
            prefix.append(part)
            crumbs.append({"name": part, "path": "/".join(prefix)})
        listing["breadcrumbs"] = crumbs
        listing["parent_path"] = "/".join(listing["parts"][:-1])
        listing["at_root"] = not listing["parts"]
        query_base = {"root": listing["root"].id, "path": listing["path"]}
        if listing["search"]:
            query_base["q"] = listing["search"]
        if listing["show_hidden"]:
            query_base["hidden"] = "1"
        if listing["show_sensitive"]:
            query_base["protected"] = "1"
        toggle_params = dict(query_base)
        if listing["show_sensitive"]:
            toggle_params.pop("protected", None)
        else:
            toggle_params["protected"] = "1"
        listing["protected_toggle_url"] = reverse("paxalia:server_files") + "?" + urlencode(toggle_params)
        listing["sort_links"] = {}
        for key in ("name", "type", "size", "modified"):
            direction = "desc" if listing["sort_by"] == key and listing["direction"] == "asc" else "asc"
            listing["sort_links"][key] = "?" + urlencode({**query_base, "sort": key, "dir": direction})
        return render(request, "paxalia/server_files.html", {
            "active_page": "server_files",
            "page_title": _("Paxalia Server Files"),
            "roots": roots,
            "listing": listing,
            "capabilities": _capabilities(request.user),
            "empty_roots": False,
            "operation_url": reverse("paxalia:server_files_operation"),
            "history_url": reverse("paxalia:server_files_history"),
        })
    except ServerFilesError as exc:
        _finish_failed(request, record, exc)
        return _failure_response(request, exc)
    except Exception:
        _finish_failed(request, record, ServerFilesError())
        logger.error("Unexpected Server Files listing failure")
        return HttpResponse(_("The directory could not be listed."), status=500)


@require_section_permission("server_files")
@require_GET
def server_files_preview(request):
    root_id = request.GET.get("root", "")
    path = request.GET.get("path", "")
    record = None
    try:
        _enforce_rate_limit(request, "preview")
        if _sensitive_path(path):
            _require_capability_audited(
                request, "view_sensitive_files", "preview", root_id=root_id, path=path
            )
            redirect_response = _require_recent_reauth(request)
            if redirect_response:
                return redirect_response
        record = _audit(request, "preview", root_id=root_id, path=path)
        preview = service.preview_file(root_id, path, request.user)
        finish_operation(request, record, "success")
        return render(request, "paxalia/server_files_preview.html", {
            "active_page": "server_files",
            "page_title": _("Preview: %(name)s") % {"name": preview["filename"]},
            "preview": preview,
            "back_url": reverse("paxalia:server_files") + "?" + urlencode({
                "root": root_id,
                "path": "/".join(split_relative_path(path)[:-1]),
            }),
        })
    except ServerFilesError as exc:
        _finish_failed(request, record, exc)
        return _failure_response(request, exc)
    except Exception:
        _finish_failed(request, record, ServerFilesError())
        logger.error("Unexpected Server Files preview failure")
        return HttpResponse(_("The preview could not be opened."), status=500)


@require_section_permission("server_files")
@require_GET
def server_files_download(request):
    root_id = request.GET.get("root", "")
    path = request.GET.get("path", "")
    record = None
    try:
        _enforce_rate_limit(request, "download")
        _require_capability_audited(
            request, "download_server_files", "download", root_id=root_id, path=path
        )
        if _sensitive_path(path):
            _require_capability_audited(
                request, "view_sensitive_files", "download", root_id=root_id, path=path
            )
            redirect_response = _require_recent_reauth(request)
            if redirect_response:
                return redirect_response
        record = _audit(request, "download", root_id=root_id, path=path)
        stream, metadata, filename, _root = service.open_download(root_id, path, request.user)
        finish_operation(request, record, "success")
        response = FileResponse(stream, as_attachment=True, filename=filename, content_type="application/octet-stream")
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Length"] = str(metadata.st_size)
        return response
    except ServerFilesError as exc:
        _finish_failed(request, record, exc)
        return _failure_response(request, exc)
    except PermissionDenied:
        raise
    except Exception:
        _finish_failed(request, record, ServerFilesError())
        logger.error("Unexpected Server Files download failure")
        return HttpResponse(_("The file could not be downloaded."), status=500)


def _server_files_upload_preflight(request, *args, **kwargs):
    """Reject oversized/unknown-length operation bodies before POST parsing."""
    try:
        maximum = service.limits()["upload_bytes"]
    except ServerFilesError as exc:
        return HttpResponse(exc.public_message, status=exc.http_status)
    raw_length = request.META.get("CONTENT_LENGTH")
    try:
        content_length = int(raw_length)
    except (TypeError, ValueError, OverflowError):
        return HttpResponse(_("A bounded Content-Length is required for Server Files operations."), status=411)
    # Include a small allowance for multipart headers and hidden form fields.
    if content_length < 0 or content_length > maximum + 1024 * 1024:
        return HttpResponse(_("The request exceeds the configured Server Files upload limit."), status=413)
    return None


@honeypot_exempt
@require_section_permission("server_files")
@require_POST
@admin_security_preflight(_server_files_upload_preflight)
def server_files_operation(request):
    action = str(request.POST.get("operation", "")).strip().casefold()
    allowed = {"upload", "mkdir", "rename", "move", "copy", "delete"}
    if action not in allowed:
        return HttpResponse(_("Unsupported Server Files operation."), status=400)

    permission = {
        "upload": "upload_server_files",
        "mkdir": "modify_server_files",
        "rename": "modify_server_files",
        "move": "modify_server_files",
        "copy": "modify_server_files",
        "delete": "delete_server_files",
    }[action]

    root_id = str(request.POST.get("root", ""))
    path = str(request.POST.get("path", ""))
    target_root_id = str(request.POST.get("target_root", ""))
    target_path = str(request.POST.get("target_path", ""))
    name = str(request.POST.get("name", ""))
    upload = request.FILES.get("file") if action == "upload" else None
    effective_name = name or str(getattr(upload, "name", ""))

    try:
        _enforce_rate_limit(request, action)
    except ServerFilesError as exc:
        return _failure_response(request, exc)
    _require_capability_audited(
        request, permission, action, root_id=root_id, path=path,
        target_root_id=target_root_id, target_path=target_path,
    )

    try:
        source_parts = split_relative_path(path, allow_empty=action in {"upload", "mkdir"})
        if action == "rename":
            destination_parts = (*source_parts[:-1], effective_name)
            destination_root = root_id
        elif action in {"move", "copy"}:
            destination_parts = (*split_relative_path(target_path), effective_name or (source_parts[-1] if source_parts else ""))
            destination_root = target_root_id or root_id
        elif action in {"upload", "mkdir"}:
            destination_parts = (*source_parts, effective_name)
            destination_root = root_id
        else:
            destination_parts = ()
            destination_root = ""
        sensitive = (
            _sensitive_path(path)
            or _sensitive_path("/".join(destination_parts))
            or _sensitive_path(target_path)
        )
    except ServerFilesError:
        # Let the service return the canonical validation error; the audit
        # layer independently converts invalid path spellings to [invalid].
        source_parts = ()
        sensitive = False
        destination_parts = ()
        destination_root = target_root_id or root_id

    if sensitive:
        _require_capability_audited(
            request, "view_sensitive_files", action, root_id=root_id, path=path,
            target_root_id=destination_root, target_path="/".join(destination_parts),
        )
        redirect_response = _require_recent_reauth(request)
        if redirect_response:
            return redirect_response
    if action == "delete":
        redirect_response = _require_recent_reauth(request)
        if redirect_response:
            return redirect_response

    audit_target_root = target_root_id
    audit_target_path = target_path
    if action in {"upload", "mkdir", "rename", "move", "copy"}:
        audit_target_root = destination_root
        audit_target_path = "/".join(destination_parts)

    record = None
    try:
        record = _audit(
            request,
            action,
            root_id=root_id,
            path=path,
            target_root_id=audit_target_root,
            target_path=audit_target_path,
        )
        try:
            if action == "upload":
                if upload is None:
                    raise ServerFilesError("Select a file to upload.")
                service.upload_file(root_id, path, effective_name, upload, request.user)
            elif action == "mkdir":
                service.create_directory(root_id, path, effective_name, request.user)
            elif action == "rename":
                service.rename_or_move(root_id, path, root_id, "/".join(source_parts[:-1]), effective_name, request.user)
            elif action == "move":
                service.rename_or_move(root_id, path, destination_root, target_path, effective_name, request.user)
            elif action == "copy":
                service.copy_file(
                    root_id, path, destination_root, target_path,
                    effective_name or (source_parts[-1] if source_parts else ""), request.user,
                )
            elif action == "delete":
                service.delete_item(root_id, path, request.user)
            finish_operation(request, record, "success")
        except ServerFilesError as exc:
            _finish_failed(request, record, exc)
            raise
        except Exception:
            _finish_failed(request, record, ServerFilesError())
            raise
        messages.success(request, _("Server Files operation completed."))
    except ServerFilesError as exc:
        return _failure_response(request, exc)
    except PermissionDenied:
        raise
    except Exception:
        logger.error("Unexpected Server Files operation failure (operation=%s)", action)
        return HttpResponse(_("The filesystem operation could not be completed."), status=500)

    destination = reverse("paxalia:server_files")
    if root_id:
        destination += "?" + urlencode({"root": root_id, "path": path})
    return redirect(_safe_next(request, request.POST.get("next") or destination))


@require_section_permission("server_files")
@require_GET
def server_files_history(request):
    """Render a bounded, filterable operation-history view."""
    record = None
    try:
        config = get_config()
        page_size = int(config.get("FILE_MANAGER_HISTORY_PAGE_SIZE", 50))
        if page_size < 1 or page_size > 200:
            raise ValueError

        _enforce_rate_limit(request, "history")
        record = _audit(request, "history")

        operation_filter = str(request.GET.get("operation", "")).strip().casefold()
        status_filter = str(request.GET.get("status", "")).strip().casefold()
        search = str(request.GET.get("q", "")).strip()[:128]

        valid_operations = {value for value, _label in ServerFileOperation.OPERATIONS}
        valid_statuses = {value for value, _label in ServerFileOperation.STATUSES}
        if operation_filter not in valid_operations:
            operation_filter = ""
        if status_filter not in valid_statuses:
            status_filter = ""

        queryset = (
            ServerFileOperation.objects
            .select_related("actor")
            .order_by("-created_at", "-id")
        )

        if operation_filter:
            queryset = queryset.filter(operation=operation_filter)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(
                Q(root_id__icontains=search)
                | Q(path__icontains=search)
                | Q(target_root_id__icontains=search)
                | Q(target_path__icontains=search)
                | Q(request_id__icontains=search)
            )

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(request.GET.get("page", 1))

        history_rows = []
        for row in page_obj.object_list:
            actor_name = ""
            if row.actor is not None:
                getter = getattr(row.actor, "get_username", None)
                if callable(getter):
                    actor_name = str(getter())
                else:
                    actor_name = str(getattr(row.actor, "username", "") or "")

            history_rows.append({
                "created_at": row.created_at,
                "actor_name": actor_name,
                "operation": row.get_operation_display(),
                "root_id": row.root_id or "",
                "path": row.path or "",
                "target_root_id": row.target_root_id or "",
                "target_path": row.target_path or "",
                "status": row.status,
                "status_display": row.get_status_display(),
                "error_code": row.error_code or "",
                "request_id": row.request_id or "",
            })

        # Preserve active filters across pagination without trusting arbitrary
        # query-string destinations.
        previous_url = ""
        next_url = ""
        if page_obj.has_previous():
            params = request.GET.copy()
            params["page"] = page_obj.previous_page_number()
            previous_url = "?" + params.urlencode()
        if page_obj.has_next():
            params = request.GET.copy()
            params["page"] = page_obj.next_page_number()
            next_url = "?" + params.urlencode()

        finish_operation(request, record, "success")
        return render(request, "paxalia/server_files_history.html", {
            "active_page": "server_files_history",
            "page_title": _("Operation history"),
            "page_subtitle": _("Review the content-free audit trail of Server Files activity."),
            "history_rows": history_rows,
            "page_number": page_obj.number,
            "page_count": page_obj.paginator.num_pages,
            "total_records": page_obj.paginator.count,
            "has_previous": page_obj.has_previous(),
            "has_next": page_obj.has_next(),
            "previous_url": previous_url,
            "next_url": next_url,
            "operation_filter": operation_filter,
            "status_filter": status_filter,
            "search": search,
            "operation_choices": ServerFileOperation.OPERATIONS,
            "status_choices": ServerFileOperation.STATUSES,
            "browse_url": reverse("paxalia:server_files"),
        })
    except ServerFilesError as exc:
        _finish_failed(request, record, exc)
        return _failure_response(request, exc)
    except Exception:
        _finish_failed(request, record, ServerFilesError())
        logger.exception("Unexpected Server Files history failure")
        return HttpResponse(_("Operation history could not be loaded."), status=503)


def _server_files_reauth_preflight(request, *args, **kwargs):
    """Bound password reauthentication POSTs before Django parses form data."""
    if request.method != "POST":
        return None
    try:
        content_length = int(request.META.get("CONTENT_LENGTH"))
    except (TypeError, ValueError, OverflowError):
        return HttpResponse(_("A bounded request length is required."), status=411)
    if content_length < 0 or content_length > 8192:
        return HttpResponse(_("The reauthentication request is too large."), status=413)
    return None


@honeypot_exempt
@require_section_permission("server_files")
@admin_security_preflight(_server_files_reauth_preflight)
def server_files_reauth(request):
    next_url = _safe_next(request, request.GET.get("next") or request.POST.get("next"))
    if request.method == "GET":
        return render(request, "paxalia/server_files_reauth.html", {
            "active_page": "server_files",
            "page_title": _("Confirm your password"),
            "next": next_url,
        })
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        _enforce_rate_limit(request, "reauth")
    except ServerFilesError as exc:
        return _failure_response(request, exc)
    password = request.POST.get("password", "")
    if len(password) > 4096:
        password = ""
    user = authenticate(request, username=request.user.get_username(), password=password)
    if user is None or user.pk != request.user.pk:
        log_action(request, "server_files.reauth_failed")
        messages.error(request, _("Incorrect password."))
        return render(request, "paxalia/server_files_reauth.html", {
            "active_page": "server_files", "page_title": _("Confirm your password"), "next": next_url,
        }, status=401)
    request.session[_REAUTH_SESSION_KEY] = timezone.now().isoformat()
    log_action(request, "server_files.reauth_success")
    return redirect(next_url)
