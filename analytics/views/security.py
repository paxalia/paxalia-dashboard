# analytics/views/security.py
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import BlockedIP, LoginEvent, SecurityAuditLog
from ..security_audit import log_action
from .utils import section_enabled

User = get_user_model()


@staff_member_required
def security_center(request):
    """
    Single page combining every Security Center subsection. Mirrors the
    pattern used by backup_management(): one view, tabbed sections
    switched client-side (see static/analytics/scripts/security.js),
    so every action lives on one URL and there's no page reload between
    tabs.
    """
    if not section_enabled('security'):
        raise Http404

    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    # ── Login Activity ──
    recent_logins = LoginEvent.objects.select_related('user').filter(
        created_at__gte=last_30_days
    )[:200]

    total_success_30d = LoginEvent.objects.filter(
        result='success', created_at__gte=last_30_days
    ).count()
    total_failed_30d = LoginEvent.objects.filter(
        result='failed', created_at__gte=last_30_days
    ).count()
    new_location_logins_30d = LoginEvent.objects.filter(
        result='success', is_new_location=True, created_at__gte=last_30_days
    ).count()

    # ── Active Sessions (successful logins with no logout yet, last 30 days) ──
    active_sessions = LoginEvent.objects.select_related('user').filter(
        result='success',
        logged_out_at__isnull=True,
        created_at__gte=last_30_days,
    ).exclude(session_key='').exclude(session_key__isnull=True)[:100]

    # ── Failed-login / brute-force monitor ──
    failed_by_ip = (
        LoginEvent.objects.filter(result='failed', created_at__gte=last_30_days)
        .exclude(ip_address__isnull=True)
        .values('ip_address')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    failed_by_username = (
        LoginEvent.objects.filter(result='failed', created_at__gte=last_30_days)
        .exclude(username_attempted='')
        .values('username_attempted')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )

    # ── IP Blocklist ──
    blocked_ips = BlockedIP.objects.all()[:200]

    # ── Admin action audit log ──
    audit_entries = SecurityAuditLog.objects.select_related('user').filter(
        created_at__gte=last_30_days
    )[:200]

    context = {
        'active_page': 'security',
        'page_title': _('Security Center'),
        'page_subtitle': _('Login activity, sessions, and admin audit log'),
        'recent_logins': recent_logins,
        'total_success_30d': total_success_30d,
        'total_failed_30d': total_failed_30d,
        'new_location_logins_30d': new_location_logins_30d,
        'active_sessions': active_sessions,
        'failed_by_ip': failed_by_ip,
        'failed_by_username': failed_by_username,
        'blocked_ips': blocked_ips,
        'audit_entries': audit_entries,
    }
    return render(request, 'analytics/security.html', context)


@staff_member_required
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
    return redirect('analytics:security')


@staff_member_required
@require_POST
def security_block_ip(request):
    ip_address = request.POST.get('ip_address', '').strip()
    reason = request.POST.get('reason', '').strip()[:255]
    if not ip_address:
        messages.error(request, _('IP address is required.'))
        return redirect('analytics:security')

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
    return redirect('analytics:security')


@staff_member_required
@require_POST
def security_unblock_ip(request, block_id):
    blocked = get_object_or_404(BlockedIP, id=block_id)
    blocked.active = False
    blocked.save(update_fields=['active'])
    log_action(request, 'security.ip_unblocked', detail=f'ip={blocked.ip_address}')
    messages.success(request, _('IP address unblocked.'))
    return redirect('analytics:security')
