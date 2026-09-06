# analytics/views/segments.py
import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.models import Segment
from analytics.segments import ALLOWED_FILTER_FIELDS

from .utils import section_enabled, get_current_site


@staff_member_required
def segments_management(request):
    if not section_enabled('segments'):
        raise Http404

    current_site = get_current_site(request)

    if request.method == 'POST' and 'save_segment' in request.POST:
        name = request.POST.get('name', '').strip()
        filters = {}
        for field in ALLOWED_FILTER_FIELDS:
            value = request.POST.get(f'filter_{field}', '').strip()
            if value:
                filters[field] = value

        if not name or not filters:
            messages.error(request, _('Name and at least one filter value are required.'))
        else:
            Segment.objects.create(site=current_site, name=name, filters=filters)
            messages.success(request, _('Segment saved.'))
        return redirect('analytics:segments')

    segments = Segment.objects.all()
    if current_site is not None:
        segments = segments.filter(site=current_site)

    context = {
        'active_page': 'segments',
        'page_title': _('Segments'),
        'page_subtitle': _('Saved filters, reusable across Overview, Pages, and Traffic'),
        'segments': segments,
        'filter_fields': sorted(ALLOWED_FILTER_FIELDS),
        'show_search': False,
    }
    return render(request, 'analytics/segments.html', context)


@staff_member_required
@require_POST
def segment_delete(request, segment_id):
    segment = get_object_or_404(Segment, id=segment_id)
    segment.delete()
    messages.success(request, _('Segment deleted.'))
    return redirect('analytics:segments')
