"""Generic, dependency-light localization introspection for Paxalia Admin."""

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


def language_choices():
    configured = getattr(settings, "LANGUAGES", ()) or ()
    return [(str(code), str(name)) for code, name in configured]


def is_translatable_model(model) -> bool:
    return bool(translated_field_objects(model))


def translated_field_objects(model, excluded_names=()):
    if not hasattr(model, "_parler_meta"):
        return []
    try:
        fields = model._parler_meta.get_all_fields()
    except Exception:
        return []
    sensitive = {name.lower().replace("_", "") for name in _SENSITIVE_NAMES}
    excluded = {str(name).lower().replace("_", "") for name in (excluded_names or ())}
    return [
        field
        for field in fields
        if (
            getattr(field, "name", "")
            and str(getattr(field, "name", "")).lower().replace("_", "") not in sensitive
            and str(getattr(field, "name", "")).lower().replace("_", "") not in excluded
        )
    ]


def translated_fields(model, excluded_names=()):
    return [field.name for field in translated_field_objects(model, excluded_names=excluded_names)]


def _translation_values(obj, language):
    values = {}
    fields = translated_field_objects(obj.__class__)
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


def translation_values(obj, language):
    current = getattr(obj, "get_current_language", lambda: None)()
    try:
        return _translation_values(obj, language)
    finally:
        if current and hasattr(obj, "set_current_language"):
            try:
                obj.set_current_language(current)
            except Exception:
                pass


def save_translation(obj, language, values):
    if not hasattr(obj, "set_current_language"):
        raise ValueError("This model does not expose a supported translation API.")
    enabled_languages = {str(code) for code, _ in language_choices()}
    if str(language) not in enabled_languages:
        raise ValueError("The selected language is not enabled in the current site configuration.")

    allowed = {field.name: field for field in translated_field_objects(obj.__class__)}
    current = getattr(obj, "get_current_language", lambda: None)()
    try:
        obj.set_current_language(language)
        for name, raw_value in values.items():
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


def translation_state(obj, languages=None):
    languages = languages or [code for code, _ in language_choices()]
    languages = [str(code) for code in languages if any(str(code) == configured for configured, _ in language_choices())]
    result = []
    for code in languages:
        complete = False
        try:
            has_translation = getattr(obj, "has_translation", None)
            if callable(has_translation):
                complete = bool(has_translation(code))
            if complete:
                values = _translation_values(obj, code)
                if not values or not any(value not in (None, "") for value in values.values()):
                    complete = False
        except Exception:
            complete = False
        result.append({"code": code, "complete": complete})
    return result


def completeness_for_queryset(queryset, limit=100):
    languages = [code for code, _ in language_choices()]
    language_names = dict(language_choices())
    rows = []
    total = queryset.count()
    checked = 0
    complete = 0
    fields = translation_editor_fields(queryset.model)
    for obj in queryset[:limit]:
        state = translation_state(obj, languages)
        translation_map = {code: translation_values(obj, code) for code in languages}
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
            "languages": state,
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
