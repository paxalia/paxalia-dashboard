from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Min
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from honeypot.decorators import honeypot_exempt

from ..admin_security import admin_security_required
from ..bot_classification import classify_bot_identity
from ..bot_management import add_bot_path_prefix, can_manage_bot_paths
from ..models import AnalyticsSettings, DailySiteStats, PageView
from ..security_rate_limit import allowed as rate_allowed
from ..security_audit import log_action
from ..settings import get_config
from .utils import detect_active_preset, get_current_site, get_date_range, site_scoped


def _config_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(get_config().get(name, default))
    except (TypeError, ValueError, OverflowError):
        value = default
    return max(minimum, min(value, maximum))


def _category_labels():
    return dict(PageView._meta.get_field("bot_category").choices)


@admin_security_required
def bots_overview(request):
    start_dt, end_dt = get_date_range(request)
    current_site = get_current_site(request)
    labels = _category_labels()
    category = request.GET.get("category", "").strip()
    ip_query = request.GET.get("ip", "").strip()

    base = site_scoped(
        PageView.objects.filter(
            is_bot=True,
            is_api=False,
            created_at__range=(start_dt, end_dt),
        ),
        current_site,
    )
    if category in labels:
        base = base.filter(bot_category=category)
    if ip_query:
        base = base.filter(ip_hash=ip_query)

    total_bot_views = base.count()
    unique_bot_ips = base.exclude(ip_hash="").values("ip_hash").distinct().count()

    today = timezone.localdate()
    bot_views_today = site_scoped(
        PageView.objects.filter(is_bot=True, is_api=False, created_at__date=today),
        current_site,
    ).count()

    stats = DailySiteStats.objects.filter(date__range=(start_dt.date(), end_dt.date())).order_by("date")
    if current_site is not None:
        stats = stats.filter(site=current_site)
    stats = list(stats)
    dates = [row.date.isoformat() for row in stats]
    bot_counts = [row.bot_views for row in stats]

    category_rows = (
        base.exclude(bot_category="")
        .values("bot_category")
        .annotate(count=Count("id"))
        .order_by("-count", "bot_category")
    )
    category_breakdown = [
        {
            "category": row["bot_category"],
            "label": labels.get(row["bot_category"], row["bot_category"]),
            "count": row["count"],
        }
        for row in category_rows
    ]

    max_paths = _config_int("BOT_TRAFFIC_MAX_PATHS_PER_IP", 8, 1, 25)
    max_ips = _config_int("BOT_TRAFFIC_MAX_IPS", 30, 1, 100)
    max_scanners = _config_int("BOT_TRAFFIC_MAX_SCANNER_ROWS", 40, 1, 200)
    max_crawlers = _config_int("BOT_TRAFFIC_MAX_CRAWLER_ROWS", 20, 1, 100)

    path_rows = list(
        base.values("path")
        .annotate(count=Count("id"), unique_ips=Count("ip_hash", distinct=True), last_seen=Max("created_at"))
        .order_by("-count", "path")[:40]
    )
    country_rows = list(
        base.values("country_code")
        .annotate(count=Count("id"))
        .order_by("-count", "country_code")[:15]
    )

    top_ip_rows = list(
        base.exclude(ip_hash="")
        .values("ip_hash")
        .annotate(
            requests=Count("id"),
            unique_paths=Count("path", distinct=True),
            first_seen=Min("created_at"),
            last_seen=Max("created_at"),
        )
        .order_by("-requests", "ip_hash")[:max_ips]
    )

    ip_rows = []
    for summary in top_ip_rows:
        ip = summary["ip_hash"]
        distribution = {
            row["bot_category"]: row["count"]
            for row in base.filter(ip_hash=ip)
            .values("bot_category")
            .annotate(count=Count("id"))
            .order_by("-count", "bot_category")
        }
        dominant = max(distribution, key=distribution.get) if distribution else "unknown"
        ua_row = (
            base.filter(ip_hash=ip)
            .exclude(user_agent="")
            .values("user_agent")
            .annotate(count=Count("id"))
            .order_by("-count", "user_agent")
            .first()
        )
        identity = classify_bot_identity(dominant == "malicious", (ua_row or {}).get("user_agent", ""))
        paths = list(
            base.filter(ip_hash=ip)
            .values("path", "bot_category")
            .annotate(count=Count("id"), last_seen=Max("created_at"))
            .order_by("-count", "path")[:max_paths]
        )
        ip_rows.append({
            **summary,
            "dominant_category": dominant,
            "dominant_category_label": labels.get(dominant, dominant.replace("_", " ").title()),
            "identity_name": identity["name"],
            "identity_provider": identity["provider"],
            "identity_confidence": identity["confidence"],
            "user_agent": (ua_row or {}).get("user_agent", ""),
            "paths": [
                {
                    "path": item["path"],
                    "count": item["count"],
                    "last_seen": item["last_seen"],
                    "category": item["bot_category"] or "unknown",
                    "category_label": labels.get(item["bot_category"], item["bot_category"] or "Unclassified"),
                }
                for item in paths
            ],
        })

    scanner_rows = list(
        base.filter(bot_category="malicious")
        .values("ip_hash", "path")
        .annotate(count=Count("id"), unique_agents=Count("user_agent", distinct=True), last_seen=Max("created_at"))
        .order_by("-count", "ip_hash", "path")[:max_scanners]
    )
    crawler_rows = []
    for row in list(
        base.exclude(bot_category="malicious")
        .exclude(bot_category="")
        .values("bot_category", "user_agent")
        .annotate(count=Count("id"), unique_ips=Count("ip_hash", distinct=True), last_seen=Max("created_at"))
        .order_by("-count", "user_agent")[:max_crawlers]
    ):
        identity = classify_bot_identity(False, row["user_agent"] or "")
        crawler_rows.append({**row, **identity})

    settings_row = AnalyticsSettings.objects.first()
    configured_bot_paths = [
        line.strip()
        for line in (settings_row.bot_paths if settings_row else "").splitlines()
        if line.strip()
    ]

    context = {
        "active_page": "bots",
        "page_title": _("Bot Traffic"),
        "page_subtitle": _("Investigate crawlers and scanners by client, category, and requested path"),
        "total_bot_views": total_bot_views,
        "bot_views_today": bot_views_today,
        "unique_bot_ips": unique_bot_ips,
        "category_breakdown": category_breakdown,
        "pageview_bot_categories": PageView._meta.get_field("bot_category").choices,
        "path_rows": path_rows,
        "ip_rows": ip_rows,
        "scanner_rows": scanner_rows,
        "crawler_rows": crawler_rows,
        "bot_path_prefixes": configured_bot_paths,
        "can_manage_bot_paths": can_manage_bot_paths(request.user),
        "bot_data": {
            "dates": dates,
            "bot_counts": bot_counts,
            "top_paths": [x["path"] for x in path_rows],
            "top_counts": [x["count"] for x in path_rows],
            "country_codes": [x["country_code"] or "Unknown" for x in country_rows],
            "country_counts": [x["count"] for x in country_rows],
            "category_labels": [x["label"] for x in category_breakdown],
            "category_counts": [x["count"] for x in category_breakdown],
        },
        "start_date": start_dt.date(),
        "end_date": end_dt.date(),
        "active_preset": detect_active_preset(start_dt.date(), end_dt.date()),
        "active_category": category,
        "active_ip": ip_query,
    }
    return render(request, "paxalia/bots.html", context)


@admin_security_required
@honeypot_exempt
@require_POST
def bot_path_mark(request):
    if not can_manage_bot_paths(request.user):
        raise PermissionDenied(_("You do not have permission to manage Bot/Scanner path rules."))

    try:
        from ..middleware import AnalyticsMiddleware
        client_ip = AnalyticsMiddleware._get_ip(request) or "unknown"
    except Exception:
        client_ip = request.META.get("REMOTE_ADDR") or "unknown"
    ok, _remaining = rate_allowed(
        "bot-path-mutation",
        _config_int("BOT_PATH_MAX_MUTATIONS_PER_MINUTE", 30, 1, 120),
        60,
        client_ip,
        request.user.pk,
    )
    if not ok:
        messages.error(request, _("Bot path management is temporarily rate limited. Try again shortly."))
        return redirect(reverse("paxalia:bots"))

    prefix = request.POST.get("path", "")
    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)
    try:
        result = add_bot_path_prefix(
            prefix=prefix,
            site=current_site,
            start_dt=start_dt,
            end_dt=end_dt,
            remove_normal_views=request.POST.get("remove_normal_views", "1") == "1",
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            _("Bot path rule %(prefix)s saved. %(removed)s normal page-view record(s) were moved out of normal traffic in this bounded pass.") % result,
        )
        log_action(
            request,
            "bot_path.added",
            detail=(
                f"prefix={result['prefix']} "
                f"reclassified={result['reclassified']} "
                f"already_present={result['already_present']}"
            ),
        )
        if result["more_normal_views_remain"]:
            messages.warning(
                request,
                _("The cleanup limit was reached; more matching normal views remain. Repeat the action or use a narrower date/site scope."),
            )

    target = request.POST.get("return_to", "")
    if url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ) and target.startswith("/"):
        return redirect(target)
    return redirect(reverse("paxalia:bots"))
