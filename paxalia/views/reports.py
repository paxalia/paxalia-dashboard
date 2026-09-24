# paxalia/views/reports.py
from django.contrib import messages
from ..admin_security import admin_security_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from paxalia.models import ScheduledReport
from paxalia.security_audit import log_action

from .utils import section_enabled, get_current_site, scoped_object_or_404


@admin_security_required
def reports_management(request):
    if not section_enabled('reports'):
        raise Http404

    current_site = get_current_site(request)

    if request.method == 'POST' and 'save_report' in request.POST:
        name = request.POST.get('name', '').strip()
        recipient_emails = request.POST.get('recipient_emails', '').strip()
        frequency = request.POST.get('frequency', 'weekly')
        if frequency not in ('weekly', 'monthly'):
            frequency = 'weekly'

        if not name or not recipient_emails:
            messages.error(request, _('Name and at least one recipient email are required.'))
        else:
            ScheduledReport.objects.create(
                site=current_site, name=name, recipient_emails=recipient_emails,
                frequency=frequency, created_by=request.user,
            )
            log_action(request, 'report.created', detail=f'name={name} frequency={frequency}')
            messages.success(request, _('Scheduled report created.'))
        return redirect('paxalia:reports')

    reports = ScheduledReport.objects.select_related('site')
    if current_site is not None:
        reports = reports.filter(site=current_site)

    context = {
        'active_page': 'reports',
        'page_title': _('Scheduled Reports'),
        'page_subtitle': _('Recurring email traffic digests, with an optional PDF attachment'),
        'reports': reports,
        'show_search': False,
    }
    return render(request, 'paxalia/reports.html', context)


@admin_security_required
@require_POST
def report_toggle_active(request, report_id):
    if not section_enabled('reports'):
        raise Http404
    report = scoped_object_or_404(ScheduledReport, request, report_id)
    report.is_active = not report.is_active
    report.save(update_fields=['is_active'])
    log_action(request, 'report.toggled', detail=f'name={report.name} is_active={report.is_active}')
    messages.success(request, _('Report updated.'))
    return redirect('paxalia:reports')


@admin_security_required
@require_POST
def report_delete(request, report_id):
    if not section_enabled('reports'):
        raise Http404
    report = scoped_object_or_404(ScheduledReport, request, report_id)
    name = report.name
    report.delete()
    log_action(request, 'report.deleted', detail=f'name={name}')
    messages.success(request, _('Scheduled report deleted.'))
    return redirect('paxalia:reports')

