from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count, Max, Min
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from paxalia.models import PageView
from ..admin_security import admin_security_required
from ..bot_management import can_manage_bot_paths
from ..settings import get_config
from .utils import detect_active_preset, get_current_site, get_date_range, section_enabled, site_scoped


def _config_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(get_config().get(name, default))
    except (TypeError, ValueError, OverflowError):
        value = default
    return max(minimum, min(value, maximum))


def _client_rows(queryset, *, limit: int, path_limit: int):
    rows = list(
        queryset.exclude(ip_hash="")
        .values("ip_hash")
        .annotate(
            hits=Count("id"),
            unique_paths=Count("path", distinct=True),
            first_seen=Min("created_at"),
            last_seen=Max("created_at"),
        )
        .order_by("-hits", "ip_hash")[:limit]
    )
    for row in rows:
        paths = list(
            queryset.filter(ip_hash=row["ip_hash"])
            .values("path")
            .annotate(count=Count("id"), last_seen=Max("created_at"))
            .order_by("-count", "path")[:path_limit]
        )
        row["paths"] = paths
    return rows


@admin_security_required
def broken_links(request):
    if not section_enabled("broken_links"):
        raise Http404

    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)
    all_404s = site_scoped(
        PageView.objects.filter(
            created_at__range=(start_dt, end_dt),
            status_code=404,
            is_api=False,
        ),
        current_site,
    )
    human_404s = all_404s.filter(is_bot=False)
    bot_404s = all_404s.filter(is_bot=True)

    max_paths = _config_int("BROKEN_LINKS_MAX_PATHS", 50, 1, 100)
    max_ips = _config_int("BROKEN_LINKS_MAX_IPS", 25, 1, 100)
    path_limit = min(6, max_paths)

    path_query = request.GET.get("path", "").strip()[:255]
    broken_path_queryset = human_404s
    if path_query:
        broken_path_queryset = broken_path_queryset.filter(path__icontains=path_query)
    broken_path_queryset = (
        broken_path_queryset.values("path")
        .annotate(
            count=Count("id"),
            unique_ips=Count("ip_hash", distinct=True),
            unique_referrers=Count("referrer", distinct=True),
            first_seen=Min("created_at"),
            last_seen=Max("created_at"),
        )
        .order_by("-count", "path")
    )
    broken_paths_paginator = Paginator(broken_path_queryset, max_paths)
    broken_paths_page = broken_paths_paginator.get_page(request.GET.get("page"))
    top_broken_paths = list(broken_paths_page.object_list)

    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)
    scanner_paths = list(
        bot_404s.values("path", "bot_category")
        .annotate(
            count=Count("id"),
            unique_ips=Count("ip_hash", distinct=True),
            first_seen=Min("created_at"),
            last_seen=Max("created_at"),
        )
        .order_by("-count", "path", "bot_category")[:max_paths]
    )
    top_referrers = list(
        human_404s.exclude(referrer="")
        .values("referrer")
        .annotate(count=Count("id"), unique_paths=Count("path", distinct=True), last_seen=Max("created_at"))
        .order_by("-count", "referrer")[:20]
    )
    category_labels = dict(PageView._meta.get_field("bot_category").choices)
    category_breakdown = list(
        bot_404s.values("bot_category")
        .annotate(count=Count("id"))
        .order_by("-count", "bot_category")
    )
    for row in category_breakdown:
        row["label"] = category_labels.get(row["bot_category"], row["bot_category"] or "Unclassified")

    human_clients = _client_rows(human_404s, limit=max_ips, path_limit=path_limit)
    bot_clients = _client_rows(bot_404s, limit=max_ips, path_limit=path_limit)

    context = {
        "active_page": "broken_links",
        "page_title": _("Broken Links"),
        "page_subtitle": _("Separate real missing pages from crawler and scanner probes, then clean known scanner paths in one bounded action"),
        "total_404s": all_404s.count(),
        "human_404s": human_404s.count(),
        "bot_404s": bot_404s.count(),
        "unique_human_404_ips": human_404s.exclude(ip_hash="").values("ip_hash").distinct().count(),
        "unique_bot_404_ips": bot_404s.exclude(ip_hash="").values("ip_hash").distinct().count(),
        "unique_missing_paths": human_404s.values("path").distinct().count(),
        "top_broken_paths": top_broken_paths,
        "broken_paths_page": broken_paths_page,
        "pagination_query": pagination_query,
        "path_query": path_query,
        "scanner_paths": scanner_paths,
        "top_referrers": top_referrers,
        "category_breakdown": category_breakdown,
        "human_clients": human_clients,
        "bot_clients": bot_clients,
        "can_manage_bot_paths": can_manage_bot_paths(request.user),
        "start_date": start_dt.date(),
        "end_date": end_dt.date(),
        "active_preset": detect_active_preset(start_dt.date(), end_dt.date()),
        "date_range_label": f"{start_dt.date()} – {end_dt.date()}",
        "show_search": False,
    }
    return render(request, "paxalia/broken_links.html", context)
