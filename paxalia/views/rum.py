# paxalia/views/rum.py
from ..admin_security import admin_security_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from paxalia.rum import compute_web_vitals_summary, compute_top_js_errors

from .utils import get_date_range, detect_active_preset, section_enabled, get_current_site


@admin_security_required
def rum_overview(request):
    if not section_enabled('rum'):
        raise Http404

    start_dt, end_dt = get_date_range(request)
    current_site = get_current_site(request)

    web_vitals = compute_web_vitals_summary(start_dt, end_dt, site=current_site)
    top_errors = compute_top_js_errors(start_dt, end_dt, site=current_site)

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'active_page': 'rum',
        'page_title': _('Real User Monitoring'),
        'page_subtitle': _('Core Web Vitals and JavaScript errors from real visitors'),
        'web_vitals': web_vitals,
        'top_errors': top_errors,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
    }
    return render(request, 'paxalia/rum.html', context)
