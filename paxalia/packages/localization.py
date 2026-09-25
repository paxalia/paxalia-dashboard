"""Generic, dependency-light localization introspection for Paxalia Admin.

The localization layer deliberately treats django-parler as an adapter rather
than depending on private field shapes.  In django-parler 2.x,
``_parler_meta.get_all_fields()`` returns translated field *names* while the
actual Django ``Field`` objects live on the translated model.  Normalizing that
boundary here keeps export, import and the admin editor on the same contract.
"""

from __future__ import annotations

from django.conf import settings
from django.utils.text import capfirst

from ..logging.redaction import redact_text


_SENSITIVE_NAMES = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "client_secret", "signing_secret", "api_key", "apikey",
    "private_key", "session_key", "csrf_token", "authorization", "cookie",
    "credential", "credentials", "secret_key", "encryption_key",
}


def _normalize_code(code):
    return str(code or "").strip().lower()


def language_choices():
    """Return the effective supported languages in stable display order.

    Django's ``LANGUAGES`` remains the primary source because it controls the
    dashboard UI.  django-parler's configured language tuples are merged in so
    a valid translation language is not accidentally hidden merely because a
    host project keeps the two settings lists slightly different.
    """
    choices = []
    seen = set()

    configured = getattr(settings, "LANGUAGES", ()) or ()
    for code, name in configured:
        normalized = _normalize_code(code)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        choices.append((str(code), str(name)))

    parler_languages = getattr(settings, "PARLER_LANGUAGES", None) or {}
    parler_entries = parler_languages.get(None, ()) if isinstance(parler_languages, dict) else ()
    for entry in parler_entries or ():
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "").strip()
        normalized = _normalize_code(code)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        choices.append((code, code))

    return choices


def _meta_field_name(item):
    if isinstance(item, str):
        return item
    name = getattr(item, "name", None)
    return str(name) if name else ""


def _translation_field_objects(model):
    """Resolve django-parler translated field names to actual Django Fields."""
    meta = getattr(model, "_parler_meta", None)
    if meta is None:
        return []

    try:
        raw_fields = list(meta.get_all_fields())
    except Exception:
        return []

    resolved = []
    seen = set()
    for item in raw_fields:
        name = _meta_field_name(item)
        normalized = _normalize_code(name).replace("_", "")
        if not name or normalized in seen:
            continue
        seen.add(normalized)

        field = item if hasattr(item, "formfield") and hasattr(item, "name") else None
        if field is None:
            try:
                translation_target = meta.get_model_by_field(name)
                # django-parler compatibility layers may return the concrete
                # Field itself instead of its translation model. Accept both
                # shapes; requiring ``._meta.get_field()`` for the Field case
                # incorrectly drops an otherwise valid translation surface.
                if hasattr(translation_target, "formfield") and hasattr(translation_target, "name"):
                    field = translation_target
                else:
                    field = translation_target._meta.get_field(name)
            except Exception:
                try:
                    # Compatibility fallback for older/custom parler adapters.
                    translation_model = getattr(meta, "model", None)
                    if translation_model is not None:
                        field = translation_model._meta.get_field(name)
                except Exception:
                    field = None
        if field is not None and getattr(field, "name", None):
            resolved.append(field)

    return resolved


def is_translatable_model(model) -> bool:
    return bool(_translation_field_objects(model))


def translated_field_objects(model, excluded_names=()):
    fields = _translation_field_objects(model)
    sensitive = {
        _normalize_code(name).replace("_", "")
        for name in _SENSITIVE_NAMES
    }
    excluded = {
        _normalize_code(name).replace("_", "")
        for name in (excluded_names or ())
    }
    return [
        field
        for field in fields
        if _normalize_code(getattr(field, "name", "")).replace("_", "") not in sensitive
        and _normalize_code(getattr(field, "name", "")).replace("_", "") not in excluded
    ]


def translated_fields(model, excluded_names=()):
    return [field.name for field in translated_field_objects(model, excluded_names=excluded_names)]


def _has_translation_value(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _translation_values(obj, language, excluded_names=()):
    values = {}
    fields = translated_field_objects(obj.__class__, excluded_names=excluded_names)
    getter = getattr(obj, "safe_translation_getter", None)
    for field in fields:
        try:
            if callable(getter):
                value = getter(field.name, language_code=language, default=None)
            else:
                obj.set_current_language(language)
                value = getattr(obj, field.name, None)
        except Exception:
            value = None
        if value is not None:
            values[field.name] = value
    return values


def translation_editor_fields(model, excluded_names=()):
    fields = []
    for field in translated_field_objects(model, excluded_names=excluded_names):
        if not getattr(field, "editable", True):
            continue
        internal_type = getattr(field, "get_internal_type", lambda: "")()
        choices = list(getattr(field, "choices", ()) or ())
        widget = "textarea" if internal_type == "TextField" else "input"
        input_type = "checkbox" if internal_type == "BooleanField" else "text"
        fields.append({
            "name": field.name,
            "label": capfirst(str(getattr(field, "verbose_name", field.name))),
            "widget": widget,
            "input_type": input_type,
            "choices": [(str(value), str(label)) for value, label in choices],
        })
    return fields


def translation_values(obj, language, excluded_names=()):
    current = getattr(obj, "get_current_language", lambda: None)()
    try:
        return _translation_values(obj, language, excluded_names=excluded_names)
    finally:
        if current and hasattr(obj, "set_current_language"):
            try:
                obj.set_current_language(current)
            except Exception:
                pass


def save_translation(obj, language, values):
    if not hasattr(obj, "set_current_language"):
        raise ValueError("This model does not expose a supported translation API.")
    enabled_languages = {_normalize_code(code) for code, _ in language_choices()}
    normalized_language = _normalize_code(language)
    if normalized_language not in enabled_languages:
        raise ValueError("The selected language is not enabled in the current site configuration.")

    allowed = {field.name: field for field in translated_field_objects(obj.__class__)}
    current = getattr(obj, "get_current_language", lambda: None)()
    try:
        obj.set_current_language(language)
        for name, raw_value in (values or {}).items():
            field = allowed.get(name)
            if field is None:
                continue
            form_field = None
            try:
                form_field = field.formfield(required=False)
            except Exception:
                form_field = None
            if form_field is not None:
                cleaned = form_field.clean(raw_value)
            else:
                cleaned = field.to_python(raw_value)
            setattr(obj, name, cleaned)
        obj.save()
    finally:
        if current and hasattr(obj, "set_current_language"):
            try:
                obj.set_current_language(current)
            except Exception:
                pass


def translation_state(obj, languages=None, excluded_names=()):
    supported = {_normalize_code(code) for code, _ in language_choices()}
    languages = languages or [code for code, _ in language_choices()]
    languages = [
        str(code)
        for code in languages
        if _normalize_code(code) in supported
    ]
    fields = translated_field_objects(obj.__class__, excluded_names=excluded_names)
    result = []
    for code in languages:
        complete = False
        try:
            has_translation = getattr(obj, "has_translation", None)
            complete = bool(has_translation(code)) if callable(has_translation) else False
            if complete:
                values = _translation_values(obj, code, excluded_names=excluded_names)
                complete = bool(fields) and all(
                    _has_translation_value(values.get(field.name))
                    for field in fields
                )
        except Exception:
            complete = False
        result.append({"code": code, "complete": complete})
    return result


def completeness_for_queryset(queryset, limit=100, offset=0, excluded_names=()):
    languages = [code for code, _ in language_choices()]
    language_names = dict(language_choices())
    rows = []
    total = queryset.count()
    checked = 0
    complete = 0
    fields = translation_editor_fields(queryset.model, excluded_names=excluded_names)
    try:
        offset = max(0, int(offset or 0))
    except (TypeError, ValueError):
        offset = 0
    for obj in queryset[offset:offset + limit]:
        state = translation_state(obj, languages, excluded_names=excluded_names)
        language_status = [
            {**item, "name": language_names.get(item["code"], item["code"])}
            for item in state
        ]
        translation_map = {
            code: translation_values(obj, code, excluded_names=excluded_names)
            for code in languages
        }
        editor_languages = []
        for item in state:
            code = item["code"]
            values = translation_map.get(code, {})
            editor_languages.append({
                "code": code,
                "name": language_names.get(code, code),
                "complete": item["complete"],
                "fields": [dict(field, value=values.get(field["name"], "")) for field in fields],
            })
        checked += 1
        complete += int(all(item["complete"] for item in state)) if state else 0
        try:
            identity = redact_text(str(obj)[:240])
        except Exception:
            identity = redact_text(str(getattr(obj, "pk", "—")))
        rows.append({
            "object": obj,
            "identity": identity,
            "languages": language_status,
            "translations": translation_map,
            "editor_languages": editor_languages,
            "missing": [item["code"] for item in state if not item["complete"]],
        })
    return {
        "languages": languages,
        "language_names": language_names,
        "translation_fields": fields,
        "rows": rows,
        "total": total,
        "checked": checked,
        "complete": complete,
        "incomplete": max(0, checked - complete),
    }

