# analytics/views/page_detail.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count
from django.http import Http404
from django.db.models.functions import TruncDate

from analytics.models import PageView

from .utils import get_date_range, detect_active_preset, section_enabled, get_current_site, site_scoped

from datetime import timedelta
from urllib.parse import unquote


# Create your views here.

@staff_member_required
def analytics_page_detail(request, path):
    if not section_enabled('pages'):
        raise Http404
    decoded_path = unquote(path)

    start_dt, end_dt = get_date_range(request)
    current_site = get_current_site(request)
    base_qs = site_scoped(PageView.objects.filter(path=decoded_path, created_at__range=(start_dt, end_dt), is_bot=False, is_api=False), current_site)

    # Check that there is at least one view for this path in the range
    if not base_qs.exists():
        raise Http404("No page views found for this path in the given date range.")

    daily = (
        base_qs
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels = [d['day'].strftime('%b %d') for d in daily]
    chart_views = [d['count'] for d in daily]

    # Compare to previous period?
    compare_active = request.GET.get('compare') == '1'
    previous_labels = []
    previous_views = []

    if compare_active:
        period_delta = (end_dt - start_dt).days
        prev_end = start_dt - timedelta(seconds=1)
        prev_start = prev_end - timedelta(days=period_delta)
        prev_qs = site_scoped(PageView.objects.filter(
            path=decoded_path,
            created_at__range=(prev_start, prev_end),
            is_bot=False,
            is_api=False
        ), current_site)
        prev_daily = (
            prev_qs
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        previous_labels = [d['day'].strftime('%b %d') for d in prev_daily]
        previous_views = [d['count'] for d in prev_daily]

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'page_path': decoded_path,
        'chart_labels': chart_labels,
        'chart_views': chart_views,
        'compare_active': compare_active,
        'previous_labels': previous_labels,
        'previous_views': previous_views,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
        'active_page': 'pages',
    }
    return render(request, 'analytics/page_detail.html', context)
