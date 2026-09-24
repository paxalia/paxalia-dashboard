"""Mandatory three-layer security gate for Paxalia Dashboard administration.

Layer 1: the configured Django authentication backend and password through
Paxalia's bundled administrator login flow by default.
Layer 2: a confirmed django-otp TOTP device or a one-time Paxalia recovery code.
Layer 3: an authorized Paxalia WebAuthn credential.

Only the final state is treated as an authenticated Paxalia Dashboard admin
session. Intermediate state is deliberately stored in separate, non-privileged
session keys and cannot be used by protected dashboard views.
"""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from functools import wraps
from hashlib import sha256
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.core.exceptions import DisallowedHost, PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, resolve_url
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.http import url_has_allowed_host_and_scheme

from .models import LoginEvent, PaxaliaDevice, PaxaliaDeviceCredential
from .settings import get_config

ADMIN_FINAL_KEY = "paxalia.admin.authenticated"
ADMIN_USER_KEY = "paxalia.admin.pending_user_id"
ADMIN_BACKEND_KEY = "paxalia.admin.pending_backend"
ADMIN_STAGE_KEY = "paxalia.admin.stage"
ADMIN_AUTH_AT_KEY = "paxalia.admin.authenticated_at"
ADMIN_DEVICE_KEY = "paxalia.admin.device_credential"
ADMIN_INTENT_KEY = "paxalia.admin.login_intent"
ADMIN_HOST_AUTH_PENDING_KEY = "paxalia.admin.host_auth_pending"
ADMIN_HOST_2FA_PENDING_KEY = "paxalia.admin.host_2fa_pending_at"
ADMIN_NEXT_KEY = "paxalia.admin.safe_next"
ADMIN_DEVICE_NAME_KEY = "paxalia.admin.pending_device_name"
ADMIN_ISOLATED_SESSION_KEY = "paxalia.admin.isolated_session_id"

STAGE_PRIMARY = "primary"
STAGE_2FA = "2fa"
STAGE_DEVICE = "device"
STAGE_COMPLETE = "complete"

# Package-owned TOTP device names. The legacy name is retained so existing
# Paxalia installations do not have to re-enroll solely because the auth
# boundary was isolated from the host site. Host sites should keep their own
# two-factor device names separate.
PAXALIA_TOTP_DEVICE_NAMES = (
    "Paxalia Dashboard Authenticator",
    "Paxalia Authenticator",
)


def admin_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    checker = get_config().get("SECURITY_ADMIN_USER_CHECK")
    if callable(checker):
        try:
            return bool(checker(user))
        except Exception:
            return False
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def host_authentication_enabled() -> bool:
    """Return whether Paxalia should use the host application's login flow."""
    return bool(get_config().get("AUTH_USE_HOST_LOGIN", False))


def _safe_path(value: str | None, request, default: str | None = None) -> str:
    candidate = str(value or "")
    try:
        allowed_hosts = {request.get_host()}
    except DisallowedHost:
        # A malformed/untrusted Host header must never turn URL-safety
        # validation into an application error. Treat it as having no
        # trusted absolute redirect host and fall back to the dashboard.
        allowed_hosts = set()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts=allowed_hosts,
        require_https=request.is_secure(),
    ):
        parsed = urlsplit(candidate)
        if parsed.netloc:
            # The helper above already validates the host; return only a path
            # so a stored next value can never turn into an off-site redirect.
            return parsed.path + (("?" + parsed.query) if parsed.query else "")
        return candidate
    return default or reverse("paxalia:dashboard")


def _append_safe_next(url: str, request, next_url: str | None = None) -> str:
    """Attach a safe internal next path to a configured login URL."""
    safe_next = _safe_path(next_url or admin_home_url(request), request)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'next': safe_next})}"


def admin_home_url(request) -> str:
    """Return the canonical Paxalia admin destination without exposing config.

    AUTH_ADMIN_HOME_URL is intentionally consumed only on the server. It is
    never copied into template context, JavaScript, or a public config object.
    Invalid/external values are rejected and the named Paxalia dashboard URL
    remains the safe fallback.
    """
    configured = str(get_config().get("AUTH_ADMIN_HOME_URL") or "").strip()
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            configured = ""
        else:
            return _safe_path(configured, request, default=reverse("paxalia:dashboard"))
    return reverse("paxalia:dashboard")


def configured_host_login_url(request, next_url: str | None = None) -> str | None:
    """Return the host application's canonical login URL, when configured.

    Paxalia is embedded into existing Django applications. Those applications
    already own the primary credential page, so the dashboard should reuse it
    rather than maintain a competing password entry point.
    """
    config = get_config()
    if not bool(config.get("AUTH_USE_HOST_LOGIN", False)):
        return None

    target = config.get("AUTH_LOGIN_URL") or getattr(settings, "LOGIN_URL", None)
    if not target:
        return None

    try:
        resolved = resolve_url(target)
    except (NoReverseMatch, TypeError, ValueError):
        resolved = str(target).strip()

    if not resolved:
        return None

    # Never recurse back into Paxalia's own bundled login view when the host
    # deliberately points LOGIN_URL at that endpoint.
    try:
        paxalia_login_path = reverse("paxalia:auth_login")
        if str(resolved).rstrip("/") == paxalia_login_path.rstrip("/"):
            return None
    except Exception:
        pass

    return _append_safe_next(str(resolved), request, next_url)


def authentication_backend_for(request, user=None, *, required: bool = False) -> str:
    """Resolve the authentication backend associated with the current flow.

    In isolated mode this never derives the backend from the host's session or
    host backend list. The default is Django's local ModelBackend; a deployment
    may explicitly configure AUTH_ISOLATED_AUTHENTICATION_BACKENDS when it needs
    a custom credential source.

    In host compatibility mode, prefer the backend recorded for the current
    authentication flow, then Django's own session backend marker, and finally
    the transient ``User.backend`` attribute.
    """
    if not host_authentication_enabled():
        configured = get_config().get("AUTH_ISOLATED_AUTHENTICATION_BACKENDS")
        if isinstance(configured, str):
            configured = (configured,)
        configured = tuple(str(value).strip() for value in (configured or ()) if str(value).strip())
        if configured:
            return configured[0]
        return "django.contrib.auth.backends.ModelBackend"


    session = getattr(request, "session", None)
    get_session_value = getattr(session, "get", lambda key, default=None: default)
    candidates = (
        get_session_value(ADMIN_BACKEND_KEY),
        get_session_value(BACKEND_SESSION_KEY),
        getattr(user, "backend", None) if user is not None else None,
    )
    configured = tuple(getattr(settings, "AUTHENTICATION_BACKENDS", ()) or ())

    # Prefer an explicitly stored backend. It represents the backend that
    # authenticated the current/just-completed Layer-1 login. When the host
    # settings contain the backend, use it directly; otherwise verify that the
    # backend path is still loadable before accepting the persisted value.
    for candidate in candidates:
        candidate = str(candidate or "").strip()
        if not candidate:
            continue
        if not configured or candidate in configured:
            return candidate
        try:
            from django.contrib.auth import load_backend

            backend = load_backend(candidate)
        except (ImportError, AttributeError, TypeError, ValueError):
            continue
        if callable(getattr(backend, "get_user", None)):
            return candidate

    if len(configured) == 1:
        return str(configured[0])

    if required:
        raise ValueError(
            "Unable to determine the Django authentication backend for the "
            "Paxalia administrator session."
        )
    return ""


def begin_admin_verification(request, next_url: str | None = None):
    """Start or resume the Paxalia administrator verification flow.

    In isolated mode Paxalia owns Layer 1 as well as Layers 2/3. The host
    application's authenticated user is deliberately not accepted as a
    substitute for Paxalia Layer 1. In compatibility mode the host login is
    reused as Layer 1 and the response bridge handles the handoff.
    """
    target = _safe_path(
        next_url or request.session.get(ADMIN_NEXT_KEY) or admin_home_url(request),
        request,
    )

    if not host_authentication_enabled():
        pending_user_id = str(request.session.get(ADMIN_USER_KEY) or "")
        pending_stage = str(request.session.get(ADMIN_STAGE_KEY) or "")
        if pending_user_id and pending_stage in {STAGE_PRIMARY, STAGE_2FA, STAGE_DEVICE}:
            if pending_stage == STAGE_PRIMARY:
                return redirect("paxalia:auth_2fa_setup")
            if pending_stage == STAGE_2FA:
                return redirect("paxalia:auth_2fa_verify")
            return redirect("paxalia:auth_device_login")
        return redirect(_append_safe_next(reverse("paxalia:auth_login"), request, target))

    if not request.user.is_authenticated:
        mark_admin_intent(request, target)
        host_login = configured_host_login_url(request, target)
        if host_login:
            return redirect(host_login)
        login_url = reverse("paxalia:auth_login")
        return redirect(_append_safe_next(login_url, request, target))

    if not admin_user(request.user):
        raise PermissionDenied("You do not have access to Paxalia Dashboard administration.")

    pending_user_id = str(request.session.get(ADMIN_USER_KEY) or "")
    pending_stage = str(request.session.get(ADMIN_STAGE_KEY) or "")
    if pending_user_id == str(request.user.pk) and pending_stage in {STAGE_PRIMARY, STAGE_2FA, STAGE_DEVICE}:
        authentication_backend_for(request, request.user, required=True)
        request.session[ADMIN_INTENT_KEY] = True
        request.session[ADMIN_NEXT_KEY] = target
        request.session.modified = True
        if pending_stage == STAGE_PRIMARY:
            return redirect("paxalia:auth_2fa_setup")
        if pending_stage == STAGE_2FA:
            return redirect("paxalia:auth_2fa_verify")
        return redirect("paxalia:auth_device_login")

    clear_admin_security_state(request)
    backend = authentication_backend_for(request, request.user, required=True)
    set_pending_primary(request, request.user, backend=backend, next_url=target)
    return redirect("paxalia:auth_2fa_setup")

def mark_admin_intent(request, next_url: str | None = None) -> None:
    request.session[ADMIN_INTENT_KEY] = True
    request.session[ADMIN_NEXT_KEY] = _safe_path(
        next_url or admin_home_url(request),
        request,
    )
    if host_authentication_enabled():
        # These markers are strictly for host-login compatibility mode.
        request.session[ADMIN_HOST_AUTH_PENDING_KEY] = True
        request.session[ADMIN_HOST_2FA_PENDING_KEY] = timezone.now().timestamp()
    else:
        # Never leave host-auth markers behind in isolated mode. A later normal
        # website login must not be mistaken for a Paxalia administrator flow.
        request.session.pop(ADMIN_HOST_AUTH_PENDING_KEY, None)
        request.session.pop(ADMIN_HOST_2FA_PENDING_KEY, None)
    request.session.modified = True


def clear_admin_security_state(request, *, keep_intent: bool = False) -> None:
    keys = (
        ADMIN_FINAL_KEY,
        ADMIN_USER_KEY,
        ADMIN_BACKEND_KEY,
        ADMIN_STAGE_KEY,
        ADMIN_AUTH_AT_KEY,
        ADMIN_DEVICE_KEY,
        ADMIN_NEXT_KEY,
        ADMIN_DEVICE_NAME_KEY,
        ADMIN_ISOLATED_SESSION_KEY,
        ADMIN_HOST_AUTH_PENDING_KEY,
        ADMIN_HOST_2FA_PENDING_KEY,
    )
    if keep_intent:
        keys = tuple(k for k in keys if k != ADMIN_NEXT_KEY)
    for key in keys:
        request.session.pop(key, None)
    if not keep_intent:
        request.session.pop(ADMIN_INTENT_KEY, None)
    request.session.modified = True


def set_pending_primary(request, user, *, backend: str | None = None, next_url: str | None = None) -> None:
    resolved_backend = str(backend or "").strip() or authentication_backend_for(request, user, required=True)
    request.session.cycle_key()
    request.session[ADMIN_USER_KEY] = str(user.pk)
    request.session[ADMIN_BACKEND_KEY] = resolved_backend
    request.session[ADMIN_STAGE_KEY] = STAGE_PRIMARY
    request.session[ADMIN_INTENT_KEY] = True
    request.session[ADMIN_NEXT_KEY] = _safe_path(next_url, request)
    request.session.pop(ADMIN_FINAL_KEY, None)
    request.session.pop(ADMIN_AUTH_AT_KEY, None)
    request.session.pop(ADMIN_DEVICE_KEY, None)
    # A bundled Paxalia credential login is not the host-login transition.
    # Clear any stale one-shot host marker so the eventual privileged
    # login event is not accidentally suppressed by the signal handler.
    request.session.pop(ADMIN_HOST_AUTH_PENDING_KEY, None)
    request.session.pop(ADMIN_HOST_2FA_PENDING_KEY, None)
    request.session.modified = True


def set_2fa_verified(request) -> None:
    request.session[ADMIN_STAGE_KEY] = STAGE_2FA
    request.session.modified = True


def set_device_stage(request) -> None:
    request.session[ADMIN_STAGE_KEY] = STAGE_DEVICE
    request.session.modified = True


def finalize_admin_session(
    request,
    user,
    credential: PaxaliaDeviceCredential,
    backend: str | None = None,
) -> None:
    """Complete all three layers without entering the host auth flow in isolation mode."""
    from django.contrib.auth import login

    resolved_backend = (
        str(backend or "").strip()
        or authentication_backend_for(request, user, required=True)
    )

    if host_authentication_enabled():
        login(request, user, backend=resolved_backend)
        request.session.pop(ADMIN_USER_KEY, None)
    else:
        # Keep the host Django authentication session untouched. The isolated
        # Paxalia middleware exposes this package-authenticated user only while
        # handling Paxalia dashboard routes. Its ordinary Django session key is
        # the authoritative Paxalia session identifier.
        if not getattr(request.session, "session_key", None):
            request.session.save()
        request.session[ADMIN_USER_KEY] = str(user.pk)
        request.session[ADMIN_ISOLATED_SESSION_KEY] = str(request.session.session_key or "")

    request.session[ADMIN_FINAL_KEY] = True
    request.session[ADMIN_STAGE_KEY] = STAGE_COMPLETE
    request.session[ADMIN_AUTH_AT_KEY] = timezone.now().isoformat()
    request.session[ADMIN_DEVICE_KEY] = str(credential.pk)
    request.session.pop(ADMIN_BACKEND_KEY, None)
    request.session.pop(ADMIN_INTENT_KEY, None)
    request.session.pop(ADMIN_HOST_AUTH_PENDING_KEY, None)
    request.session.pop(ADMIN_HOST_2FA_PENDING_KEY, None)
    request.session.pop(ADMIN_DEVICE_NAME_KEY, None)
    request.session.modified = True


def _parse_auth_time(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _effective_admin_user(request):
    """Return the Paxalia administrator identity for the current request."""
    if host_authentication_enabled():
        return getattr(request, "user", None)

    # Unit/integration callers that deliberately supply the package-authenticated
    # request user may bypass the database lookup. The marker is only set by
    # PaxaliaIsolatedAdminAuthenticationMiddleware; a normal host-authenticated
    # user is never treated as a Paxalia identity in isolated mode.
    if getattr(request, "_paxalia_isolated_auth", False):
        candidate = getattr(request, "user", None)
        if candidate is not None and admin_user(candidate):
            return candidate

    user_id = request.session.get(ADMIN_USER_KEY)
    if not user_id:
        return None

    try:
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.get(pk=user_id)
    except Exception:
        return None

    return user if admin_user(user) else None


def current_paxalia_session_id(request) -> str:
    """Return the host or isolated Paxalia session identifier."""
    if not host_authentication_enabled():
        value = getattr(request.session, "session_key", None)
        if value:
            return str(value).strip()
        value = request.session.get(ADMIN_ISOLATED_SESSION_KEY)
        return str(value or "").strip()
    return str(getattr(request.session, "session_key", "") or "").strip()


def admin_session_is_valid(request) -> bool:
    if not request.session.get(ADMIN_FINAL_KEY):
        return False
    if request.session.get(ADMIN_STAGE_KEY) != STAGE_COMPLETE:
        return False

    user = _effective_admin_user(request)
    if user is None or not admin_user(user):
        return False
    if not getattr(user, "is_active", True):
        return False

    # Layer 2 remains mandatory for the lifetime of the privileged session.
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice
        if not TOTPDevice.objects.filter(
            user=user, confirmed=True, name__in=PAXALIA_TOTP_DEVICE_NAMES
        ).exists():
            return False
    except Exception:
        return False

    auth_at = _parse_auth_time(request.session.get(ADMIN_AUTH_AT_KEY))
    if auth_at is None:
        return False
    max_age = max(60, int(get_config().get("ADMIN_SESSION_MAX_AGE_SECONDS", 8 * 60 * 60)))
    if (timezone.now() - auth_at).total_seconds() > max_age:
        return False

    credential_id = request.session.get(ADMIN_DEVICE_KEY)
    if not credential_id:
        return False
    try:
        credential = PaxaliaDeviceCredential.objects.select_related("device").get(pk=credential_id)
    except PaxaliaDeviceCredential.DoesNotExist:
        return False

    device = getattr(credential, "device", None)
    if user is None or device is None:
        return False
    if device.user_id != user.pk or device.status != "active":
        return False

    # A LoginEvent is the authoritative revocation marker. In isolated mode
    # this prevents revocation from requiring deletion of the shared Django
    # session, which would otherwise sign the host user out as well.
    try:
        session_key = current_paxalia_session_id(request)
        if not session_key:
            return False
        active_event = LoginEvent.objects.filter(
            user=user,
            event_type="login",
            result="success",
            session_key=session_key,
            admin_device=device,
            logged_out_at__isnull=True,
        ).exists()
        if not active_event:
            return False
    except Exception:
        return False

    return True


def current_device_credential(request):
    credential_id = request.session.get(ADMIN_DEVICE_KEY)
    if not credential_id:
        return None
    try:
        return PaxaliaDeviceCredential.objects.select_related("device").get(pk=credential_id)
    except PaxaliaDeviceCredential.DoesNotExist:
        return None


PAXALIA_SECURITY_PREFLIGHT_ATTR = "_paxalia_security_preflight"


def admin_security_preflight(callback):
    """Register a safe, non-authorizing request preflight for a gated view.

    Preflights are intentionally limited to validation that can be performed
    without granting access or mutating privileged state. They run only for
    an already-authenticated Paxalia administrator and may return a response
    (for example, a 400/413 validation error) before the privileged gate.
    """
    def decorator(view_func):
        setattr(view_func, PAXALIA_SECURITY_PREFLIGHT_ATTR, callback)
        return view_func
    return decorator


def admin_security_required(view_func):
    """Require the completed three-layer Paxalia Dashboard admin session."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        effective_user = _effective_admin_user(request)

        if effective_user is not None and admin_user(effective_user):
            preflight = getattr(view_func, PAXALIA_SECURITY_PREFLIGHT_ATTR, None)
            if callable(preflight):
                result = preflight(request, *args, **kwargs)
                if result is not None:
                    return result

        # Isolated mode authenticates only the Paxalia dashboard; the host
        # request.user must never be treated as Layer 1 for this gate.
        if not host_authentication_enabled():
            if admin_session_is_valid(request):
                return view_func(request, *args, **kwargs)
            return begin_admin_verification(request, request.get_full_path())

        if not request.user.is_authenticated:
            result = begin_admin_verification(request, request.get_full_path())
            if request.headers.get("Accept", "").lower().find("application/json") >= 0:
                if getattr(result, "status_code", None) == 302:
                    auth_url = result["Location"]
                    return JsonResponse({
                        "detail": "Authentication is required.",
                        "auth_url": auth_url,
                    }, status=401)
            return result

        if not admin_user(request.user):
            raise PermissionDenied("You do not have access to Paxalia Dashboard administration.")

        if admin_session_is_valid(request):
            return view_func(request, *args, **kwargs)

        return begin_admin_verification(request, request.get_full_path())
    wrapped.paxalia_gate = True
    return wrapped


# Public name used by dashboard views and extension code.
paxalia_admin_required = admin_security_required


def hash_identifier(value: str) -> str:
    return sha256(str(value or "").strip().lower().encode("utf-8", "ignore")).hexdigest()


def device_label(device: PaxaliaDeviceCredential | None) -> str:
    if not device:
        return ""
    return device.device.display_name
