# paxalia/views/security.py
import django
from datetime import timedelta

from django.contrib import messages
from paxalia.permissions import require_section_permission
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import BlockedIP, LoginEvent, SecurityAuditLog, CSPViolation
from ..settings import get_config
from ..security_audit import log_action
from ..security_scorecard import run_scorecard_checks
from ..security_health import run_security_health_checks
from ..admin_security import current_device_credential
from .utils import section_enabled

User = get_user_model()

# Best-effort, manually-maintained EOL reference for Django's currently
# supported release lines. Not a live CVE feed — just enough to flag
# "you're on an unsupported version" at a glance. Update as new LTS/
# feature releases ship. See https://www.djangoproject.com/download/#supported-versions
_DJANGO_SUPPORTED_MINORS = {
    (4, 2): "April 2026 (LTS)",
    (5, 1): "December 2025",
    (5, 2): "April 2028 (LTS)",
}


def _dependency_health():
    current = django.VERSION[:2]
    supported = current in _DJANGO_SUPPORTED_MINORS
    return {
        'django_version': django.get_version(),
        'django_supported': supported,
        'django_eol_note': _DJANGO_SUPPORTED_MINORS.get(current, 'Unknown — check djangoproject.com/download/#supported-versions'),
    }


def _mfa_status():
    """Best-effort MFA status per staff user, if django_otp is installed.
    Returns None (not an empty list) when django_otp isn't available, so
    the template can distinguish "not installed" from "installed, 0 devices"."""
    try:
        from django_otp import devices_for_user
    except ImportError:
        return None

    try:
        staff_users = User.objects.filter(is_staff=True).order_by('username')
    except Exception:
        return []
    rows = []
    for user in staff_users:
        try:
            has_device = any(True for _d in devices_for_user(user, confirmed=True))
        except Exception:
            has_device = False
        rows.append({'user': user, 'mfa_enabled': has_device})
    return rows


def _runtime_security_snapshot():
    """Best-effort runtime/host posture; never makes the Security Center 500."""
    import os
    import platform
    import socket
    from importlib.metadata import PackageNotFoundError, version as package_version

    try:
        import psutil
    except ImportError:
        psutil = None

    try:
        installed_version = package_version('paxalia-dashboard')
    except PackageNotFoundError:
        installed_version = 'development/source tree'
    except Exception:
        installed_version = 'unknown'

    middleware = list(getattr(__import__('django.conf', fromlist=['settings']).settings, 'MIDDLEWARE', []) or [])
    middleware_names = {m.rsplit('.', 1)[-1] for m in middleware}

    snapshot = {
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'python': platform.python_version(),
        'django': django.get_version(),
        'dashboard_version': installed_version,
        'environment': getattr(__import__('django.conf', fromlist=['settings']).settings, 'ENVIRONMENT', os.environ.get('ENVIRONMENT', 'unknown')),
        'debug': bool(getattr(__import__('django.conf', fromlist=['settings']).settings, 'DEBUG', False)),
        'db_vendor': 'unknown',
        'secure_ssl_redirect': bool(getattr(__import__('django.conf', fromlist=['settings']).settings, 'SECURE_SSL_REDIRECT', False)),
        'session_cookie_secure': bool(getattr(__import__('django.conf', fromlist=['settings']).settings, 'SESSION_COOKIE_SECURE', False)),
        'csrf_cookie_secure': bool(getattr(__import__('django.conf', fromlist=['settings']).settings, 'CSRF_COOKIE_SECURE', False)),
        'security_block_middleware': 'SecurityBlockMiddleware' in middleware_names,
        'slow_query_middleware': 'SlowQueryMiddleware' in middleware_names,
        'os_users': [],
        'memory_percent': None,
        'disk_percent': None,
    }

    try:
        from django.db import connection
        snapshot['db_vendor'] = connection.vendor
    except Exception:
        pass

    if psutil is not None:
        try:
            snapshot['memory_percent'] = round(psutil.virtual_memory().percent, 1)
        except Exception:
            pass
        try:
            root_usage = psutil.disk_usage(os.path.abspath(os.sep))
            snapshot['disk_percent'] = round(root_usage.percent, 1)
        except Exception:
            pass
        try:
            # Names and login times only; no terminal/device secrets or commands.
            snapshot['os_users'] = [
                {
                    'name': u.name,
                    'terminal': u.terminal or '—',
                    'host': u.host or '—',
                    'started': timezone.datetime.fromtimestamp(u.started, tz=timezone.get_current_timezone()),
                }
                for u in psutil.users()
            ]
        except Exception:
            snapshot['os_users'] = []
    return snapshot


@require_section_permission('security')
def security_center(request):
    """
    Single page combining every Security Center subsection. Mirrors the
    pattern used by backup_management(): one view, tabbed sections
    switched client-side (see static/paxalia/scripts/security.js),
    so every action lives on one URL and there's no page reload between
    tabs.
    """
    if not section_enabled('security'):
        raise Http404

    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    # ── Login Activity ──
    recent_logins = LoginEvent.objects.select_related('user', 'admin_device').filter(
        event_type='login', created_at__gte=last_30_days
    )[:200]

    login_base = LoginEvent.objects.filter(
        event_type='login',
        created_at__gte=last_30_days,
    )
    login_counts = login_base.aggregate(
        total_success=Count('id', filter=Q(result='success')),
        total_failed=Count('id', filter=Q(result='failed')),
        new_locations=Count('id', filter=Q(result='success', is_new_location=True)),
        admin_success=Count('id', filter=Q(result='success', is_admin=True)),
        admin_failed=Count('id', filter=Q(result='failed', is_admin=True)),
        unknown_account_failures=Count(
            'id',
            filter=Q(result='failed', failure_category='invalid_credentials', user__isnull=True),
        ),
    )
    total_success_30d = login_counts['total_success'] or 0
    total_failed_30d = login_counts['total_failed'] or 0
    new_location_logins_30d = login_counts['new_locations'] or 0
    admin_success_30d = login_counts['admin_success'] or 0
    admin_failed_30d = login_counts['admin_failed'] or 0
    unknown_account_failures_30d = login_counts['unknown_account_failures'] or 0

    # ── Active Sessions (successful logins with no logout yet, last 30 days) ──
    active_sessions = LoginEvent.objects.select_related('user', 'admin_device').filter(
        event_type='login', result='success',
        logged_out_at__isnull=True,
        created_at__gte=last_30_days,
    ).exclude(session_key='').exclude(session_key__isnull=True)[:100]

    # ── Failed-login / brute-force monitor ──
    failed_by_ip = (
        LoginEvent.objects.filter(event_type='login', result='failed', created_at__gte=last_30_days)
        .exclude(ip_address__isnull=True)
        .values('ip_address')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    failed_identifier_field = 'username_attempted' if get_config().get('SECURITY_STORE_FAILED_USERNAME', False) else 'identifier_hash'
    failed_by_username = (
        LoginEvent.objects.filter(event_type='login', result='failed', created_at__gte=last_30_days)
        .exclude(**{failed_identifier_field: ''})
        .values(failed_identifier_field)
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    # ── IP Blocklist ──
    blocked_ips = BlockedIP.objects.all()[:200]

    # ── Admin action audit log ──
    audit_entries = SecurityAuditLog.objects.select_related('user').filter(
        created_at__gte=last_30_days
    )[:200]

    # ── CSP violations ──
    csp_violations = CSPViolation.objects.filter(created_at__gte=last_30_days)[:200]

    context = {
        'active_page': 'security',
        'page_title': _('Security Center'),
        'page_subtitle': _('Login activity, sessions, and admin audit log'),
        'recent_logins': recent_logins,
        'total_success_30d': total_success_30d,
        'total_failed_30d': total_failed_30d,
        'new_location_logins_30d': new_location_logins_30d,
        'admin_success_30d': admin_success_30d,
        'admin_failed_30d': admin_failed_30d,
        'unknown_account_failures_30d': unknown_account_failures_30d,
        'active_sessions': active_sessions,
        'failed_by_ip': failed_by_ip,
        'failed_by_username': failed_by_username,
        'blocked_ips': blocked_ips,
        'audit_entries': audit_entries,
        'csp_violations': csp_violations,
        'dependency_health': _dependency_health(),
        'scorecard': run_scorecard_checks(),
        'runtime_security': _runtime_security_snapshot(),
        'security_health': run_security_health_checks(request),
        'current_admin_device': current_device_credential(request),
    }
    return render(request, 'paxalia/security.html', context)


@require_section_permission('security')
@require_POST
def security_revoke_session(request, login_event_id):
    """Force-logout the session tied to a LoginEvent, if it's still live.

    NOTE: this deletes the Django session row, which only takes effect
    for the default DB-backed session engine. If the project uses a
    different SESSION_ENGINE (cache, signed cookies), sessions can't be
    revoked server-side this way — see the note in security.html.
    """
    event = get_object_or_404(LoginEvent, id=login_event_id)
    revoked = False
    if event.session_key:
        deleted, _unused = Session.objects.filter(pk=event.session_key).delete()
        revoked = deleted > 0
    if not event.logged_out_at:
        event.logged_out_at = timezone.now()
        event.save(update_fields=['logged_out_at'])

    log_action(
        request, 'security.session_revoked',
        detail=f'login_event_id={event.id} user={event.user} revoked={revoked}',
    )
    messages.success(request, _('Session revoked.') if revoked else _('Session already expired.'))
    return redirect('paxalia:security')


@require_section_permission('security')
@require_POST
def security_block_ip(request):
    ip_address = request.POST.get('ip_address', '').strip()
    reason = request.POST.get('reason', '').strip()[:255]
    if not ip_address:
        messages.error(request, _('IP address is required.'))
        return redirect('paxalia:security')

    obj, created = BlockedIP.objects.get_or_create(
        ip_address=ip_address,
        defaults={'reason': reason, 'created_by': request.user, 'active': True},
    )
    if not created:
        obj.active = True
        obj.reason = reason or obj.reason
        obj.save(update_fields=['active', 'reason'])

    log_action(request, 'security.ip_blocked', detail=f'ip={ip_address} reason={reason}')
    messages.success(request, _('IP address blocked.'))
    return redirect('paxalia:security')


@require_section_permission('security')
@require_POST
def security_unblock_ip(request, block_id):
    blocked = get_object_or_404(BlockedIP, id=block_id)
    blocked.active = False
    blocked.save(update_fields=['active'])
    log_action(request, 'security.ip_unblocked', detail=f'ip={blocked.ip_address}')
    messages.success(request, _('IP address unblocked.'))
    return redirect('paxalia:security')
