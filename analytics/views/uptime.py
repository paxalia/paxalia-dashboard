# analytics/views/uptime.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import UptimeIncident, UptimeMonitor
from ..security_audit import log_action
from ..uptime import compute_uptime_percentage, validate_monitor_url
from .utils import get_date_range, section_enabled, scoped_object_or_404


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
            valid_url, url_error = validate_monitor_url(url)
            try:
                expected = int(expected_status_code)
                timeout = int(timeout_seconds)
                interval = int(check_interval_minutes)
            except (ValueError, TypeError):
                expected = timeout = interval = None

            if not valid_url:
                messages.error(request, _(url_error))
            elif expected is None:
                messages.error(request, _('Status code, timeout, and interval must be numbers.'))
            elif not (100 <= expected <= 599):
                messages.error(request, _('Expected status code must be between 100 and 599.'))
            elif not (1 <= timeout <= 60):
                messages.error(request, _('Timeout must be between 1 and 60 seconds.'))
            elif not (1 <= interval <= 1440):
                messages.error(request, _('Check interval must be between 1 minute and 24 hours.'))
            elif method not in {'GET', 'HEAD', 'POST'}:
                messages.error(request, _('Unsupported HTTP method.'))
            else:
                UptimeMonitor.objects.create(
                    name=name, url=url, method=method,
                    expected_status_code=expected,
                    timeout_seconds=timeout,
                    check_interval_minutes=interval,
                )
                log_action(request, 'uptime.monitor_created', detail=f'name={name} url={url}')
                messages.success(request, _('Monitor added.'))
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
    monitor = scoped_object_or_404(UptimeMonitor, request, monitor_id)
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
    monitor = scoped_object_or_404(UptimeMonitor, request, monitor_id)
    name = monitor.name
    monitor.delete()
    log_action(request, 'uptime.monitor_deleted', detail=f'name={name}')
    messages.success(request, _('Monitor and its history deleted.'))
    return redirect('analytics:uptime')

