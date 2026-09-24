# paxalia/uptime.py
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
import ipaddress
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone

from .alerts import send_alert


_DEFAULT_TIMEOUT_MAX_SECONDS = 60
_DEFAULT_INTERVAL_MAX_MINUTES = 1440


def _is_disallowed_ip(address):
    """Return True for loopback/private/link-local/reserved/multicast IPs."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return any((
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_reserved,
        ip.is_multicast,
        ip.is_unspecified,
    ))


def validate_monitor_url(url):
    """Validate a monitor target before allowing the server to fetch it.

    Uptime checks are server-side HTTP requests, so accepting arbitrary URLs
    creates an SSRF primitive.  We allow only HTTP(S), reject userinfo, and
    reject hostnames whose current DNS answers point at non-public addresses.
    Redirects are disabled separately in ``perform_check`` so a public URL
    cannot redirect the worker into an internal network.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False, 'Invalid monitor URL.'

    if parsed.scheme.lower() not in {'http', 'https'}:
        return False, 'Only http:// and https:// monitor URLs are allowed.'
    if parsed.username or parsed.password:
        return False, 'Monitor URLs must not contain embedded credentials.'
    if not parsed.hostname:
        return False, 'Monitor URL must include a hostname.'

    hostname = parsed.hostname.rstrip('.').lower()
    try:
        port = parsed.port
    except ValueError:
        return False, 'Monitor URL contains an invalid port.'
    if port is not None and not (1 <= port <= 65535):
        return False, 'Monitor URL contains an invalid port.'

    # A numeric address can be checked directly; hostnames are resolved and
    # every current answer must be public. Rejecting if *any* answer is private
    # avoids accepting a hostname with mixed public/private DNS records.
    try:
        infos = socket.getaddrinfo(hostname, port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except OSError:
        return False, 'Monitor hostname could not be resolved.'

    addresses = {info[4][0] for info in infos if info and info[4]}
    if not addresses:
        return False, 'Monitor hostname has no usable address.'
    if any(_is_disallowed_ip(address) for address in addresses):
        return False, 'Monitor URL resolves to a private, local, or reserved network address.'

    return True, ''


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Redirects are disabled for uptime checks', headers, fp)


def perform_check(monitor):
    """
    Actually hit the monitor's URL once. Never raises — every failure
    mode (timeout, DNS failure, connection refused, wrong status code,
    an HTTP error response) is normalized into a result dict with
    status='down' and a human-readable error_message.
    """
    valid, reason = validate_monitor_url(monitor.url)
    if not valid:
        return {
            'status': 'down',
            'status_code': None,
            'response_time_ms': None,
            'error_message': reason,
        }

    start = time.monotonic()
    req = urllib.request.Request(monitor.url, method=monitor.method)
    opener = urllib.request.build_opener(_NoRedirect())

    try:
        with opener.open(req, timeout=max(1, min(int(monitor.timeout_seconds), _DEFAULT_TIMEOUT_MAX_SECONDS))) as resp:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _result_for_status(monitor, resp.status, elapsed_ms)
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        # A normal 4xx/5xx is a legitimate uptime result. Our custom
        # redirect handler uses HTTPError too, but those are explicitly
        # treated as an error so no cross-network redirect is followed.
        if e.reason == 'Redirects are disabled for uptime checks':
            return {
                'status': 'down',
                'status_code': e.code,
                'response_time_ms': elapsed_ms,
                'error_message': 'Redirects are not followed by uptime checks.',
            }
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
    """Persist a check and apply the incident state machine atomically."""
    from django.db import transaction
    from .models import UptimeCheck, UptimeIncident, UptimeMonitor

    alert = None
    with transaction.atomic():
        # UptimeMonitor.site is nullable. Do not combine select_for_update()
        # with a nullable outer join on PostgreSQL; lock the monitor row only.
        locked_monitor = UptimeMonitor.objects.select_for_update().get(pk=monitor.pk)
        previous = locked_monitor.checks.order_by('-checked_at').first()
        was_up = previous is None or previous.status == 'up'

        check = UptimeCheck.objects.create(
            monitor=locked_monitor,
            status=result['status'],
            status_code=result['status_code'],
            response_time_ms=result['response_time_ms'],
            error_message=result['error_message'],
        )

        if result['status'] == 'down' and was_up:
            # Re-check under the same monitor lock so overlapping scheduler
            # workers cannot open duplicate incidents.
            open_incident = locked_monitor.incidents.filter(resolved_at__isnull=True).first()
            if open_incident is None:
                UptimeIncident.objects.create(
                    monitor=locked_monitor, cause=result['error_message']
                )
                alert = (
                    f'{locked_monitor.name} is down',
                    f'{locked_monitor.name} ({locked_monitor.url}) failed a check: '
                    f'{result["error_message"] or "unexpected status code"}',
                    locked_monitor.site,
                )
        elif result['status'] == 'up' and not was_up:
            open_incident = locked_monitor.incidents.filter(resolved_at__isnull=True).first()
            if open_incident is not None:
                open_incident.resolved_at = timezone.now()
                open_incident.save(update_fields=['resolved_at'])
                alert = (
                    f'{locked_monitor.name} is back up',
                    f'{locked_monitor.name} ({locked_monitor.url}) recovered after '
                    f'{int(open_incident.duration_seconds)}s of downtime.',
                    locked_monitor.site,
                )

    if alert:
        send_alert(subject=alert[0], message=alert[1], category='uptime', site=alert[2])
    return check


def monitors_due_for_check(now=None):
    """Active monitors that haven't been checked within their configured interval (or ever)."""
    from .models import UptimeMonitor

    now = now or timezone.now()
    due = []
    for monitor in UptimeMonitor.objects.filter(is_active=True):
        last = monitor.latest_check
        if last is None or (now - last.checked_at).total_seconds() >= max(1, monitor.check_interval_minutes) * 60:
            due.append(monitor)
    return due


def compute_uptime_percentage(monitor, start_dt, end_dt):
    """
    % of checks in [start_dt, end_dt) that were 'up'. Returns None
    (not 0 or 100) if there were no checks in the window at all —
    nothing to compute rather than a misleading number.
    """
    checks = monitor.checks.filter(checked_at__gte=start_dt, checked_at__lt=end_dt)
    total = checks.count()
    if not total:
        return None
    up_count = checks.filter(status='up').count()
    return round(100 * up_count / total, 2)

