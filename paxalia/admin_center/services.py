import logging
import re
from dataclasses import dataclass

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import router, transaction
from django.db.models import Count
from django.db.models.deletion import Collector
from django.utils import timezone

from ..logging.redaction import redact_text
from ..security_audit import log_action
from ..settings import get_config
from .permissions import can_change, can_delete, can_view
from .registry import is_sensitive_field
from .utils import json_preview, readonly_rows, safe_object_repr

logger = logging.getLogger("paxalia.admin")


@dataclass
class RelatedItem:
    label: str
    value: object
    url: str | None = None


def safe_display_repr(obj, limit=240):
    """Render an object representation with the central Paxalia redaction policy."""
    return redact_text(safe_object_repr(obj, limit))


def audit(request, action, definition, obj=None, detail=""):
    object_identity = ""
    if obj is not None:
        try:
            object_identity = f"pk={redact_text(str(obj.pk))};repr={redact_text(safe_object_repr(obj, 180))}"
        except Exception:
            object_identity = "pk=unavailable"
    payload = "; ".join(
        part for part in [f"model={definition.label}", object_identity, str(detail)[:1200]] if part
    )
    try:
        log_action(request, f"admin.{action}", payload)
    except Exception:
        # Administrative auditing is best-effort and must never break the
        # underlying management operation.
        logger.exception("Failed to record Paxalia Admin audit action %s", action)


def django_admin_audit(request, action_flag, obj, message="", object_id=None, object_repr=None):
    try:
        object_id = str(obj.pk if object_id is None else object_id)
        object_repr = safe_object_repr(obj, 200) if object_repr is None else str(object_repr)
        object_repr = redact_text(object_repr)
        ct = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        manager = LogEntry.objects
        if hasattr(manager, "log_actions"):
            manager.log_actions(
                user_id=request.user.pk,
                queryset=[obj],
                action_flag=action_flag,
                change_message=message,
            )
        else:
            manager.log_action(
                user_id=request.user.pk,
                content_type_id=ct.pk,
                object_id=object_id,
                object_repr=object_repr,
                action_flag=action_flag,
                change_message=message,
            )
    except Exception:
        logger.exception("Failed to write Django admin LogEntry")


def django_admin_model_log(request, definition, obj, action_flag, message="", object_repr=None):
    """Prefer ModelAdmin's own hooks, with a safe fallback."""
    try:
        representation = safe_object_repr(obj, 200) if object_repr is None else object_repr
        representation = redact_text(str(representation))
        if action_flag == ADDITION and hasattr(definition.model_admin, "log_addition"):
            definition.model_admin.log_addition(request, obj, message)
        elif action_flag == CHANGE and hasattr(definition.model_admin, "log_change"):
            definition.model_admin.log_change(request, obj, message)
        elif action_flag == DELETION and hasattr(definition.model_admin, "log_deletion"):
            definition.model_admin.log_deletion(request, obj, representation)
        else:
            django_admin_audit(request, action_flag, obj, message=message, object_repr=representation)
    except Exception:
        django_admin_audit(request, action_flag, obj, message=message, object_repr=object_repr)


def safe_form_class(definition, request, obj=None):
    return definition.model_admin.get_form(request, obj=obj, change=obj is not None)


def build_form_sections(definition, request, form, obj=None, exclude_names=()):
    fieldsets = list(definition.model_admin.get_fieldsets(request, obj) or ())
    sections = []
    used = set()
    hidden = set(definition.hidden_fields) | {str(name) for name in (exclude_names or ())}
    for title, options in fieldsets:
        names = []
        for name in (options or {}).get("fields", ()):
            if isinstance(name, (list, tuple)):
                names.extend(name)
            else:
                names.append(name)
        bound_fields = []
        for name in names:
            if name in form.fields and name not in hidden:
                bound_fields.append(form[name])
                used.add(name)
        if bound_fields:
            sections.append({"title": title or "General", "fields": bound_fields})
    remaining = [form[name] for name in form.fields if name not in used and name not in hidden]
    if remaining:
        sections.append({"title": "General", "fields": remaining})
    return sections


def configured_readonly_fields(definition, request, obj=None):
    configured = tuple(definition.options.get("readonly_fields") or ())
    try:
        registered = tuple(definition.model_admin.get_readonly_fields(request, obj) or ())
    except Exception:
        registered = ()
    return tuple(dict.fromkeys((*registered, *configured)))


def protect_configured_readonly_fields(definition, form):
    for name in definition.options.get("readonly_fields") or ():
        if name in form.fields:
            form.fields[name].disabled = True


def protect_sensitive_form_fields(definition, form, obj=None):
    """Keep configured read-only/secret fields safe in Paxalia forms."""
    protect_configured_readonly_fields(definition, form)
    for name, field in form.fields.items():
        if name in definition.hidden_fields and getattr(form, "instance", None) is not None and getattr(form.instance, "pk", None):
            # A configured hidden field is immutable on an existing object. On
            # creation it is kept as a normal hidden form control so projects
            # can still supply a safe initial value/default.
            field.disabled = True
        elif name in definition.hidden_fields:
            from django.forms.widgets import HiddenInput
            field.widget = HiddenInput()
        try:
            model_field = definition.model._meta.get_field(name)
        except Exception:
            continue
        if not is_sensitive_field(model_field, definition.model):
            continue
        from django.forms.widgets import PasswordInput
        field.widget = PasswordInput(render_value=False, attrs={"autocomplete": "new-password"})
        # Creation forms must still accept a secret value. Existing objects
        # never echo or replace a stored secret through the generic editor.
        field.disabled = bool(getattr(form, "instance", None) is not None and getattr(form.instance, "pk", None))


def _model_label(model):
    return model._meta.label


def _collector_fallback(objects, using):
    collector = Collector(using=using)
    collector.collect(objects)
    counts = {model._meta.label: len(items) for model, items in collector.data.items()}
    return {
        "blocked": False,
        "error": "",
        "counts": counts,
        "protected": [],
        "perms_needed": [],
        "deleted_objects": [],
    }


def _flatten_delete_preview(values, limit):
    flattened = []

    def visit(value):
        if len(flattened) >= limit:
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
                if len(flattened) >= limit:
                    return
        else:
            flattened.append(redact_text(str(value)))

    visit(values)
    return flattened


def deletion_preview(definition, request, objects, max_preview=None):
    """Return a bounded, Django-compatible deletion impact report."""
    objects = [obj for obj in objects if obj is not None]
    configured_limit = max_preview or 100
    try:
        configured_limit = max(1, min(int(configured_limit), 500))
    except (TypeError, ValueError):
        configured_limit = 100
    if not objects:
        return {
            "blocked": False,
            "error": "",
            "counts": {},
            "protected": [],
            "perms_needed": [],
            "deleted_objects": [],
        }

    get_deleted_objects = getattr(definition.model_admin, "get_deleted_objects", None)
    if get_deleted_objects is None:
        try:
            return _collector_fallback(objects, objects[0]._state.db or router.db_for_write(definition.model, instance=objects[0]) or "default")
        except Exception as exc:
            return {
                "blocked": True,
                "error": redact_text(str(exc))[:300],
                "counts": {},
                "protected": [],
                "perms_needed": [],
                "deleted_objects": [],
            }

    try:
        deleted_objects, model_count, perms_needed, protected = get_deleted_objects(objects, request)
        counts = {}
        for model, count in (model_count or {}).items():
            label = getattr(getattr(model, "_meta", None), "label", str(model))
            counts[label] = int(count)
        # Django can expose human-facing verbose model names (for example
        # ``Sites``) here. Paxalia also publishes the concrete model label as
        # a stable machine-readable key for APIs, tests, and audit consumers.
        root_label = definition.model._meta.label
        counts.setdefault(root_label, len(objects))
        return {
            "blocked": bool(perms_needed or protected),
            "error": "",
            "counts": counts,
            "protected": _flatten_delete_preview(protected or [], configured_limit),
            "perms_needed": _flatten_delete_preview(perms_needed or [], configured_limit),
            "deleted_objects": _flatten_delete_preview(deleted_objects or [], configured_limit),
        }
    except Exception as exc:
        return {
            "blocked": True,
            "error": redact_text(str(exc))[:300],
            "counts": {},
            "protected": [],
            "perms_needed": [],
            "deleted_objects": [],
        }


def destructive_impact(definition, request, obj):
    return deletion_preview(definition, request, [obj])


def object_statistics(definition, request):
    qs = definition.model_admin.get_queryset(request)
    model = definition.model
    stats = {
        "total": 0,
        "created_today": None,
        "updated_today": None,
        "timestamp_field": None,
        "updated_field": None,
        "choice_breakdowns": [],
        "related_fields": 0,
    }
    try:
        stats["total"] = qs.count()
    except Exception:
        stats["total"] = 0

    fields = list(model._meta.fields)
    created_candidates = ("created_at", "created", "date_created", "timestamp", "joined_at")
    updated_candidates = ("updated_at", "updated", "modified_at", "modified")
    for field in fields:
        if stats["timestamp_field"] is None and field.name in created_candidates:
            stats["timestamp_field"] = field.name
        if stats["updated_field"] is None and field.name in updated_candidates:
            stats["updated_field"] = field.name
    today = timezone.localdate()
    if stats["timestamp_field"]:
        try:
            stats["created_today"] = qs.filter(**{f"{stats['timestamp_field']}__date": today}).count()
        except Exception:
            stats["created_today"] = None
    if stats["updated_field"]:
        try:
            stats["updated_today"] = qs.filter(**{f"{stats['updated_field']}__date": today}).count()
        except Exception:
            stats["updated_today"] = None

    for field in fields:
        if is_sensitive_field(field, model) or not getattr(field, "choices", None):
            continue
        try:
            rows = qs.values(field.name).annotate(count=Count("pk")).order_by("-count")[:6]
            stats["choice_breakdowns"].append({
                "field": field.name,
                "label": str(field.verbose_name),
                "rows": [{"value": row.get(field.name), "count": row["count"]} for row in rows],
            })
        except Exception:
            continue
        if len(stats["choice_breakdowns"]) >= 3:
            break

    stats["related_fields"] = sum(
        1 for field in model._meta.get_fields() if getattr(field, "is_relation", False)
    )
    return stats


def _related_url(request, related_obj):
    from .registry import registry
    try:
        definition = registry.get(
            related_obj._meta.app_label,
            related_obj._meta.model_name,
            request=request,
        )
        if can_view(definition, request, related_obj):
            return definition.url("admin_object_detail", object_id=str(related_obj.pk))
    except Exception:
        return None
    return None


def object_sections(definition, request, obj):
    """Return safe, template-friendly object data without bypassing ModelAdmin."""
    rows = []
    model = definition.model
    max_items = definition.max_relation_items
    display_fields = definition.display_fields

    for field in model._meta.get_fields():
        if (getattr(field, "one_to_many", False) or getattr(field, "one_to_one", False)) and getattr(field, "auto_created", False):
            accessor = field.get_accessor_name()
            if not accessor:
                continue
            try:
                related = getattr(obj, accessor)
                if hasattr(related, "all"):
                    # Never use the unrestricted manager count as the visible
                    # relationship count: that would disclose the existence
                    # of objects hidden by object-level ModelAdmin policy.
                    candidates = list(related.all()[: max_items + 1])
                else:
                    candidates = [related] if related is not None else []

                related_definition = None
                try:
                    from .registry import registry
                    related_model = getattr(field, "related_model", None)
                    if related_model is not None:
                        related_definition = registry.get(
                            related_model._meta.app_label,
                            related_model._meta.model_name,
                            request=request,
                        )
                except Exception:
                    related_definition = None

                visible = []
                hidden_seen = False
                for item in candidates:
                    if related_definition is None or not can_view(related_definition, request, item):
                        hidden_seen = True
                        continue
                    visible.append(item)
                    if len(visible) >= max_items:
                        break

                # `more` is deliberately an existence indicator rather than
                # the raw hidden-object count. This prevents relationship
                # cardinality from becoming a side-channel.
                more = 1 if hidden_seen or len(candidates) > len(visible) else 0
                rows.append({
                    "name": accessor,
                    "label": str(getattr(field, "verbose_name", accessor)),
                    "kind": "reverse_relation",
                    "items": [
                        {"value": safe_display_repr(item, 160), "url": _related_url(request, item)}
                        for item in visible
                    ],
                    "more": more,
                    "count": len(visible),
                    "has_restricted": hidden_seen,
                })
            except ObjectDoesNotExist:
                rows.append({
                    "name": accessor,
                    "label": str(getattr(field, "verbose_name", accessor)),
                    "kind": "reverse_relation",
                    "items": [],
                    "more": 0,
                    "count": 0,
                    "has_restricted": False,
                })
            except Exception:
                rows.append({
                    "name": accessor,
                    "label": accessor,
                    "kind": "reverse_relation",
                    "items": [],
                    "more": 0,
                    "count": 0,
                    "has_restricted": False,
                    "error": True,
                })
            continue

        if getattr(field, "many_to_many", False):
            if field.name in definition.hidden_fields:
                continue
            if display_fields is not None and field.name not in display_fields:
                continue
            try:
                manager = getattr(obj, field.name)
                count = manager.count()
                values = list(manager.all()[:max_items])
                rows.append({
                    "name": field.name,
                    "label": str(field.verbose_name),
                    "kind": "many_to_many",
                    "items": [
                        {"value": safe_display_repr(item, 160), "url": _related_url(request, item)}
                        for item in values
                    ],
                    "more": max(0, count - len(values)),
                    "count": count,
                })
            except Exception:
                rows.append({
                    "name": field.name,
                    "label": field.name,
                    "kind": "many_to_many",
                    "items": [],
                    "more": 0,
                    "count": 0,
                    "error": True,
                })
            continue

        if getattr(field, "auto_created", False) and not getattr(field, "concrete", False):
            continue
        if field.name in definition.hidden_fields:
            continue
        if display_fields is not None and field.name not in display_fields:
            continue

        try:
            value = field.value_from_object(obj)
        except Exception:
            try:
                value = getattr(obj, field.name)
            except Exception:
                value = None

        sensitive = is_sensitive_field(field, model)
        if sensitive:
            display = "••••••••"
        elif getattr(field, "choices", None):
            display = dict(field.flatchoices).get(value, value)
        elif getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False):
            try:
                related_obj = getattr(obj, field.name)
                display = safe_display_repr(related_obj, 240) if related_obj is not None else "—"
                if related_obj is not None:
                    display = {"value": display, "url": _related_url(request, related_obj)}
            except Exception:
                display = "—"
        elif field.get_internal_type() == "JSONField":
            display = json_preview(value, extra_keys=definition.sensitive_fields)
        else:
            display = redact_text(safe_object_repr(value, 4000)) if value is not None else "—"

        rows.append({
            "name": field.name,
            "label": str(field.verbose_name),
            "kind": "field",
            "display": display,
            "sensitive": sensitive,
            "type": field.get_internal_type(),
            "help_text": str(getattr(field, "help_text", "") or ""),
        })
    return rows


def _selected_queryset(definition, request, selected_ids, *, require_object_permissions=False):
    if not selected_ids:
        raise ValidationError("Select at least one object.")
    max_items = int(get_config().get("ADMIN_MAX_BULK_OPERATIONS", 500) or 500)
    if len(selected_ids) > max_items:
        raise ValidationError(f"Select no more than {max_items} objects.")
    qs = definition.model_admin.get_queryset(request).filter(pk__in=selected_ids)
    objects = list(qs)
    found_ids = {str(obj.pk) for obj in objects}
    missing = [str(pk) for pk in selected_ids if str(pk) not in found_ids]
    if missing:
        raise PermissionDenied("One or more selected objects are not available to this account.")
    if require_object_permissions:
        denied = [safe_object_repr(obj, 120) for obj in objects if not can_delete(definition, request, obj)]
        if denied:
            raise PermissionDenied("One or more selected objects cannot be deleted with the current permissions.")
    return qs


def _edited_object_pks(formset_class, request, model):
    prefix = formset_class.get_default_prefix()
    pk_name = model._meta.pk.name
    pattern = re.compile(rf"^{re.escape(prefix)}-\d+-{re.escape(pk_name)}$")
    values = []
    seen = set()
    for key, value in request.POST.items():
        if not pattern.match(key):
            continue
        value = str(value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def build_list_editable_formset(definition, request, change_list, *, save=False):
    if not definition.list_editable(request):
        return None, []
    if not can_change(definition, request):
        return None, []
    factory = getattr(definition.model_admin, "get_changelist_formset", None)
    if factory is None:
        return None, []
    FormSet = factory(request)
    denied = []

    if save:
        raw_ids = _edited_object_pks(FormSet, request, definition.model)
        max_items = int(get_config().get("ADMIN_MAX_BULK_OPERATIONS", 500) or 500)
        if len(raw_ids) > max_items:
            raise ValidationError(f"No more than {max_items} rows may be edited at once.")
        native_queryset_builder = getattr(definition.model_admin, "_get_list_editable_queryset", None)
        if callable(native_queryset_builder):
            queryset = native_queryset_builder(request, FormSet.get_default_prefix())
            objects = list(queryset)
            submitted_ids = {str(value) for value in raw_ids}
            found_ids = {str(obj.pk) for obj in objects}
            missing = submitted_ids - found_ids
        else:
            editable_queryset = definition.model_admin.get_queryset(request)
            objects = list(editable_queryset.filter(pk__in=raw_ids))
            missing = {str(value) for value in raw_ids} - {str(obj.pk) for obj in objects}
            queryset = editable_queryset.filter(pk__in=[obj.pk for obj in objects])
        if missing:
            raise PermissionDenied("One or more edited rows are not available to this account.")
        denied = [obj for obj in objects if not can_change(definition, request, obj)]
        if denied:
            raise PermissionDenied("One or more edited rows cannot be changed with the current permissions.")
        formset = FormSet(request.POST, request.FILES, queryset=queryset)
    else:
        # A custom ChangeList may materialize ``result_list`` as a Python
        # list. ModelFormSet requires a QuerySet, so reconstruct the current
        # page from the already-scoped changelist queryset.
        result_page = change_list.result_list
        if hasattr(result_page, "filter") and hasattr(result_page, "model"):
            queryset = result_page
        else:
            page_ids = [obj.pk for obj in result_page]
            queryset = change_list.queryset.filter(pk__in=page_ids) if page_ids else change_list.queryset.none()
        formset = FormSet(queryset=queryset)

    for form in formset.forms:
        protect_sensitive_form_fields(definition, form, obj=form.instance if form.instance.pk else None)
    return formset, denied


def save_list_editable(definition, request, formset):
    changed = 0
    changed_fields = []
    if not formset.is_valid():
        return 0, []
    formsets = []
    with transaction.atomic(using=router.db_for_write(definition.model)):
        for form in formset.forms:
            if not form.has_changed():
                continue
            obj = definition.model_admin.save_form(request, form, change=True)
            definition.model_admin.save_model(request, obj, form, change=True)
            definition.model_admin.save_related(request, form, formsets, change=True)
            message = ""
            try:
                # Match Django's native changelist_view hook signature:
                # construct_change_message(request, form, formsets, add=False).
                message = definition.model_admin.construct_change_message(request, form, formsets)
            except Exception:
                message = ", ".join(
                    name for name in form.changed_data if name not in definition.sensitive_fields
                )
            django_admin_model_log(request, definition, obj, CHANGE, message=message)
            safe_fields = [
                name for name in form.changed_data if name not in definition.sensitive_fields
            ]
            changed_fields.extend(safe_fields)
            audit(
                request,
                "list_changed",
                definition,
                obj=obj,
                detail=f"fields={','.join(safe_fields)[:800]}",
            )
            changed += 1
    return changed, changed_fields


def execute_action(definition, request, action_name, selected_ids):
    actions = definition.model_admin.get_actions(request) or {}
    action_info = actions.get(action_name)
    if not action_info:
        raise PermissionDenied
    func, name, description = action_info
    if not selected_ids:
        raise ValidationError("Select at least one object.")

    allowed_permissions = getattr(func, "allowed_permissions", None)
    if allowed_permissions is None:
        allowed_permissions = ("change",)
    elif isinstance(allowed_permissions, str):
        allowed_permissions = (allowed_permissions,)

    permission_methods = {
        "add": definition.model_admin.has_add_permission,
        "change": definition.model_admin.has_change_permission,
        "delete": definition.model_admin.has_delete_permission,
        "view": definition.model_admin.has_view_permission,
    }
    if not any(
        method(request)
        for permission in allowed_permissions
        if (method := permission_methods.get(permission)) is not None
    ):
        raise PermissionDenied

    qs = _selected_queryset(definition, request, selected_ids)
    objects = list(qs)
    if not all(
        any(
            method(request, obj)
            for permission in allowed_permissions
            if (method := permission_methods.get(permission)) is not None
        )
        for obj in objects
    ):
        raise PermissionDenied
    count = len(objects)
    if getattr(func, "__self__", None) is not None:
        response = func(request, qs)
    else:
        response = func(definition.model_admin, request, qs)
    audit(request, "action", definition, detail=f"action={name};count={count}")
    return response


def perform_delete(definition, request, obj):
    with transaction.atomic(using=router.db_for_write(definition.model, instance=obj)):
        representation = safe_object_repr(obj, 180)
        django_admin_model_log(request, definition, obj, DELETION, object_repr=representation)
        definition.model_admin.delete_model(request, obj)
        audit(request, "deleted", definition, detail=f"object={representation};pk={obj.pk}")


def perform_delete_queryset(definition, request, qs):
    objects = list(qs)
    if not objects:
        return 0
    with transaction.atomic(using=router.db_for_write(definition.model)):
        definition.model_admin.delete_queryset(request, qs)
        audit(request, "bulk_deleted", definition, detail=f"count={len(objects)}")
    return len(objects)


def readonly_context(definition, request, obj):
    return readonly_rows(definition, request, obj, configured_readonly_fields(definition, request, obj))


def history_queryset(definition, obj):
    content_type = ContentType.objects.get_for_model(definition.model, for_concrete_model=False)
    return LogEntry.objects.select_related("user").filter(
        content_type=content_type,
        object_id=str(obj.pk),
    ).order_by("-action_time", "-pk")
