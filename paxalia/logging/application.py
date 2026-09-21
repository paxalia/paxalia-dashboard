"""Safe read-only adapters for host-application log models."""
from dataclasses import dataclass

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from ..settings import get_config
from .redaction import redact


@dataclass(frozen=True)
class ApplicationLogSource:
    name: str
    model: object
    fields: dict
    classification: dict

    @property
    def label(self):
        return self.name


def _field_exists(model, field_name):
    if not field_name or not isinstance(field_name, str):
        return False
    # Only direct model fields are supported by the generic adapter. This keeps
    # configuration declarative and avoids executing arbitrary methods/properties.
    if "__" in field_name or "." in field_name:
        return False
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def resolve_application_sources(user=None):
    sources = []
    config = get_config()
    for entry in config.get("APPLICATION_LOGS", []) or []:
        try:
            model_label = str(entry.get("model", ""))
            if "." not in model_label:
                continue
            app_label, model_name = model_label.split(".", 1)
            model = apps.get_model(app_label, model_name)
            if model is None:
                continue
            fields = dict(entry.get("fields") or {})
            valid_fields = {key: value for key, value in fields.items() if value is None or _field_exists(model, value)}
            if not valid_fields:
                continue
            if user is not None:
                try:
                    ct = ContentType.objects.get_for_model(model)
                    if not user.is_superuser and not user.has_perm(f"{ct.app_label}.view_{ct.model}"):
                        continue
                except Exception:
                    continue
            sources.append(ApplicationLogSource(
                name=str(entry.get("name") or model._meta.verbose_name_plural).strip()[:100],
                model=model,
                fields=valid_fields,
                classification={str(k): str(v).upper() for k, v in (entry.get("classification") or {}).items()},
            ))
        except Exception:
            continue
    return sources


def source_by_name(user, name):
    for source in resolve_application_sources(user):
        if source.name == name:
            return source
    return None


def _mapped(source, concept):
    value = source.fields.get(concept)
    return value if value else None


def queryset_for(source):
    qs = source.model.objects.all()
    timestamp = _mapped(source, "timestamp")
    if timestamp:
        try:
            return qs.order_by(f"-{timestamp}")
        except Exception:
            pass
    return qs.order_by("-pk")


def serialize_row(source, obj):
    out = {"source": source.name}
    for concept, field_name in source.fields.items():
        if not field_name:
            continue
        try:
            value = getattr(obj, field_name)
            if callable(value):
                continue
            if concept == "user":
                try:
                    value = value.get_username() if value else ""
                except Exception:
                    value = str(value) if value else ""
            if concept == "metadata" and value is not None:
                value = redact(value, extra_keys=get_config().get("LOG_SENSITIVE_KEYS") or [])
            elif hasattr(value, "isoformat"):
                value = value.isoformat()
            elif value is not None:
                value = str(value)
            out[concept] = value
        except Exception:
            out[concept] = None
    action = str(out.get("action") or "")
    severity = str(out.get("severity") or source.classification.get(action, "INFO")).upper()
    if severity not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        severity = str(source.classification.get(action, "INFO")).upper()
    if severity not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        severity = "INFO"
    out["severity"] = severity
    return out


def source_summary(source):
    qs = source.model.objects.all()
    total = qs.count()
    action_field = _mapped(source, "action")
    timestamp = _mapped(source, "timestamp")
    error_count = 0
    warning_count = 0
    top_actions = []
    if action_field:
        try:
            rows = qs.values(action_field).annotate(count=Count("pk")).order_by("-count")[:20]
            for row in rows:
                action = str(row.get(action_field) or "")
                sev = source.classification.get(action, "INFO")
                top_actions.append({"action": action, "count": row["count"], "severity": sev})
                if sev == "ERROR" or sev == "CRITICAL":
                    error_count += row["count"]
                elif sev == "WARNING":
                    warning_count += row["count"]
        except Exception:
            pass
    return {
        "total": total, "errors": error_count, "warnings": warning_count,
        "top_actions": top_actions, "timestamp_field": timestamp,
    }
