"""Paxalia administrator devices, sessions, and security configuration views."""
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.sessions.models import Session
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.db.models import Count, Max, Q

from ..admin_security import admin_security_required, current_device_credential, current_paxalia_session_id
from ..logging import log as paxalia_log
from ..models import LoginEvent, PaxaliaDevice, PaxaliaDeviceCredential, PaxaliaRecoveryCode
from ..security_audit import log_action
from ..security_health import run_security_health_checks
from ..settings import get_config
from .auth import _generate_recovery_codes, _has_confirmed_totp



def _flash(request, level, message):
    """Add a Django flash message when MessageMiddleware is installed.

    The dashboard always has MessageMiddleware in normal operation. The guard
    also makes these mutating views safe to exercise directly with RequestFactory,
    which intentionally does not install the messages middleware.
    """
    if getattr(request, "_messages", None) is None:
        return False
    getattr(messages, level)(request, message)
    return True


def _delete_session_keys(session_keys):
    """Delete DB-backed Django sessions in bounded batches."""
    keys = [key for key in session_keys if key]
    deleted = 0
    for start in range(0, len(keys), 500):
        batch = keys[start:start + 500]
        if batch:
            count, _ = Session.objects.filter(session_key__in=batch).delete()
            deleted += count
    return deleted



def _event_session_keys(queryset):
    """Collect session keys without relying on an arbitrary fixed result cap."""
    keys = []
    for key in (
        queryset.exclude(session_key="")
        .exclude(session_key__isnull=True)
        .values_list("session_key", flat=True)
        .iterator(chunk_size=500)
    ):
        keys.append(key)
    return keys


def _host_auth_enabled():
    return bool(get_config().get("AUTH_USE_HOST_LOGIN", False))


@admin_security_required
def security_overview(request):
    config = get_config()
    health = run_security_health_checks(request)
    return render(request, "paxalia/security_overview.html", {
        "active_page": "security_overview",
        "page_title": _("Security Overview"),
        "page_subtitle": _("Effective security controls, configuration state, and administrator access protection"),
        "security_health": health,
        "current_device": current_device_credential(request),
        "admin_device_count": PaxaliaDevice.objects.filter(user=request.user, status="active").count(),
        "recovery_codes_remaining": PaxaliaRecoveryCode.objects.filter(
            user=request.user, used_at__isnull=True, revoked_at__isnull=True
        ).count(),
        "totp_enabled": _has_confirmed_totp(request.user),
        "session_max_age": max(60, int(config.get("ADMIN_SESSION_MAX_AGE_SECONDS", 8 * 60 * 60))),
    })


@admin_security_required
def security_authentication(request):
    config = get_config()
    return render(request, "paxalia/security_authentication.html", {
        "active_page": "security_authentication",
        "page_title": _("Authentication & Recovery"),
        "page_subtitle": _("Manage the mandatory second factor and recovery controls for your administrator account"),
        "totp_enabled": _has_confirmed_totp(request.user),
        "recovery_codes_remaining": PaxaliaRecoveryCode.objects.filter(
            user=request.user, used_at__isnull=True, revoked_at__isnull=True
        ).count(),
        "current_device": current_device_credential(request),
        "max_devices": max(1, int(config.get("ADMIN_MAX_DEVICES", 5))),
        "login_limit": max(1, int(config.get("SECURITY_LOGIN_RATE_LIMIT_ATTEMPTS", 8))),
        "login_window": max(1, int(config.get("SECURITY_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 900))),
        "twofa_limit": max(1, int(config.get("SECURITY_2FA_RATE_LIMIT_ATTEMPTS", 5))),
        "twofa_window": max(1, int(config.get("SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS", 300))),
        "device_limit": max(1, int(config.get("SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS", 5))),
        "device_window": max(1, int(config.get("SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS", 300))),
        "session_max_age": max(60, int(config.get("ADMIN_SESSION_MAX_AGE_SECONDS", 8 * 60 * 60))),
        "challenge_ttl": max(30, int(config.get("WEBAUTHN_CHALLENGE_TTL_SECONDS", 120))),
        "password_change_enabled": bool(config.get("AUTH_PASSWORD_CHANGE_ENABLED", True)),
        "webauthn_rp_id": config.get("WEBAUTHN_RP_ID"),
        "webauthn_origin": config.get("WEBAUTHN_ORIGIN"),
    })


@admin_security_required
def admin_devices(request):
    devices = list(
        PaxaliaDevice.objects.filter(user=request.user).prefetch_related("credential")
    )
    current = current_device_credential(request)
    return render(request, "paxalia/admin_devices.html", {
        "active_page": "admin_devices",
        "page_title": _("Admin Devices"),
        "page_subtitle": _("Authorized authenticators for this administrator"),
        "devices": devices,
        "current_device": current.device if current else None,
        "max_devices": max(1, int(get_config().get("ADMIN_MAX_DEVICES", 5))),
    })


@admin_security_required
def security_admins(request):
    """Show the security state of every staff administrator without exposing secrets."""
    now = timezone.now()
    cutoff = now - timedelta(days=30)
    user_model = get_user_model()

    admins = list(
        user_model.objects.filter(is_staff=True)
        .annotate(
            active_device_count=Count(
                "paxalia_devices",
                filter=Q(paxalia_devices__status="active"),
                distinct=True,
            ),
            active_session_count=Count(
                "login_events",
                filter=Q(
                    login_events__event_type="login",
                    login_events__result="success",
                    login_events__is_admin=True,
                    login_events__logged_out_at__isnull=True,
                ),
                distinct=True,
            ),
            last_admin_login=Max(
                "login_events__created_at",
                filter=Q(
                    login_events__event_type="login",
                    login_events__result="success",
                    login_events__is_admin=True,
                ),
            ),
            failed_admin_logins_30d=Count(
                "login_events",
                filter=Q(
                    login_events__event_type="login",
                    login_events__result="failed",
                    login_events__is_admin=True,
                    login_events__created_at__gte=cutoff,
                ),
                distinct=True,
            ),
        )
        .order_by("username")
    )

    rows = []
    for admin in admins:
        rows.append({
            "user": admin,
            "is_current": admin.pk == request.user.pk,
            "account_active": bool(getattr(admin, "is_active", False)),
            "totp_enabled": _has_confirmed_totp(admin),
            "active_device_count": int(getattr(admin, "active_device_count", 0) or 0),
            "active_session_count": int(getattr(admin, "active_session_count", 0) or 0),
            "last_admin_login": getattr(admin, "last_admin_login", None),
            "failed_admin_logins_30d": int(getattr(admin, "failed_admin_logins_30d", 0) or 0),
        })

    return render(request, "paxalia/security_admins.html", {
        "active_page": "security_admins",
        "page_title": _("Administrator Security"),
        "page_subtitle": _(
            "Layer status, authorized devices, sessions, and recent administrator access across all staff accounts"
        ),
        "admin_rows": rows,
        "administrator_count": len(rows),
    })


@admin_security_required
@require_POST
def admin_device_rename(request, device_id):
    device = get_object_or_404(PaxaliaDevice, pk=device_id, user=request.user)
    name = str(request.POST.get("device_name", "")).strip()[:120]
    if not name:
        _flash(request, "error", _("A device name is required."))
        return redirect("paxalia:admin_devices")
    if device.display_name == name:
        _flash(request, "info", _("The device name is already set to that value."))
        return redirect("paxalia:admin_devices")

    device.display_name = name
    device.save(update_fields=["display_name"])
    log_action(request, "security.admin_device_renamed", detail=f"device={device.id}")
    paxalia_log(
        "Administrator device renamed",
        level="INFO",
        source="Security",
        category="authentication",
        action="admin_device_renamed",
        request=request,
        metadata={"device_id": str(device.id)},
    )
    _flash(request, "success", _("Admin device renamed."))
    return redirect("paxalia:admin_devices")


@admin_security_required
@require_POST
def admin_device_revoke(request, device_id):
    device = get_object_or_404(PaxaliaDevice, pk=device_id, user=request.user)
    if device.status != "active":
        _flash(request, "info", _("That device is already inactive."))
        return redirect("paxalia:admin_devices")

    now = timezone.now()
    device.status = "revoked"
    device.revoked_at = now
    device.save(update_fields=["status", "revoked_at"])

    event_rows = LoginEvent.objects.filter(
        user=request.user,
        admin_device=device,
        event_type="login",
        result="success",
        logged_out_at__isnull=True,
    )
    if _host_auth_enabled():
        session_keys = _event_session_keys(event_rows)
        deleted_sessions = _delete_session_keys(session_keys) if session_keys else 0
    else:
        # In isolated mode these LoginEvent rows are the revocation source of
        # truth. Do not delete Django sessions because they may also carry the
        # host site's ordinary authentication state.
        deleted_sessions = 0
    event_rows.update(logged_out_at=now)

    log_action(request, "security.admin_device_revoked", detail=f"device={device.id}")
    paxalia_log(
        "Administrator device revoked",
        level="WARNING",
        source="Security",
        category="authentication",
        action="admin_device_revoked",
        request=request,
        metadata={"device_id": str(device.id), "sessions_revoked": deleted_sessions},
    )

    current = current_device_credential(request)
    if current and current.device_id == device.id:
        if _host_auth_enabled():
            logout(request)
        else:
            # Flush only Paxalia's dedicated dashboard session. The website's
            # separate Django session cookie is never touched.
            request.session.flush()
        return redirect("paxalia:auth_login")
    _flash(request, "success", _("Admin device revoked."))
    return redirect("paxalia:admin_devices")


@admin_security_required
def admin_sessions(request):
    now = timezone.now()
    cutoff = now - timedelta(days=30)
    sessions = list(
        LoginEvent.objects.select_related("admin_device", "user").filter(
            user=request.user,
            event_type="login",
            result="success",
            logged_out_at__isnull=True,
            created_at__gte=cutoff,
        )
        .exclude(session_key="")
        .exclude(session_key__isnull=True)
        .order_by("-created_at")[:100]
    )
    current_key = current_paxalia_session_id(request)
    return render(request, "paxalia/admin_sessions.html", {
        "active_page": "admin_sessions",
        "page_title": _("Admin Sessions"),
        "page_subtitle": _("Active privileged sessions and their authorized device context"),
        "sessions": sessions,
        "current_session_key": current_key,
    })


@admin_security_required
@require_POST
def admin_session_revoke(request, login_event_id):
    event = get_object_or_404(
        LoginEvent,
        pk=login_event_id,
        user=request.user,
        event_type="login",
        result="success",
    )
    session_deleted = False
    if _host_auth_enabled() and event.session_key:
        deleted, _session_details = Session.objects.filter(session_key=event.session_key).delete()
        session_deleted = deleted > 0

    event.logged_out_at = event.logged_out_at or timezone.now()
    event.save(update_fields=["logged_out_at"])
    log_action(request, "security.admin_session_revoked", detail=f"login_event_id={event.id}")
    paxalia_log(
        "Administrator session revoked",
        level="WARNING",
        source="Security",
        category="authentication",
        action="admin_session_revoked",
        request=request,
        metadata={"login_event_id": str(event.id)},
    )
    if event.session_key == current_paxalia_session_id(request):
        if _host_auth_enabled():
            logout(request)
        else:
            # Revoke and flush only the Paxalia dashboard session.
            request.session.flush()
        return redirect("paxalia:auth_login")
    _flash(
        request,
        "success",
        _("Admin session revoked.") if session_deleted else _("Admin session already expired."),
    )
    return redirect("paxalia:admin_sessions")


@admin_security_required
@require_POST
def admin_sessions_revoke_others(request):
    current_key = current_paxalia_session_id(request)
    events = (
        LoginEvent.objects.filter(
            user=request.user,
            event_type="login",
            result="success",
            logged_out_at__isnull=True,
        )
        .exclude(session_key=current_key)
    )
    if _host_auth_enabled():
        keys = _event_session_keys(events)
        deleted_sessions = _delete_session_keys(keys) if keys else 0
    else:
        deleted_sessions = 0
    now = timezone.now()
    events.update(logged_out_at=now)
    log_action(request, "security.admin_sessions_revoked_others", detail=f"count={deleted_sessions}")
    paxalia_log(
        "Other administrator sessions revoked",
        level="WARNING",
        source="Security",
        category="authentication",
        action="admin_sessions_revoked_others",
        request=request,
        metadata={"count": deleted_sessions},
    )
    _flash(request, "success", _("Other administrator sessions have been revoked."))
    return redirect("paxalia:admin_sessions")


@admin_security_required
@require_POST
def admin_sessions_revoke_all(request):
    events = LoginEvent.objects.filter(
        user=request.user,
        event_type="login",
        result="success",
        logged_out_at__isnull=True,
    )
    if _host_auth_enabled():
        keys = _event_session_keys(events)
        deleted_sessions = _delete_session_keys(keys) if keys else 0
    else:
        deleted_sessions = 0
    now = timezone.now()
    events.update(logged_out_at=now)
    log_action(request, "security.admin_sessions_revoked_all", detail=f"count={deleted_sessions}")
    paxalia_log(
        "All administrator sessions revoked",
        level="CRITICAL",
        source="Security",
        category="authentication",
        action="admin_all_sessions_revoked",
        request=request,
        metadata={"count": deleted_sessions},
    )
    if _host_auth_enabled():
        logout(request)
    else:
        request.session.flush()
    return redirect("paxalia:auth_login")

