# analytics/views/traffic.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.db.models import Count

from analytics.models import PageView

from .utils import get_date_range, detect_active_preset, parse_user_agent, section_enabled


# Create your views here.

@staff_member_required
def analytics_traffic(request):
    if not section_enabled('traffic'):
        raise Http404
    start_dt, end_dt = get_date_range(request)
    base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False)

    # Top referrers
    top_referrers = (
        base_qs
        .exclude(referrer='')
        .values('referrer')
        .annotate(count=Count('id'))
        .order_by('-count')[:15]
    )

    # Parse user agents and build counts
    browser_counts = {}
    os_counts = {}
    device_counts = {}
    raw_agents = base_qs.values('user_agent').annotate(count=Count('id'))

    for item in raw_agents:
        ua_string = item.get('user_agent', '')
        parsed = parse_user_agent(ua_string)
        cnt = item['count']

        # Browser
        b = parsed['browser']
        browser_counts[b] = browser_counts.get(b, 0) + cnt

        # OS
        o = parsed['os']
        os_counts[o] = os_counts.get(o, 0) + cnt

        # Device
        d = parsed['device']
        device_counts[d] = device_counts.get(d, 0) + cnt

    # Sort
    browser_counts = sorted(browser_counts.items(), key=lambda x: x[1], reverse=True)
    os_counts = sorted(os_counts.items(), key=lambda x: x[1], reverse=True)
    device_counts = sorted(device_counts.items(), key=lambda x: x[1], reverse=True)

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())

    context = {
        'top_referrers': top_referrers,
        'browser_counts': browser_counts,  # list of (name, count) tuples
        'os_counts': os_counts,
        'device_counts': device_counts,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'show_search': False,
        'active_page': 'traffic',
    }
    return render(request, 'analytics/traffic.html', context)
