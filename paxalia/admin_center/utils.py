import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import PurePath

from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.admin.utils import label_for_field, lookup_field

from ..logging.redaction import redact
from .registry import is_sensitive_field


def safe_object_repr(obj, limit=240):
    try:
        return str(obj)[:limit]
    except Exception:
        return obj.__class__.__name__


def safe_primitive(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "[BINARY DATA]"
    if isinstance(value, PurePath):
        return str(value)
    if hasattr(value, "url") and hasattr(value, "name"):
        return getattr(value, "name", "") or ""
    try:
        return str(value)
    except Exception:
        return "[UNSERIALIZABLE]"


def json_preview(value, max_bytes=12000, extra_keys=None):
    cleaned = redact(value, extra_keys=extra_keys)
    try:
        raw = json.dumps(cleaned, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
    except Exception:
        raw = json.dumps(str(cleaned), ensure_ascii=False)
    if len(raw.encode("utf-8")) <= max_bytes:
        return raw
    return raw[:max(100, max_bytes - 80)] + "\n… [truncated]"


def iter_fieldsets(definition, request, obj=None):
    model_admin = definition.model_admin
    try:
        fieldsets = model_admin.get_fieldsets(request, obj)
    except Exception:
        fieldsets = []
    if fieldsets:
        for title, options in fieldsets:
            field_names = []
            for name in (options or {}).get("fields", ()):
                if isinstance(name, (list, tuple)):
                    field_names.extend(name)
                else:
                    field_names.append(name)
            yield title or "General", field_names
        return

    names = []
    for field in definition.model._meta.get_fields():
        if getattr(field, "auto_created", False) and not getattr(field, "concrete", False):
            continue
        if getattr(field, "editable", True) or getattr(field, "many_to_many", False):
            names.append(field.name)
    yield "General", names


def model_field_metadata(model, field_name):
    try:
        return model._meta.get_field(field_name)
    except Exception:
        return None


def _label_for_name(definition, name):
    try:
        return label_for_field(name, definition.model, model_admin=definition.model_admin)
    except Exception:
        try:
            return str(definition.model._meta.get_field(name).verbose_name)
        except Exception:
            return str(name).replace("_", " ").title()


def _field_is_displayable(definition, name):
    hidden = definition.hidden_fields
    display = definition.display_fields
    if name in hidden:
        return False
    return display is None or name in display


def readonly_rows(definition, request, obj, readonly_fields):
    rows = []
    for name in readonly_fields or ():
        if name in definition.hidden_fields:
            continue
        try:
            field, attr, value = lookup_field(name, obj, definition.model_admin)
            if field is not None and is_sensitive_field(field, definition.model):
                display = "••••••••"
                sensitive = True
            elif field is not None and getattr(field, "choices", None):
                display = dict(field.flatchoices).get(value, value)
                sensitive = False
            elif value is None:
                display = "—"
                sensitive = False
            elif field is not None and field.get_internal_type() == "JSONField":
                display = json_preview(value, extra_keys=definition.sensitive_fields)
                sensitive = False
            else:
                display = redact(safe_object_repr(value, 4000), extra_keys=definition.sensitive_fields)
                sensitive = False
            rows.append({
                "name": name,
                "label": _label_for_name(definition, name),
                "display": str(display),
                "sensitive": sensitive,
            })
        except Exception:
            rows.append({
                "name": name,
                "label": str(name),
                "display": "—",
                "sensitive": False,
            })
    return rows
