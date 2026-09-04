# analytics/signals.py
"""
Populates LoginEvent from Django's built-in authentication signals.

No custom auth backend or middleware is needed for this — user_logged_in,
user_logged_out, and user_login_failed already fire for the project's
existing login view(s) (including django.contrib.admin's login form),
so this "just works" once analytics.apps.AnalyticsConfig.ready() wires
these handlers up.
"""
import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.utils import timezone

from .middleware import AnalyticsMiddleware, _resolve_ip
from .models import LoginEvent
from .settings import get_config
from .views.utils import parse_user_agent

logger = logging.getLogger('analytics.security')


def _should_track(user):
    """Respect SECURITY_TRACK_ONLY_STAFF (default True) — this is a
    privacy-first package, so by default we only log privileged accounts,
    not every regular site visitor's login."""
    config = get_config()
    if not config.get('SECURITY_TRACK_ONLY_STAFF', True):
        return True
    return bool(user and (user.is_staff or user.is_superuser))


def _request_context(request):
    """Best-effort extraction of IP/UA/geo from the request. Never raises —
    a broken login log must never break login itself."""
    ip = None
    ua_string = ''
    try:
        if request is not None:
            ip = AnalyticsMiddleware._get_ip(request)
            ua_string = request.META.get('HTTP_USER_AGENT', '')[:512]
    except Exception:
        logger.exception('Failed to extract request context for LoginEvent')

    country_code = country_name = city = ''
    if ip:
        try:
            country_code, country_name, city = _resolve_ip(ip)
        except Exception:
            pass

    ua = parse_user_agent(ua_string)
    return {
        'ip_address': ip or None,
        'user_agent': ua_string,
        'browser': ua['browser'],
        'os': ua['os'],
        'device': ua['device'],
        'country_code': country_code or '',
        'country_name': country_name or '',
        'city': city or '',
    }


def _is_new_location(user, ip_address):
    if not user or not ip_address:
        return False
    return not LoginEvent.objects.filter(
        user=user, ip_address=ip_address, result='success'
    ).exists()


def handle_login(sender, request, user, **kwargs):
    if not _should_track(user):
        return
    try:
        ctx = _request_context(request)
        new_location = _is_new_location(user, ctx['ip_address'])
        LoginEvent.objects.create(
            user=user,
            username_attempted=getattr(user, 'get_username', lambda: '')(),
            result='success',
            session_key=getattr(getattr(request, 'session', None), 'session_key', '') or '',
            is_new_location=new_location,
            **ctx,
        )
    except Exception:
        # A logging failure must never prevent a legitimate login.
        logger.exception('Failed to record successful LoginEvent')


def handle_logout(sender, request, user, **kwargs):
    if user is None or not _should_track(user):
        return
    try:
        session_key = getattr(getattr(request, 'session', None), 'session_key', '') or ''
        qs = LoginEvent.objects.filter(
            user=user, result='success', logged_out_at__isnull=True
        )
        if session_key:
            qs = qs.filter(session_key=session_key)
        event = qs.order_by('-created_at').first()
        if event:
            event.logged_out_at = timezone.now()
            event.save(update_fields=['logged_out_at'])
    except Exception:
        logger.exception('Failed to record logout on LoginEvent')


def handle_login_failed(sender, credentials, request=None, **kwargs):
    # We can't know is_staff for a failed attempt (no user resolved), so
    # failed attempts are always recorded when SECURITY_TRACK_ONLY_STAFF
    # matters least — a brute-force attempt against a staff username is
    # exactly what we want visibility into, and it costs nothing to store.
    try:
        username = credentials.get('username', '') if credentials else ''
        ctx = _request_context(request)
        LoginEvent.objects.create(
            user=None,
            username_attempted=str(username)[:255],
            result='failed',
            failure_reason='invalid_credentials',
            **ctx,
        )
    except Exception:
        logger.exception('Failed to record failed LoginEvent')


def register_signals():
    user_logged_in.connect(handle_login, dispatch_uid='analytics_login_event')
    user_logged_out.connect(handle_logout, dispatch_uid='analytics_logout_event')
    user_login_failed.connect(handle_login_failed, dispatch_uid='analytics_login_failed_event')
