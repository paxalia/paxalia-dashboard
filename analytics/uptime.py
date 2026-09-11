# analytics/uptime.py
"""
Uptime monitoring — periodic HTTP checks against configured URLs, with
status history (UptimeCheck) and an incident log (UptimeIncident).

Deliberately uses only the standard library (urllib.request) for the
HTTP check itself rather than adding `requests` as a new dependency —
a GET/HEAD request with a timeout and a status-code check doesn't need
anything requests provides over urllib. This package already goes out
of its way to keep optional features from forcing new dependencies
(django-otp and weasyprint are both guarded imports); this one needs
no guard at all, since it adds nothing to requirements.txt.

SCHEDULING MODEL: `manage.py check_uptime` is meant to run frequently
(every minute is typical) via cron/Celery beat — the same assumption
this package already makes for aggregate_daily_stats,
send_scheduled_reports, and detect_anomalies. Each run only actually
pings a monitor whose check_interval_minutes has elapsed since its
last check (see monitors_due_for_check()) — running the command every
minute doesn't mean every monitor is hit every minute, it means every
monitor is hit within about one minute of when it's next due,
regardless of what its own configured interval is.

INCIDENT MODEL: an incident is opened on an up→down transition (or a
monitor's very first check coming back down) and resolved on the next
down→up transition — one incident per outage, not one row per failed
check. A monitor that's down for an hour with a check every minute is
one incident with a ~60-minute duration, not sixty separate rows.
"""
import socket
import time
import urllib.error
import urllib.request

from django.utils import timezone

from .alerts import send_alert


def perform_check(monitor):
    """
    Actually hit the monitor's URL once. Never raises — every failure
    mode (timeout, DNS failure, connection refused, wrong status code,
    an HTTP error response) is normalized into a result dict with
    status='down' and a human-readable error_message.
    """
    start = time.monotonic()
    req = urllib.request.Request(monitor.url, method=monitor.method)

    try:
        with urllib.request.urlopen(req, timeout=monitor.timeout_seconds) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _result_for_status(monitor, resp.status, elapsed_ms)
    except urllib.error.HTTPError as e:
        # A real HTTP response came back — just one urllib treats as
        # an error by default (4xx/5xx). Still a legitimate result:
        # measure it and check it the same way as a "successful" one.
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return _result_for_status(monitor, e.code, elapsed_ms)
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        reason = getattr(e, 'reason', e)
        return {
            'status': 'down', 'status_code': None, 'response_time_ms': elapsed_ms,
            'error_message': str(reason)[:500] or 'Request failed',
        }


def _result_for_status(monitor, status_code, elapsed_ms):
    if status_code == monitor.expected_status_code:
        return {'status': 'up', 'status_code': status_code, 'response_time_ms': elapsed_ms, 'error_message': ''}
    return {
        'status': 'down', 'status_code': status_code, 'response_time_ms': elapsed_ms,
        'error_message': f'Expected status {monitor.expected_status_code}, got {status_code}',
    }


def record_check(monitor, result):
    """
    Save the UptimeCheck row and drive the incident state machine —
    see this module's docstring for the incident model. Returns the
    created UptimeCheck.
    """
    from .models import UptimeCheck, UptimeIncident

    previous = monitor.latest_check
    was_up = previous is None or previous.status == 'up'

    check = UptimeCheck.objects.create(
        monitor=monitor,
        status=result['status'],
        status_code=result['status_code'],
        response_time_ms=result['response_time_ms'],
        error_message=result['error_message'],
    )

    if result['status'] == 'down' and was_up:
        UptimeIncident.objects.create(monitor=monitor, cause=result['error_message'])
        send_alert(
            subject=f'{monitor.name} is down',
            message=f'{monitor.name} ({monitor.url}) failed a check: {result["error_message"] or "unexpected status code"}',
            category='uptime', site=monitor.site,
        )
    elif result['status'] == 'up' and not was_up:
        open_incident = monitor.open_incident
        if open_incident is not None:
            open_incident.resolved_at = timezone.now()
            open_incident.save(update_fields=['resolved_at'])
            send_alert(
                subject=f'{monitor.name} is back up',
                message=f'{monitor.name} ({monitor.url}) recovered after {int(open_incident.duration_seconds)}s of downtime.',
                category='uptime', site=monitor.site,
            )

    return check


def monitors_due_for_check(now=None):
    """Active monitors that haven't been checked within their configured interval (or ever)."""
    from .models import UptimeMonitor

    now = now or timezone.now()
    due = []
    for monitor in UptimeMonitor.objects.filter(is_active=True):
        last = monitor.latest_check
        if last is None or (now - last.checked_at).total_seconds() >= monitor.check_interval_minutes * 60:
            due.append(monitor)
    return due


def compute_uptime_percentage(monitor, start_dt, end_dt):
    """
    % of checks in [start_dt, end_dt) that were 'up'. Returns None
    (not 0 or 100) if there were no checks in the window at all —
    nothing to compute rather than a misleading number.
    """
    checks = monitor.checks.filter(checked_at__range=(start_dt, end_dt))
    total = checks.count()
    if not total:
        return None
    up_count = checks.filter(status='up').count()
    return round(100 * up_count / total, 2)
