"""Generic Django model import/export engine for Paxalia Admin."""

from __future__ import annotations

import base64
import json
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import PurePath
from collections.abc import Mapping
from uuid import UUID

from django import VERSION as DJANGO_VERSION
from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.functional import Promise
from django.db.models.fields.files import FieldFile
from django.utils.translation import gettext as _

from ..settings import get_config
from .format import build_package, read_package
from .security import PackageSecurityError, decrypt, encrypt

logger = logging.getLogger("paxalia.packages")


class PackageError(ValueError):
    """A safe, user-facing package error."""


@dataclass
class PackageResult:
    package_id: str
    model_count: int
    record_count: int
    relationship_count: int
    translation_count: int
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[dict] | None = None

    def as_dict(self):
        return {
            "package_id": self.package_id,
            "model_count": self.model_count,
            "record_count": self.record_count,
            "relationship_count": self.relationship_count,
            "translation_count": self.translation_count,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors or [],
        }


def _max_package_bytes() -> int:
    cfg = get_config()
    try:
        return max(1, int(cfg.get("PACKAGE_MAX_FILE_SIZE_MB", 100))) * 1024 * 1024
    except (TypeError, ValueError):
        return 100 * 1024 * 1024


def _max_records() -> int:
    try:
        return max(1, min(int(get_config().get("PACKAGE_MAX_OBJECTS", 10000)), 1_000_000))
    except (TypeError, ValueError):
        return 10000


def _max_relations() -> int:
    try:
        return max(1, min(int(get_config().get("PACKAGE_MAX_RELATIONS", 50000) or 50000), 1_000_000))
    except (TypeError, ValueError):
        return 50000


def _model_label(model):
    return model._meta.label_lower


def _model_from_label(label):
    try:
        app_label, model_name = str(label).split(".", 1)
        return apps.get_model(app_label, model_name)
    except (ValueError, LookupError) as exc:
        raise PackageError(_("Model '%(label)s' is not available in this Django installation.") % {"label": label}) from exc


def _model_options(label):
    options = get_config().get("ADMIN_MODELS") or {}
    if not isinstance(options, dict):
        return {}
    for key, value in options.items():
        if str(key).lower() == str(label).lower():
            return value if isinstance(value, dict) else {}
    return {}


def _hidden_names(model):
    configured = (_model_options(_model_label(model)).get("hidden_fields") or [])
    return {
        str(name).lower().replace("_", "")
        for name in configured
        if str(name).strip()
    }


def _is_hidden(model, name):
    normalized = str(name).lower().replace("_", "")
    return normalized in _hidden_names(model)


def _sensitive_names(model):
    configured = get_config().get("ADMIN_SENSITIVE_FIELDS") or []
    names = {str(x).lower() for x in configured}
    names.update(str(x).lower() for x in (_model_options(_model_label(model)).get("sensitive_fields") or []))
    names.update({"password", "token", "secret", "access_token", "refresh_token", "api_key", "apikey", "private_key", "authorization", "cookie"})
    return names


def _is_sensitive(model, name):
    norm = str(name).lower().replace("_", "")
    return str(name).lower() in _sensitive_names(model) or norm in {x.replace("_", "") for x in _sensitive_names(model)}


def _normalise_sensitive_names(names):
    return {
        str(name).lower().replace("_", "")
        for name in (names or ())
        if str(name).strip()
    }


def _is_sensitive_key(name, sensitive_names):
    return str(name).lower().replace("_", "") in sensitive_names


def _jsonable(value, *, sensitive_names=None):
    """Return a JSON-safe value while protecting nested secret keys."""
    sensitive_names = _normalise_sensitive_names(sensitive_names)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Promise):
        return str(value)
    if isinstance(value, FieldFile):
        return str(getattr(value, "name", "") or "")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PackageError(_("A field contains a non-finite numeric value that cannot be exported safely."))
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "__paxalia_type__": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, Mapping):
        result = {}
        seen_keys = set()
        for key, item in value.items():
            string_key = str(key)
            if string_key in seen_keys:
                raise PackageError(
                    _("A mapping contains duplicate keys after JSON normalization and cannot be exported safely.")
                )
            seen_keys.add(string_key)
            if _is_sensitive_key(string_key, sensitive_names):
                result[string_key] = {"__paxalia_type__": "redacted"}
            else:
                result[string_key] = _jsonable(item, sensitive_names=sensitive_names)
        return result
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, sensitive_names=sensitive_names) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_jsonable(item, sensitive_names=sensitive_names) for item in sorted(value, key=lambda item: str(item))]
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise PackageError(_("A field contains an unsupported value type for Paxalia package export.")) from exc
    return value


def _field_names(model):
    hidden = {str(x).lower().replace("_", "") for x in (_model_options(_model_label(model)).get("hidden_fields") or [])}
    return [
        f.name
        for f in model._meta.concrete_fields
        if (
            not getattr(f, "auto_created", False)
            and f.name.lower().replace("_", "") not in hidden
            and not _is_sensitive(model, f.name)
        )
    ]


def identity_fields(model):
    opts = _model_options(_model_label(model))
    configured = opts.get("identity_fields")
    if configured:
        return [
            str(x)
            for x in configured
            if str(x) in {f.name for f in model._meta.concrete_fields}
            and not _is_sensitive(model, str(x))
        ]
    # A nullable unique column is not a reliable identity: multiple rows may
    # legitimately contain NULL, while `_identity()` must be able to match a
    # concrete record deterministically. Only auto-select non-null unique
    # fields; an explicitly configured identity remains strict and is validated
    # at export time.
    unique_fields = [
        f.name
        for f in model._meta.concrete_fields
        if (
            getattr(f, "unique", False)
            and not getattr(f, "null", False)
            and not _is_sensitive(model, f.name)
        )
    ]
    if unique_fields:
        return unique_fields[:3]
    pk_name = model._meta.pk.name
    if _is_sensitive(model, pk_name):
        return []
    return [pk_name]


def _identity(model, obj):
    names = identity_fields(model)
    if not names:
        raise PackageError(
            _("Model %(model)s does not expose a non-sensitive identity field for package operations.")
            % {"model": _model_label(model)}
        )
    values = {}
    for name in names:
        if _is_sensitive(model, name):
            continue
        try:
            field = model._meta.get_field(name)
        except Exception as exc:
            raise PackageError(
                _("Model %(model)s has an invalid configured identity field.")
                % {"model": _model_label(model)}
            ) from exc
        raw_value = field.value_from_object(obj)
        if raw_value is None:
            raise PackageError(
                _("Model %(model)s has an empty value for identity field '%(field)s'.")
                % {"model": _model_label(model), "field": name}
            )
        values[name] = _jsonable(raw_value, sensitive_names=_sensitive_names(model))
    return values


def _relationship_ref(related, request=None, field_name=None):
    model = related.__class__
    if request is not None:
        from django.contrib import admin
        model_admin = admin.site._registry.get(model)
        if model_admin is None or not model_admin.has_view_permission(request):
            raise PermissionDenied
        if not model_admin.has_view_permission(request, related):
            raise PermissionDenied
    return {"model": _model_label(model), "identity": _identity(model, related)}


def _translation_data(obj):
    if not hasattr(obj, "_parler_meta"):
        return {}
    model = obj.__class__
    try:
        meta = obj._parler_meta
        fields = [
            field.name for field in meta.get_all_fields()
            if not _is_sensitive(model, field.name)
        ]
        from django.conf import settings
        configured_languages = {str(code) for code, _name in getattr(settings, "LANGUAGES", [])}
        language_codes = []
        manager = getattr(obj, "translations", None)
        if manager is not None:
            qs = manager.all()
            language_field = getattr(getattr(meta, "fields", None), "language_code", None)
            if language_field is not None:
                language_codes = list(qs.values_list(language_field.name, flat=True).distinct())
        language_codes = [str(code) for code in language_codes if code]
        unsupported_languages = sorted(set(language_codes) - configured_languages)
        if unsupported_languages:
            raise PackageError(
                _("Model %(model)s contains translations for languages that are not enabled: %(languages)s.")
                % {
                    "model": _model_label(model),
                    "languages": ", ".join(unsupported_languages[:8]),
                }
            )
        if not language_codes:
            language_codes = list(configured_languages)
        getter = getattr(obj, "get_current_language", None)
        current = getter() if callable(getter) else None
        try:
            language_map = {}
            for language in dict.fromkeys(str(code) for code in language_codes if code):
                values = {}
                try:
                    translation_getter = getattr(obj, "safe_translation_getter", None)
                    for field_name in fields:
                        if callable(translation_getter):
                            value = translation_getter(field_name, language_code=language, default=None)
                        else:
                            obj.set_current_language(language)
                            value = getattr(obj, field_name, None)
                        if value is not None:
                            values[field_name] = _jsonable(
                                value,
                                sensitive_names=_sensitive_names(model),
                            )
                except PackageError:
                    raise
                except Exception as exc:
                    logger.exception(
                        "Translation serialization failed for %s language=%s",
                        _model_label(model), language,
                    )
                    raise PackageError(
                        _("Translation data could not be exported for %(model)s.")
                        % {"model": _model_label(model)}
                    ) from exc
                if values:
                    language_map[language] = values
            return language_map
        finally:
            if current and hasattr(obj, "set_current_language"):
                try:
                    obj.set_current_language(current)
                except Exception:
                    logger.exception("Failed to restore translation language for %s", _model_label(model))
    except PackageError:
        raise
    except Exception as exc:
        logger.exception("Translation metadata discovery failed for %s", _model_label(model))
        raise PackageError(
            _("Translation metadata could not be exported for %(model)s.")
            % {"model": _model_label(model)}
        ) from exc


def serialize_object(obj, request=None, *, translations_only=False):
    model = obj.__class__
    sensitive_names = _sensitive_names(model)
    field_names = set(_field_names(model))
    fields = {}
    relationships = {}
    for field in model._meta.concrete_fields:
        if field.name not in field_names:
            continue
        if translations_only and getattr(field, "is_relation", False):
            continue
        value = field.value_from_object(obj)
        if field.is_relation:
            if value is None:
                # Nullable FK/O2O fields are represented in the relationship
                # namespace as an explicit null. Serializing them as scalar
                # fields makes our own package validator reject a valid export.
                relationships[field.name] = None
                continue
            try:
                related = getattr(obj, field.name, None)
            except Exception as exc:
                logger.exception("Relationship serialization failed for %s.%s", _model_label(model), field.name)
                raise PackageError(
                    _("Relationship '%(field)s' could not be exported for %(model)s.")
                    % {"field": field.name, "model": _model_label(model)}
                ) from exc
            if related is None:
                raise PackageError(
                    _("Relationship '%(field)s' could not be loaded for %(model)s.")
                    % {"field": field.name, "model": _model_label(model)}
                )
            relationships[field.name] = _relationship_ref(related, request=request, field_name=field.name)
            continue
        fields[field.name] = _jsonable(value, sensitive_names=sensitive_names)

    if translations_only:
        return {
            "model": _model_label(model),
            "identity": _identity(model, obj),
            "fields": {},
            "relationships": {},
            "many_to_many": {},
            "translations": _translation_data(obj),
        }

    many_to_many = {}
    relation_limit = _max_relations()
    for field in model._meta.many_to_many:
        if _is_sensitive(model, field.name):
            continue
        try:
            manager = getattr(obj, field.name)
            items = list(manager.all()[: relation_limit + 1])
            if len(items) > relation_limit:
                raise PackageError(
                    _("Many-to-many relationship '%(field)s' exceeds the configured export relation limit of %(limit)s for %(model)s.")
                    % {
                        "field": field.name,
                        "limit": f"{relation_limit:,}",
                        "model": _model_label(model),
                    }
                )
            many_to_many[field.name] = [
                _relationship_ref(item, request=request, field_name=field.name)
                for item in items
            ]
        except PermissionDenied:
            raise
        except PackageError:
            raise
        except Exception as exc:
            logger.exception("M2M serialization failed for %s.%s", _model_label(model), field.name)
            raise PackageError(
                _("Many-to-many relationship '%(field)s' could not be exported for %(model)s.")
                % {"field": field.name, "model": _model_label(model)}
            ) from exc

    translations = _translation_data(obj)
    return {
        "model": _model_label(model),
        "identity": _identity(model, obj),
        "fields": fields,
        "relationships": relationships,
        "many_to_many": many_to_many,
        "translations": translations,
    }


def _enforce_export_permission(model, request, *, encrypted: bool = False):
    from django.contrib import admin
    model_admin = admin.site._registry.get(model)
    if model_admin is None or not model_admin.has_view_permission(request):
        raise PermissionDenied
    if _model_options(_model_label(model)).get("protected") and get_config().get("PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED", True) and not encrypted:
        raise PackageError(_("This protected model requires an encrypted Paxalia package."))


def export_models(models, request, *, querysets=None, selected_ids_by_model=None, translations_only=False, password=None):
    models = list(models or [])
    if not models:
        raise PackageError(_("Select at least one model to export."))
    querysets = querysets or {}
    selected_ids_by_model = selected_ids_by_model or {}
    definitions = []
    records = []
    relationship_count = 0
    translation_count = 0
    max_records = _max_records()
    max_relations = _max_relations()

    for model in models:
        _enforce_export_permission(model, request, encrypted=bool(password))
        if translations_only:
            from .localization import translated_field_objects
            if not translated_field_objects(model):
                raise PackageError(
                    _("Translation-only export is available only for models with a supported translation layer.")
                )
        from django.contrib import admin
        model_admin = admin.site._registry.get(model)
        try:
            visible_qs = model_admin.get_queryset(request) if model_admin is not None else model.objects.none()
        except Exception as exc:
            logger.exception("Unable to prepare %s for export", _model_label(model))
            raise PackageError(
                _("Unable to prepare %(model)s for export.") % {"model": _model_label(model)}
            ) from exc

        selected = selected_ids_by_model.get(_model_label(model))
        if selected is not None:
            selected = list(dict.fromkeys(str(value) for value in selected if str(value)))
            if len(selected) > max_records:
                raise PackageError(
                    _("The selected records exceed the configured export limit of %(limit)s.")
                    % {"limit": f"{max_records:,}"}
                )

        supplied_qs = querysets.get(_model_label(model)) if isinstance(querysets, dict) else None
        qs = supplied_qs if supplied_qs is not None else visible_qs
        try:
            qs = qs.filter(pk__in=visible_qs.values("pk"))
            if selected is not None:
                qs = qs.filter(pk__in=selected)
            objects = list(qs[:max_records + 1])
        except Exception as exc:
            logger.exception("Unable to read %s records for export", _model_label(model))
            raise PackageError(
                _("Unable to read %(model)s records for export.") % {"model": _model_label(model)}
            ) from exc
        if len(objects) > max_records:
            raise PackageError(
                _("%(model)s exceeds the configured export limit of %(limit)s records.")
                % {"model": _model_label(model), "limit": f"{max_records:,}"}
            )
        definitions.append({
            "label": _model_label(model),
            "identity_fields": identity_fields(model),
            "record_count": len(objects),
        })
        for obj in objects:
            if not model_admin.has_view_permission(request, obj):
                raise PermissionDenied
            try:
                row = serialize_object(obj, request=request, translations_only=translations_only)
            except (PackageError, PermissionDenied):
                raise
            except Exception as exc:
                logger.exception("Unable to serialize %s record", _model_label(model))
                raise PackageError(
                    _("Unable to export a %(model)s record safely.") % {"model": _model_label(model)}
                ) from exc
            records.append(row)
            relationship_count += len(row.get("relationships", {})) + sum(
                len(values) for values in row.get("many_to_many", {}).values()
            )
            translation_count += len(row.get("translations", {}))
            if relationship_count > max_relations:
                raise PackageError(_("The export exceeds the configured relationship limit."))
            if len(records) > max_records:
                raise PackageError(
                    _("The combined export exceeds the configured limit of %(limit)s records.")
                    % {"limit": f"{max_records:,}"}
                )

    payload = {
        "schema": 1,
        "project": {"django_version": ".".join(str(x) for x in DJANGO_VERSION[:3])},
        "translations_only": bool(translations_only),
        "models": definitions,
        "records": records,
        "record_count": len(records),
        "relationship_count": relationship_count,
        "translation_count": translation_count,
    }
    raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    encrypted_payload = encrypt(raw_payload, password) if password else None
    package_bytes = build_package(payload, encrypted_payload=encrypted_payload)
    if len(package_bytes) > _max_package_bytes():
        raise PackageError(
            _("The generated Paxalia package exceeds the configured maximum size of %(limit)s MB.")
            % {"limit": max(1, _max_package_bytes() // (1024 * 1024))}
        )
    return package_bytes


def export_model(model, request, *, queryset=None, selected_ids=None, translations_only=False, password=None):
    return export_models(
        [model],
        request,
        querysets={_model_label(model): queryset} if queryset is not None else None,
        selected_ids_by_model={_model_label(model): selected_ids} if selected_ids is not None else None,
        translations_only=translations_only,
        password=password,
    )

def _resolve_identity(model, identity, queryset=None):
    identity = identity or {}
    if not identity:
        return None
    try:
        _validate_identity(model, identity)
    except ValueError as exc:
        raise PackageError(str(exc)) from exc
    filters = {}
    valid_fields = {f.name: f for f in model._meta.concrete_fields}
    for name, value in identity.items():
        field = valid_fields[name]
        try:
            filters[name] = field.to_python(value)
        except Exception as exc:
            raise PackageError(
                _("Identity field '%(field)s' contains an invalid value.") % {"field": name}
            ) from exc
    try:
        qs = queryset if queryset is not None else model.objects.all()
        matches = list(qs.filter(**filters)[:2])
        if len(matches) > 1:
            raise PackageError(
                _("Identity for %(model)s matches multiple existing objects and cannot be resolved safely.")
                % {"model": _model_label(model)}
            )
        return matches[0] if matches else None
    except PackageError:
        raise
    except Exception as exc:
        logger.exception("Identity resolution failed for %s", _model_label(model))
        raise PackageError(
            _("Unable to resolve an identity for %(model)s safely.") % {"model": _model_label(model)}
        ) from exc


def _reference_key(ref):
    if not isinstance(ref, dict):
        return None
    return (
        str(ref.get("model") or "").lower(),
        json.dumps(ref.get("identity") or {}, sort_keys=True, default=str),
    )


def _record_key(record):
    return _reference_key({"model": record.get("model"), "identity": record.get("identity") or {}})


_MISSING = object()


def _restore_redacted(value, existing=_MISSING):
    """Restore redacted JSON values without silently deleting protected data."""
    if (
        isinstance(value, dict)
        and set(value) == {"__paxalia_type__"}
        and value.get("__paxalia_type__") == "redacted"
    ):
        if existing is _MISSING:
            raise PackageError(
                _("A protected JSON value cannot be reconstructed because no existing value is available.")
            )
        return existing
    if isinstance(value, dict):
        result = {}
        existing_map = existing if isinstance(existing, dict) else {}
        for key, item in value.items():
            prior = existing_map.get(key, _MISSING)
            result[key] = _restore_redacted(item, prior)
        return result
    if isinstance(value, list):
        existing_list = existing if isinstance(existing, list) else []
        result = []
        for index, item in enumerate(value):
            prior = existing_list[index] if index < len(existing_list) else _MISSING
            result.append(_restore_redacted(item, prior))
        return result
    return value


def _decode_field_value(field, raw, existing=_MISSING):
    if field.get_internal_type() == "JSONField":
        raw = _restore_redacted(raw, existing)
        if raw is _MISSING:
            return _MISSING
    if field.get_internal_type() != "BinaryField":
        return field.to_python(raw)
    if isinstance(raw, dict) and raw.get("__paxalia_type__") == "bytes":
        if raw.get("encoding") != "base64" or not isinstance(raw.get("value"), str):
            raise PackageError(_("A binary field contains an invalid Paxalia value."))
        try:
            return base64.b64decode(raw["value"], validate=True)
        except Exception as exc:
            raise PackageError(_("A binary field contains invalid encoded data.")) from exc
    if raw == "[BINARY DATA]":
        raise PackageError(_("A binary field uses an older non-restorable package encoding."))
    return field.to_python(raw)


def _assign_scalar_fields(obj, data):
    valid_fields = {f.name: f for f in obj.__class__._meta.concrete_fields}
    pk_name = obj.__class__._meta.pk.name
    for name, raw in (data or {}).items():
        field = valid_fields.get(name)
        if (
            name == pk_name
            or field is None
            or getattr(field, "is_relation", False)
            or _is_sensitive(obj.__class__, name)
            or _is_hidden(obj.__class__, name)
        ):
            continue
        try:
            value = _decode_field_value(field, raw, getattr(obj, name, _MISSING))
            if value is _MISSING:
                continue
        except PackageError:
            raise
        except Exception as exc:
            raise PackageError(
                _("Field '%(field)s' could not be converted safely.") % {"field": name}
            ) from exc
        setattr(obj, name, value)


def _ensure_reference_permission(model, request, obj):
    if request is None:
        return
    from django.contrib import admin
    model_admin = admin.site._registry.get(model)
    if model_admin is None or not model_admin.has_view_permission(request):
        raise PermissionDenied
    if obj is not None and not model_admin.has_view_permission(request, obj):
        raise PermissionDenied


def _resolve_reference(ref, object_cache=None, request=None):
    if not isinstance(ref, dict):
        return None
    key = _reference_key(ref)
    if object_cache is not None and key in object_cache:
        cached = object_cache[key]
        _ensure_reference_permission(cached.__class__, request, cached)
        return cached
    model = _model_from_label(ref.get("model", ""))
    queryset = None
    if request is not None:
        from django.contrib import admin
        model_admin = admin.site._registry.get(model)
        if model_admin is None or not model_admin.has_view_permission(request):
            raise PermissionDenied
        queryset = model_admin.get_queryset(request)
    related = _resolve_identity(model, ref.get("identity") or {}, queryset=queryset)
    if related is not None:
        _ensure_reference_permission(model, request, related)
    return related


def _apply_translations(obj, translations):
    if not translations:
        return 0
    if not hasattr(obj, "set_current_language"):
        raise PackageError(_("Translation data was supplied for a model without a supported translation layer."))
    try:
        from .localization import language_choices, translated_field_objects
        configured_languages = {str(code) for code, _name in language_choices()}
        allowed = {
            field.name: field
            for field in translated_field_objects(obj.__class__)
            if not _is_hidden(obj.__class__, field.name)
        }
    except Exception as exc:
        raise PackageError(_("The translation layer could not be inspected safely.")) from exc
    current = getattr(obj, "get_current_language", lambda: None)()
    count = 0
    try:
        for language, values in translations.items():
            if str(language) not in configured_languages:
                raise PackageError(
                    _("Translation language '%(language)s' is not enabled in the current site configuration.")
                    % {"language": language}
                )
            if not isinstance(values, dict):
                raise PackageError(_("Translation values for '%(language)s' are invalid.") % {"language": language})
            obj.set_current_language(language)
            for name, raw_value in values.items():
                field = allowed.get(name)
                if field is None or _is_sensitive(obj.__class__, name):
                    raise PackageError(
                        _("Translation field '%(field)s' is not supported for import.") % {"field": name}
                    )
                try:
                    form_field = field.formfield(required=False)
                    cleaned = form_field.clean(raw_value) if form_field is not None else field.to_python(raw_value)
                except Exception as exc:
                    raise PackageError(
                        _("Translation field '%(field)s' contains an invalid value.") % {"field": name}
                    ) from exc
                setattr(obj, name, cleaned)
            obj.save()
            count += 1
    finally:
        if current and hasattr(obj, "set_current_language"):
            try:
                obj.set_current_language(current)
            except Exception:
                logger.exception("Failed to restore translation language for %s", _model_label(obj.__class__))
    return count


def _validate_identity(model, identity):
    concrete_fields = {f.name: f for f in model._meta.concrete_fields}
    expected = set(identity_fields(model))
    if not expected:
        raise ValueError("model does not expose a safe identity field")
    if not isinstance(identity, dict) or not identity:
        raise ValueError("identity must contain at least one field")
    if set(identity) != expected:
        raise ValueError("identity fields do not match the model's configured identity definition")
    for name in identity:
        field = concrete_fields.get(name)
        if field is None:
            raise ValueError(f"unknown identity field: {name}")
        if identity.get(name) is None:
            raise ValueError(f"identity field cannot be null: {name}")
        if _is_sensitive(model, name):
            raise ValueError(f"sensitive identity field is blocked: {name}")


def _validate_reference(ref, expected_model, field_name):
    if not isinstance(ref, dict) or not isinstance(ref.get("identity", {}), dict):
        raise ValueError(f"relationship reference is invalid: {field_name}")
    target = _model_from_label(ref.get("model", ""))
    if target is not expected_model:
        raise ValueError(f"relationship reference targets the wrong model: {field_name}")
    _validate_identity(target, ref.get("identity") or {})


def _validate_records(records, *, translations_only=False):
    if not isinstance(records, list):
        raise PackageError(_("The Paxalia package records payload is invalid."))
    if len(records) > _max_records():
        raise PackageError(_("The Paxalia package exceeds the configured object limit."))
    models = {}
    errors = []
    seen_keys = set()
    for index, record in enumerate(records):
        try:
            if not isinstance(record, dict):
                raise ValueError("record must be an object")
            label = str(record.get("model") or "")
            model = _model_from_label(label)
            canonical_label = _model_label(model)
            if label != canonical_label:
                raise ValueError("model label is not canonical")
            models[label] = model
            concrete_fields = {f.name: f for f in model._meta.concrete_fields}
            relation_fields = {f.name: f for f in model._meta.concrete_fields if getattr(f, "is_relation", False)}
            many_to_many_fields = {f.name: f for f in model._meta.many_to_many}

            identity = record.get("identity", {})
            _validate_identity(model, identity)
            record_key = _record_key({"model": label, "identity": identity})
            if record_key in seen_keys:
                raise ValueError("duplicate model identity in package records")
            seen_keys.add(record_key)

            fields = record.get("fields", {})
            if fields is None:
                fields = {}
            if not isinstance(fields, dict):
                raise ValueError("fields must be an object")
            for name in fields:
                field = concrete_fields.get(name)
                if field is None:
                    raise ValueError(f"unknown field: {name}")
                if field in relation_fields.values():
                    raise ValueError(f"relationship field must be encoded in relationships: {name}")
                if _is_sensitive(model, name):
                    raise ValueError(f"sensitive field export/import is blocked: {name}")
                if _is_hidden(model, name):
                    raise ValueError(f"hidden field export/import is blocked: {name}")
                if field.get_internal_type() == "BinaryField":
                    raw = fields[name]
                    if not isinstance(raw, dict) or raw.get("__paxalia_type__") != "bytes":
                        raise ValueError(f"binary field uses an unsupported package encoding: {name}")

            relationships = record.get("relationships", {})
            if relationships is None:
                relationships = {}
            if not isinstance(relationships, dict):
                raise ValueError("relationships must be an object")
            unknown_relationships = set(relationships) - set(relation_fields)
            if unknown_relationships:
                raise ValueError(f"unknown relationship field: {sorted(unknown_relationships)[0]}")
            for name, ref in relationships.items():
                if ref is None:
                    continue
                remote_model = getattr(getattr(relation_fields[name], "remote_field", None), "model", None)
                if remote_model is None:
                    raise ValueError(f"relationship field has no target model: {name}")
                _validate_reference(ref, remote_model, name)

            many_to_many = record.get("many_to_many", {})
            if many_to_many is None:
                many_to_many = {}
            if not isinstance(many_to_many, dict):
                raise ValueError("many_to_many must be an object")
            unknown_many_to_many = set(many_to_many) - set(many_to_many_fields)
            if unknown_many_to_many:
                raise ValueError(f"unknown many-to-many field: {sorted(unknown_many_to_many)[0]}")
            for name, refs in many_to_many.items():
                if not isinstance(refs, list):
                    raise ValueError(f"many-to-many references are invalid: {name}")
                remote_model = getattr(getattr(many_to_many_fields[name], "remote_field", None), "model", None)
                if remote_model is None:
                    raise ValueError(f"many-to-many field has no target model: {name}")
                for ref in refs:
                    _validate_reference(ref, remote_model, name)

            translations = record.get("translations", {})
            if translations is None:
                translations = {}
            if not isinstance(translations, dict) or any(not isinstance(values, dict) for values in translations.values()):
                raise ValueError("translations must be a language-to-object mapping")
            if translations_only and not hasattr(model, "_parler_meta"):
                raise ValueError("translations-only packages require a supported translation model")
            if translations:
                if not hasattr(model, "_parler_meta"):
                    raise ValueError("translations are supplied for a model without supported translation metadata")
                from .localization import language_choices, translated_field_objects
                configured_languages = {str(code) for code, _name in language_choices()}
                allowed_translation_fields = {
                    field.name
                    for field in translated_field_objects(model)
                    if not _is_hidden(model, field.name)
                }
                if not allowed_translation_fields:
                    raise ValueError("no supported translation fields are available")
                for language, values in translations.items():
                    if str(language) not in configured_languages:
                        raise ValueError(f"translation language is not enabled: {language}")
                    for name in values:
                        if name not in allowed_translation_fields or _is_sensitive(model, name):
                            raise ValueError(f"unsupported translation field: {name}")

            if translations_only and (fields or relationships or many_to_many):
                raise ValueError("translations-only packages cannot contain scalar fields or relationships")
        except Exception as exc:
            errors.append({"index": index, "reason": str(exc)[:500]})
    if errors:
        raise PackageError(
            _("Package validation failed: %(errors)s")
            % {"errors": "; ".join(e["reason"] for e in errors[:8])}
        )
    return models


def _validate_payload_metadata(payload, manifest, records, models):
    payload_models = payload.get("models")
    if not isinstance(payload_models, list):
        raise PackageError(_("Paxalia package model metadata is invalid."))
    normalized_payload = {}
    for item in payload_models:
        if not isinstance(item, dict) or not item.get("label"):
            raise PackageError(_("Paxalia package model metadata is invalid."))
        label = str(item["label"])
        try:
            canonical_model = _model_from_label(label)
        except PackageError:
            raise
        if label != _model_label(canonical_model):
            raise PackageError(_("Paxalia package model metadata contains a non-canonical model label."))
        key = label.lower()
        if key in normalized_payload:
            raise PackageError(_("Paxalia package contains duplicate model metadata."))
        normalized_payload[key] = item
    if set(normalized_payload) != {label.lower() for label in models}:
        raise PackageError(_("Paxalia package model metadata does not match its records."))
    for label, model in models.items():
        metadata = normalized_payload[label.lower()]
        raw_record_count = metadata.get("record_count")
        if isinstance(raw_record_count, bool) or not isinstance(raw_record_count, int) or raw_record_count < 0:
            raise PackageError(_("Paxalia package model counts are invalid."))
        expected_count = sum(1 for record in records if str(record.get("model", "")).lower() == label.lower())
        if raw_record_count != expected_count:
            raise PackageError(_("Paxalia package model counts are inconsistent."))
        metadata_identity_fields = metadata.get("identity_fields")
        expected_identity_fields = identity_fields(model)
        concrete_names = {f.name for f in model._meta.concrete_fields}
        if (
            not isinstance(metadata_identity_fields, list)
            or [str(name) for name in metadata_identity_fields] != expected_identity_fields
            or any(str(name) not in concrete_names for name in metadata_identity_fields)
            or any(_is_sensitive(model, str(name)) for name in metadata_identity_fields)
        ):
            raise PackageError(_("Paxalia package identity metadata is invalid."))

    record_count = len(records)
    relationship_count = sum(
        len(record.get("relationships", {}))
        + sum(len(values) for values in record.get("many_to_many", {}).values())
        for record in records
    )
    translation_count = sum(len(record.get("translations", {})) for record in records)
    if relationship_count > _max_relations():
        raise PackageError(_("Paxalia package exceeds the configured relationship limit."))
    raw_counts = {
        "payload_record_count": payload.get("record_count"),
        "payload_relationship_count": payload.get("relationship_count"),
        "payload_translation_count": payload.get("translation_count"),
        "manifest_record_count": manifest.get("record_count"),
        "manifest_relationship_count": manifest.get("relationship_count"),
        "manifest_translation_count": manifest.get("translation_count"),
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in raw_counts.values()):
        raise PackageError(_("Paxalia package count metadata is invalid."))
    payload_record_count = raw_counts["payload_record_count"]
    payload_relationship_count = raw_counts["payload_relationship_count"]
    payload_translation_count = raw_counts["payload_translation_count"]
    manifest_record_count = raw_counts["manifest_record_count"]
    manifest_relationship_count = raw_counts["manifest_relationship_count"]
    manifest_translation_count = raw_counts["manifest_translation_count"]
    if payload_record_count != record_count:
        raise PackageError(_("Paxalia package record count is inconsistent."))
    if payload_relationship_count != relationship_count:
        raise PackageError(_("Paxalia package relationship count is inconsistent."))
    if payload_translation_count != translation_count:
        raise PackageError(_("Paxalia package translation count is inconsistent."))
    payload_translations_only = payload.get("translations_only", False)
    manifest_translations_only = manifest.get("translations_only", False)
    if not isinstance(payload_translations_only, bool) or not isinstance(manifest_translations_only, bool):
        raise PackageError(_("Paxalia package translation-only metadata is invalid."))
    if payload_translations_only != manifest_translations_only:
        raise PackageError(_("Paxalia package translation-only metadata is inconsistent."))
    if (manifest_record_count, manifest_relationship_count, manifest_translation_count) != (record_count, relationship_count, translation_count):
        raise PackageError(_("Paxalia package manifest counts are inconsistent with its data."))
    if manifest.get("models") != payload_models:
        raise PackageError(_("Paxalia package manifest model metadata is inconsistent with its data."))


def inspect_package(raw: bytes, password: str | None = None):
    manifest, content, encrypted = read_package(raw, max_size=_max_package_bytes())
    if encrypted:
        try:
            content = decrypt(content, password or "")
        except PackageSecurityError as exc:
            raise PackageError(str(exc)) from exc
    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise PackageError(_("Paxalia package data is not valid UTF-8 JSON.")) from exc
    if not isinstance(payload, dict):
        raise PackageError(_("Paxalia package data must be a JSON object."))
    if payload.get("schema") != 1:
        raise PackageError(_("Unsupported Paxalia package schema."))
    if not isinstance(payload.get("translations_only"), bool):
        raise PackageError(_("Paxalia package translation-only metadata is invalid."))
    records = payload.get("records")
    if not isinstance(records, list):
        raise PackageError(_("Paxalia package records payload is invalid."))
    models = _validate_records(records, translations_only=payload["translations_only"])
    payload_models = payload.get("models")
    if not isinstance(payload_models, list):
        raise PackageError(_("Paxalia package model metadata is invalid."))
    for item in payload_models:
        if not isinstance(item, dict):
            raise PackageError(_("Paxalia package model metadata is invalid."))
        label = str(item.get("label") or "")
        model = _model_from_label(label)
        if label != _model_label(model):
            raise PackageError(_("Paxalia package model metadata contains a non-canonical model label."))
        models[label] = model
    _validate_payload_metadata(payload, manifest, records, models)
    return manifest, payload, models



def _allowed_conflicts():
    configured = get_config().get("PACKAGE_ALLOWED_CONFLICTS") or ["update", "skip"]
    if isinstance(configured, str):
        configured = [configured]
    allowed = {str(value).strip().lower() for value in configured}
    allowed &= {"update", "skip"}
    return allowed or {"update", "skip"}


def _allow_duplicate(model):
    return bool(_model_options(_model_label(model)).get("allow_duplicate", False))

def _check_import_models_permissions(models, request, manifest):
    from django.contrib import admin
    for model in models.values() if isinstance(models, dict) else models:
        model_admin = admin.site._registry.get(model)
        if model_admin is None or not model_admin.has_view_permission(request):
            raise PermissionDenied
        if (
            _model_options(_model_label(model)).get("protected")
            and get_config().get("PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED", True)
            and not manifest.get("encrypted")
        ):
            raise PackageError(_("This protected model requires an encrypted Paxalia package."))


def _prepare_record(index, record, models, request, *, conflict, object_cache, allow_duplicate=True):
    from django.contrib import admin
    model = models[record["model"]]
    model_admin = admin.site._registry.get(model)
    if model_admin is None or not model_admin.has_view_permission(request):
        raise PermissionDenied
    visible_qs = model_admin.get_queryset(request)
    existing = None if allow_duplicate else _resolve_identity(
        model, record.get("identity") or {}, queryset=visible_qs
    )
    if existing is not None and conflict == "skip":
        if not model_admin.has_view_permission(request, existing):
            raise PermissionDenied
        object_cache[_record_key(record)] = existing
        return {"status": "skipped", "object": existing}
    if existing is not None:
        if not model_admin.has_change_permission(request, existing):
            raise PermissionDenied
    elif not model_admin.has_add_permission(request):
        raise PermissionDenied
    obj = existing or model()
    _assign_scalar_fields(obj, record.get("fields") or {})

    # Concrete FK/O2O values must be assigned before the first save. A generic
    # importer cannot safely insert a required relation as NULL and hope to
    # repair it later: PostgreSQL enforces the NOT NULL constraint immediately.
    # Dependency ordering guarantees package-local references are already in
    # object_cache, while external references are resolved through the
    # requesting user's ModelAdmin queryset/permissions. M2M relations remain
    # a post-save operation.
    for name, ref in (record.get("relationships") or {}).items():
        try:
            field = model._meta.get_field(name)
        except Exception as exc:
            raise PackageError(
                _("Relationship field '%(field)s' is not available on %(model)s.")
                % {"field": name, "model": _model_label(model)}
            ) from exc
        if not getattr(field, "is_relation", False) or not (
            getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False)
        ):
            raise PackageError(
                _("Relationship field '%(field)s' is not a supported FK/O2O field on %(model)s.")
                % {"field": name, "model": _model_label(model)}
            )
        related = _resolve_reference(ref, object_cache=object_cache, request=request)
        if related is None and ref is not None:
            raise PackageError(
                _("Relationship '%(field)s' could not be resolved before importing %(model)s.")
                % {"field": name, "model": _model_label(model)}
            )
        setattr(obj, name, related)

    try:
        obj.save()
    except Exception as exc:
        logger.exception("Paxalia package record save failed for %s", _model_label(model))
        raise PackageError(
            _("The %(model)s record could not be saved safely.") % {"model": _model_label(model)}
        ) from exc
    return {"status": "updated" if existing is not None else "created", "object": obj}


def _apply_record_relations(record, operation, object_cache, request):
    obj = operation["object"]
    if operation["status"] == "skipped":
        return 0
    for name, ref in (record.get("relationships") or {}).items():
        related = _resolve_reference(ref, object_cache=object_cache, request=request)
        if related is None and ref is not None:
            raise PackageError(_("Relationship '%(field)s' could not be resolved.") % {"field": name})
        setattr(obj, name, related)
    obj.save()
    for name, refs in (record.get("many_to_many") or {}).items():
        manager = getattr(obj, name)
        related_objects = []
        for ref in refs:
            related = _resolve_reference(ref, object_cache=object_cache, request=request)
            if related is None:
                raise PackageError(
                    _("Many-to-many relationship '%(field)s' could not be fully resolved.")
                    % {"field": name}
                )
            related_objects.append(related)
        manager.set(related_objects)
    translation_count = _apply_translations(obj, record.get("translations") or {})
    object_cache[_record_key(record)] = obj
    return translation_count


def _append_import_error(result, index, model_label, exc):
    result.failed += 1
    if len(result.errors or []) >= 250:
        return
    if isinstance(exc, PermissionDenied):
        reason = _("You do not have permission to import this record.")
    elif isinstance(exc, PackageError):
        reason = str(exc)
    elif isinstance(exc, ValidationError):
        reason = _("The record failed validation.")
    else:
        logger.exception("Paxalia package import failed at record %s for %s", index, model_label)
        reason = _("The record could not be imported safely.")
    result.errors.append({"index": index, "model": model_label, "reason": str(reason)[:500]})


def preview_package(raw: bytes, *, password: str | None = None, conflict: str = "update", request=None):
    manifest, payload, models = inspect_package(raw, password=password)
    if conflict not in _allowed_conflicts():
        raise PackageError(_("Unsupported import conflict strategy."))
    if request is not None:
        _check_import_models_permissions(models, request, manifest)
    records = payload.get("records") or []
    result = PackageResult(
        package_id=str(manifest.get("package_id") or ""),
        model_count=len(models),
        record_count=len(records),
        relationship_count=int(payload.get("relationship_count", 0) or 0),
        translation_count=int(payload.get("translation_count", 0) or 0),
        errors=[],
    )
    from django.contrib import admin
    translations_only = bool(payload.get("translations_only", False))
    for index, record in enumerate(records):
        model = models[record["model"]]
        model_admin = admin.site._registry.get(model)
        queryset = model_admin.get_queryset(request) if request is not None and model_admin is not None else None
        try:
            existing = None if (_allow_duplicate(model) and not translations_only) else _resolve_identity(
                model, record.get("identity") or {}, queryset=queryset
            )
            if translations_only and existing is None:
                _append_import_error(
                    result,
                    index,
                    record.get("model"),
                    PackageError(_("Translation-only packages require an existing matching object.")),
                )
            elif existing is None:
                if model_admin is None or not model_admin.has_add_permission(request):
                    raise PermissionDenied
                result.created += 1
            elif conflict == "skip":
                if model_admin is not None and not model_admin.has_view_permission(request, existing):
                    raise PermissionDenied
                result.skipped += 1
            else:
                if model_admin is None or not model_admin.has_change_permission(request, existing):
                    raise PermissionDenied
                result.updated += 1
        except Exception as exc:
            _append_import_error(result, index, record.get("model"), exc)
    return result.as_dict()


def _apply_operation_counts(result, operation, translation_count=0):
    result.skipped += int(operation["status"] == "skipped")
    result.updated += int(operation["status"] == "updated")
    result.created += int(operation["status"] == "created")
    result.translation_count += translation_count


def _dependency_indices(records):
    keys = {}
    for index, record in enumerate(records):
        key = _record_key(record)
        keys.setdefault(key, []).append(index)
    dependencies = {index: set() for index in range(len(records))}
    for index, record in enumerate(records):
        refs = list((record.get("relationships") or {}).values())
        refs.extend(
            ref
            for values in (record.get("many_to_many") or {}).values()
            for ref in values
        )
        for ref in refs:
            key = _reference_key(ref)
            if key in keys:
                targets = keys[key]
                if len(targets) != 1:
                    raise PackageError(_("A package relationship points to an ambiguous record identity."))
                if targets[0] != index:
                    dependencies[index].add(targets[0])
    return dependencies


def import_package(raw: bytes, request, *, password: str | None = None, conflict: str = "update", atomic: bool = True, dry_run: bool = False):
    manifest, payload, models = inspect_package(raw, password=password)
    if conflict not in _allowed_conflicts():
        raise PackageError(_("Unsupported import conflict strategy."))
    _check_import_models_permissions(models, request, manifest)
    if dry_run:
        return preview_package(raw, password=password, conflict=conflict, request=request)

    records = payload.get("records") or []
    translations_only = bool(payload.get("translations_only", False))
    result = PackageResult(
        package_id=str(manifest.get("package_id") or ""),
        model_count=len(models),
        record_count=len(records),
        relationship_count=int(payload.get("relationship_count", 0) or 0),
        translation_count=int(payload.get("translation_count", 0) or 0),
        errors=[],
    )
    object_cache = {}

    if atomic:
        try:
            with transaction.atomic():
                operations = []
                local_cache = dict(object_cache)
                for index, record in enumerate(records):
                    operation = _prepare_record(
                        index, record, models, request,
                        conflict=conflict,
                        object_cache=local_cache,
                        allow_duplicate=_allow_duplicate(models[record["model"]]) and not translations_only,
                    )
                    if translations_only and operation["status"] == "created":
                        raise PackageError(_("Translation-only packages require existing matching objects."))
                    local_cache[_record_key(record)] = operation["object"]
                    operations.append((index, record, operation))
                for index, record, operation in operations:
                    translation_count = _apply_record_relations(record, operation, local_cache, request)
                    _apply_operation_counts(result, operation, translation_count)
            object_cache.update(local_cache)
        except PermissionDenied:
            raise
        except PackageError:
            raise
        except Exception as exc:
            logger.exception("Paxalia atomic package import failed")
            raise PackageError(_("Paxalia import failed safely.")) from exc
        return result.as_dict()

    dependencies = _dependency_indices(records)
    remaining = set(range(len(records)))
    completed = set()
    failed = set()
    while remaining:
        # A record that depends on a failed package record must not be allowed
        # to resolve that reference against a pre-existing database object.
        # Doing so could silently create a state that is only partly derived
        # from the package. Surface the dependency failure instead.
        blocked = sorted(
            index for index in remaining if dependencies[index] & failed
        )
        for index in blocked:
            dependency_error = PackageError(
                _("This record was not imported because one of its package dependencies failed.")
            )
            _append_import_error(result, index, records[index].get("model"), dependency_error)
            failed.add(index)
            remaining.remove(index)

        if not remaining:
            break

        ready = sorted(index for index in remaining if dependencies[index].issubset(completed))
        if not ready:
            # No dependency-free record is available, but no record is blocked
            # by a known failure. The remaining records therefore form a cycle
            # (including valid self/cyclic relationships). Import them together
            # so all objects exist before relationships are applied.
            batch = sorted(remaining)
            try:
                with transaction.atomic():
                    local = []
                    local_cache = dict(object_cache)
                    for index in batch:
                        operation = _prepare_record(
                            index, records[index], models, request,
                            conflict=conflict,
                            object_cache=local_cache,
                            allow_duplicate=_allow_duplicate(models[records[index]["model"]]) and not translations_only,
                        )
                        if translations_only and operation["status"] == "created":
                            raise PackageError(_("Translation-only packages require existing matching objects."))
                        local_cache[_record_key(records[index])] = operation["object"]
                        local.append((index, operation))
                    local_counts = []
                    for index, operation in local:
                        count = _apply_record_relations(
                            records[index], operation, local_cache, request
                        )
                        local_counts.append((index, operation, count))
                object_cache.update(local_cache)
                for index, operation, count in local_counts:
                    _apply_operation_counts(result, operation, count)
                    completed.add(index)
                    remaining.remove(index)
            except Exception as exc:
                for index in batch:
                    _append_import_error(result, index, records[index].get("model"), exc)
                    failed.add(index)
                    remaining.remove(index)
            continue

        for index in ready:
            try:
                with transaction.atomic():
                    local_cache = dict(object_cache)
                    operation = _prepare_record(
                        index, records[index], models, request,
                        conflict=conflict,
                        object_cache=local_cache,
                        allow_duplicate=_allow_duplicate(models[records[index]["model"]]) and not translations_only,
                    )
                    if translations_only and operation["status"] == "created":
                        raise PackageError(_("Translation-only packages require existing matching objects."))
                    local_cache[_record_key(records[index])] = operation["object"]
                    translation_count = _apply_record_relations(
                        records[index], operation, local_cache, request
                    )
                object_cache.update(local_cache)
                _apply_operation_counts(result, operation, translation_count)
                completed.add(index)
            except PermissionDenied as exc:
                _append_import_error(result, index, records[index].get("model"), exc)
                failed.add(index)
            except Exception as exc:
                _append_import_error(result, index, records[index].get("model"), exc)
                failed.add(index)
            finally:
                remaining.remove(index)

    return result.as_dict()


def build_retry_package_from_payload(
    payload: dict,
    result: dict,
    *,
    source_package_id: str | None = None,
    password: str | None = None,
    encrypted: bool = False,
) -> bytes | None:
    """Build a retry package containing only failed source records.

    Encryption is preserved when the source package was encrypted; retry
    artifacts must never silently downgrade protected data to plaintext.
    """
    errors = result.get("errors") or []
    indexes = {int(item.get("index")) for item in errors if str(item.get("index", "")).isdigit()}
    if not indexes:
        return None
    records = [record for index, record in enumerate(payload.get("records") or []) if index in indexes]
    if not records:
        return None
    retry_payload = dict(payload)
    retry_payload["records"] = records
    retry_payload["record_count"] = len(records)
    retry_payload["relationship_count"] = sum(len(record.get("relationships", {})) + sum(len(values) for values in record.get("many_to_many", {}).values()) for record in records)
    failed_model_counts = {}
    for record in records:
        failed_model_counts[record["model"]] = failed_model_counts.get(record["model"], 0) + 1
    retry_payload["models"] = [
        dict(metadata, record_count=failed_model_counts[metadata.get("label")])
        for metadata in (payload.get("models") or [])
        if metadata.get("label") in failed_model_counts
    ]
    retry_payload["translation_count"] = sum(len(record.get("translations", {})) for record in records)
    if source_package_id:
        retry_payload["retry_of"] = source_package_id
    if encrypted:
        if not password:
            raise PackageError(_("An encryption password is required to build an encrypted retry package."))
        encoded = json.dumps(
            retry_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        package_bytes = build_package(retry_payload, encrypted_payload=encrypt(encoded, password))
    else:
        package_bytes = build_package(retry_payload)
    if len(package_bytes) > _max_package_bytes():
        raise PackageError(
            _("The generated retry package exceeds the configured maximum size of %(limit)s MB.")
            % {"limit": max(1, _max_package_bytes() // (1024 * 1024))}
        )
    return package_bytes


def build_retry_package(raw: bytes, result: dict, *, password: str | None = None) -> bytes | None:
    """Build a retry package from a source package, preserving encryption."""
    manifest, payload, _models = inspect_package(raw, password=password)
    return build_retry_package_from_payload(
        payload,
        result,
        source_package_id=manifest.get("package_id"),
        password=password,
        encrypted=bool(manifest.get("encrypted")),
    )
