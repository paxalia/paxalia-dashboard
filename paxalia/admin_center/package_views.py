"""Paxalia Admin package and localization surfaces."""

from __future__ import annotations

import os
import tempfile
import uuid
import logging
import stat
from pathlib import Path
from datetime import datetime, timezone

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from honeypot.decorators import honeypot_exempt
from django.http import QueryDict

from ..security_audit import log_action
from ..admin_security import admin_security_required
from ..settings import get_config
from ..packages.engine import PackageError, export_model, export_models, import_package, inspect_package, preview_package, build_retry_package
from ..packages.format import read_package
from ..packages.format import paxalia_version
from ..packages.localization import completeness_for_queryset, is_translatable_model, language_choices, save_translation, translation_editor_fields
from .permissions import require_staff, require_view, require_change
from .query import build_changelist
from .registry import registry

logger = logging.getLogger("paxalia.admin.packages")

_PACKAGE_TEMP_TTL_SECONDS = 24 * 60 * 60
_PACKAGE_TEMP_CLEANUP_LIMIT = 100



def _public_package_error(exc):
    if isinstance(exc, PackageError):
        return str(exc)[:500]
    if isinstance(exc, PermissionDenied):
        return _("You do not have permission to perform this package operation.")
    if isinstance(exc, ValidationError):
        return _("The package operation failed validation.")
    logger.exception("Paxalia Admin package operation failed")
    return _("The package operation could not be completed. The failure has been recorded.")


def _secure_pending_path(path, root):
    candidate = Path(path)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionDenied from exc
    if candidate.is_symlink():
        raise PermissionDenied
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionDenied from exc
    return resolved


def _read_pending_file(path, max_bytes):
    """Read a session-owned package without following a final symlink."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise Http404 from exc
    except OSError as exc:
        raise PermissionDenied from exc
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISREG(stat_result.st_mode):
            raise PermissionDenied
        if stat.S_IMODE(stat_result.st_mode) & 0o077:
            raise PermissionDenied
        getuid = getattr(os, "getuid", None)
        if getuid is not None and stat_result.st_uid != getuid():
            raise PermissionDenied
        if stat_result.st_size > max_bytes:
            raise Http404
        with os.fdopen(fd, "rb") as handle:
            fd = None
            raw = handle.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise Http404
        return raw
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _require_enabled():
    if not get_config().get("ADMIN_ENABLED", True):
        raise Http404


def _base(definition=None, **extra):
    context = {
        "active_page": "admin_model" if definition else "admin_home",
        "page_title": _("Paxalia Packages") if definition is None else definition.verbose_name_plural,
        "page_subtitle": _("Safe logical import/export for Django application data") if definition is None else "",
        "definition": definition,
    }
    context.update(extra)
    return context


def _pending_root():
    root = Path(tempfile.gettempdir()) / "paxalia-admin-imports"
    try:
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileNotFoundError:
        Path(tempfile.gettempdir()).mkdir(mode=0o700, parents=True, exist_ok=True)
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError:
        pass

    flags = getattr(os, "O_RDONLY", 0)
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(root, flags)
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
        raise PermissionDenied from exc
    try:
        stat_result = os.fstat(fd)
        if not stat.S_ISDIR(stat_result.st_mode):
            raise PermissionDenied
        try:
            os.fchmod(fd, 0o700)
        except OSError as exc:
            raise PermissionDenied from exc
        stat_result = os.fstat(fd)
        if stat.S_IMODE(stat_result.st_mode) & 0o077:
            raise PermissionDenied
        getuid = getattr(os, "getuid", None)
        if getuid is not None and stat_result.st_uid != getuid():
            raise PermissionDenied
    finally:
        os.close(fd)
    return root


def _cleanup_stale_package_files(root):
    """Bound disk use from abandoned session-owned package artifacts."""
    now = datetime.now(timezone.utc).timestamp()
    try:
        entries = list(root.iterdir())
    except OSError:
        return
    cleaned = 0
    for candidate in entries:
        if cleaned >= _PACKAGE_TEMP_CLEANUP_LIMIT:
            break
        if candidate.is_symlink() or candidate.suffix != ".paxalia":
            continue
        try:
            stat_result = candidate.stat()
            if not stat.S_ISREG(stat_result.st_mode):
                continue
            getuid = getattr(os, "getuid", None)
            if getuid is not None and stat_result.st_uid != getuid():
                continue
            if now - stat_result.st_mtime < _PACKAGE_TEMP_TTL_SECONDS:
                continue
            candidate.unlink(missing_ok=True)
            cleaned += 1
        except OSError:
            continue


def _max_package_bytes():
    try:
        return max(1, int(get_config().get("PACKAGE_MAX_FILE_SIZE_MB", 100) or 100)) * 1024 * 1024
    except (TypeError, ValueError):
        return 100 * 1024 * 1024


def _safe_pending_id():
    return uuid.uuid4().hex


def _save_pending(request, raw: bytes):
    if len(raw) > _max_package_bytes():
        raise ValidationError(_("The package exceeds the configured upload limit."))
    root = _pending_root()
    _cleanup_stale_package_files(root)
    pending_id = _safe_pending_id()
    path = root / f"{pending_id}.paxalia"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    _clear_pending(request)
    request.session["paxalia_pending_package"] = {"id": pending_id, "path": str(path)}
    request.session.modified = True
    return pending_id


def _load_pending(request, pending_id):
    data = request.session.get("paxalia_pending_package") or {}
    if data.get("id") != pending_id:
        raise PermissionDenied
    root = _pending_root().resolve()
    path = _secure_pending_path(str(data.get("path") or ""), root)
    max_bytes = _max_package_bytes()
    return _read_pending_file(path, max_bytes), path


def _clear_pending(request):
    data = request.session.pop("paxalia_pending_package", None) or {}
    path = data.get("path")
    if path:
        try:
            candidate = _secure_pending_path(path, _pending_root().resolve())
            candidate.unlink(missing_ok=True)
        except Exception:
            pass
    request.session.modified = True


def _save_retry(request, raw: bytes):
    if len(raw) > _max_package_bytes():
        raise ValidationError(_("The retry package exceeds the configured maximum size."))
    root = _pending_root()
    _cleanup_stale_package_files(root)
    retry_id = _safe_pending_id()
    path = root / f"retry-{retry_id}.paxalia"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    _clear_retry(request)
    request.session["paxalia_retry_package"] = {"id": retry_id, "path": str(path)}
    request.session.modified = True
    return retry_id


def _load_retry(request, retry_id):
    data = request.session.get("paxalia_retry_package") or {}
    if data.get("id") != retry_id:
        raise PermissionDenied
    root = _pending_root().resolve()
    path = _secure_pending_path(str(data.get("path") or ""), root)
    max_bytes = _max_package_bytes()
    return _read_pending_file(path, max_bytes), path


def _clear_retry(request):
    data = request.session.pop("paxalia_retry_package", None) or {}
    path = data.get("path")
    if path:
        try:
            candidate = _secure_pending_path(path, _pending_root().resolve())
            candidate.unlink(missing_ok=True)
        except Exception:
            pass
    request.session.modified = True


@admin_security_required
@honeypot_exempt
def package_center(request):
    _require_enabled()
    require_staff(request)
    definitions = registry.definitions(request)
    localized = [definition for definition in definitions if definition.capabilities(request).localization]
    protected = sum(int(definition.capabilities(request).protected) for definition in definitions)
    recent = []
    try:
        from ..models import SecurityAuditLog
        recent = SecurityAuditLog.objects.select_related("user").filter(action__startswith="package.").order_by("-created_at")[:12]
    except Exception:
        recent = []
    context = _base(
        active_page="admin_packages",
        application_count=len({definition.app_label for definition in definitions}),
        model_count=len(definitions),
        localization_count=len(localized),
        protected_count=protected,
        package_version=1,
        paxalia_version=paxalia_version(),
        languages=language_choices(),
        recent_operations=recent,
    )
    return render(request, "paxalia/admin/package_center.html", context)


@admin_security_required
@honeypot_exempt
def package_history(request):
    _require_enabled()
    require_staff(request)
    from ..models import SecurityAuditLog
    queryset = SecurityAuditLog.objects.select_related("user").filter(action__startswith="package.").order_by("-created_at")
    search = (request.GET.get("q") or "").strip()
    if search:
        from django.db.models import Q
        queryset = queryset.filter(Q(action__icontains=search) | Q(detail__icontains=search))
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "paxalia/admin/package_history.html", _base(
        title=_("Package history"),
        page_title=_("Package history"),
        page_subtitle=_("Import, export, validation, and protected package operations"),
        active_page="admin_packages",
        page_obj=page_obj,
        search=search,
        paginator=paginator,
    ))


def _filtered_queryset(definition, request, filter_query):
    if not filter_query:
        return definition.model_admin.get_queryset(request)
    original = request.GET
    try:
        request.GET = QueryDict(filter_query, mutable=False)
        return build_changelist(definition, request).queryset
    finally:
        request.GET = original


@admin_security_required
@staff_member_required
@honeypot_exempt

def package_export_center(request):
    _require_enabled()
    require_staff(request)
    definitions = registry.definitions(request)
    selected_labels = []
    export_error = None
    encrypted_value = False
    translations_only_value = False
    if request.method == "POST":
        selected_labels = [str(value).strip().lower() for value in request.POST.getlist("models") if str(value).strip()]
        selected = [item.model for item in definitions if item.label.lower() in selected_labels]
        encrypted_value = request.POST.get("encrypted") == "on"
        translations_only_value = request.POST.get("translations_only") == "on"
        password = request.POST.get("password") or None
        try:
            if not selected:
                raise PackageError(_("Select at least one model to export."))
            if encrypted_value and not password:
                raise PackageError(_("A package password is required for encryption."))
            raw = export_models(
                selected,
                request,
                translations_only=translations_only_value,
                password=password if encrypted_value else None,
            )
            log_action(request, "package.export", detail=f"models={len(selected)};scope=models;encrypted={encrypted_value}")
            response = HttpResponse(raw, content_type="application/octet-stream")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            response["Content-Disposition"] = f'attachment; filename="paxalia-package-{stamp}.paxalia"'
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["X-Content-Type-Options"] = "nosniff"
            return response
        except PermissionDenied:
            raise
        except Exception as exc:
            export_error = _public_package_error(exc)
            messages.error(request, export_error)
    groups = {}
    for definition in definitions:
        groups.setdefault(definition.app_label, []).append(definition)
    return render(request, "paxalia/admin/package_export_center.html", _base(
        active_page="admin_packages",
        page_title=_("Export package"),
        page_subtitle=_("Create a multi-model logical .paxalia package"),
        groups=groups,
        history_url=reverse("paxalia:admin_package_history"),
        selected_labels=selected_labels,
        export_error=export_error,
        encrypted_value=encrypted_value,
        translations_only_value=translations_only_value,
        require_encryption_for_protected=bool(get_config().get("PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED", True)),
    ))


@admin_security_required
@staff_member_required
@honeypot_exempt

def package_import_center(request):
    _require_enabled()
    require_staff(request)
    pending = request.POST.get("pending_id") or request.GET.get("pending_id")
    if request.method == "POST" and request.FILES.get("package"):
        uploaded = request.FILES["package"]
        max_bytes = _max_package_bytes()
        if uploaded.size > max_bytes:
            messages.error(request, _("The package exceeds the configured upload limit."))
        else:
            raw = uploaded.read(max_bytes + 1)
            try:
                manifest, _content, _encrypted = read_package(raw, max_size=max_bytes)
                upload_password = request.POST.get("password") or None
                _manifest, _payload, models = inspect_package(raw, password=upload_password)
                registered = {definition.label.lower(): definition for definition in registry.definitions(request)}
                missing = [label for label in models if label.lower() not in registered]
                if missing:
                    raise PackageError(_("The package contains models that are not available through Paxalia Admin: %(models)s") % {"models": ", ".join(missing[:8])})
                preview = preview_package(raw, password=upload_password, conflict=request.POST.get("conflict") or "update", request=request)
                pending = _save_pending(request, raw)
                return render(request, "paxalia/admin/package_import_center.html", _base(
                    active_page="admin_packages",
                    page_title=_("Import package"),
                    page_subtitle=_("Validate the complete package before applying any model changes"),
                    manifest=manifest, preview=preview, pending_id=pending,
                    conflict=request.POST.get("conflict") or "update",
                ))
            except Exception as exc:
                messages.error(request, _public_package_error(exc))

    if request.method == "POST" and pending and request.POST.get("commit") == "1":
        raw, _path = _load_pending(request, pending)
        try:
            commit_password = request.POST.get("password") or None
            dry_run = request.POST.get("dry_run") == "1"
            result = import_package(
                raw, request, password=commit_password,
                conflict=request.POST.get("conflict") or "update",
                atomic=request.POST.get("mode", "atomic") == "atomic", dry_run=dry_run,
            )
            retry_id = None
            if result.get("failed") and not dry_run:
                retry_raw = build_retry_package(raw, result, password=commit_password)
                if retry_raw:
                    retry_id = _save_retry(request, retry_raw)
            action = "package.dry_run" if dry_run else "package.import"
            log_action(request, action, detail=f"package={result.get('package_id')};models={result.get('model_count',0)};created={result.get('created',0)};updated={result.get('updated',0)};failed={result.get('failed',0)}")
            request.session["paxalia_last_package_result"] = result
            request.session["paxalia_last_package_result"]["dry_run"] = dry_run
            request.session.modified = True
            _clear_pending(request)
            return render(request, "paxalia/admin/package_result.html", _base(
                active_page="admin_packages", page_title=_("Dry run result") if dry_run else _("Import completed"),
                page_subtitle=_("Validation and operation planning completed. No database changes were committed.") if dry_run else _("Review the result and retry only failed records when available."),
                result=result, retry_id=retry_id, dry_run=dry_run,
                next_url=reverse("paxalia:admin_packages"),
                failure_report_url=reverse("paxalia:admin_package_failure_report"),
                retry_url=reverse("paxalia:admin_package_retry", kwargs={"retry_id": retry_id}) if retry_id else None,
            ))
        except PermissionDenied:
            raise
        except Exception as exc:
            messages.error(request, _public_package_error(exc))
    return render(request, "paxalia/admin/package_import_center.html", _base(
        active_page="admin_packages",
        page_title=_("Import package"),
        page_subtitle=_("Upload and validate a multi-model .paxalia package"),
        pending_id=pending, preview=None,
    ))


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_export(request, app_label, model_name):
    _require_enabled()
    require_staff(request)
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    capabilities = definition.capabilities(request)

    if request.method == "POST":
        scope = (request.POST.get("scope") or "all").strip()
        selected = request.POST.getlist("selected")
        filter_query = request.POST.get("filter_query") or ""
        encrypted = request.POST.get("encrypted") == "on"
        password = request.POST.get("password") or None
        try:
            if scope not in {"all", "selected", "filtered"}:
                raise PackageError(_("The selected export scope is invalid."))
            queryset = None
            selected_ids = None
            if scope == "selected":
                if not selected:
                    raise PackageError(_("Select at least one record to export."))
                selected_ids = selected
            elif scope == "filtered":
                queryset = _filtered_queryset(definition, request, filter_query)
            if encrypted and not password:
                raise PackageError(_("A package password is required for encryption."))
            raw = export_model(
                definition.model,
                request,
                queryset=queryset,
                selected_ids=selected_ids,
                translations_only=request.POST.get("translations_only") == "on",
                password=password if encrypted else None,
            )
            log_action(request, "package.export", detail=f"model={definition.label};scope={scope};encrypted={encrypted}")
            response = HttpResponse(raw, content_type="application/octet-stream")
            safe_label = definition.label.replace(".", "-").replace("/", "-")[:80]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            response["Content-Disposition"] = f'attachment; filename="paxalia-{safe_label}-{stamp}.paxalia"'
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["X-Content-Type-Options"] = "nosniff"
            return response
        except PermissionDenied:
            raise
        except Exception as exc:
            messages.error(request, _public_package_error(exc))

    return render(request, "paxalia/admin/package_export.html", _base(
        definition,
        page_title=_("Export %(model)s") % {"model": definition.verbose_name_plural},
        page_subtitle=_("Create a safe, logical .paxalia package from this registered model"),
        active_page="admin_model",
        overview_url=definition.url("admin_model_overview"),
        list_url=definition.url("admin_model_list"),
        export_url=definition.url("admin_model_export"),
        can_select=True,
        sensitive=capabilities.protected,
        single_export_protected=bool(definition.protected),
        require_encryption_for_protected=bool(get_config().get("PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED", True)),
        django_fallback_url=registry.django_admin_url(),
    ))


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_import(request, app_label, model_name):
    _require_enabled()
    require_staff(request)
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    pending = request.POST.get("pending_id") or request.GET.get("pending_id")

    if request.method == "POST" and request.FILES.get("package"):
        uploaded = request.FILES["package"]
        max_bytes = _max_package_bytes()
        if uploaded.size > max_bytes:
            messages.error(request, _("The package exceeds the configured upload limit."))
        else:
            raw = uploaded.read(max_bytes + 1)
            try:
                manifest, _content, _encrypted = read_package(raw)
                upload_password = request.POST.get("password") or None
                manifest, payload, models = inspect_package(raw, password=upload_password)
                if set(models.keys()) - {definition.label, definition.model._meta.label_lower}:
                    raise PackageError(_("This model import accepts only packages containing this model."))
                # Do not echo package contents into HTML. The preview only
                # contains bounded aggregate data and the package identity.
                preview = preview_package(raw, password=upload_password, conflict=request.POST.get("conflict") or "update", request=request)
                pending = _save_pending(request, raw)
                return render(request, "paxalia/admin/package_import.html", _base(
                    definition,
                    page_title=_("Import into %(model)s") % {"model": definition.verbose_name_plural},
                    page_subtitle=_("Validate first, then choose how existing identities should be handled"),
                    active_page="admin_model",
                    overview_url=definition.url("admin_model_overview"),
                    list_url=definition.url("admin_model_list"),
                    import_url=definition.url("admin_model_import"),
                    manifest=manifest,
                    preview=preview,
                    pending_id=pending,
                    conflict=request.POST.get("conflict") or "update",
                ))
            except Exception as exc:
                messages.error(request, _public_package_error(exc))

    if request.method == "POST" and pending and request.POST.get("commit") == "1":
        raw, _path = _load_pending(request, pending)
        try:
            commit_password = request.POST.get("password") or None
            dry_run = request.POST.get("dry_run") == "1"
            result = import_package(
                raw, request, password=commit_password,
                conflict=request.POST.get("conflict") or "update",
                atomic=request.POST.get("mode", "atomic") == "atomic", dry_run=dry_run,
            )
            retry_id = None
            if result.get("failed") and not dry_run:
                retry_raw = build_retry_package(raw, result, password=commit_password)
                if retry_raw:
                    retry_id = _save_retry(request, retry_raw)
            action = "package.dry_run" if dry_run else "package.import"
            log_action(request, action, detail=f"model={definition.label};package={result.get('package_id')};created={result.get('created',0)};updated={result.get('updated',0)};failed={result.get('failed',0)}")
            request.session["paxalia_last_package_result"] = result
            request.session["paxalia_last_package_result"]["dry_run"] = dry_run
            request.session.modified = True
            _clear_pending(request)
            return render(request, "paxalia/admin/package_result.html", _base(
                active_page="admin_model", page_title=_("Dry run result") if dry_run else _("Import completed"),
                page_subtitle=_("Validation and operation planning completed. No database changes were committed.") if dry_run else _("Review the result and retry only failed records when available."),
                result=result, retry_id=retry_id, dry_run=dry_run,
                next_url=definition.url("admin_model_list"),
                failure_report_url=reverse("paxalia:admin_package_failure_report"),
                retry_url=reverse("paxalia:admin_package_retry", kwargs={"retry_id": retry_id}) if retry_id else None,
            ))
        except PermissionDenied:
            raise
        except Exception as exc:
            messages.error(request, _public_package_error(exc))

    return render(request, "paxalia/admin/package_import.html", _base(
        definition,
        page_title=_("Import into %(model)s") % {"model": definition.verbose_name_plural},
        page_subtitle=_("Upload and validate a Paxalia logical data package"),
        active_page="admin_model",
        overview_url=definition.url("admin_model_overview"),
        list_url=definition.url("admin_model_list"),
        import_url=definition.url("admin_model_import"),
        pending_id=pending,
        preview=None,
    ))


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_localization(request, app_label, model_name):
    _require_enabled()
    require_staff(request)
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    if not is_translatable_model(definition.model):
        return render(request, "paxalia/admin/model_localization.html", _base(
            definition,
            page_title=_("Localization"),
            page_subtitle=_("This model does not expose a recognized translation layer."),
            overview_url=definition.url("admin_model_overview"),
            list_url=definition.url("admin_model_list"),
            support=False,
        ))

    if request.method == "POST" and request.POST.get("translation_save") == "1":
        object_id = (request.POST.get("object_id") or "").strip()
        language = (request.POST.get("language") or "").strip()
        configured_languages = {code for code, _ in language_choices()}
        if language not in configured_languages:
            messages.error(request, _("That language is not enabled in the current site configuration."))
        else:
            queryset = definition.model_admin.get_queryset(request)
            try:
                obj = queryset.get(pk=object_id)
                require_change(definition, request, obj)
                readonly_fields = set()
                try:
                    readonly_fields.update(
                        str(name)
                        for name in (definition.model_admin.get_readonly_fields(request, obj) or ())
                        if isinstance(name, str)
                    )
                except Exception:
                    logger.exception("Unable to resolve readonly translation fields for %s", definition.label)
                    raise PackageError(_("The model's readonly translation policy could not be resolved safely."))
                translation_fields = translation_editor_fields(
                    definition.model,
                    excluded_names=set(definition.hidden_fields) | readonly_fields,
                )
                values = {field["name"]: request.POST.get(field["name"], "") for field in translation_fields}
                save_translation(obj, language, values)
                log_action(request, "admin.translation.save", detail=f"model={definition.label};object={object_id};language={language}")
                messages.success(request, _("Translation saved."))
                localization_url = definition.url("admin_model_localization")
                page = str(request.POST.get("page") or "").strip()
                if page.isdigit() and int(page) > 1:
                    localization_url = f"{localization_url}?page={int(page)}"
                return redirect(localization_url)
            except PermissionDenied:
                raise
            except Exception as exc:
                messages.error(request, _public_package_error(exc))

    queryset = definition.model_admin.get_queryset(request)
    try:
        page_size = max(10, min(int(get_config().get("ADMIN_LIST_PER_PAGE", 50) or 50), 100))
    except (TypeError, ValueError):
        page_size = 50
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    data = completeness_for_queryset(
        queryset,
        limit=page_size,
        offset=(page_obj.number - 1) * page_size,
        excluded_names=set(definition.hidden_fields),
    )
    page_range = paginator.get_elided_page_range(page_obj.number)
    return render(request, "paxalia/admin/model_localization.html", _base(
        definition,
        page_title=_("Localization"),
        page_subtitle=_("Translation completeness and multilingual content coverage"),
        overview_url=definition.url("admin_model_overview"),
        list_url=definition.url("admin_model_list"),
        import_url=definition.url("admin_model_import"),
        export_url=definition.url("admin_model_export"),
        support=True,
        page_obj=page_obj,
        page_range=page_range,
        page_size=page_size,
        **data,
    ))



@admin_security_required
@staff_member_required
def package_failure_report(request):
    _require_enabled()
    require_staff(request)
    result = request.session.get("paxalia_last_package_result")
    if not result:
        raise Http404
    import json
    response = HttpResponse(json.dumps(result.get("errors") or [], ensure_ascii=False, indent=2), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="paxalia-import-failures.json"'
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@admin_security_required
@staff_member_required
def package_retry(request, retry_id):
    _require_enabled()
    require_staff(request)
    raw, _path = _load_retry(request, retry_id)
    response = HttpResponse(raw, content_type="application/octet-stream")
    response["Content-Disposition"] = 'attachment; filename="paxalia-failed-records-retry.paxalia"'
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response

