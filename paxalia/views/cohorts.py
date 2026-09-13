# paxalia/views/cohorts.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from paxalia.cohorts import compute_retention, MAX_PERIODS

from .utils import section_enabled, get_current_site


@staff_member_required
def cohorts_retention(request):
    if not section_enabled('cohorts'):
        raise Http404

    current_site = get_current_site(request)
    unit = request.GET.get('unit', 'week')
    if unit not in ('week', 'month'):
        unit = 'week'

    default_periods = 8 if unit == 'week' else 6
    try:
        num_periods = int(request.GET.get('periods', default_periods))
    except (TypeError, ValueError):
        num_periods = default_periods
    num_periods = max(2, min(num_periods, MAX_PERIODS))

    cohort_rows = compute_retention(unit, num_periods, current_site)

    # Column headers (offset 0, 1, 2, ...) — use the widest row so the
    # table has a consistent number of columns even though later
    # cohorts naturally have fewer measurable offsets so far. Pad each
    # row's offsets list with None for columns it doesn't have data
    # for yet, so the template can just iterate positionally instead
    # of cross-referencing offset numbers.
    max_offset = max((len(row['offsets']) - 1 for row in cohort_rows), default=0)
    for row in cohort_rows:
        padded = list(row['offsets'])
        while len(padded) <= max_offset:
            padded.append(None)
        row['offsets'] = padded

    context = {
        'active_page': 'cohorts',
        'page_title': _('Cohorts & Retention'),
        'page_subtitle': _('What fraction of each cohort comes back, by week or month'),
        'unit': unit,
        'num_periods': num_periods,
        'cohort_rows': cohort_rows,
        'offset_range': range(max_offset + 1),
        'period_options': [4, 6, 8, 10, 12],
        'show_search': False,
    }
    return render(request, 'paxalia/cohorts.html', context)
