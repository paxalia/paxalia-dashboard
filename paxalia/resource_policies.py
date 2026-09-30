"""Unified, bounded resource and retention policy helpers."""
from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from .settings import get_config


DEFAULT_SEVERITY_RETENTION_DAYS = {
    "DEBUG": 7,
    "INFO": 30,
    "WARNING": 60,
    "ERROR": 180,
    "CRITICAL": 365,
}


def _as_nonnegative_int(value, default):
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0, value)


def log_limits():
    cfg = get_config()
    try:
        max_storage_mb = int(cfg.get("LOG_MAX_STORAGE_MB", 2048))
    except (TypeError, ValueError):
        max_storage_mb = 2048
    return {
        "max_records": _as_nonnegative_int(cfg.get("LOG_MAX_RECORDS", 500_000), 500_000),
        "max_storage_bytes": max(0, max_storage_mb) * 1024 * 1024,
        "batch_size": _as_nonnegative_int(cfg.get("LOG_CLEANUP_BATCH_SIZE", 500), 500) or 500,
        "warning_thresholds": tuple(sorted({
            max(1, min(100, _as_nonnegative_int(item, 90)))
            for item in (cfg.get("LOG_STORAGE_WARNING_THRESHOLDS") or (80, 90, 95))
        })),
    }


def log_storage_status() -> dict:
    """Return current canonical log-store size and configured capacity."""
    from .models import PaxaliaLogEvent

    limits = log_limits()
    size = storage_size_bytes(PaxaliaLogEvent)
    maximum = limits["max_storage_bytes"]
    percent = None
    if size is not None and maximum > 0:
        percent = round((size / maximum) * 100, 1)
    return {"bytes": size, "max_bytes": maximum, "percent": percent, "warning": bool(percent is not None and any(percent >= t for t in limits["warning_thresholds"]))}


def realtime_limits():
    cfg = get_config()
    return {
        "display_events": _as_nonnegative_int(cfg.get("LOG_BROWSER_MAX_REALTIME_EVENTS", 2000), 2000) or 2000,
        "buffer_events": _as_nonnegative_int(cfg.get("LOG_BROWSER_MAX_REALTIME_BUFFER", 5000), 5000) or 5000,
        "events_per_page": _as_nonnegative_int(cfg.get("LOG_BROWSER_MAX_EVENTS_PER_PAGE", 50), 50) or 50,
        "payload_bytes": _as_nonnegative_int(cfg.get("LOG_BROWSER_MAX_PAYLOAD_BYTES", 32768), 32768) or 32768,
        "batch_size": _as_nonnegative_int(cfg.get("LOG_REALTIME_BATCH_SIZE", 200), 200) or 200,
        "auto_pause_threshold": _as_nonnegative_int(cfg.get("LOG_REALTIME_AUTO_PAUSE_THRESHOLD", 1000), 1000),
    }


def severity_retention_days(severity: str) -> int:
    cfg = get_config()
    explicit = cfg.get("LOG_SEVERITY_RETENTION_DAYS") or {}
    severity = str(severity or "INFO").upper()
    default = DEFAULT_SEVERITY_RETENTION_DAYS.get(severity, 30)
    return _as_nonnegative_int(explicit.get(severity, default), default)


def category_retention_days(category: str, default: int | None = None) -> int:
    """Resolve category retention while preserving the legacy flat map."""
    cfg = get_config()
    policies = cfg.get("LOG_RETENTION_DAYS") or {}
    category = str(category or "system").lower()
    default = 30 if default is None else default
    value = policies.get(category, policies.get("system", default))
    if isinstance(value, dict):
        value = value.get("days", default)
    return _as_nonnegative_int(value, default)


def storage_size_bytes(model=None) -> int | None:
    """Return a best-effort table size for common SQL backends."""
    if model is None:
        return None
    table = model._meta.db_table
    vendor = connection.vendor
    try:
        with connection.cursor() as cursor:
            if vendor == "postgresql":
                cursor.execute("SELECT pg_total_relation_size(%s)", [table])
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] is not None else None
            if vendor == "sqlite":
                cursor.execute(
                    "SELECT COALESCE(SUM(pgsize), 0) FROM dbstat WHERE name = ?",
                    [table],
                )
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] is not None else None
            if vendor in {"mysql", "mariadb"}:
                cursor.execute(
                    "SELECT COALESCE(data_length, 0) + COALESCE(index_length, 0) "
                    "FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
                    [table],
                )
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None
    return None


def protected_log_queryset(qs):
    return qs.exclude(
        Q(severity="CRITICAL")
        | Q(source="Authentication")
        | Q(category__startswith="security")
    )


def _cleanup_ordering():
    return [
        Case(
            When(severity="DEBUG", then=Value(0)),
            When(severity="INFO", then=Value(1)),
            When(severity="WARNING", then=Value(2)),
            When(severity="ERROR", then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ),
        "timestamp",
        "id",
    ]


def prune_log_events(*, dry_run=False, batch_size=None):
    """Apply retention, count, and storage policies incrementally."""
    from .models import PaxaliaLogEvent, PaxaliaLogGroup

    limits = log_limits()
    batch_size = max(1, _as_nonnegative_int(batch_size, limits["batch_size"]))
    summary = {"retention": 0, "max_records": 0, "storage": 0, "groups": 0}
    now = timezone.now()

    remaining = batch_size
    for severity in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        if remaining <= 0:
            break
        cutoff = now - timedelta(days=severity_retention_days(severity))
        qs = PaxaliaLogEvent.objects.filter(severity=severity)
        category_policies = get_config().get("LOG_RETENTION_DAYS") or {}
        if category_policies:
            category_names = []
            for raw_category in category_policies:
                category = str(raw_category or "").strip().lower()
                if category:
                    category_names.append(category)
            category_names = sorted(set(category_names))
            category_q = Q()
            for category in category_names:
                days = category_retention_days(category, severity_retention_days(severity))
                category_q |= Q(category=category, timestamp__lt=now - timedelta(days=days))
            if category_names:
                qs = qs.filter(Q(timestamp__lt=cutoff) & ~Q(category__in=category_names) | category_q)
            else:
                qs = qs.filter(timestamp__lt=cutoff)
        else:
            qs = qs.filter(timestamp__lt=cutoff)
        if severity == "CRITICAL":
            qs = qs.none()
        else:
            qs = qs.exclude(Q(source="Authentication") | Q(category__startswith="security"))
        ids = list(qs.order_by(*_cleanup_ordering()).values_list("id", flat=True)[:remaining])
        if dry_run:
            amount = len(ids)
        elif ids:
            amount = len(ids)
            PaxaliaLogEvent.objects.filter(id__in=ids).delete()
        else:
            amount = 0
        summary["retention"] += amount
        remaining = max(0, remaining - amount)

    excess = max(0, PaxaliaLogEvent.objects.count() - limits["max_records"])
    excess = min(excess, remaining)
    if excess:
        ids = list(protected_log_queryset(PaxaliaLogEvent.objects.all()).order_by(*_cleanup_ordering()).values_list("id", flat=True)[:excess])
        if dry_run:
            summary["max_records"] = len(ids)
            amount = len(ids)
        elif ids:
            amount = len(ids)
            PaxaliaLogEvent.objects.filter(id__in=ids).delete()
            summary["max_records"] = amount
        else:
            amount = 0
        remaining = max(0, remaining - amount)

    size = storage_size_bytes(PaxaliaLogEvent)
    if size is not None and limits["max_storage_bytes"] and size > limits["max_storage_bytes"]:
        ids = list(protected_log_queryset(PaxaliaLogEvent.objects.all()).order_by(*_cleanup_ordering()).values_list("id", flat=True)[:max(0, remaining)])
        if dry_run:
            summary["storage"] = len(ids)
        elif ids:
            summary["storage"] = len(ids)
            PaxaliaLogEvent.objects.filter(id__in=ids).delete()
        remaining = max(0, remaining - summary["storage"])

    dangling = PaxaliaLogGroup.objects.filter(events__isnull=True).order_by("last_seen")
    group_budget = max(0, remaining)
    ids = list(dangling.values_list("id", flat=True)[:group_budget])
    if dry_run:
        summary["groups"] = len(ids)
    elif ids:
        summary["groups"] = len(ids)
        PaxaliaLogGroup.objects.filter(id__in=ids).delete()
    return summary


def notify_log_storage_warning(storage_status=None):
    """Notify once per warning level when Paxalia log storage crosses a threshold."""
    from .alerts import send_alert

    config = get_config()
    if not config.get('LOG_STORAGE_WARNING_NOTIFICATIONS', True):
        return False
    status = storage_status or log_storage_status()
    percent = status.get('percent')
    if percent is None:
        return False
    try:
        thresholds = sorted({int(v) for v in (config.get('LOG_STORAGE_WARNING_THRESHOLDS') or ()) if 0 < int(v) <= 100})
    except (TypeError, ValueError, OverflowError):
        thresholds = [80, 90, 95]
    crossed = [value for value in thresholds if percent >= value]
    if not crossed:
        return False
    level = max(crossed)
    return send_alert(
        f'Paxalia log storage at {level}%',
        f'Paxalia log storage is using approximately {percent:.1f}% of its configured limit. '
        f'Current bytes: {status.get("bytes")}; configured maximum: {status.get("max_bytes")}.',
        category='general',
        dedupe_key=f'log-storage:{level}',
        cooldown_seconds=config.get('LOG_STORAGE_WARNING_COOLDOWN_SECONDS', 21600),
    )
