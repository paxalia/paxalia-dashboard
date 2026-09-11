# analytics/views/uptime.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import UptimeIncident, UptimeMonitor
from ..security_audit import log_action
from ..uptime import compute_uptime_percentage
from .utils import get_date_range, section_enabled


@staff_member_required
def uptime_overview(request):
    """Single page combining the monitor list/add-form and recent
    incident history, same pattern as sites_management()."""
    if not section_enabled('uptime'):
        raise Http404

    if request.method == 'POST' and 'save_monitor' in request.POST:
        name = request.POST.get('name', '').strip()
        url = request.POST.get('url', '').strip()
        method = request.POST.get('method', 'GET')
        expected_status_code = request.POST.get('expected_status_code', '200')
        timeout_seconds = request.POST.get('timeout_seconds', '10')
        check_interval_minutes = request.POST.get('check_interval_minutes', '5')

        if not name or not url:
            messages.error(request, _('Name and URL are required.'))
        else:
            try:
                UptimeMonitor.objects.create(
                    name=name, url=url, method=method,
                    expected_status_code=int(expected_status_code),
                    timeout_seconds=int(timeout_seconds),
                    check_interval_minutes=int(check_interval_minutes),
                )
                log_action(request, 'uptime.monitor_created', detail=f'name={name} url={url}')
                messages.success(request, _('Monitor added.'))
            except (ValueError, TypeError):
                messages.error(request, _('Status code, timeout, and interval must be numbers.'))
        return redirect('analytics:uptime')

    start_dt, end_dt = get_date_range(request)

    monitors = []
    for monitor in UptimeMonitor.objects.all():
        latest = monitor.latest_check
        monitors.append({
            'monitor': monitor,
            'current_status': latest.status if latest else 'unknown',
            'latest_check': latest,
            'uptime_pct': compute_uptime_percentage(monitor, start_dt, end_dt),
            'open_incident': monitor.open_incident,
        })

    recent_incidents = (
        UptimeIncident.objects.select_related('monitor')
        .filter(started_at__lte=end_dt)
        .order_by('-started_at')[:25]
    )

    context = {
        'active_page': 'uptime',
        'page_title': _('Uptime Monitoring'),
        'page_subtitle': _('Scheduled checks against URLs you configure'),
        'monitors': monitors,
        'recent_incidents': recent_incidents,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
    }
    return render(request, 'analytics/uptime.html', context)


@staff_member_required
@require_POST
def uptime_monitor_toggle(request, monitor_id):
    if not section_enabled('uptime'):
        raise Http404
    monitor = get_object_or_404(UptimeMonitor, id=monitor_id)
    monitor.is_active = not monitor.is_active
    monitor.save(update_fields=['is_active'])
    log_action(request, 'uptime.monitor_toggled', detail=f'name={monitor.name} is_active={monitor.is_active}')
    messages.success(request, _('Monitor updated.'))
    return redirect('analytics:uptime')


@staff_member_required
@require_POST
def uptime_monitor_delete(request, monitor_id):
    if not section_enabled('uptime'):
        raise Http404
    monitor = get_object_or_404(UptimeMonitor, id=monitor_id)
    name = monitor.name
    monitor.delete()
    log_action(request, 'uptime.monitor_deleted', detail=f'name={name}')
    messages.success(request, _('Monitor and its history deleted.'))
    return redirect('analytics:uptime')
