# analytics/views/dashboard.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate

from analytics.models import DailySiteStats, PageView

from .utils import get_date_range, detect_active_preset, section_enabled

from datetime import timedelta


# Create your views here.


@staff_member_required
def analytics_dashboard(request):
    if not section_enabled('overview'):
        raise Http404
    start_dt, end_dt = get_date_range(request)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Base queryset for the selected range
    base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False, is_api=False)

    # Today live counts (always today)
    today_views = PageView.objects.filter(created_at__date=today, is_bot=False, is_api=False).count()
    today_unique = PageView.objects.filter(created_at__date=today, is_bot=False, is_api=False).values('ip_hash').distinct().count()
    today_api = PageView.objects.filter(created_at__date=today, is_bot=False, is_api=True).count()

    # --- Yesterday (try aggregated stats first, fallback to live queries) ---
    try:
        yest_stats = DailySiteStats.objects.get(date=yesterday)
        yesterday_views = yest_stats.total_views
        yesterday_unique = yest_stats.unique_ips
        yesterday_sessions = yest_stats.total_sessions
        yesterday_bounces = yest_stats.bounces
        yesterday_bounce_rate = round((yesterday_bounces / yesterday_sessions) * 100, 1) if yesterday_sessions else 0
        yesterday_pages_per_session = round(yesterday_views / yesterday_sessions, 1) if yesterday_sessions else 0
    except DailySiteStats.DoesNotExist:
        yest_pageviews = PageView.objects.filter(created_at__date=yesterday, is_bot=False, is_api=False)
        yesterday_views = yest_pageviews.count()
        yesterday_unique = yest_pageviews.values('ip_hash').distinct().count()
        yesterday_sessions = yest_pageviews.exclude(session_id='').values('session_id').distinct().count()
        yesterday_bounce_sessions = (
            yest_pageviews.exclude(session_id='')
            .values('session_id')
            .annotate(cnt=Count('id'))
            .filter(cnt=1)
            .count()
        )
        yesterday_bounce_rate = round((yesterday_bounce_sessions / yesterday_sessions) * 100, 1) if yesterday_sessions else 0
        yesterday_pages_per_session = round(yesterday_views / yesterday_sessions, 1) if yesterday_sessions else 0

    # --- Today's session stats (live) ---
    today_pageviews = PageView.objects.filter(created_at__date=today, is_bot=False, is_api=False)
    today_sessions = today_pageviews.exclude(session_id='').values('session_id').distinct().count()
    today_bounce_sessions = (
        today_pageviews.exclude(session_id='')
        .values('session_id')
        .annotate(cnt=Count('id'))
        .filter(cnt=1)
        .count()
    )
    today_bounce_rate = round((today_bounce_sessions / today_sessions) * 100, 1) if today_sessions else 0
    today_pages_per_session = round(today_views / today_sessions, 1) if today_sessions else 0

    # Daily views for the selected range (line chart)
    daily = (
        base_qs
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels = [d['day'].strftime('%b %d') for d in daily]
    chart_views = [d['count'] for d in daily]

    # ========== Compare to previous period ==========
    compare_active = request.GET.get('compare') == '1'
    previous_labels = []
    previous_views = []

    if compare_active:
        period_delta = (end_dt - start_dt).days
        prev_end = start_dt - timedelta(seconds=1)  # end just before current range
        prev_start = prev_end - timedelta(days=period_delta)
        prev_qs = PageView.objects.filter(created_at__range=(prev_start, prev_end), is_bot=False, is_api=False)
        prev_daily = (
            prev_qs
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        previous_labels = [d['day'].strftime('%b %d') for d in prev_daily]
        previous_views = [d['count'] for d in prev_daily]

    # Top pages within the range (bar chart and table)
    top_pages_qs = (
        base_qs
        .values('path')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    top_pages = {item['path']: item['count'] for item in top_pages_qs}
    top_page_path = next(iter(top_pages), None)
    top_pages_labels = list(top_pages.keys())
    top_pages_data = list(top_pages.values())

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'today_views': today_views,
        'today_unique': today_unique,
        'today_api': today_api,
        'yesterday_views': yesterday_views,
        'yesterday_unique': yesterday_unique,
        'today_sessions': today_sessions,
        'today_bounce_rate': today_bounce_rate,
        'today_pages_per_session': today_pages_per_session,
        'yesterday_sessions': yesterday_sessions,
        'yesterday_bounce_rate': yesterday_bounce_rate,
        'yesterday_pages_per_session': yesterday_pages_per_session,
        'chart_labels': chart_labels,
        'chart_views': chart_views,
        'compare_active': compare_active,
        'previous_labels': previous_labels,
        'previous_views': previous_views,
        'top_pages': top_pages,
        'top_page_path': top_page_path,
        'top_pages_labels': top_pages_labels,
        'top_pages_data': top_pages_data,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
        'active_page': 'overview',
    }
    return render(request, 'analytics/dashboard.html', context)
