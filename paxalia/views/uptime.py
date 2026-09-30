# paxalia/views/uptime.py
import json
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..admin_security import admin_security_required
from ..models import UptimeCheck, UptimeIncident, UptimeMonitor
from ..permissions import require_section_permission
from ..server_files.policy import has_capability
from ..security_audit import log_action
from ..settings import get_config
from ..uptime import compute_response_stats, compute_uptime_percentage, validate_monitor_url, _validate_headers
from .utils import get_current_site, get_date_range, section_enabled, scoped_object_or_404


def _int_field(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = int(default)
        except (TypeError, ValueError, OverflowError):
            parsed = minimum
    return max(minimum, min(maximum, parsed))


def _json_object(value, default=None, max_items=32):
    default = {} if default is None else default
    if not value:
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid JSON value.")
    if not isinstance(parsed, dict) or len(parsed) > max_items:
        raise ValueError("JSON object is invalid or too large.")
    return parsed


def _json_list(value, max_items=20):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid JSON value.")
    if not isinstance(parsed, list) or len(parsed) > max_items:
        raise ValueError("JSON list is invalid or too large.")
    return parsed


def _monitor_payload(request, existing=None):
    config = get_config()
    default_interval = _int_field(config.get('AVAILABILITY_DEFAULT_INTERVAL_SECONDS', 300), 300, 30, 86400)
    default_timeout = _int_field(config.get('AVAILABILITY_DEFAULT_TIMEOUT_SECONDS', 10), 10, 1, 120)
    default_failure = _int_field(config.get('AVAILABILITY_FAILURE_THRESHOLD', 2), 2, 1, 20)
    default_recovery = _int_field(config.get('AVAILABILITY_RECOVERY_THRESHOLD', 2), 2, 1, 20)
    kinds = {'server', 'website', 'api', 'endpoint'}
    methods = {str(item).upper() for item in (config.get('AVAILABILITY_ALLOWED_METHODS') or ['GET', 'HEAD', 'POST'])}
    if existing is None:
        raw = {
            'name': request.POST.get('name', ''),
            'url': request.POST.get('url', ''),
            'kind': request.POST.get('kind', 'website'),
            'method': request.POST.get('method', 'GET'),
            'expected_status_code': request.POST.get('expected_status_code'),
            'timeout_seconds': request.POST.get('timeout_seconds'),
            'check_interval_seconds': request.POST.get('check_interval_seconds'),
            'failure_threshold': request.POST.get('failure_threshold'),
            'recovery_threshold': request.POST.get('recovery_threshold'),
            'expected_content_type': request.POST.get('expected_content_type', ''),
            'request_body': request.POST.get('request_body', ''),
            'follow_redirects': bool(request.POST.get('follow_redirects')),
            'request_headers': request.POST.get('request_headers', ''),
            'response_assertions': request.POST.get('response_assertions', ''),
        }
    else:
        raw = {
            'name': request.POST.get('name', existing.name),
            'url': request.POST.get('url', existing.url),
            'kind': request.POST.get('kind', existing.kind),
            'method': request.POST.get('method', existing.method),
            'expected_status_code': request.POST.get('expected_status_code', existing.expected_status_code),
            'timeout_seconds': request.POST.get('timeout_seconds', existing.timeout_seconds),
            'check_interval_seconds': request.POST.get('check_interval_seconds', existing.effective_interval_seconds),
            'failure_threshold': request.POST.get('failure_threshold', existing.failure_threshold),
            'recovery_threshold': request.POST.get('recovery_threshold', existing.recovery_threshold),
            'expected_content_type': request.POST.get('expected_content_type', existing.expected_content_type),
            'request_body': request.POST.get('request_body', existing.request_body),
            'follow_redirects': bool(request.POST.get('follow_redirects')),
            'request_headers': request.POST.get('request_headers', ''),
            'response_assertions': request.POST.get('response_assertions', ''),
        }
    name = str(raw['name']).strip()[:200]
    url = str(raw['url']).strip()[:500]
    kind = str(raw['kind']).strip().lower()
    method = str(raw['method']).strip().upper()
    valid_url, url_error = validate_monitor_url(url)
    interval = _int_field(raw['check_interval_seconds'], default_interval, 30, 86400)
    timeout = _int_field(raw['timeout_seconds'], default_timeout, 1, 120)
    expected = _int_field(raw['expected_status_code'], 200, 100, 599)
    failure_threshold = _int_field(raw['failure_threshold'], default_failure, 1, 20)
    recovery_threshold = _int_field(raw['recovery_threshold'], default_recovery, 1, 20)
    if not name or not url:
        return None, _('Name and URL are required.')
    if not valid_url:
        return None, url_error
    if kind not in kinds:
        return None, _('Unsupported monitor type.')
    if method not in methods or method not in {'GET', 'HEAD', 'POST'}:
        return None, _('Unsupported HTTP method.')
    try:
        headers = _json_object(raw['request_headers'], {}) if 'request_headers' in request.POST else (existing.request_headers or {} if existing else {})
        assertions = _json_list(raw['response_assertions']) if 'response_assertions' in request.POST else (existing.response_assertions or [] if existing else [])
        _validated_headers, header_error = _validate_headers(headers)
        if header_error:
            return None, header_error
    except ValueError as exc:
        return None, str(exc)
    request_body = str(raw['request_body'] or '')
    try:
        max_request_body_bytes = max(1024, min(int(config.get('AVAILABILITY_MAX_REQUEST_BODY_BYTES', 65536)), 1024 * 1024))
    except (TypeError, ValueError, OverflowError):
        max_request_body_bytes = 65536
    if len(request_body.encode('utf-8')) > max_request_body_bytes:
        return None, _('Configured request body exceeds the Availability validation limit.')

    payload = {
        'name': name, 'url': url, 'kind': kind, 'method': method,
        'expected_status_code': expected, 'timeout_seconds': timeout,
        'check_interval_minutes': max(1, interval // 60),
        'check_interval_seconds': interval,
        'failure_threshold': failure_threshold, 'recovery_threshold': recovery_threshold,
        'follow_redirects': bool(raw['follow_redirects']),
        'request_headers': headers, 'request_body': request_body,
        'expected_content_type': str(raw['expected_content_type'] or '').strip()[:120],
        'response_assertions': assertions,
    }
    return payload, None


def _monitor_form_values(monitor):
    return {
        'name': monitor.name, 'url': monitor.url, 'kind': monitor.kind, 'method': monitor.method,
        'kind_choices': tuple(UptimeMonitor.KIND_CHOICES),
        'method_choices': tuple(UptimeMonitor.METHOD_CHOICES),
        'expected_status_code': monitor.expected_status_code, 'timeout_seconds': monitor.timeout_seconds,
        'check_interval_seconds': monitor.effective_interval_seconds,
        'failure_threshold': monitor.failure_threshold, 'recovery_threshold': monitor.recovery_threshold,
        'expected_content_type': monitor.expected_content_type,
        'request_headers_json': json.dumps(monitor.request_headers or {}, ensure_ascii=False, indent=2),
        'response_assertions_json': json.dumps(monitor.response_assertions or [], ensure_ascii=False, indent=2),
        'request_body': monitor.request_body or '', 'follow_redirects': monitor.follow_redirects,
    }


@require_section_permission('availability')
def uptime_overview(request):
    """Availability workspace backed by Paxalia's existing uptime engine."""
    if not section_enabled('availability'):
        raise Http404

    current_site = get_current_site(request)
    can_manage_availability = request.user.is_superuser or has_capability(request.user, 'manage_availability')
    can_view_incidents = request.user.is_superuser or has_capability(request.user, 'view_incidents')
    can_view_logs = section_enabled('logs') and (request.user.is_superuser or has_capability(request.user, 'view_logs'))
    if request.method == 'POST' and 'save_monitor' in request.POST:
        if not can_manage_availability:
            raise PermissionDenied(_('You do not have permission to manage Availability monitors.'))
        payload, error = _monitor_payload(request)
        if error:
            messages.error(request, _(error))
        else:
            payload['site'] = current_site
            monitor = UptimeMonitor.objects.create(**payload)
            log_action(request, 'availability.monitor_created', detail=f'name={monitor.name} kind={monitor.kind}')
            messages.success(request, _('Availability monitor added.'))
        return redirect('paxalia:availability')

    start_dt, end_dt = get_date_range(request)
    monitor_qs = UptimeMonitor.objects.select_related('site').all()
    incident_qs = UptimeIncident.objects.select_related('monitor', 'acknowledged_by').all()
    if current_site is not None:
        monitor_qs = monitor_qs.filter(site=current_site)
        incident_qs = incident_qs.filter(monitor__site=current_site)

    monitors = []
    summary = {'up': 0, 'down': 0, 'unknown': 0, 'open_incidents': 0}
    for monitor in monitor_qs:
        latest = monitor.latest_check
        status = latest.status if latest else 'unknown'
        summary[status] = summary.get(status, 0) + 1
        open_incident = monitor.open_incident if can_view_incidents else None
        if open_incident:
            summary['open_incidents'] += 1
        monitors.append({
            'monitor': monitor, 'current_status': status, 'latest_check': latest,
            'uptime_pct': compute_uptime_percentage(monitor, start_dt, end_dt),
            'response_stats': compute_response_stats(monitor, start_dt, end_dt),
            'open_incident': open_incident, 'form': _monitor_form_values(monitor),
        })

    recent_incidents = (
        list(incident_qs.filter(started_at__lte=end_dt).order_by('-started_at')[:50])
        if can_view_incidents else []
    )
    for incident in recent_incidents:
        start = incident.first_confirmed_failure_at or incident.started_at
        end = incident.first_confirmed_recovery_at or timezone.now()
        incident.related_logs_url = reverse('paxalia:logs') + '?' + urlencode({
            'start_date': start.date().isoformat(), 'end_date': end.date().isoformat(),
            **({'request_id': incident.request_id} if incident.request_id else {}),
        })
    return render(request, 'paxalia/uptime.html', {
        'active_page': 'availability', 'page_title': _('Paxalia Availability'),
        'page_subtitle': _('Observed health, response timing, and incidents for configured targets'),
        'monitors': monitors, 'recent_incidents': recent_incidents,
        'availability_summary': summary, 'start_date': start_dt.date(), 'end_date': end_dt.date(),
        'availability_default_interval': _int_field(get_config().get('AVAILABILITY_DEFAULT_INTERVAL_SECONDS', 300), 300, 30, 86400),
        'can_manage_availability': can_manage_availability,
        'can_view_incidents': can_view_incidents,
        'can_view_logs': can_view_logs,
    })


@require_section_permission('availability')
@require_POST
def uptime_monitor_update(request, monitor_id):
    if not section_enabled('availability'):
        raise Http404
    if not has_capability(request.user, 'manage_availability'):
        raise PermissionDenied
    monitor = scoped_object_or_404(UptimeMonitor, request, monitor_id)
    payload, error = _monitor_payload(request, existing=monitor)
    if error:
        messages.error(request, _(error))
        return redirect('paxalia:availability')
    for field, value in payload.items():
        setattr(monitor, field, value)
    monitor.save()
    log_action(request, 'availability.monitor_updated', detail=f'name={monitor.name} kind={monitor.kind}')
    messages.success(request, _('Availability monitor updated.'))
    return redirect('paxalia:availability')


@require_section_permission('availability')
@require_POST
def uptime_monitor_toggle(request, monitor_id):
    if not section_enabled('availability'):
        raise Http404
    if not has_capability(request.user, 'manage_availability'):
        raise PermissionDenied
    monitor = scoped_object_or_404(UptimeMonitor, request, monitor_id)
    monitor.is_active = not monitor.is_active
    monitor.save(update_fields=['is_active'])
    log_action(request, 'availability.monitor_toggled', detail=f'name={monitor.name} is_active={monitor.is_active}')
    messages.success(request, _('Monitor updated.'))
    return redirect('paxalia:availability')


@require_section_permission('availability')
@require_POST
def uptime_monitor_delete(request, monitor_id):
    if not section_enabled('availability'):
        raise Http404
    if not has_capability(request.user, 'manage_availability'):
        raise PermissionDenied
    monitor = scoped_object_or_404(UptimeMonitor, request, monitor_id)
    name = monitor.name
    monitor.delete()
    log_action(request, 'availability.monitor_deleted', detail=f'name={name}')
    messages.success(request, _('Monitor and its history deleted.'))
    return redirect('paxalia:availability')


@require_section_permission('availability')
@require_POST
def availability_incident_acknowledge(request, incident_id):
    if not has_capability(request.user, 'manage_availability') and not request.user.is_superuser:
        raise PermissionDenied
    incident = scoped_object_or_404(UptimeIncident, request, incident_id, site_field='monitor__site')
    if not incident.is_ongoing:
        messages.info(request, _('This incident is already recovered.'))
        return redirect('paxalia:availability')
    with transaction.atomic():
        incident.state = 'acknowledged'
        incident.acknowledged_at = timezone.now()
        incident.acknowledged_by = request.user
        incident.save(update_fields=['state', 'acknowledged_at', 'acknowledged_by'])
    log_action(request, 'availability.incident_acknowledged', detail=f'incident={incident.id} monitor={incident.monitor.name}')
    messages.success(request, _('Incident acknowledged.'))
    return redirect('paxalia:availability')
