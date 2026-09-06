# analytics/views/realtime.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.http import JsonResponse, Http404

from analytics.models import PageView, AnalyticsSettings
from analytics.settings import get_config

from datetime import timedelta

from analytics.views.utils import section_enabled, get_current_site, site_scoped


# Create your views here.

@staff_member_required
def analytics_realtime(request):
    if not section_enabled('realtime'):
        raise Http404
    settings = AnalyticsSettings.objects.first()
    refresh_seconds = settings.realtime_refresh_seconds if settings else get_config()['DEFAULT_REALTIME_REFRESH']
    context = {
        'active_page': 'realtime',
        'refresh_seconds': refresh_seconds,
    }
    return render(request, 'analytics/realtime.html', context)


@staff_member_required
def analytics_realtime_data(request):
    """AJAX endpoint – returns live visitor counts as JSON."""
    current_site = get_current_site(request)
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)

    # Total page views in last 5 minutes (API calls tracked separately below
    # — a burst of API traffic shouldn't read as a spike in live visitors)
    total_views = site_scoped(PageView.objects.filter(created_at__gte=five_min_ago, is_bot=False, is_api=False), current_site).count()

    # Unique IPs in last 5 minutes
    unique_ips = site_scoped(PageView.objects.filter(created_at__gte=five_min_ago, is_bot=False, is_api=False), current_site).values('ip_hash').distinct().count()

    # API calls in last 5 minutes
    api_calls = site_scoped(PageView.objects.filter(created_at__gte=five_min_ago, is_bot=False, is_api=True), current_site).count()

    # Recent page views (last 20) — excludes API calls; those are noisy at
    # request-per-request granularity and belong on the API page instead
    recent = site_scoped(PageView.objects.filter(created_at__gte=five_min_ago, is_bot=False, is_api=False), current_site).order_by('-created_at')[:20]
    recent_data = [
        {
            'path': r.path,
            'ip_hash': r.ip_hash[:12] + '…' if r.ip_hash else 'anonymous',
            'method': r.method,
            'status_code': r.status_code,
            'time': r.created_at.strftime('%H:%M:%S'),
            'seconds_ago': (now - r.created_at).total_seconds(),
        }
        for r in recent
    ]

    data = {
        'total_views': total_views,
        'unique_ips': unique_ips,
        'api_calls': api_calls,
        'recent': recent_data,
        'timestamp': now.strftime('%H:%M:%S'),
    }
    return JsonResponse(data)
