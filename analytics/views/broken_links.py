# analytics/views/broken_links.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Max
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from analytics.models import PageView

from .utils import get_date_range, detect_active_preset, section_enabled, get_current_site, site_scoped


@staff_member_required
def broken_links(request):
    """
    404 / broken-link report. Reuses PageView.status_code (already
    logged for every request) and PageView.referrer — no new tracking
    needed, this is purely a new read/view over existing data.
    """
    if not section_enabled('broken_links'):
        raise Http404

    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)

    base_qs = site_scoped(
        PageView.objects.filter(
            created_at__range=(start_dt, end_dt),
            status_code=404,
            is_bot=False,
        ),
        current_site,
    )

    total_404s = base_qs.count()

    top_broken_paths = (
        base_qs
        .values('path')
        .annotate(count=Count('id'), last_seen=Max('created_at'))
        .order_by('-count')[:50]
    )

    # Referrers pointing at 404s are the most actionable signal — an
    # internal link that's actually broken, as opposed to a scanner
    # probing random paths (which typically has no referrer at all).
    top_referrers = (
        base_qs
        .exclude(referrer='')
        .values('referrer')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'active_page': 'broken_links',
        'page_title': _('Broken Links'),
        'page_subtitle': _('404s and the referrers pointing at them'),
        'total_404s': total_404s,
        'top_broken_paths': top_broken_paths,
        'top_referrers': top_referrers,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
    }
    return render(request, 'analytics/broken_links.html', context)
