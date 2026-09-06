# analytics/views/campaigns.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import render

from analytics.models import PageView
from django.utils.translation import gettext as _

from .utils import get_date_range, detect_active_preset, section_enabled, get_current_site, site_scoped


@staff_member_required
def campaigns_dashboard(request):
    if not section_enabled('campaigns'):
        raise Http404

    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)

    base_qs = site_scoped(
        PageView.objects.filter(
            created_at__range=(start_dt, end_dt), is_bot=False, is_api=False,
        ).exclude(utm_source=''),
        current_site,
    )

    total_campaign_views = base_qs.count()

    top_campaigns = (
        base_qs.exclude(utm_campaign='')
        .values('utm_campaign', 'utm_source', 'utm_medium')
        .annotate(count=Count('id'))
        .order_by('-count')[:50]
    )
    top_sources = (
        base_qs.values('utm_source')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    top_mediums = (
        base_qs.exclude(utm_medium='')
        .values('utm_medium')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())

    context = {
        'active_page': 'campaigns',
        'page_title': _('Campaigns'),
        'page_subtitle': _('Traffic tagged with UTM parameters'),
        'total_campaign_views': total_campaign_views,
        'top_campaigns': top_campaigns,
        'top_sources': top_sources,
        'top_mediums': top_mediums,
        'active_preset': active_preset,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'show_search': False,
    }
    return render(request, 'analytics/campaigns.html', context)
