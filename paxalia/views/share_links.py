# paxalia/views/share_links.py
import hashlib

from django.contrib import messages
from ..admin_security import admin_security_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from paxalia.models import ShareLink
from paxalia.reporting import compute_overview_snapshot
from paxalia.security_audit import log_action
from paxalia.security_rate_limit import allowed as rate_allowed, clear as rate_clear
from paxalia.middleware import AnalyticsMiddleware

from .utils import section_enabled, get_current_site, scoped_object_or_404


def _hash_password(raw):
    return make_password(raw)


def _check_password(raw, encoded):
    if not encoded:
        return not raw
    if check_password(raw, encoded):
        return True, False
    # Backward compatibility for v3 hashes created before the secure hash
    # migration.  Upgrade the stored hash after a successful legacy match.
    legacy = hashlib.sha256(raw.encode()).hexdigest()
    return legacy == encoded, legacy == encoded


SHARE_PASSWORD_RATE_LIMIT_ATTEMPTS = 10
SHARE_PASSWORD_RATE_LIMIT_WINDOW_SECONDS = 300
SHARE_VIEW_WRITE_THROTTLE_SECONDS = 60


# ─── Staff-side management ─────────────────────────────────────────

@admin_security_required
def share_links_management(request):
    if not section_enabled('share_links'):
        raise Http404

    current_site = get_current_site(request)

    if request.method == 'POST' and 'save_link' in request.POST:
        name = request.POST.get('name', '').strip()
        password = request.POST.get('password', '').strip()
        expires_days = request.POST.get('expires_days', '').strip()

        if not name:
            messages.error(request, _('Name is required.'))
        else:
            expires_at = None
            if expires_days:
                try:
                    expires_at = timezone.now() + timezone.timedelta(days=int(expires_days))
                except ValueError:
                    pass
            link = ShareLink.objects.create(
                site=current_site, name=name,
                password_hash=_hash_password(password) if password else '',
                expires_at=expires_at, created_by=request.user,
            )
            log_action(request, 'share_link.created', detail=f'name={name} id={link.id}')
            messages.success(request, _('Share link created.'))
        return redirect('paxalia:share_links')

    links = ShareLink.objects.select_related('site')
    if current_site is not None:
        links = links.filter(site=current_site)

    context = {
        'active_page': 'share_links',
        'page_title': _('Share Links'),
        'page_subtitle': _('Public, read-only links to a traffic snapshot — no login required to view'),
        'links': links,
        'show_search': False,
    }
    return render(request, 'paxalia/share_links.html', context)


@admin_security_required
@require_POST
def share_link_revoke(request, link_id):
    link = scoped_object_or_404(ShareLink, request, link_id)
    link.is_active = False
    link.save(update_fields=['is_active'])
    log_action(request, 'share_link.revoked', detail=f'name={link.name} id={link.id}')
    messages.success(request, _('Share link revoked.'))
    return redirect('paxalia:share_links')


@admin_security_required
@require_POST
def share_link_delete(request, link_id):
    link = scoped_object_or_404(ShareLink, request, link_id)
    name = link.name
    link.delete()
    log_action(request, 'share_link.deleted', detail=f'name={name}')
    messages.success(request, _('Share link deleted.'))
    return redirect('paxalia:share_links')


# ─── Public view — deliberately no @admin_security_required ─────────

def shared_dashboard_view(request, token):
    """
    Public, unauthenticated view. Access is gated by knowing the
    token (the ShareLink's UUID pk — 128 bits of randomness, same
    unguessable-token pattern this app already uses for every UUID
    primary key) plus, if set, a password. Never requires a login.
    """
    link = get_object_or_404(ShareLink, id=token)
    if not link.is_usable:
        raise Http404

    session_key = f'share_link_authed_{link.id}'
    if link.has_password and not request.session.get(session_key):
        if request.method == 'POST':
            ip = AnalyticsMiddleware._get_ip(request) or 'unknown'
            allowed, _remaining = rate_allowed(
                'share-link-password',
                SHARE_PASSWORD_RATE_LIMIT_ATTEMPTS,
                SHARE_PASSWORD_RATE_LIMIT_WINDOW_SECONDS,
                str(link.id),
                ip,
            )
            if not allowed:
                return render(request, 'paxalia/shared_dashboard.html', {
                    'link': link, 'needs_password': True, 'error': True,
                    'rate_limited': True,
                }, status=429)

            password = request.POST.get('password', '')
            valid, legacy_match = _check_password(password, link.password_hash)
            if valid:
                rate_clear('share-link-password', str(link.id), ip)
                request.session[session_key] = True
                if legacy_match:
                    ShareLink.objects.filter(pk=link.pk).update(
                        password_hash=_hash_password(password)
                    )
            else:
                return render(request, 'paxalia/shared_dashboard.html', {
                    'link': link, 'needs_password': True, 'error': True,
                })
        else:
            return render(request, 'paxalia/shared_dashboard.html', {
                'link': link, 'needs_password': True, 'error': False,
            })

    now = timezone.now()
    last_viewed_at = link.last_viewed_at
    if last_viewed_at is None or (now - last_viewed_at).total_seconds() >= SHARE_VIEW_WRITE_THROTTLE_SECONDS:
        ShareLink.objects.filter(pk=link.pk).update(last_viewed_at=now)

    end_dt = now
    start_dt = end_dt - timezone.timedelta(days=30)
    snapshot = compute_overview_snapshot(start_dt, end_dt, link.site)

    return render(request, 'paxalia/shared_dashboard.html', {
        'link': link, 'needs_password': False, 'snapshot': snapshot,
    })

