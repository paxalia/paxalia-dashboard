"""Paxalia Availability checks, transition semantics, and observation history."""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from django.db import transaction
from django.core.cache import cache
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone

from .alerts import send_alert
from .logging import log as paxalia_log
from .settings import get_config


def _cfg_int(name, default, minimum=0, maximum=None):
    try:
        value = int(get_config().get(name, default))
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _is_disallowed_ip(address):
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


def _resolve_public_target(url):
    """Resolve and validate one monitor target immediately before its socket connect."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        raise ValueError('Invalid monitor URL.') from exc
    if parsed.scheme.lower() not in {'http', 'https'}:
        raise ValueError('Only http:// and https:// monitor URLs are allowed.')
    if parsed.username or parsed.password:
        raise ValueError('Monitor URLs must not contain embedded credentials.')
    if not parsed.hostname:
        raise ValueError('Monitor URL must include a hostname.')
    hostname = parsed.hostname.rstrip('.').lower()
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == 'https' else 80)
    except ValueError as exc:
        raise ValueError('Monitor URL contains an invalid port.') from exc
    if not 1 <= port <= 65535:
        raise ValueError('Monitor URL contains an invalid port.')
    try:
        infos = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise ValueError('Monitor hostname could not be resolved.') from exc
    addresses = []
    for info in infos:
        if not info or not info[4]:
            continue
        address = info[4][0]
        if not _is_disallowed_ip(address):
            addresses.append(address)
        else:
            # Reject mixed public/private resolution rather than choosing a
            # public record and allowing DNS failover to an internal target.
            raise ValueError('Monitor URL resolves to a private, local, or reserved network address.')
    if not addresses:
        raise ValueError('Monitor hostname has no usable address.')
    return parsed, addresses[0]


def validate_monitor_url(url):
    """Validate an availability target against the package SSRF policy."""
    try:
        _resolve_public_target(url)
    except ValueError as exc:
        return False, str(exc)
    return True, ''


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, *args, resolved_ip=None, **kwargs):
        self._resolved_ip = resolved_ip
        super().__init__(host, *args, **kwargs)

    def connect(self):
        self.sock = socket.create_connection((self._resolved_ip, self.port), self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, *args, resolved_ip=None, **kwargs):
        self._resolved_ip = resolved_ip
        super().__init__(host, *args, **kwargs)

    def connect(self):
        sock = socket.create_connection((self._resolved_ip, self.port), self.timeout, self.source_address)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        _parsed, resolved_ip = _resolve_public_target(req.full_url)
        def connection(host, **kwargs):
            return _PinnedHTTPConnection(host, resolved_ip=resolved_ip, **kwargs)
        return self.do_open(connection, req)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        _parsed, resolved_ip = _resolve_public_target(req.full_url)
        def connection(host, **kwargs):
            return _PinnedHTTPSConnection(host, resolved_ip=resolved_ip, **kwargs)
        return self.do_open(connection, req, context=self._context)


def _validate_headers(headers):
    if not isinstance(headers, dict):
        return {}, 'Request headers must be an object.'
    if len(headers) > 32:
        return {}, 'Too many request headers configured.'
    clean = {}
    for raw_name, raw_value in headers.items():
        name = str(raw_name or '').strip()
        value = str(raw_value or '')
        if not name or len(name) > 100 or '\r' in name or '\n' in name:
            return {}, 'A configured request header name is invalid.'
        if name.casefold() in {'host', 'content-length', 'transfer-encoding', 'connection', 'proxy-connection', 'keep-alive', 'te', 'trailer', 'upgrade'}:
            return {}, 'Hop-by-hop or framing request headers cannot be configured.'
        if len(value) > 2048 or '\r' in value or '\n' in value:
            return {}, 'A configured request header value is invalid.'
        clean[name] = value
    return clean, ''


def _get_json_value(data, path):
    current = data
    for part in str(path or '').split('.'):
        if not part:
            return None, False
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None, False
    return current, True


def _check_assertions(assertions, body, headers):
    if not assertions:
        return True, []
    if not isinstance(assertions, list) or len(assertions) > 20:
        return False, [{'passed': False, 'reason': 'Too many response assertions configured.'}]
    results = []
    parsed_json = None
    json_loaded = False
    for assertion in assertions:
        if not isinstance(assertion, dict):
            results.append({'passed': False, 'reason': 'Assertion must be an object.'})
            continue
        passed = False
        reason = 'Assertion failed.'
        try:
            if 'contains' in assertion:
                needle = str(assertion['contains'])[:5000]
                passed = needle in body
                reason = 'Response contains expected text.' if passed else 'Expected text was not found.'
            elif 'not_contains' in assertion:
                needle = str(assertion['not_contains'])[:5000]
                passed = needle not in body
                reason = 'Response does not contain forbidden text.' if passed else 'Forbidden text was found.'
            elif 'header' in assertion:
                header_name = str(assertion.get('header') or '').lower()
                expected = str(assertion.get('equals') or '')
                actual = next((v for k, v in headers.items() if k.lower() == header_name), '')
                passed = actual == expected
                reason = 'Response header matched.' if passed else 'Response header did not match.'
            elif 'json_path' in assertion:
                if not json_loaded:
                    parsed_json = json.loads(body)
                    json_loaded = True
                actual, exists = _get_json_value(parsed_json, assertion['json_path'])
                if 'equals' in assertion:
                    passed = exists and actual == assertion['equals']
                elif 'not_equals' in assertion:
                    passed = exists and actual != assertion['not_equals']
                elif 'contains' in assertion:
                    passed = exists and str(assertion['contains']) in str(actual)
                else:
                    passed = False
                reason = 'JSON assertion matched.' if passed else 'JSON assertion did not match.'
            else:
                reason = 'Unsupported assertion.'
        except (ValueError, TypeError, json.JSONDecodeError):
            passed = False
            reason = 'Response could not be validated against the configured assertion.'
        results.append({'passed': passed, 'reason': reason})
    return all(item['passed'] for item in results), results


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Redirects are disabled for availability checks', headers, fp)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        valid, reason = validate_monitor_url(newurl)
        if not valid:
            raise urllib.error.HTTPError(req.full_url, code, reason, headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _response_media_type(value):
    return str(value or '').split(';', 1)[0].strip().lower()


def _read_bounded_body(response, max_bytes, method):
    if method == 'HEAD':
        return ''
    raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError('Response body exceeded the configured validation limit.')
    return raw.decode('utf-8', errors='replace')


def _evaluate_response(monitor, status_code, headers, body, elapsed_ms):
    expected_type = _response_media_type(getattr(monitor, 'expected_content_type', ''))
    content_type = _response_media_type(headers.get('Content-Type', ''))
    if expected_type and content_type != expected_type:
        return {
            'status': 'down', 'status_code': status_code, 'response_time_ms': elapsed_ms,
            'error_message': f'Expected content type {expected_type}, got {content_type or "missing"}.',
            'assertion_result': [],
        }
    passed, assertion_result = _check_assertions(
        getattr(monitor, 'response_assertions', []) or [], body, dict(headers.items()) if hasattr(headers, 'items') else dict(headers),
    )
    if not passed:
        return {
            'status': 'down', 'status_code': status_code, 'response_time_ms': elapsed_ms,
            'error_message': 'Response validation failed.', 'assertion_result': assertion_result,
        }
    ok = status_code == monitor.expected_status_code
    return {
        'status': 'up' if ok else 'down',
        'status_code': status_code,
        'response_time_ms': elapsed_ms,
        'error_message': '' if ok else f'Expected status {monitor.expected_status_code}, got {status_code}',
        'assertion_result': assertion_result,
    }


def perform_check(monitor):
    """Execute one bounded check with DNS-pinned SSRF validation and body assertions."""
    valid, reason = validate_monitor_url(monitor.url)
    if not valid:
        return {'status': 'unknown', 'status_code': None, 'response_time_ms': None, 'error_message': reason, 'assertion_result': []}

    headers, header_error = _validate_headers(getattr(monitor, 'request_headers', {}) or {})
    if header_error:
        return {'status': 'unknown', 'status_code': None, 'response_time_ms': None, 'error_message': header_error, 'assertion_result': []}

    start = time.monotonic()
    raw_body = str(getattr(monitor, 'request_body', '') or '')
    max_request_body = _cfg_int('AVAILABILITY_MAX_REQUEST_BODY_BYTES', 65536, 0, 1024 * 1024)
    if monitor.method == 'POST' and len(raw_body.encode('utf-8')) > max_request_body:
        return {
            'status': 'unknown', 'status_code': None, 'response_time_ms': None,
            'error_message': 'Configured request body exceeds the Availability validation limit.',
            'assertion_result': [],
        }
    req = urllib.request.Request(
        monitor.url,
        data=raw_body.encode('utf-8') if monitor.method == 'POST' and raw_body else None,
        headers=headers,
        method=monitor.method,
    )
    handlers = [urllib.request.ProxyHandler({}), _PinnedHTTPHandler(), _PinnedHTTPSHandler()]
    handlers.append(_SafeRedirect() if getattr(monitor, 'follow_redirects', False) else _NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    timeout = _cfg_int('AVAILABILITY_DEFAULT_TIMEOUT_SECONDS', 10, 1, 60)
    try:
        timeout = max(1, min(int(monitor.timeout_seconds), 60))
    except (TypeError, ValueError):
        timeout = 10
    max_bytes = _cfg_int('AVAILABILITY_MAX_RESPONSE_BYTES', 262144, 1024, 5 * 1024 * 1024)

    try:
        with opener.open(req, timeout=timeout) as resp:
            try:
                body = _read_bounded_body(resp, max_bytes, monitor.method)
            except ValueError as exc:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                return {
                    'status': 'down', 'status_code': resp.status, 'response_time_ms': elapsed_ms,
                    'error_message': str(exc), 'assertion_result': [],
                }
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _evaluate_response(monitor, resp.status, resp.headers, body, elapsed_ms)
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        reason = str(getattr(exc, 'reason', '') or '')
        lowered = reason.lower()
        if any(token in lowered for token in ('private', 'local', 'reserved', 'multicast', 'unspecified')):
            return {'status': 'unknown', 'status_code': exc.code, 'response_time_ms': elapsed_ms, 'error_message': reason[:500], 'assertion_result': []}
        try:
            body = _read_bounded_body(exc, max_bytes, monitor.method)
        except ValueError as body_error:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                'status': 'down', 'status_code': exc.code, 'response_time_ms': elapsed_ms,
                'error_message': str(body_error), 'assertion_result': [],
            }
        except (OSError, urllib.error.URLError) as body_error:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                'status': 'down', 'status_code': exc.code, 'response_time_ms': elapsed_ms,
                'error_message': str(getattr(body_error, 'reason', body_error))[:500] or 'Request failed',
                'assertion_result': [],
            }
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return _evaluate_response(monitor, exc.code, exc.headers or {}, body, elapsed_ms)
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        reason = getattr(exc, 'reason', exc)
        return {'status': 'down', 'status_code': None, 'response_time_ms': elapsed_ms, 'error_message': str(reason)[:500] or 'Request failed', 'assertion_result': []}
    except Exception:
        return {'status': 'unknown', 'status_code': None, 'response_time_ms': None, 'error_message': 'Availability worker could not complete the check safely.', 'assertion_result': []}


def _streak(checks, status):
    streak = []
    for check in checks:
        if check.status != status:
            break
        streak.append(check)
    return streak


def record_check(monitor, result):
    """Persist an observation and apply configurable failure/recovery thresholds."""
    from .models import UptimeCheck, UptimeIncident, UptimeMonitor

    alert = None
    transition_log = None
    with transaction.atomic():
        locked = UptimeMonitor.objects.select_for_update().get(pk=monitor.pk)
        try:
            failure_threshold = max(1, min(20, int(getattr(locked, 'failure_threshold', 2) or 2)))
        except (TypeError, ValueError, OverflowError):
            failure_threshold = 2
        try:
            recovery_threshold = max(1, min(20, int(getattr(locked, 'recovery_threshold', 2) or 2)))
        except (TypeError, ValueError, OverflowError):
            recovery_threshold = 2
        status = str(result.get('status') or 'unknown').lower()
        if status not in {'up', 'down', 'unknown'}:
            status = 'unknown'
        request_id = str(result.get('request_id') or uuid.uuid4().hex)[:100]
        check = UptimeCheck.objects.create(
            monitor=locked,
            status=status,
            status_code=result.get('status_code'),
            response_time_ms=result.get('response_time_ms'),
            error_message=str(result.get('error_message') or '')[:500],
            assertion_result=result.get('assertion_result') or [],
        )
        recent = list(locked.checks.order_by('-checked_at')[:max(failure_threshold, recovery_threshold) + 2])
        open_incident = locked.incidents.filter(state__in=['open', 'acknowledged']).first()

        if check.status == 'down':
            down_streak = _streak(recent, 'down')
            if len(down_streak) >= failure_threshold and open_incident is None:
                first_failure = down_streak[-1]
                prior = recent[len(down_streak)] if len(recent) > len(down_streak) else None
                open_incident = UptimeIncident.objects.create(
                    monitor=locked,
                    state='open',
                    started_at=first_failure.checked_at,
                    first_confirmed_failure_at=first_failure.checked_at,
                    last_confirmed_healthy_at=(prior.checked_at if prior and prior.status == 'up' else None),
                    cause=check.error_message,
                    status_code=check.status_code,
                    response_time_ms=check.response_time_ms,
                    request_id=request_id,
                )
                alert = (
                    f'{locked.name} is down',
                    f'{locked.name} has {len(down_streak)} consecutive failed availability observations. '
                    f'First confirmed failure: {first_failure.checked_at.isoformat()}.',
                    locked.site,
                    f'uptime:{locked.pk}:opened',
                )
                transition_log = (
                    'WARNING', 'availability.incident_opened',
                    f'{locked.name} availability incident opened after confirmed failures.',
                    request_id, locked.site_id,
                )
        elif check.status == 'up':
            up_streak = _streak(recent, 'up')
            if open_incident is not None and len(up_streak) >= recovery_threshold:
                first_recovery = up_streak[-1]
                open_incident.first_confirmed_recovery_at = first_recovery.checked_at
                open_incident.resolved_at = first_recovery.checked_at
                open_incident.state = 'recovered'
                open_incident.status_code = check.status_code
                open_incident.response_time_ms = check.response_time_ms
                open_incident.request_id = request_id or open_incident.request_id
                open_incident.save(update_fields=[
                    'first_confirmed_recovery_at', 'resolved_at', 'state', 'status_code',
                    'response_time_ms', 'request_id'
                    ])
                alert = (
                    f'{locked.name} is back up',
                    f'{locked.name} has {len(up_streak)} consecutive healthy availability observations. '
                    f'First confirmed recovery: {first_recovery.checked_at.isoformat()}.',
                    locked.site,
                    f'uptime:{locked.pk}:recovered:{open_incident.pk}',
                )
                transition_log = (
                    'INFO', 'availability.incident_recovered',
                    f'{locked.name} availability incident recovered after confirmed healthy observations.',
                    open_incident.request_id, locked.site_id,
                )

    if transition_log:
        try:
            paxalia_log(
                transition_log[2],
                level=transition_log[0],
                source='Availability',
                category='availability',
                action=transition_log[1],
                request_id=transition_log[3],
                metadata={'monitor_id': locked.pk, 'site_id': transition_log[4]},
            )
        except Exception:
            pass
    if alert:
        send_alert(subject=alert[0], message=alert[1], category='uptime', site=alert[2], dedupe_key=alert[3])
    return check


def compute_response_stats(monitor, start_dt, end_dt, max_points=2000):
    """Return bounded response-time statistics for a monitor's observed checks."""
    from statistics import mean, median
    from .models import UptimeCheck

    try:
        max_points = max(1, min(10000, int(max_points)))
    except (TypeError, ValueError):
        max_points = 2000
    values = list(
        UptimeCheck.objects
        .filter(monitor=monitor, checked_at__gte=start_dt, checked_at__lt=end_dt, response_time_ms__isnull=False)
        .order_by('-checked_at')
        .values_list('response_time_ms', flat=True)[:max_points]
    )
    if not values:
        return {'count': 0, 'average_ms': None, 'median_ms': None, 'p95_ms': None, 'p99_ms': None}
    values = sorted(int(value) for value in values)

    def percentile(percent):
        index = max(0, min(len(values) - 1, int(round((percent / 100) * (len(values) - 1)))))
        return values[index]

    return {
        'count': len(values),
        'average_ms': round(mean(values), 1),
        'median_ms': round(median(values), 1),
        'p95_ms': percentile(95),
        'p99_ms': percentile(99),
    }


def acquire_monitor_check_lease(monitor):
    """Acquire a short scheduler lease so concurrent workers do not double-check one monitor."""
    try:
        timeout = max(30, min(300, int(getattr(monitor, 'timeout_seconds', 10) or 10) + 30))
    except (TypeError, ValueError, OverflowError):
        timeout = 60
    key = f"paxalia:availability:monitor:{monitor.pk}"
    try:
        return bool(cache.add(key, uuid.uuid4().hex, timeout=timeout))
    except Exception:
        return False


def monitors_due_for_check(now=None):
    """Return a bounded set of monitors whose configured interval has elapsed."""
    from .models import UptimeMonitor, UptimeCheck

    now = now or timezone.now()
    try:
        limit = int(get_config().get('AVAILABILITY_MAX_CHECKS_PER_RUN', 100))
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(limit, 5000))
    latest = UptimeCheck.objects.filter(monitor=OuterRef('pk')).order_by('-checked_at').values('checked_at')[:1]
    due = []
    monitors = (
        UptimeMonitor.objects.filter(is_active=True)
        .annotate(_last_checked=Subquery(latest))
        .order_by(F('_last_checked').asc(nulls_first=True), 'id')
    )
    scan_limit = _cfg_int('AVAILABILITY_MAX_SCHEDULER_SCAN', max(limit, 1000), limit, 50000)
    scanned = 0
    for monitor in monitors.iterator(chunk_size=min(scan_limit, 500)):
        scanned += 1
        if monitor._last_checked is None or (now - monitor._last_checked).total_seconds() >= monitor.effective_interval_seconds:
            due.append(monitor)
            if len(due) >= limit:
                break
        if scanned >= scan_limit:
            break
    return due


def compute_uptime_percentage(monitor, start_dt, end_dt):
    from .models import UptimeCheck
    rows = UptimeCheck.objects.filter(monitor=monitor, checked_at__gte=start_dt, checked_at__lt=end_dt)
    up = rows.filter(status='up').count()
    down = rows.filter(status='down').count()
    observed = up + down
    if observed == 0:
        return None
    return round((up / observed) * 100, 2)
