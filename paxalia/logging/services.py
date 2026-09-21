"""Persistence services for Paxalia observability.

All public functions are deliberately best-effort: observability must never
become the application's failure path.
"""
import os
import socket
import threading
import traceback
import uuid
from importlib import metadata

from django.apps import apps as django_apps
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..bot_classification import classify_bot
from ..middleware import AnalyticsMiddleware, _resolve_ip, _resolve_site_id, get_analytics_settings
from ..settings import get_config
from .context import get_context
from .fingerprint import build_fingerprint, normalize_message
from .redaction import bound_json, redact_text


SOURCE_BY_LOGGER = (
    ("django.request", "HTTP"),
    ("django.server", "HTTP"),
    ("django.db", "Database"),
    ("django.security", "Authentication"),
    ("django.contrib.auth", "Authentication"),
    ("celery", "Celery"),
    ("uvicorn", "Server"),
    ("gunicorn", "Server"),
    ("daphne", "Server"),
    ("paxalia.security", "Authentication"),
    ("django", "Django"),
    ("paxalia", "Application"),
)


def _release_value():
    cfg = get_config()
    configured = cfg.get("LOG_RELEASE")
    if configured:
        return str(configured)[:100]
    for key in ("PAXALIA_RELEASE", "RELEASE_VERSION", "GIT_SHA"):
        if os.environ.get(key):
            return os.environ[key][:100]
    try:
        return metadata.version("paxalia-dashboard")
    except Exception:
        return "development"


def classify_source(logger_name, override=None):
    if override:
        return str(override)[:50]
    name = logger_name or ""
    for prefix, source in SOURCE_BY_LOGGER:
        if name == prefix or name.startswith(prefix + "."):
            return source
    return "Python"


def _safe_id(value, fallback=""):
    """Normalize optional correlation identifiers for non-request events.

    PaxaliaLogEvent stores request_id/correlation_id/trace_id as non-null
    strings. Background, CLI, startup, and direct logging events legitimately
    have no request context, so they must persist an empty string rather than
    NULL. Oversized identifiers are also reduced to the same safe fallback.
    """
    value = str(value or "").strip()
    if len(value) > 100:
        return fallback
    return value or fallback


def _privacy_ip(ip):
    if not ip:
        return None, "none"
    try:
        from ..models import AnalyticsSettings
        cached = cache.get("paxalia:analytics:anonymize_ip", "__unset__")
        if cached == "__unset__":
            settings_obj = AnalyticsSettings.objects.first()
            cached = (
                bool(settings_obj.anonymize_ip)
                if settings_obj is not None
                else bool(get_config().get("DEFAULT_ANONYMIZE_IP", False))
            )
            cache.set("paxalia:analytics:anonymize_ip", cached, timeout=30)
        anonymize = bool(cached)
    except Exception:
        anonymize = bool(get_config().get("DEFAULT_ANONYMIZE_IP", False))
    if anonymize:
        import hashlib
        return hashlib.sha256(str(ip).encode()).hexdigest(), "sha256"
    return str(ip)[:255], "raw"


def build_request_context(request):
    """Best-effort request context builder; it never raises."""
    if request is None:
        return {}
    try:
        ip = AnalyticsMiddleware._get_ip(request)
    except Exception:
        ip = None
    ua_string = str(request.META.get("HTTP_USER_AGENT", ""))[:512]
    try:
        # Import lazily. `paxalia.views` has an eager `events` import, and
        # `views.events` imports this module for `emit_message`. Importing
        # `parse_user_agent` at module load time therefore creates a cycle
        # during Django app initialization.
        from ..views.utils import parse_user_agent
        ua = parse_user_agent(ua_string)
    except Exception:
        ua = {"browser": "Other", "os": "Unknown", "device": "Other"}
    try:
        site_id = _resolve_site_id(request)
    except Exception:
        site_id = None
    path = str(getattr(request, "path_info", getattr(request, "path", "")) or "")[:2048]
    api_prefix = str(get_config().get("API_PATH_PREFIX", "/api/") or "/api/")
    try:
        settings_obj = getattr(request, "_paxalia_logging_analytics_settings", None) or get_analytics_settings()
        bot_paths = [p.strip() for p in settings_obj.bot_paths.split("\n") if p.strip()]
        malicious_path = any(path.startswith(bp) for bp in bot_paths)
        bot_category = classify_bot(malicious_path, ua_string)
    except Exception:
        bot_category = None
    is_bot = bool(bot_category)
    if is_bot:
        traffic_type = "BOT"
    elif api_prefix and path.startswith(api_prefix):
        traffic_type = "API"
    else:
        traffic_type = "WEB"
    stored_ip, ip_mode = _privacy_ip(ip)
    request_id = _safe_id(request.META.get("HTTP_X_REQUEST_ID"), uuid.uuid4().hex)
    correlation_id = _safe_id(request.META.get("HTTP_X_CORRELATION_ID"), request_id)
    traceparent = str(request.META.get("HTTP_TRACEPARENT", ""))[:100]
    trace_id = ""
    if traceparent:
        pieces = traceparent.split("-")
        if len(pieces) >= 4 and len(pieces[1]) == 32:
            trace_id = pieces[1]
    return {
        "session_id": str(getattr(request, "analytics_session_id", "") or request.COOKIES.get("_analytics_sid", ""))[:64],
        "request_id": request_id,
        "correlation_id": correlation_id,
        "trace_id": trace_id,
        "request_method": str(getattr(request, "method", ""))[:20],
        "request_path": path,
        "user": getattr(request, "user", None),
        "user_display": "",
        "admin_flag": bool(getattr(getattr(request, "user", None), "is_staff", False) or getattr(getattr(request, "user", None), "is_superuser", False)),
        "site_id": site_id,
        "traffic_type": traffic_type,
        "is_api": traffic_type == "API",
        "is_bot": is_bot,
        "bot_category": bot_category or "",
        "ip_address": stored_ip,
        "ip_mode": ip_mode,
        "user_agent": ua_string,
        "browser": ua.get("browser", "Other")[:100],
        "operating_system": ua.get("os", "Unknown")[:100],
        "device": ua.get("device", "Other")[:50],
    }


def _base_payload(*, message, severity, source, category, action, logger_name,
                  exception_type="", stack_trace="", module="", file_name="",
                  line_number=None, function_name="", metadata=None,
                  request=None, request_id=None, correlation_id=None, trace_id=None,
                  response_status=None, duration_ms=None, traffic_type=None):
    cfg = get_config()
    now = timezone.now()
    ctx = get_context()
    if request is not None:
        ctx.update(build_request_context(request))
    user = ctx.get("user")
    if user is not None:
        try:
            user_display = str(user.get_username())[:255]
            user_type = user.__class__.__name__[:100]
        except Exception:
            user_display = str(user)[:255]
            user_type = "User"
    else:
        user_display = str(ctx.get("user_display") or "")[:255]
        user_type = str(ctx.get("user_type") or "")[:100]
    custom_keys = cfg.get("LOG_SENSITIVE_KEYS") or []
    clean_metadata = bound_json(metadata or {}, max_bytes=int(cfg.get("LOG_MAX_METADATA_BYTES", 16384)), extra_keys=custom_keys)
    message_clean = redact_text(str(message or ""))[: int(cfg.get("LOG_MAX_MESSAGE_LENGTH", 4000))]
    stack_clean = redact_text(str(stack_trace or ""))[: int(cfg.get("LOG_MAX_STACK_LENGTH", 12000))]
    sensitive_state = "safe"
    if message_clean != str(message or "") or stack_clean != str(stack_trace or "") or clean_metadata != (metadata or {}):
        sensitive_state = "redacted"
    payload = {
        "id": uuid.uuid4(),
        "timestamp": now,
        "received_at": now,
        "severity": str(severity or "INFO").upper()[:10],
        "source": str(source or "Other")[:50],
        "category": str(category or "")[:100],
        "action": str(action or "")[:100],
        "logger_name": str(logger_name or "")[:255],
        "message": message_clean,
        "exception_type": str(exception_type or "")[:255],
        "stack_trace": stack_clean,
        "module": str(module or "")[:255],
        "file_name": str(file_name or "")[:500],
        "line_number": line_number,
        "function_name": str(function_name or "")[:255],
        "session_id": str(ctx.get("session_id") or (request.COOKIES.get("_analytics_sid", "") if request is not None else ""))[:64],
        "request_id": _safe_id(request_id or ctx.get("request_id")),
        "correlation_id": _safe_id(correlation_id or ctx.get("correlation_id")),
        "trace_id": _safe_id(trace_id or ctx.get("trace_id")),
        "request_method": str(ctx.get("request_method") or "")[:20],
        "request_path": str(ctx.get("request_path") or "")[:2048],
        "response_status": response_status,
        "duration_ms": duration_ms,
        "site_id": ctx.get("site_id"),
        "traffic_type": str(traffic_type or ctx.get("traffic_type") or "INTERNAL")[:12],
        "is_api": str(traffic_type or ctx.get("traffic_type") or "INTERNAL") == "API",
        "is_bot": str(traffic_type or ctx.get("traffic_type") or "INTERNAL") == "BOT",
        "bot_category": str(ctx.get("bot_category") or "")[:30],
        "user_id": getattr(user, "pk", None),
        "user_display": user_display,
        "user_type": user_type,
        "admin_flag": bool(ctx.get("admin_flag")),
        "ip_address": ctx.get("ip_address"),
        "ip_mode": str(ctx.get("ip_mode") or "none")[:10],
        "user_agent": str(ctx.get("user_agent") or "")[:512],
        "browser": str(ctx.get("browser") or "")[:100],
        "operating_system": str(ctx.get("operating_system") or "")[:100],
        "device": str(ctx.get("device") or "")[:50],
        "process_id": os.getpid(),
        "thread_name": threading.current_thread().name[:255],
        "host": socket.gethostname()[:255],
        "environment": str(getattr(settings, "ENVIRONMENT", os.environ.get("ENVIRONMENT", "unknown")))[:100],
        "release": _release_value(),
        "metadata": clean_metadata,
        "sensitive_data_state": sensitive_state,
    }
    payload["fingerprint"] = build_fingerprint(
        source=payload["source"], severity=payload["severity"], category=payload["category"],
        exception_type=payload["exception_type"], message=payload["message"],
        module=payload["module"], function_name=payload["function_name"],
        file_name=payload["file_name"], traffic_type=payload["traffic_type"],
    )
    return payload




_PERSISTENCE_STATE = threading.local()


def _clear_persistence_error():
    _PERSISTENCE_STATE.error = None


def _set_persistence_error(*, stage, exc, attempt=None):
    detail = {
        "stage": stage,
        "type": exc.__class__.__name__,
        "message": str(exc) or repr(exc),
        "attempt": attempt,
        "traceback": traceback.format_exc(),
    }
    _PERSISTENCE_STATE.error = detail
    return detail


def get_last_persistence_error():
    """Return the most recent persistence failure recorded on this thread."""
    value = getattr(_PERSISTENCE_STATE, "error", None)
    return dict(value) if isinstance(value, dict) else None


def persist_event(payload, *, raise_on_error=False):
    """Store one event with grouping and bounded duplicate samples.

    Normal application logging is fail-safe and returns ``None`` when storage
    is unavailable. Diagnostic callers can pass ``raise_on_error=True`` to get
    the original exception with a stage-specific thread-local diagnostic saved
    for the caller to print.
    """
    from ..models import PaxaliaLogEvent, PaxaliaLogGroup

    _clear_persistence_error()

    cfg = get_config()
    if not cfg.get("LOGGING_ENABLED", True):
        detail = {
            "stage": "configuration",
            "type": "LoggingDisabled",
            "message": "PAXALIA_DASHBOARD['LOGGING_ENABLED'] is false",
            "attempt": None,
            "traceback": "",
        }
        _PERSISTENCE_STATE.error = detail
        if raise_on_error:
            raise RuntimeError(detail["message"])
        return None

    if not django_apps.ready:
        detail = {
            "stage": "app_registry",
            "type": "AppRegistryNotReady",
            "message": "Django app registry is not ready; ORM persistence was skipped",
            "attempt": None,
            "traceback": "",
        }
        _PERSISTENCE_STATE.error = detail
        if raise_on_error:
            raise RuntimeError(detail["message"])
        return None

    max_samples = max(0, int(cfg.get("LOG_MAX_SAMPLES_PER_GROUP", 5)))
    dedupe_seconds = max(1, int(cfg.get("LOG_DEDUPE_WINDOW_SECONDS", 60)))
    now = payload["timestamp"]

    for attempt in range(2):
        stage = "group_lookup"
        try:
            with transaction.atomic():
                group = (
                    PaxaliaLogGroup.objects.select_for_update()
                    .filter(fingerprint=payload["fingerprint"]).first()
                )
                if group is None:
                    stage = "group_insert"
                    group = PaxaliaLogGroup.objects.create(
                        fingerprint=payload["fingerprint"],
                        severity=payload["severity"],
                        source=payload["source"],
                        category=payload["category"],
                        exception_type=payload["exception_type"],
                        normalized_message=normalize_message(payload["message"]),
                        first_seen=now,
                        last_seen=now,
                        occurrence_count=1,
                        suppressed_count=0,
                        window_started_at=now,
                        sample_count=0,
                    )
                    if max_samples <= 0:
                        return group
                else:
                    stage = "group_update"
                    if group.window_started_at and (now - group.window_started_at).total_seconds() >= dedupe_seconds:
                        group.window_started_at = now
                        group.sample_count = 0
                    group.last_seen = now
                    group.occurrence_count += 1
                    group.severity = payload["severity"]
                    group.source = payload["source"]
                    group.category = payload["category"]
                    group.save(update_fields=[
                        "window_started_at", "sample_count", "last_seen",
                        "occurrence_count", "severity", "source", "category",
                    ])
                    if group.sample_count >= max_samples:
                        stage = "group_suppressed"
                        group.suppressed_count += 1
                        group.save(update_fields=["suppressed_count"])
                        return group

                stage = "event_insert"
                event_payload = dict(payload)
                event_payload["group_id"] = group.id
                event = PaxaliaLogEvent.objects.create(**event_payload)

                stage = "group_sample_update"
                group.sample_count += 1
                group.save(update_fields=["sample_count", "last_seen", "occurrence_count", "suppressed_count"])
                return event
        except IntegrityError as exc:
            detail = _set_persistence_error(stage=stage, exc=exc, attempt=attempt + 1)
            # A concurrent first insert can legitimately race on the unique
            # fingerprint. Retry once using a fresh transaction.
            if attempt == 0 and stage == "group_insert":
                continue
            if raise_on_error:
                raise
            return None
        except Exception as exc:  # noqa: BLE001 - logging must never be fatal
            _set_persistence_error(stage=stage, exc=exc, attempt=attempt + 1)
            if raise_on_error:
                raise
            return None

    return None


def emit_message(message, *, level="INFO", source="Application", category="",
                 action="", metadata=None, request=None, exception=None, **kwargs):
    """Public internal service used by Paxalia's helper/API integrations."""
    exc_type = ""
    stack = ""
    if exception is not None:
        exc_type = exception.__class__.__name__
        try:
            stack = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        except Exception:
            stack = str(exception)
    return persist_event(_base_payload(
        message=message, severity=level, source=source, category=category,
        action=action, logger_name=kwargs.get("logger_name", "paxalia"),
        exception_type=exc_type, stack_trace=stack, metadata=metadata, request=request,
        request_id=kwargs.get("request_id"), correlation_id=kwargs.get("correlation_id"),
        trace_id=kwargs.get("trace_id"), response_status=kwargs.get("response_status"),
        duration_ms=kwargs.get("duration_ms"), traffic_type=kwargs.get("traffic_type"), module=kwargs.get("module", ""),
        file_name=kwargs.get("file_name", ""), line_number=kwargs.get("line_number"),
        function_name=kwargs.get("function_name", ""),
    ))


def build_from_log_record(record):
    """Convert a stdlib LogRecord into a canonical payload."""
    extras = getattr(record, "paxalia", None)
    if not isinstance(extras, dict):
        extras = {}
    request = extras.get("request")
    metadata = extras.get("metadata") or {}
    try:
        message = record.getMessage()
    except Exception:
        message = str(getattr(record, "msg", ""))
    exception = None
    stack = ""
    exc_type = ""
    if record.exc_info:
        try:
            exception = record.exc_info[1]
            exc_type = exception.__class__.__name__ if exception else ""
            stack = "".join(traceback.format_exception(*record.exc_info))
        except Exception:
            pass
    level_name = getattr(record, "levelname", "INFO").upper()
    if level_name not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        level_name = "INFO" if record.levelno < 30 else "ERROR"
    source = classify_source(record.name, extras.get("source"))
    return _base_payload(
        message=message,
        severity=level_name,
        source=source,
        category=extras.get("category", ""),
        action=extras.get("action", ""),
        logger_name=record.name,
        exception_type=exc_type,
        stack_trace=stack,
        module=getattr(record, "module", ""),
        file_name=getattr(record, "pathname", ""),
        line_number=getattr(record, "lineno", None),
        function_name=getattr(record, "funcName", ""),
        metadata=metadata,
        request=request,
        request_id=extras.get("request_id"),
        correlation_id=extras.get("correlation_id"),
        trace_id=extras.get("trace_id"),
        response_status=extras.get("response_status"),
        duration_ms=extras.get("duration_ms"),
    )

