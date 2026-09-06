# analytics/views/annotations.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.models import ChartAnnotation

from .utils import section_enabled, get_current_site


@staff_member_required
def annotations_management(request):
    if not section_enabled('annotations'):
        raise Http404

    current_site = get_current_site(request)

    if request.method == 'POST' and 'save_annotation' in request.POST:
        date = request.POST.get('date', '').strip()
        label = request.POST.get('label', '').strip()
        if not date or not label:
            messages.error(request, _('Date and label are both required.'))
        else:
            ChartAnnotation.objects.create(
                site=current_site, date=date, label=label, created_by=request.user,
            )
            messages.success(request, _('Annotation added.'))
        return redirect('analytics:annotations')

    annotations = ChartAnnotation.objects.select_related('created_by')
    if current_site is not None:
        annotations = annotations.filter(site=current_site)

    context = {
        'active_page': 'annotations',
        'page_title': _('Chart Annotations'),
        'page_subtitle': _('Mark deploys, campaigns, or incidents on the Overview chart'),
        'annotations': annotations[:200],
        'show_search': False,
    }
    return render(request, 'analytics/annotations.html', context)


@staff_member_required
@require_POST
def annotation_delete(request, annotation_id):
    annotation = get_object_or_404(ChartAnnotation, id=annotation_id)
    annotation.delete()
    messages.success(request, _('Annotation deleted.'))
    return redirect('analytics:annotations')
