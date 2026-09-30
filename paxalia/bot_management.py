"""Safe, bounded management helpers for analytics Bot/Scanner path prefixes."""
from __future__ import annotations

from collections import Counter

from django.db import transaction
from django.db.models import F

from .models import AnalyticsSettings, DailySiteStats, PageView
from .settings import get_config

MAX_BOT_PATH_PREFIX_LENGTH = 255
MAX_RECLASSIFY_PER_ACTION = 10_000
# Backwards-compatible name for any host code that imported the old bound.
MAX_DELETE_PER_ACTION = MAX_RECLASSIFY_PER_ACTION


def _bounded_config_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(get_config().get(name, default))
    except (TypeError, ValueError, OverflowError):
        value = default
    return max(0, min(value, maximum))


def normalize_bot_path_prefix(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError("A bot/scanner path prefix is required.")
    max_length = max(
        1,
        _bounded_config_int(
            "BOT_PATH_MAX_PREFIX_LENGTH",
            MAX_BOT_PATH_PREFIX_LENGTH,
            MAX_BOT_PATH_PREFIX_LENGTH,
        ),
    )
    if len(value) > max_length:
        raise ValueError("The bot/scanner path prefix is too long.")
    if not value.startswith("/") or value.startswith("//"):
        raise ValueError("Bot/scanner path prefixes must be absolute URL paths.")
    if value == "/":
        raise ValueError("The root path cannot be added as a Bot/Scanner prefix; choose a narrower path.")
    if "?" in value or "#" in value or "\x00" in value:
        raise ValueError("Bot/scanner path prefixes cannot contain query strings, fragments, or NUL bytes.")
    return value


def can_manage_bot_paths(user) -> bool:
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    return bool(getattr(user, "is_superuser", False) or user.has_perm("paxalia.manage_bot_paths"))


def _settings_instance_locked():
    instance = AnalyticsSettings.objects.select_for_update().first()
    if instance is not None:
        return instance
    return AnalyticsSettings.objects.create()


def _prefixes(settings_row):
    return [line.strip() for line in settings_row.bot_paths.splitlines() if line.strip()]


def _update_daily_bot_counts(page_views):
    """Move bounded historical rows into the daily bot aggregate without changing total views."""
    grouped = Counter((view.created_at.date(), view.site_id) for view in page_views)
    for (day, site_id), count in grouped.items():
        updated = DailySiteStats.objects.filter(date=day, site_id=site_id).update(
            bot_views=F("bot_views") + count
        )
        # A host may have imported PageView history without creating the daily
        # aggregate. Do not manufacture aggregate rows during a classification
        # action; the authoritative evidence remains the PageView rows.
        if not updated:
            continue


@transaction.atomic
def add_bot_path_prefix(
    *,
    prefix: str,
    site=None,
    start_dt=None,
    end_dt=None,
    remove_normal_views: bool = True,
    delete_limit: int = MAX_RECLASSIFY_PER_ACTION,
):
    """Add a path rule and move matching normal traffic into bot/scanner traffic.

    The one-click cleanup is deliberately non-destructive: matching normal
    ``PageView`` rows are reclassified as ``malicious`` instead of deleted.
    This preserves investigation history while removing them from every normal
    traffic query that already filters on ``is_bot=False``.
    """
    prefix = normalize_bot_path_prefix(prefix)
    configured_limit = _bounded_config_int(
        "BOT_PATH_MAX_DELETE_PER_ACTION",
        MAX_RECLASSIFY_PER_ACTION,
        MAX_RECLASSIFY_PER_ACTION,
    )
    reclassify_limit = max(0, min(int(delete_limit), configured_limit))

    row = _settings_instance_locked()
    prefixes = _prefixes(row)
    already_present = prefix in prefixes
    if not already_present:
        prefixes.append(prefix)
        row.bot_paths = "\n".join(prefixes)
        row.save(update_fields=["bot_paths"])

    reclassified = 0
    if remove_normal_views and reclassify_limit:
        qs = PageView.objects.filter(
            path__startswith=prefix,
            is_bot=False,
            is_api=False,
        ).order_by("created_at", "pk")
        if site is not None:
            qs = qs.filter(site=site)
        if start_dt is not None:
            qs = qs.filter(created_at__gte=start_dt)
        if end_dt is not None:
            qs = qs.filter(created_at__lt=end_dt)

        rows = list(qs[:reclassify_limit])
        ids = [row.pk for row in rows]
        if ids:
            PageView.objects.filter(pk__in=ids).update(
                is_bot=True,
                bot_category="malicious",
            )
            _update_daily_bot_counts(rows)
            reclassified = len(ids)

    remaining = False
    if remove_normal_views and reclassify_limit:
        remaining_qs = PageView.objects.filter(
            path__startswith=prefix,
            is_bot=False,
            is_api=False,
        )
        if site is not None:
            remaining_qs = remaining_qs.filter(site=site)
        if start_dt is not None:
            remaining_qs = remaining_qs.filter(created_at__gte=start_dt)
        if end_dt is not None:
            remaining_qs = remaining_qs.filter(created_at__lt=end_dt)
        remaining = remaining_qs.exists()

    return {
        "prefix": prefix,
        "already_present": already_present,
        "added": not already_present,
        # Kept for compatibility with the first v5 implementation: these rows
        # were removed from normal traffic, but not destroyed.
        "removed": reclassified,
        "reclassified": reclassified,
        "more_normal_views_remain": bool(remaining),
    }
