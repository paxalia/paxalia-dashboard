# analytics/views/api.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate

from analytics.models import PageView, DailySiteStats
from analytics.settings import get_config

from .utils import get_date_range, detect_active_preset, section_enabled

from datetime import timedelta


# Create your views here.

@staff_member_required
def analytics_api(request):
    if not section_enabled('api'):
        raise Http404
    start_dt, end_dt = get_date_range(request)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Base queryset for API calls in the range
    api_prefix = get_config()['API_PATH_PREFIX']
    api_qs = PageView.objects.filter(
        created_at__range=(start_dt, end_dt),
        path__startswith=api_prefix
    )

    # Today's live API calls (always today)
    today_api = PageView.objects.filter(created_at__date=today, path__startswith=api_prefix).count()

    # Yesterday's API calls (prefer aggregated stats if available)
    try:
        yest_stats = DailySiteStats.objects.get(date=yesterday)
        yesterday_api = yest_stats.api_calls
    except DailySiteStats.DoesNotExist:
        yesterday_api = PageView.objects.filter(created_at__date=yesterday, path__startswith=api_prefix).count()

    # Daily API chart for the selected range
    daily_api = (
        api_qs
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels = [d['day'].strftime('%b %d') for d in daily_api]
    chart_api = [d['count'] for d in daily_api]

    # Compare to previous period?
    compare_active = request.GET.get('compare') == '1'
    previous_labels = []
    previous_data = []

    if compare_active:
        period_delta = (end_dt - start_dt).days
        prev_end = start_dt - timedelta(seconds=1)
        prev_start = prev_end - timedelta(days=period_delta)
        prev_qs = PageView.objects.filter(
            created_at__range=(prev_start, prev_end),
            path__startswith=api_prefix,
        )
        prev_daily = (
            prev_qs
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        previous_labels = [d['day'].strftime('%b %d') for d in prev_daily]
        previous_data = [d['count'] for d in prev_daily]

    # Top API endpoints in the range
    top_endpoints = (
        api_qs
        .values('path')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Status code distribution in the range
    status_dist = (
        api_qs
        .values('status_code')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'today_api': today_api,
        'yesterday_api': yesterday_api,
        'chart_labels': chart_labels,
        'chart_api': chart_api,
        'compare_active': compare_active,
        'previous_labels': previous_labels,
        'previous_api': previous_data,
        'top_endpoints': top_endpoints,
        'status_dist': status_dist,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
        'active_page': 'api',
    }
    return render(request, 'analytics/api.html', context)
