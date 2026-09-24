# paxalia/signals.py
"""Django authentication signals for Paxalia historical login activity."""
import hashlib
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.cache import cache
from django.utils import timezone

from .alerts import send_security_alert
from .logging import log as paxalia_log
from .logging.services import build_request_context
from .middleware import _resolve_ip, AnalyticsMiddleware
from .models import LoginEvent
from .settings import get_config

try:
    from .admin_security import ADMIN_HOST_AUTH_PENDING_KEY
except Exception:  # pragma: no cover - defensive import during app bootstrap
    ADMIN_HOST_AUTH_PENDING_KEY = "paxalia.admin.host_auth_pending"

logger = logging.getLogger('paxalia.security')
User = get_user_model()


def _admin_user(user):
    if not user:
        return False
    checker = get_config().get('SECURITY_ADMIN_USER_CHECK')
    if callable(checker):
        try:
            return bool(checker(user))
        except Exception:
            return False
    return bool(user.is_staff or user.is_superuser)


def _should_track(user):
    config = get_config()
    if not config.get('SECURITY_TRACK_ONLY_STAFF', False):
        return True
    return _admin_user(user)


def _request_context(request):
    """Best-effort auth context. Never raises into the auth operation."""
    # `build_request_context()` applies the normal Paxalia logging privacy
    # policy, so its `ip_address` may be a SHA-256 hash. LoginEvent is an
    # operational security record and its GenericIPAddressField intentionally
    # stores the validated request IP. Resolve geo information from that raw
    # IP before building the LoginEvent payload.
    try:
        raw_ip = AnalyticsMiddleware._get_ip(request)
    except Exception:
        raw_ip = None

    try:
        ctx = build_request_context(request)
    except Exception:
        ctx = {}

    country_code = country_name = city = ''
    if raw_ip:
        try:
            country_code, country_name, city = _resolve_ip(raw_ip)
        except Exception:
            pass

    return {
        'ip_address': raw_ip,
        'user_agent': ctx.get('user_agent', '')[:512],
        'browser': ctx.get('browser', ''),
        'os': ctx.get('operating_system', ''),
        'device': ctx.get('device', ''),
        'country_code': country_code or '',
        'country_name': country_name or '',
        'city': city or '',
        'request_id': ctx.get('request_id', ''),
        'correlation_id': ctx.get('correlation_id', ''),
        'trace_id': ctx.get('trace_id', ''),
        'traffic_type': ctx.get('traffic_type', 'WEB'),
    }


def _identifier_hash(identifier):
    if not identifier:
        return ''
    return hashlib.sha256(str(identifier).strip().lower().encode('utf-8', 'ignore')).hexdigest()


def _is_new_location(user, ip_address):
    if not user or not ip_address:
        return False
    return not LoginEvent.objects.filter(
        user=user, ip_address=ip_address, result='success', event_type='login'
    ).exists()


def _record_login(user, request, *, result, failure_category='', username_attempted=''):
    ctx = _request_context(request)
    is_admin = _admin_user(user)
    new_location = _is_new_location(user, ctx.get('ip_address')) if result == 'success' else False
    config = get_config()
    # Keep the attempted identifier for security investigation by default;
    # deployments that require hashed-only failure identifiers can set
    # SECURITY_STORE_FAILED_USERNAME=False.
    stored_identifier = username_attempted if config.get('SECURITY_STORE_FAILED_USERNAME', True) else ''
    event = LoginEvent.objects.create(
        event_type='login',
        user=user,
        username_attempted=(getattr(user, 'get_username', lambda: '')() if result == 'success' else stored_identifier)[:255],
        result=result,
        failure_reason=failure_category[:255],
        failure_category=failure_category[:100],
        identifier_hash=_identifier_hash(username_attempted),
        is_admin=is_admin,
        request_id=ctx.get('request_id', ''),
        correlation_id=ctx.get('correlation_id', ''),
        trace_id=ctx.get('trace_id', ''),
        traffic_type=ctx.get('traffic_type', 'WEB'),
        session_key=getattr(getattr(request, 'session', None), 'session_key', '') or '',
        is_new_location=new_location,
        **{key: value for key, value in ctx.items() if key in {'ip_address', 'user_agent', 'browser', 'os', 'device', 'country_code', 'country_name', 'city'}},
    )
    paxalia_log(
        'Authentication event',
        level='INFO' if result == 'success' else 'WARNING',
        source='Authentication', category='authentication',
        action='login_success' if result == 'success' else 'login_failed',
        request=request,
        request_id=ctx.get('request_id'), correlation_id=ctx.get('correlation_id'), trace_id=ctx.get('trace_id'),
        metadata={
            'result': result,
            'admin': is_admin,
            'failure_category': failure_category,
            'identifier_hash': _identifier_hash(username_attempted),
        },
    )
    return event, new_location


def handle_login(sender, request, user, **kwargs):
    if not _should_track(user):
        return
    # When /insights/ initiated an administrator flow through the host
    # application's login, that host login is Layer 1, not a privileged
    # Paxalia session. Consume the one-shot marker so only the final
    # three-layer session creates the administrator LoginEvent.
    try:
        session = getattr(request, "session", None)
        if session is not None and session.get(ADMIN_HOST_AUTH_PENDING_KEY):
            session.pop(ADMIN_HOST_AUTH_PENDING_KEY, None)
            session.modified = True
            return
    except Exception:
        pass
    try:
        event, new_location = _record_login(user, request, result='success')
        if new_location:
            ctx = _request_context(request)
            send_security_alert(
                subject=f'New-location login: {user.get_username()}',
                message=(
                    f'{user.get_username()} signed in from a new IP/location: '
                    f'{ctx.get("ip_address")} ({ctx.get("city")}, {ctx.get("country_name")}). '
                    f'{ctx.get("browser")} on {ctx.get("os")}.'
                ),
                alert_type='new_location_login',
            )
    except Exception:
        # Never turn an authentication success into an error because logging failed.
        logger.exception('Failed to record successful LoginEvent')


def handle_logout(sender, request, user, **kwargs):
    if user is None or not _should_track(user):
        return
    try:
        session_key = getattr(getattr(request, 'session', None), 'session_key', '') or ''
        qs = LoginEvent.objects.filter(
            user=user, event_type='login', result='success', logged_out_at__isnull=True
        )
        if session_key:
            qs = qs.filter(session_key=session_key)
        event = qs.order_by('-created_at').first()
        if event:
            event.logged_out_at = timezone.now()
            event.save(update_fields=['logged_out_at'])

        ctx = _request_context(request)
        LoginEvent.objects.create(
            event_type='logout',
            user=user,
            username_attempted=getattr(user, 'get_username', lambda: '')()[:255],
            result='success',
            is_admin=_admin_user(user),
            request_id=ctx.get('request_id', ''),
            correlation_id=ctx.get('correlation_id', ''),
            trace_id=ctx.get('trace_id', ''),
            traffic_type=ctx.get('traffic_type', 'WEB'),
            session_key=session_key,
            **{key: value for key, value in ctx.items() if key in {'ip_address', 'user_agent', 'browser', 'os', 'device', 'country_code', 'country_name', 'city'}},
        )
        paxalia_log(
            'Authentication logout', level='INFO', source='Authentication',
            category='authentication', action='logout', request=request,
            metadata={'admin': _admin_user(user)},
        )
    except Exception:
        logger.exception('Failed to record logout on LoginEvent')


def _maybe_alert_brute_force(ip_address):
    if not ip_address:
        return
    config = get_config()
    threshold = max(1, int(config.get('SECURITY_FAILED_LOGIN_THRESHOLD', 5)))
    window_minutes = max(1, int(config.get('SECURITY_FAILED_LOGIN_WINDOW_MINUTES', 15)))
    already_alerted_key = f'paxalia:brute_force_alerted:{ip_address}'
    if cache.get(already_alerted_key):
        return
    window_start = timezone.now() - timedelta(minutes=window_minutes)
    recent_failures = LoginEvent.objects.filter(
        ip_address=ip_address, event_type='login', result='failed', created_at__gte=window_start
    ).count()
    if recent_failures >= threshold:
        cache.set(already_alerted_key, True, timeout=window_minutes * 60)
        send_security_alert(
            subject=f'Possible brute-force from {ip_address}',
            message=(
                f'{recent_failures} failed login attempts from {ip_address} '
                f'in the last {window_minutes} minutes (threshold: {threshold}).'
            ),
            alert_type='brute_force_suspected',
        )


def _resolve_failed_attempt_user(credentials):
    """Best-effort account lookup for classification only.

    A failed password attempt against an existing staff account should be
    visible in the Admin activity view. We retain the username itself only
    when SECURITY_STORE_FAILED_USERNAME is enabled; the lookup merely lets
    us set the existing account FK/is_admin flag.
    """
    if not credentials:
        return None
    identifier = credentials.get('username', '')
    if not identifier:
        return None
    try:
        return User.objects.filter(username=str(identifier)).only(
            'pk', 'is_staff', 'is_superuser'
        ).first()
    except Exception:
        return None


def handle_login_failed(sender, credentials, request=None, **kwargs):
    try:
        username = credentials.get('username', '') if credentials else ''
        matched_user = _resolve_failed_attempt_user(credentials)
        event, _ = _record_login(
            matched_user, request, result='failed',
            failure_category='invalid_credentials', username_attempted=str(username),
        )
        _maybe_alert_brute_force(event.ip_address)
    except Exception:
        logger.exception('Failed to record failed LoginEvent')


def register_signals():
    user_logged_in.connect(handle_login, dispatch_uid='analytics_login_event')
    user_logged_out.connect(handle_logout, dispatch_uid='analytics_logout_event')
    user_login_failed.connect(handle_login_failed, dispatch_uid='analytics_login_failed_event')
