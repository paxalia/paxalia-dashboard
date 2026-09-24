import logging

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBase, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from honeypot.decorators import honeypot_exempt

from ..logging.redaction import redact_text
from ..admin_security import admin_security_required
from ..models import LoginEvent, PaxaliaLogEvent, SecurityAuditLog
from ..settings import get_config
from .permissions import can_change, can_delete, require_add, require_change, require_delete, require_staff, require_view
from .query import build_changelist, column_headers, date_hierarchy_data, filter_specs, render_column_value
from .registry import registry
from .services import (
    audit,
    build_form_sections,
    build_list_editable_formset,
    deletion_preview,
    django_admin_model_log,
    execute_action,
    history_queryset,
    object_sections,
    object_statistics,
    perform_delete,
    perform_delete_queryset,
    protect_sensitive_form_fields,
    readonly_context,
    safe_form_class,
    save_list_editable,
)
from .utils import safe_object_repr

logger = logging.getLogger("paxalia.admin")


def _base_context(
    definition=None,
    *,
    active_page="admin_home",
    title="Paxalia Admin",
    subtitle="Django-native administration inside Paxalia",
):
    return {
        "active_page": active_page,
        "page_title": title,
        "page_subtitle": subtitle,
        "definition": definition,
    }


def _max_bulk():
    try:
        return max(1, min(int(get_config().get("ADMIN_MAX_BULK_OPERATIONS", 500) or 500), 5000))
    except (TypeError, ValueError):
        return 500


def _selected_ids(request):
    values = [str(value) for value in request.POST.getlist("selected") if str(value)]
    return list(dict.fromkeys(values))


def _require_enabled():
    if not get_config().get("ADMIN_ENABLED", True):
        raise Http404("Paxalia Admin is disabled.")


def _inline_instances(definition, request, obj=None):
    items = []
    for index, inline in enumerate(definition.model_admin.get_inline_instances(request, obj) or ()):
        try:
            can_view = inline.has_view_or_change_permission(request, obj)
        except Exception:
            can_view = False
        if not can_view:
            continue
        try:
            can_add = bool(inline.has_add_permission(request, obj))
        except Exception:
            can_add = False
        try:
            can_change_inline = bool(inline.has_change_permission(request, obj))
        except Exception:
            can_change_inline = False
        try:
            can_delete_inline = bool(inline.has_delete_permission(request, obj))
        except Exception:
            can_delete_inline = False
        FormSet = inline.get_formset(request, obj)
        prefix = f"{FormSet.get_default_prefix()}-{index}"
        kwargs = {"instance": obj, "prefix": prefix}
        if request.method == "POST":
            kwargs.update({"data": request.POST, "files": request.FILES})
        formset = FormSet(**kwargs)
        display_forms = []
        for inline_form in formset.forms:
            if inline_form.instance.pk is None and not can_add:
                continue
            if not can_change_inline:
                for field in inline_form.fields.values():
                    field.disabled = True
            if "DELETE" in inline_form.fields and not can_delete_inline:
                inline_form.fields["DELETE"].disabled = True
            display_forms.append(inline_form)
        items.append({
            "inline": inline,
            "formset": formset,
            "prefix": prefix,
            "forms": display_forms,
            "can_add": can_add,
            "can_change": can_change_inline,
            "can_delete": can_delete_inline,
        })
    return items


def _form_context(definition, request, form, obj=None):
    protect_sensitive_form_fields(definition, form, obj=obj)
    readonly_obj = obj if obj is not None else form.instance
    return {
        "form_sections": build_form_sections(definition, request, form, obj=obj),
        "readonly_rows": readonly_context(definition, request, readonly_obj),
    }


def _safe_int(value, default=1):
    try:
        return max(1, int(value or default))
    except (TypeError, ValueError):
        return default


def _protected_response(response, definition):
    if definition.protected and get_config().get("ADMIN_PROTECTED_NO_STORE", True):
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
    return response


@admin_security_required
@staff_member_required

def admin_home(request):
    require_staff(request)
    _require_enabled()
    definitions = registry.definitions(request)
    app_cards = registry.app_group_cards(request)
    recent_changes = SecurityAuditLog.objects.select_related("user").filter(action__startswith="admin.").order_by("-created_at")[:12]
    recent_logins = LoginEvent.objects.select_related("user").order_by("-created_at")[:8]
    recent_errors = PaxaliaLogEvent.objects.filter(severity__in=["ERROR", "CRITICAL"]).order_by("-timestamp")[:8]
    recent_django_actions = [
        {"action": entry, "object_repr": redact_text(str(entry.object_repr or ""))}
        for entry in LogEntry.objects.select_related("content_type", "user").order_by("-action_time")[:10]
    ]
    writable = localized = protected = history_enabled = 0
    for definition in definitions:
        capabilities = definition.capabilities(request)
        writable += int(capabilities.change or capabilities.add or capabilities.delete)
        localized += int(capabilities.localization)
        protected += int(capabilities.protected)
        history_enabled += int(capabilities.history)
    context = _base_context(
        title=_("Paxalia Admin"),
        subtitle=_("Manage Django-registered models without leaving the Paxalia Dashboard"),
    )
    context.update({
        "app_cards": app_cards,
        "definitions": definitions,
        "application_count": len(app_cards),
        "model_count": len(definitions),
        "writable_count": writable,
        "localized_count": localized,
        "protected_count": protected,
        "history_enabled_count": history_enabled,
        "recent_changes": recent_changes,
        "recent_logins": recent_logins,
        "recent_errors": recent_errors,
        "recent_django_actions": recent_django_actions,
        "configuration_issues": registry.validate_configuration(),
    })
    return render(request, "paxalia/admin/home.html", context)


@admin_security_required
@staff_member_required

def admin_audit(request):
    require_staff(request)
    _require_enabled()
    queryset = SecurityAuditLog.objects.select_related("user").filter(action__startswith="admin.").order_by("-created_at")
    search = (request.GET.get("q") or "").strip()
    action = (request.GET.get("action") or "").strip()
    user_id = (request.GET.get("user") or "").strip()
    model_label = (request.GET.get("model") or "").strip()
    if search:
        from django.db.models import Q
        queryset = queryset.filter(Q(action__icontains=search) | Q(detail__icontains=search))
    if action:
        queryset = queryset.filter(action=action)
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if model_label:
        queryset = queryset.filter(detail__icontains=f"model={model_label}")
    page_size = max(1, min(_safe_int(get_config().get("ADMIN_LIST_PER_PAGE", 50), 50), 200))
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(_safe_int(request.GET.get("page", 1)))
    actions = list(queryset.order_by().values_list("action", flat=True).distinct()[:100])
    context = _base_context(
        title=_("Admin Audit"),
        subtitle=_("Review traceable Paxalia administrative operations without exposing protected values"),
        active_page="admin_audit",
    )
    context.update({
        "page_obj": page_obj,
        "audit_entries": page_obj.object_list,
        "actions": actions,
        "search": search,
        "selected_action": action,
        "selected_user": user_id,
        "selected_model": model_label,
        "paginator": paginator,
        "django_fallback_url": registry.django_admin_url(),
    })
    return render(request, "paxalia/admin/audit.html", context)


@admin_security_required
@staff_member_required

def admin_models(request):
    require_staff(request)
    _require_enabled()
    app_cards = registry.app_group_cards(request)
    context = _base_context(
        title=_("Models"),
        subtitle=_("Registered Django models and their available administrative capabilities"),
        active_page="admin_models",
    )
    context["app_cards"] = app_cards
    context["model_count"] = sum(len(card["definitions"]) for card in app_cards)
    context["configuration_issues"] = registry.validate_configuration()
    return render(request, "paxalia/admin/models.html", context)


@admin_security_required
@staff_member_required

def model_overview(request, app_label, model_name):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    stats = object_statistics(definition, request)
    capabilities = definition.capabilities(request)
    recent_changes = [
        {"action": entry, "object_repr": redact_text(str(entry.object_repr or ""))}
        for entry in LogEntry.objects.select_related("user").filter(
            content_type__app_label=definition.app_label,
            content_type__model=definition.model_name,
        ).order_by("-action_time", "-pk")[:10]
    ]
    context = _base_context(
        definition,
        active_page="admin_model",
        title=definition.verbose_name_plural,
        subtitle=_("Model overview and administrative capabilities"),
    )
    context.update({
        "stats": stats,
        "capabilities": capabilities.as_dict(),
        "url_list": definition.url("admin_model_list"),
        "url_add": definition.url("admin_model_add") if capabilities.add else None,
        "url_stats": definition.url("admin_model_stats"),
        "recent_changes": recent_changes,
        "configuration": definition.options,
        "identity_fields": definition.identity_fields,
        "sensitive_fields": sorted(definition.sensitive_fields),
        "hidden_fields": sorted(definition.hidden_fields),
        "display_fields": sorted(definition.display_fields) if definition.display_fields else None,
        "django_fallback_url": registry.django_admin_url(),
    })
    return _protected_response(render(request, "paxalia/admin/model_overview.html", context), definition)


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_changelist(request, app_label, model_name):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    change_list = build_changelist(definition, request)
    list_editable_enabled = bool(change_list.list_editable) and bool(can_change(definition, request)) and bool(get_config().get("ADMIN_LIST_EDITABLE_ENABLED", True))
    editable_formset = None
    edit_error = None

    if request.method == "POST" and request.POST.get("_save") and list_editable_enabled:
        try:
            editable_formset, _formset_metadata = build_list_editable_formset(definition, request, change_list, save=True)
            changed_count, _save_metadata = save_list_editable(definition, request, editable_formset)
            if editable_formset.is_valid():
                messages.success(request, _("Saved %(count)s row(s).") % {"count": changed_count})
                return redirect(request.get_full_path())
            edit_error = _("Review the inline changes below and correct the highlighted fields.")
        except PermissionDenied:
            raise
        except ValidationError as exc:
            edit_error = str(exc)
            messages.error(request, edit_error)
        except Exception:
            logger.exception("Paxalia Admin list-editable save failed for %s", definition.label)
            edit_error = _("The inline changes could not be saved. The failure has been recorded.")
            messages.error(request, edit_error)
    elif list_editable_enabled:
        try:
            editable_formset, _formset_metadata = build_list_editable_formset(definition, request, change_list, save=False)
        except Exception:
            logger.exception("Paxalia Admin list-editable rendering failed for %s", definition.label)
            editable_formset = None

    columns = column_headers(change_list)
    rows = []
    list_display_links = set(change_list.list_display_links or ())
    can_add_model = bool(definition.model_admin.has_add_permission(request))
    can_change_model = bool(definition.model_admin.has_change_permission(request))
    can_delete_model = bool(definition.model_admin.has_delete_permission(request))
    has_registered_actions = bool(definition.model_admin.get_actions(request) or {})
    editable_by_pk = {}
    if editable_formset is not None:
        editable_by_pk = {str(form.instance.pk): form for form in editable_formset.forms if form.instance.pk is not None}

    list_editable_names = set(change_list.list_editable or ())
    for obj in change_list.result_list:
        can_view_obj = bool(definition.model_admin.has_view_permission(request, obj))
        can_change_obj = bool(definition.model_admin.has_change_permission(request, obj))
        can_delete_obj = bool(definition.model_admin.has_delete_permission(request, obj))
        edit_form = editable_by_pk.get(str(obj.pk))
        cells = []
        for index, name in enumerate(change_list.list_display):
            if edit_form is not None and name in list_editable_names and name in edit_form.fields:
                cell = {"editable": True, "form_field": edit_form[name], "href": None, "value": ""}
            else:
                value = render_column_value(obj, name, definition.model_admin, request=request)
                href = definition.url("admin_object_detail", object_id=str(obj.pk)) if (
                    name in list_display_links or (not list_display_links and index == 0)
                ) and can_view_obj else None
                cell = {"editable": False, "value": value, "href": href}
            cells.append(cell)
        rows.append({
            "object": obj,
            "can_view": can_view_obj,
            "cells": cells if can_view_obj else [],
            "object_id": str(obj.pk),
            "editable_hidden_fields": list(edit_form.hidden_fields()) if edit_form is not None else [],
            "change_url": definition.url("admin_object_change", object_id=str(obj.pk)) if can_change_obj else None,
            "delete_url": definition.url("admin_object_delete", object_id=str(obj.pk)) if can_delete_obj else None,
            "selectable": can_delete_obj or can_change_obj or (has_registered_actions and can_view_obj),
        })

    pagination = {
        "page": getattr(change_list, "page_num", 1),
        "num_pages": change_list.paginator.num_pages,
        "count": change_list.result_count,
        "full_count": getattr(change_list, "full_result_count", change_list.result_count),
        "has_previous": change_list.page_num > 1,
        "has_next": change_list.page_num < change_list.paginator.num_pages,
        "previous": change_list.page_num - 1,
        "next": change_list.page_num + 1,
        "page_range": change_list.paginator.get_elided_page_range(change_list.page_num, on_each_side=2, on_ends=1),
    }
    filters = filter_specs(change_list)
    actions = []
    for name, info in (definition.model_admin.get_actions(request) or {}).items():
        if name == "delete_selected":
            continue
        actions.append({"name": name, "label": info[2]})
    query_without_page = request.GET.copy()
    query_without_page.pop("p", None)
    query_without_page.pop("page", None)
    date_nav = date_hierarchy_data(change_list, request)
    context = _base_context(
        definition,
        active_page="admin_model",
        title=definition.verbose_name_plural,
        subtitle=_("Search, filter, inspect, and manage records"),
    )
    context.update({
        "rows": rows,
        "columns": columns,
        "filters": filters,
        "actions": actions,
        "pagination": pagination,
        "query_without_page": query_without_page.urlencode(),
        "search_query": request.GET.get("q", ""),
        "result_count": change_list.result_count,
        "can_add": can_add_model,
        "can_change": can_change_model,
        "can_delete": can_delete_model,
        "model_overview_url": definition.url("admin_model_overview"),
        "add_url": definition.url("admin_model_add"),
        "stats_url": definition.url("admin_model_stats"),
        "django_fallback_url": registry.django_admin_url(),
        "date_hierarchy": date_nav,
        "list_editable_fields": tuple(change_list.list_editable or ()),
        "list_editable_enabled": list_editable_enabled and editable_formset is not None,
        "list_editable_formset": editable_formset,
        "list_editable_error": edit_error,
        "action_url": definition.url("admin_model_action"),
    })
    return render(request, "paxalia/admin/model_list.html", context)


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_action(request, app_label, model_name):
    require_staff(request)
    _require_enabled()
    if request.method != "POST":
        raise Http404
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    action_name = (request.POST.get("action") or "").strip()
    selected = _selected_ids(request)
    if len(selected) > _max_bulk():
        messages.error(
            request,
            _("Select no more than %(max)s objects at a time.") % {"max": _max_bulk()},
        )
        return redirect(definition.url("admin_model_list"))
    if action_name == "delete_selected":
        require_delete(definition, request)
        if not selected:
            messages.warning(request, _("Select at least one object."))
            return redirect(definition.url("admin_model_list"))
        # Validate the selection now, before opening the destructive flow.
        try:
            qs = definition.model_admin.get_queryset(request).filter(pk__in=selected)
            objects = list(qs)
            if {str(obj.pk) for obj in objects} != {str(pk) for pk in selected}:
                raise PermissionDenied
            denied = [obj for obj in objects if not can_delete(definition, request, obj)]
            if denied:
                raise PermissionDenied
        except PermissionDenied:
            messages.error(request, _("One or more selected objects cannot be deleted with the current permissions."))
            return redirect(definition.url("admin_model_list"))
        request.session["paxalia_admin_delete_ids"] = selected
        request.session["paxalia_admin_delete_model"] = definition.label
        request.session.modified = True
        audit(request, "bulk_delete_started", definition, detail=f"count={len(selected)}")
        return redirect(definition.url("admin_bulk_delete"))
    try:
        response = execute_action(definition, request, action_name, selected)
        if isinstance(response, HttpResponse):
            return response
        messages.success(request, _("Action completed successfully."))
    except PermissionDenied:
        raise
    except (ValidationError, ValueError) as exc:
        messages.warning(request, str(exc))
    except Exception:
        logger.exception("Paxalia Admin action failed: %s / %s", definition.label, action_name)
        messages.error(request, _("The action could not be completed. The failure has been recorded."))
    return redirect(definition.url("admin_model_list"))


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_add(request, app_label, model_name):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    require_add(definition, request)
    form_class = safe_form_class(definition, request, None)
    form = form_class(request.POST or None, request.FILES or None)
    formsets = _inline_instances(definition, request, None)
    if request.method == "POST" and form.is_valid() and all(item["formset"].is_valid() for item in formsets):
        try:
            with transaction.atomic():
                obj = definition.model_admin.save_form(request, form, change=False)
                definition.model_admin.save_model(request, obj, form, change=False)
                inline_formsets = [item["formset"] for item in formsets]
                definition.model_admin.save_related(request, form, inline_formsets, change=False)
                try:
                    message = definition.model_admin.construct_change_message(
                        request, form, inline_formsets, add=True
                    )
                except Exception:
                    message = ""
                django_admin_model_log(request, definition, obj, ADDITION, message=message)
                audit(request, "created", definition, obj=obj)
            messages.success(request, _("%s was created successfully.") % definition.verbose_name)
            if "_addanother" in request.POST:
                return redirect(definition.url("admin_model_add"))
            if "_continue" in request.POST:
                return redirect(definition.url("admin_object_change", object_id=str(obj.pk)))
            return redirect(definition.url("admin_object_detail", object_id=str(obj.pk)))
        except Exception:
            logger.exception("Paxalia Admin add failed for %s", definition.label)
            messages.error(request, _("The object could not be saved. Review the form and try again."))
    context = _base_context(
        definition,
        active_page="admin_model",
        title=_("Add %(model)s") % {"model": definition.verbose_name},
        subtitle=_("Create a new record using Django's model validation"),
    )
    context.update({
        "form": form,
        "formsets": formsets,
        "cancel_url": definition.url("admin_model_list"),
        "submit_label": _("Create"),
        **_form_context(definition, request, form),
    })
    return _protected_response(render(request, "paxalia/admin/object_form.html", context), definition)


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_change(request, app_label, model_name, object_id):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    base_qs = definition.model_admin.get_queryset(request)
    obj = get_object_or_404(base_qs, pk=object_id)
    require_change(definition, request, obj)
    form_class = safe_form_class(definition, request, obj)
    form = form_class(request.POST or None, request.FILES or None, instance=obj)
    formsets = _inline_instances(definition, request, obj)
    if request.method == "POST" and form.is_valid() and all(item["formset"].is_valid() for item in formsets):
        try:
            with transaction.atomic():
                before = {
                    field.name: field.value_from_object(obj)
                    for field in definition.model._meta.fields
                    if field.name in form.fields
                }
                obj_to_save = definition.model_admin.save_form(request, form, change=True)
                definition.model_admin.save_model(request, obj_to_save, form, change=True)
                inline_formsets = [item["formset"] for item in formsets]
                definition.model_admin.save_related(request, form, inline_formsets, change=True)
                changed_fields = [
                    name
                    for name in form.changed_data
                    if name in before and name not in definition.sensitive_fields
                ]
                message = ""
                try:
                    message = definition.model_admin.construct_change_message(
                        request,
                        form,
                        inline_formsets,
                    )
                except Exception:
                    message = ", ".join(changed_fields)
                django_admin_model_log(request, definition, obj_to_save, CHANGE, message=message)
                audit(request, "changed", definition, obj=obj_to_save, detail=f"fields={','.join(changed_fields)[:800]}")
            messages.success(request, _("%s was saved successfully.") % definition.verbose_name)
            if "_continue" in request.POST:
                return redirect(definition.url("admin_object_change", object_id=str(obj_to_save.pk)))
            return redirect(definition.url("admin_object_detail", object_id=str(obj_to_save.pk)))
        except Exception:
            logger.exception("Paxalia Admin change failed for %s", definition.label)
            messages.error(request, _("The object could not be saved. Review the form and try again."))
    context = _base_context(
        definition,
        active_page="admin_model",
        title=_("Edit %(model)s") % {"model": definition.verbose_name},
        subtitle=_("Update the record using Django's model validation and ModelAdmin hooks"),
    )
    context.update({
        "form": form,
        "formsets": formsets,
        "cancel_url": definition.url("admin_object_detail", object_id=str(obj.pk)),
        "submit_label": _("Save changes"),
        "object": obj,
        **_form_context(definition, request, form, obj=obj),
    })
    return _protected_response(render(request, "paxalia/admin/object_form.html", context), definition)


@admin_security_required
@staff_member_required

def model_detail(request, app_label, model_name, object_id):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    obj = get_object_or_404(definition.model_admin.get_queryset(request), pk=object_id)
    require_view(definition, request, obj)
    related = object_sections(definition, request, obj)
    capabilities = definition.capabilities(request)
    if capabilities.protected:
        audit(request, "protected_viewed", definition, obj=obj)
    history_url = definition.url("admin_object_history", object_id=str(obj.pk))
    context = _base_context(
        definition,
        active_page="admin_model",
        title=redact_text(safe_object_repr(obj, 180)),
        subtitle=definition.verbose_name,
    )
    context.update({
        "object": obj,
        "fields": [row for row in related if row["kind"] == "field"],
        "relations": [row for row in related if row["kind"] != "field"],
        "readonly_rows": [],
        "can_change": can_change(definition, request, obj),
        "can_delete": can_delete(definition, request, obj),
        "list_url": definition.url("admin_model_list"),
        "change_url": definition.url("admin_object_change", object_id=str(obj.pk)),
        "delete_url": definition.url("admin_object_delete", object_id=str(obj.pk)),
        "history_url": history_url,
        "statistics": object_statistics(definition, request),
        "capabilities": capabilities.as_dict(),
        "identity_values": [
            {
                "field": field_name,
                "value": "••••••••" if field_name in definition.sensitive_fields else redact_text(str(getattr(obj, field_name, "—"))),
            }
            for field_name in definition.identity_fields
        ],
    })
    return _protected_response(render(request, "paxalia/admin/object_detail.html", context), definition)


@admin_security_required
@staff_member_required

def model_history(request, app_label, model_name, object_id):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    obj = get_object_or_404(definition.model_admin.get_queryset(request), pk=object_id)
    require_view(definition, request, obj)
    audit(request, "history_viewed", definition, obj=obj)
    queryset = history_queryset(definition, obj)
    page_size = max(1, min(_safe_int(get_config().get("ADMIN_OBJECT_HISTORY_PER_PAGE", 30), 30), 200))
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(_safe_int(request.GET.get("page", 1)))
    context = _base_context(
        definition,
        active_page="admin_model",
        title=_("History · %(object)s") % {"object": safe_object_repr(obj, 150)},
        subtitle=_("Django Admin change history for this object"),
    )
    context.update({
        "object": obj,
        "page_obj": page_obj,
        "entries": page_obj.object_list,
        "back_url": definition.url("admin_object_detail", object_id=str(obj.pk)),
        "list_url": definition.url("admin_model_list"),
        "change_url": definition.url("admin_object_change", object_id=str(obj.pk)) if can_change(definition, request, obj) else None,
    })
    return _protected_response(render(request, "paxalia/admin/history.html", context), definition)


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_delete(request, app_label, model_name, object_id):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    obj = get_object_or_404(definition.model_admin.get_queryset(request), pk=object_id)
    require_delete(definition, request, obj)
    limit = _safe_int(get_config().get("ADMIN_MAX_DELETE_PREVIEW", 100), 100)
    impact = deletion_preview(definition, request, [obj], max_preview=limit)
    if request.method == "POST":
        # Re-check the object and the deletion plan immediately before mutation.
        obj = get_object_or_404(definition.model_admin.get_queryset(request), pk=object_id)
        require_delete(definition, request, obj)
        impact = deletion_preview(definition, request, [obj], max_preview=limit)
        if impact.get("blocked"):
            reason = "; ".join(impact.get("protected") or impact.get("perms_needed") or [impact.get("error") or _("The deletion is blocked.")])
            messages.error(request, _("Django blocked this deletion: %(reason)s") % {"reason": reason})
        else:
            try:
                perform_delete(definition, request, obj)
                messages.success(request, _("The object was deleted successfully."))
                return redirect(definition.url("admin_model_list"))
            except Exception:
                logger.exception("Paxalia Admin delete failed for %s", definition.label)
                messages.error(request, _("The object could not be deleted."))
    context = _base_context(
        definition,
        active_page="admin_model",
        title=_("Delete %(model)s") % {"model": definition.verbose_name},
        subtitle=_("Review the cascade impact before confirming this destructive operation"),
    )
    context.update({
        "object": obj,
        "object_display": redact_text(safe_object_repr(obj, 500)),
        "impact": impact,
        "cancel_url": definition.url("admin_model_list"),
        "django_fallback_url": registry.django_admin_url(),
    })
    return _protected_response(render(request, "paxalia/admin/delete_confirmation.html", context), definition)


@admin_security_required
@staff_member_required
@honeypot_exempt

def model_bulk_delete(request, app_label, model_name):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    require_delete(definition, request)
    if request.session.get("paxalia_admin_delete_model") != definition.label:
        return redirect(definition.url("admin_model_list"))
    selected = list(dict.fromkeys(str(value) for value in (request.session.get("paxalia_admin_delete_ids") or [])))
    if len(selected) > _max_bulk():
        messages.error(
            request,
            _("The stored selection exceeds the maximum of %(max)s objects.") % {"max": _max_bulk()},
        )
        request.session.pop("paxalia_admin_delete_ids", None)
        request.session.pop("paxalia_admin_delete_model", None)
        request.session.modified = True
        return redirect(definition.url("admin_model_list"))
    if not selected:
        return redirect(definition.url("admin_model_list"))
    qs = definition.model_admin.get_queryset(request).filter(pk__in=selected)
    objects = list(qs)
    if {str(obj.pk) for obj in objects} != set(selected):
        messages.error(request, _("One or more selected objects are no longer available."))
        request.session.pop("paxalia_admin_delete_ids", None)
        request.session.pop("paxalia_admin_delete_model", None)
        request.session.modified = True
        return redirect(definition.url("admin_model_list"))
    if any(not can_delete(definition, request, obj) for obj in objects):
        messages.error(request, _("One or more selected objects cannot be deleted with the current permissions."))
        request.session.pop("paxalia_admin_delete_ids", None)
        request.session.pop("paxalia_admin_delete_model", None)
        request.session.modified = True
        return redirect(definition.url("admin_model_list"))

    impact = deletion_preview(
        definition,
        request,
        objects,
        max_preview=_safe_int(get_config().get("ADMIN_MAX_DELETE_PREVIEW", 100), 100),
    )
    if request.method == "POST":
        if impact.get("blocked"):
            reason = "; ".join(impact.get("protected") or impact.get("perms_needed") or [impact.get("error") or _("The deletion is blocked.")])
            messages.error(request, _("Django blocked this deletion: %(reason)s") % {"reason": reason})
        else:
            try:
                count = perform_delete_queryset(definition, request, qs)
                messages.success(
                    request,
                    _("Deleted %(count)s %(model)s.") % {
                        "count": count,
                        "model": definition.verbose_name_plural.lower(),
                    },
                )
                request.session.pop("paxalia_admin_delete_ids", None)
                request.session.pop("paxalia_admin_delete_model", None)
                request.session.modified = True
                return redirect(definition.url("admin_model_list"))
            except Exception:
                logger.exception("Paxalia Admin bulk delete failed for %s", definition.label)
                messages.error(request, _("The selected objects could not be deleted."))
    objects_preview = [
        {"display": redact_text(safe_object_repr(obj, 240)), "pk": str(obj.pk)}
        for obj in objects[:50]
    ]
    remaining_count = max(0, len(objects) - len(objects_preview))
    return _protected_response(
        render(
            request,
            "paxalia/admin/bulk_delete.html",
            _base_context(
                definition,
                active_page="admin_model",
                title=_("Delete selected %(model)s") % {"model": definition.verbose_name_plural},
                subtitle=_("Confirm this bulk destructive action"),
            )
            | {
                "objects": objects_preview,
                "selected_count": len(objects),
                "remaining_count": remaining_count,
                "impact": impact,
                "cancel_url": definition.url("admin_model_list"),
            },
        ),
        definition,
    )


@admin_security_required
@staff_member_required

def model_stats(request, app_label, model_name):
    require_staff(request)
    _require_enabled()
    definition = registry.get(app_label, model_name, request=request)
    require_view(definition, request)
    stats = object_statistics(definition, request)
    if request.GET.get("format") == "json":
        return _protected_response(JsonResponse(stats), definition)
    context = _base_context(
        definition,
        active_page="admin_model",
        title=_("%(model)s statistics") % {"model": definition.verbose_name},
        subtitle=_("Bounded model-level aggregates based on the registered Django queryset"),
    )
    context.update({
        "stats": stats,
        "list_url": definition.url("admin_model_list"),
        "overview_url": definition.url("admin_model_overview"),
    })
    return _protected_response(render(request, "paxalia/admin/model_stats.html", context), definition)
