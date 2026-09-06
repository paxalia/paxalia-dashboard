# analytics/views/api.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from analytics.models import PageView, DailySiteStats

from .utils import get_date_range, detect_active_preset, section_enabled, get_current_site, site_scoped

from datetime import timedelta


# Create your views here.

@staff_member_required
def analytics_api(request):
    if not section_enabled('api'):
        raise Http404
    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Base queryset for API calls in the range
    api_qs = site_scoped(PageView.objects.filter(
        created_at__range=(start_dt, end_dt),
        is_api=True, is_bot=False
    ), current_site)

    # Today's live API calls (always today)
    today_api = site_scoped(PageView.objects.filter(created_at__date=today, is_api=True, is_bot=False), current_site).count()

    # Yesterday's API calls (prefer aggregated stats if available)
    try:
        if current_site is not None:
            yesterday_api = DailySiteStats.objects.get(site=current_site, date=yesterday).api_calls
        else:
            agg = DailySiteStats.objects.filter(date=yesterday).aggregate(api_calls=Sum('api_calls'))
            if agg['api_calls'] is None:
                raise DailySiteStats.DoesNotExist
            yesterday_api = agg['api_calls']
    except DailySiteStats.DoesNotExist:
        yesterday_api = site_scoped(PageView.objects.filter(created_at__date=yesterday, is_api=True, is_bot=False), current_site).count()

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
        prev_qs = site_scoped(PageView.objects.filter(
            created_at__range=(prev_start, prev_end),
            is_api=True, is_bot=False
        ), current_site)
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
