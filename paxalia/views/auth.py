"""Paxalia authentication and mandatory administrator verification flows."""
from __future__ import annotations

import base64
import io
import secrets
import string
from importlib import import_module
from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import (
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..admin_security import (
    ADMIN_AUTH_AT_KEY,
    ADMIN_BACKEND_KEY,
    ADMIN_DEVICE_KEY,
    ADMIN_DEVICE_NAME_KEY,
    ADMIN_FINAL_KEY,
    ADMIN_INTENT_KEY,
    ADMIN_NEXT_KEY,
    ADMIN_STAGE_KEY,
    ADMIN_USER_KEY,
    PAXALIA_TOTP_DEVICE_NAMES,
    STAGE_2FA,
    STAGE_COMPLETE,
    STAGE_DEVICE,
    STAGE_PRIMARY,
    admin_user,
    admin_session_is_valid,
    admin_home_url,
    _safe_path,
    authentication_backend_for,
    begin_admin_verification,
    clear_admin_security_state,
    current_device_credential,
    finalize_admin_session,
    mark_admin_intent,
    host_authentication_enabled,
    set_2fa_verified,
    set_device_stage,
    set_pending_primary,
)
from ..forms import PaxaliaAuthenticationForm, PaxaliaUserCreationForm
from ..logging import log as paxalia_log
from ..models import LoginEvent, PaxaliaDevice, PaxaliaDeviceCredential, PaxaliaRecoveryCode, PaxaliaWebAuthnChallenge
from ..security_audit import log_action
from ..security_rate_limit import allowed as rate_allowed, clear as rate_clear
from ..settings import get_config
from ..webauthn_services import (
    authentication_options,
    configuration_for_request,
    is_local_web_authn_request,
    localhost_url_for_request,
    registration_options,
    verify_authentication,
    verify_registration,
    webauthn_available,
)
from .utils import section_enabled

User = get_user_model()

PAXALIA_TOTP_DEVICE_NAME = PAXALIA_TOTP_DEVICE_NAMES[0]


def _clear_host_handoff_cookie(response):
    cookie_name = str(
        get_config().get("AUTH_HOST_2FA_HANDOFF_COOKIE_NAME")
        or "paxalia_admin_handoff"
    ).strip() or "paxalia_admin_handoff"
    response.delete_cookie(cookie_name, path="/")
    return response


def _record_isolated_admin_login(request, user, credential) -> LoginEvent:
    """Create the privileged LoginEvent without invoking Django host login signals."""
    from ..admin_security import current_paxalia_session_id
    session_key = current_paxalia_session_id(request)
    if not session_key:
        raise RuntimeError("The Paxalia administrator session has no session key.")

    event = (
        LoginEvent.objects.filter(
            user=user,
            event_type="login",
            result="success",
            session_key=session_key,
            admin_device=credential.device,
            logged_out_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if event is not None:
        return event

    return LoginEvent.objects.create(
        event_type="login",
        user=user,
        username_attempted=str(user.get_username())[:255],
        result="success",
        is_admin=True,
        admin_device=credential.device,
        session_key=session_key,
        created_at=timezone.now(),
    )


def _safe_next(request, value: str | None = None) -> str:
    """Return an internal administrator destination, never an open redirect."""
    candidate = value or request.session.get(ADMIN_NEXT_KEY) or admin_home_url(request)
    return _safe_path(candidate, request, default=admin_home_url(request))


def _dashboard_path(request) -> str:
    configured = str(get_config().get("DASHBOARD_URL") or "").strip()
    if configured:
        if not configured.startswith("/"):
            configured = "/" + configured
        return urlsplit(configured).path.rstrip("/") or "/"
    return urlsplit(reverse("paxalia:dashboard")).path.rstrip("/") or "/"


def _is_admin_intent(request, next_value=None) -> bool:
    if request.session.get(ADMIN_INTENT_KEY):
        return True
    candidate = str(next_value or request.GET.get("next") or "")
    path = urlsplit(candidate).path
    dashboard = _dashboard_path(request)
    return bool(path and (path == dashboard or path.startswith(dashboard + "/")))


def _client_ip(request) -> str:
    try:
        from ..middleware import AnalyticsMiddleware
        return AnalyticsMiddleware._get_ip(request) or "unknown"
    except Exception:
        return request.META.get("REMOTE_ADDR") or "unknown"


def _identifier_for_rate_limit(value: str) -> str:
    return str(value or "").strip().lower()[:255]


def _request_data(request):
    """Return request data for JSON WebAuthn calls and legacy form posts."""
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        import json
        try:
            value = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}
    return request.POST


def _webauthn_configuration_context(request) -> dict:
    """Return safe browser-facing WebAuthn configuration state for auth pages."""
    try:
        configuration_for_request(request)
        return {
            "webauthn_configuration_error": False,
            "webauthn_configuration_detail": "",
            "webauthn_localhost_url": "",
        }
    except ValueError as exc:
        if is_local_web_authn_request(request):
            return {
                "webauthn_configuration_error": True,
                "webauthn_configuration_detail": _(
                    "For local development, WebAuthn requires the dashboard to be opened "
                    "through localhost rather than 127.0.0.1 or another IP address. "
                    "Start the administrator flow from the localhost address so the "
                    "authentication session stays on the same browser host."
                ),
                "webauthn_localhost_url": localhost_url_for_request(request),
            }
        return {
            "webauthn_configuration_error": True,
            "webauthn_configuration_detail": _(
                "WebAuthn is not configured for this browser origin. Verify "
                "WEBAUTHN_RP_ID and WEBAUTHN_ORIGIN for the current deployment."
            ),
            "webauthn_localhost_url": "",
        }


def _webauthn_configuration_error_detail(request) -> str:
    context = _webauthn_configuration_context(request)
    return context.get("webauthn_configuration_detail") or _("WebAuthn is not configured for this browser origin.")


def _otp_model():
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice
        return TOTPDevice
    except Exception:
        return None


def otp_ready() -> bool:
    model = _otp_model()
    if model is None:
        return False
    installed = set(getattr(__import__("django.conf", fromlist=["settings"]).settings, "INSTALLED_APPS", []) or [])
    return "django_otp" in installed and "django_otp.plugins.otp_totp" in installed


def _pending_user(request):
    user_id = request.session.get(ADMIN_USER_KEY)
    if not user_id:
        return None
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None
    return user if admin_user(user) else None


def _has_confirmed_totp(user) -> bool:
    model = _otp_model()
    if model is None:
        return False
    return model.objects.filter(
        user=user, confirmed=True, name__in=PAXALIA_TOTP_DEVICE_NAMES
    ).exists()


def _totp_device(user):
    model = _otp_model()
    if model is None:
        return None
    for name in PAXALIA_TOTP_DEVICE_NAMES:
        device = model.objects.filter(user=user, name=name).order_by("-confirmed", "-id").first()
        if device is not None:
            return device
    return None


def _format_totp_secret(secret) -> str:
    """Format a TOTP secret into readable four-character groups."""
    if isinstance(secret, bytes):
        try:
            secret = secret.decode("ascii")
        except UnicodeDecodeError:
            secret = base64.b32encode(secret).decode("ascii")
    normalized = "".join(str(secret or "").upper().split())
    return " ".join(normalized[index:index + 4] for index in range(0, len(normalized), 4))


def _totp_setup_visuals(device):
    """Return the provisioning URI, manual key, and QR data URI."""
    otpauth_url = str(getattr(device, "config_url", "") or "")
    raw_secret = getattr(device, "key", "")
    if isinstance(raw_secret, bytes):
        try:
            raw_secret = raw_secret.decode("ascii")
        except UnicodeDecodeError:
            raw_secret = base64.b32encode(raw_secret).decode("ascii")
    totp_secret = "".join(str(raw_secret or "").upper().split())
    qr_code_data_uri = None

    if otpauth_url:
        try:
            import qrcode

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=4,
            )
            qr.add_data(otpauth_url)
            qr.make(fit=True)
            image = qr.make_image()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            qr_code_data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception:
            # The setup page can still use the manual secret if an optional
            # image backend is unavailable; do not expose the raw URI instead.
            qr_code_data_uri = None

    return {
        "otpauth_url": otpauth_url,
        "totp_secret": totp_secret,
        "formatted_totp_secret": _format_totp_secret(totp_secret),
        "qr_code_data_uri": qr_code_data_uri,
    }


def _totp_setup_context(device, **extra):
    context = dict(extra)
    context.update(_totp_setup_visuals(device))
    context["device"] = device
    return context


def _new_recovery_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(16))
    return "-".join(raw[index:index + 4] for index in range(0, 16, 4))


def _generate_recovery_codes(user, count: int = 10) -> list[str]:
    now = timezone.now()
    PaxaliaRecoveryCode.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
    plaintext = []
    rows = []
    count = max(1, int(get_config().get("SECURITY_RECOVERY_CODE_COUNT", count) or count))
    for _ in range(count):
        code = _new_recovery_code()
        plaintext.append(code)
        rows.append(PaxaliaRecoveryCode(user=user, code_hash=make_password(code), created_at=now))
    PaxaliaRecoveryCode.objects.bulk_create(rows)
    return plaintext


def _check_recovery_code(user, submitted: str):
    normalized = "".join(ch for ch in str(submitted or "").upper() if ch.isalnum())
    if len(normalized) != 16:
        return None
    formatted = "-".join(normalized[index:index + 4] for index in range(0, 16, 4))
    qs = PaxaliaRecoveryCode.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True)
    for row in qs[:50]:
        if check_password(formatted, row.code_hash):
            return row
    return None


def _render_auth(request, template, context=None, *, status=200):
    context = dict(context or {})
    config = get_config()
    context.setdefault("brand_name", config.get("AUTH_BRAND_NAME", "Paxalia"))
    context.setdefault("dashboard_name", "Paxalia Dashboard")
    context.setdefault("auth_home_url", config.get("AUTH_HOME_URL") or "/")
    context.setdefault("auth_support_url", config.get("AUTH_SUPPORT_URL"))
    context.setdefault("auth_signup_enabled", bool(config.get("AUTH_SIGNUP_ENABLED", True)))
    context.setdefault("auth_password_reset_enabled", bool(config.get("AUTH_PASSWORD_RESET_ENABLED", True)))
    context.setdefault("auth_password_change_enabled", bool(config.get("AUTH_PASSWORD_CHANGE_ENABLED", True)))
    return render(request, template, context, status=status)


def paxalia_login(request):
    """Compatibility entry point for Paxalia administrator authentication.

    In the default isolated mode Paxalia uses its bundled administrator login
    page for Layer 1. Set AUTH_USE_HOST_LOGIN=True only when a host project
    deliberately wants Paxalia to integrate with its existing login/2FA flow.
    """
    next_value = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.session.get(ADMIN_NEXT_KEY)
    )

    current_path = urlsplit(request.get_full_path()).path.rstrip("/") or "/"
    dashboard_path = _dashboard_path(request)
    entered_private_dashboard = (
        current_path == dashboard_path
        or current_path.startswith(dashboard_path + "/")
    )
    # Any request reaching the Paxalia auth endpoints from inside the private
    # dashboard mount is an administrator flow. This prevents a direct visit
    # to /<secret>/auth/login/ from falling back to the host website login.
    admin_flow = (
        entered_private_dashboard
        or _is_admin_intent(request, next_value)
        or request.GET.get("admin") == "1"
    )
    if request.GET.get("admin") == "1":
        mark_admin_intent(request, next_value)
        admin_flow = True

    # In isolated mode the Paxalia login page is independent of the host
    # site's current authentication state. A host-authenticated browser must
    # still enter Paxalia Layer 1 explicitly rather than silently inheriting
    # the host's session.
    if not host_authentication_enabled():
        if request.session.get(ADMIN_FINAL_KEY) and admin_session_is_valid(request):
            return redirect(_safe_next(request, next_value))
        if request.session.get(ADMIN_USER_KEY):
            return begin_admin_verification(request, next_value or admin_home_url(request))
    else:
        if request.user.is_authenticated:
            if request.session.get(ADMIN_FINAL_KEY):
                return redirect(_safe_next(request, next_value))
            return begin_admin_verification(request, next_value or admin_home_url(request))
        return begin_admin_verification(request, next_value or admin_home_url(request))

    if request.method == "POST":
        identifier = request.POST.get("username", "")
        ip = _client_ip(request)
        limit = get_config().get("SECURITY_LOGIN_RATE_LIMIT_ATTEMPTS", 8)
        window = get_config().get("SECURITY_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 900)
        identifier_key = _identifier_for_rate_limit(identifier)
        ip_ok, _rate_meta_ip = rate_allowed("login-ip", limit, window, ip)
        identifier_ok, _rate_meta_identifier = rate_allowed("login-identifier", limit, window, ip, identifier_key)
        if not (ip_ok and identifier_ok):
            paxalia_log(
                "Administrator login rate limited" if admin_flow else "Login rate limited",
                level="WARNING", source="Authentication", category="authentication",
                action="admin_login_rate_limited" if admin_flow else "login_rate_limited", request=request,
                metadata={"admin": admin_flow},
            )
            form = PaxaliaAuthenticationForm(request, data=request.POST)
            return _render_auth(request, "paxalia_auth/login.html", {
                "form": form,
                "next": _safe_next(request, next_value) if admin_flow else _safe_next(request, next_value),
                "admin_flow": admin_flow,
                "rate_limited": True,
            }, status=429)

        form = PaxaliaAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            rate_clear("login-ip", ip)
            rate_clear("login-identifier", ip, identifier_key)
            if admin_flow:
                if not admin_user(user):
                    paxalia_log(
                        "Administrator login rejected", level="WARNING", source="Authentication",
                        category="authentication", action="admin_login_failed", request=request,
                        metadata={"reason": "not_admin"},
                    )
                    form.add_error(None, _("This account is not authorized to administer Paxalia Dashboard."))
                else:
                    set_pending_primary(
                        request, user,
                        backend=authentication_backend_for(request, user, required=True),
                        next_url=next_value or admin_home_url(request),
                    )
                    paxalia_log(
                        "Administrator primary authentication accepted", level="INFO", source="Authentication",
                        category="authentication", action="admin_login_started", request=request,
                        metadata={"admin": True},
                    )
                    if not otp_ready():
                        return redirect("paxalia:auth_2fa_setup")
                    if not _has_confirmed_totp(user):
                        paxalia_log(
                            "Administrator 2FA enrollment required", level="INFO", source="Security",
                            category="authentication", action="admin_2fa_required", request=request,
                        )
                        return redirect("paxalia:auth_2fa_setup")
                    return redirect("paxalia:auth_2fa_verify")
            else:
                login(request, user)
                return redirect(_safe_next(request, next_value) if next_value else "/")
        else:
            paxalia_log(
                "Administrator login failed" if admin_flow else "Login failed",
                level="WARNING", source="Authentication", category="authentication",
                action="admin_login_failed" if admin_flow else "login_failed", request=request,
                metadata={"admin": admin_flow},
            )
    else:
        form = PaxaliaAuthenticationForm(request)

    return _render_auth(request, "paxalia_auth/login.html", {
        "form": form,
        "next": _safe_next(request, next_value) if admin_flow else (next_value or "/"),
        "admin_flow": admin_flow,
    })
def paxalia_logout(request):
    if request.method != "POST":
        return redirect(reverse("paxalia:auth_login"))

    if not host_authentication_enabled():
        user = getattr(request, "user", None)
        from ..admin_security import current_paxalia_session_id
        session_key = current_paxalia_session_id(request)
        if session_key and getattr(user, "pk", None):
            LoginEvent.objects.filter(
                user=user,
                event_type="login",
                result="success",
                session_key=session_key,
                logged_out_at__isnull=True,
            ).update(logged_out_at=timezone.now())
        paxalia_log(
            "Administrator logout",
            level="INFO",
            source="Authentication",
            category="authentication",
            action="admin_logout",
            request=request,
            metadata={"admin": True, "auth_mode": "isolated"},
        )
        log_action(request, "security.admin_logout")
        # This is Paxalia's dedicated Django session. Never call
        # django.contrib.auth.logout() here: that API operates on the same
        # request.session object and would couple Paxalia logout to the host
        # site's authentication boundary.
        #
        # Do NOT use SessionBase.flush(). The DB-backed Django implementation
        # performs delete() and then creates a new session on the SAME Python
        # object. Paxalia's isolation contract requires the old privileged
        # SessionStore object itself to become keyless, while request.session
        # is replaced with a different fresh anonymous SessionStore.
        isolated_session = request.session
        try:
            isolated_session.delete()
        finally:
            # Make the revoked object harmless even when another backend keeps
            # an in-memory cache after delete(). This is also what the contract
            # test verifies directly against the original store object.
            try:
                isolated_session._session_key = None
            except Exception:
                pass
            try:
                isolated_session._session_cache = {}
            except Exception:
                pass
            try:
                isolated_session.accessed = True
                isolated_session.modified = False
            except Exception:
                pass

        # Never continue using the revoked store. A genuinely new anonymous
        # SessionStore is required so later middleware cannot repopulate the
        # just-invalidated Paxalia session key.
        request.session = import_module(getattr(settings, "SESSION_ENGINE")).SessionStore()
        response = redirect("paxalia:auth_login")
        return _clear_host_handoff_cookie(response)

    was_admin = bool(request.session.get(ADMIN_FINAL_KEY))
    if was_admin:
        session_key = request.session.session_key
        if session_key:
            LoginEvent.objects.filter(
                user=request.user,
                event_type="login",
                result="success",
                session_key=session_key,
                logged_out_at__isnull=True,
            ).update(logged_out_at=timezone.now())
        paxalia_log("Administrator logout", level="INFO", source="Authentication", category="authentication", action="admin_logout", request=request)
        log_action(request, "security.admin_logout")

    logout(request)
    response = redirect("paxalia:auth_login")
    return _clear_host_handoff_cookie(response)


def paxalia_signup(request):
    if not bool(get_config().get("AUTH_SIGNUP_ENABLED", True)):
        raise Http404
    if request.method == "POST":
        form = PaxaliaUserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
            messages.success(request, _("Your account has been created. You can now sign in."))
            return redirect("paxalia:auth_login")
    else:
        form = PaxaliaUserCreationForm()
    return _render_auth(request, "paxalia_auth/signup.html", {"form": form})


class PaxaliaPasswordResetView(PasswordResetView):
    def dispatch(self, request, *args, **kwargs):
        if not bool(get_config().get("AUTH_PASSWORD_RESET_ENABLED", True)):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    template_name = "paxalia_auth/forgot-password.html"
    email_template_name = "paxalia_auth/password_reset_email.html"
    subject_template_name = "paxalia_auth/password_reset_subject.html"
    success_url = reverse_lazy("paxalia:auth_password_reset_done")
    form_class = PasswordResetForm


class PaxaliaPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "paxalia_auth/reset-password.html"
    success_url = reverse_lazy("paxalia:auth_password_reset_complete")

    def dispatch(self, request, *args, **kwargs):
        if not bool(get_config().get("AUTH_PASSWORD_RESET_ENABLED", True)):
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def password_reset_complete(request):
    if not bool(get_config().get("AUTH_PASSWORD_RESET_ENABLED", True)):
        raise Http404
    return _render_auth(request, "paxalia_auth/password_reset_complete.html")


def password_reset_done(request):
    if not bool(get_config().get("AUTH_PASSWORD_RESET_ENABLED", True)):
        raise Http404
    return _render_auth(request, "paxalia_auth/password_reset_done.html")


def password_change(request):
    if not bool(get_config().get("AUTH_PASSWORD_CHANGE_ENABLED", True)):
        raise Http404
    if not request.user.is_authenticated:
        return redirect(f"{reverse('paxalia:auth_login')}?next={reverse('paxalia:auth_password_change')}")
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            was_admin_session = admin_session_is_valid(request)
            if host_authentication_enabled():
                # Django rotates authentication state correctly through update_session_auth_hash.
                update_session_auth_hash(request, user)
            if was_admin_session:
                # Treat a password change as a privileged re-authentication boundary.
                from ..models import LoginEvent
                session_key = request.session.session_key
                if session_key:
                    LoginEvent.objects.filter(
                        user=user, event_type="login", result="success",
                        session_key=session_key, logged_out_at__isnull=True,
                    ).update(logged_out_at=timezone.now())
                clear_admin_security_state(request)
                if host_authentication_enabled():
                    logout(request)
                paxalia_log("Administrator password changed; privileged session revoked", level="WARNING", source="Authentication", category="authentication", action="admin_password_changed", request=request, metadata={"admin": True})
                log_action(request, "security.admin_password_changed")
            else:
                paxalia_log("Password changed", level="INFO", source="Authentication", category="authentication", action="password_change", request=request)
            messages.success(request, _("Your password has been changed."))
            return redirect("paxalia:auth_password_change_done")
    else:
        form = PasswordChangeForm(request.user)
    return _render_auth(request, "paxalia_auth/password_change.html", {"form": form})


def password_change_done(request):
    if not bool(get_config().get("AUTH_PASSWORD_CHANGE_ENABLED", True)):
        raise Http404
    return _render_auth(request, "paxalia_auth/password_change_done.html")


def paxalia_2fa_setup(request):
    user = _pending_user(request)
    if user is None and request.user.is_authenticated and admin_session_is_valid(request):
        user = request.user
    if user is None:
        return redirect("paxalia:auth_login")
    if not otp_ready():
        return _render_auth(request, "paxalia_auth/two-factor-setup.html", {
            "configuration_error": True,
            "required_apps": True,
        }, status=503)
    if _has_confirmed_totp(user):
        return redirect("paxalia:auth_2fa_verify") if request.session.get(ADMIN_STAGE_KEY) in {STAGE_PRIMARY, STAGE_2FA, STAGE_DEVICE} else _render_auth(
            request, "paxalia_auth/two-factor-setup.html", {"already_enabled": True}
        )
    TOTPDevice = _otp_model()
    device = _totp_device(user)
    if device is None:
        device = TOTPDevice.objects.create(user=user, confirmed=False, name=PAXALIA_TOTP_DEVICE_NAME)
    if request.method == "POST":
        token = request.POST.get("token", "").strip()
        limit = get_config().get("SECURITY_2FA_RATE_LIMIT_ATTEMPTS", 5)
        window = get_config().get("SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS", 300)
        ok, _rate_meta = rate_allowed("2fa-setup", limit, window, _client_ip(request), user.pk)
        if not ok:
            paxalia_log("2FA enrollment rate limited", level="WARNING", source="Security", category="authentication", action="admin_2fa_rate_limited", request=request, metadata={"admin": True})
            return _render_auth(request, "paxalia_auth/two-factor-setup.html", _totp_setup_context(device, rate_limited=True), status=429)
        if token and device.verify_token(token):
            device.confirmed = True
            device.name = PAXALIA_TOTP_DEVICE_NAME
            device.save(update_fields=["confirmed", "name"])
            rate_clear("2fa-setup", _client_ip(request), user.pk)
            codes = _generate_recovery_codes(user)
            if request.session.get(ADMIN_USER_KEY):
                set_2fa_verified(request)
                paxalia_log("Administrator 2FA enrolled", level="INFO", source="Security", category="authentication", action="admin_2fa_enrolled", request=request)
                log_action(request, "security.admin_2fa_enrolled")
            return _render_auth(request, "paxalia_auth/recovery-codes.html", {"recovery_codes": codes, "next": reverse("paxalia:auth_device_login")})
        paxalia_log("Administrator 2FA enrollment failed", level="WARNING", source="Security", category="authentication", action="admin_2fa_failed", request=request)
    return _render_auth(request, "paxalia_auth/two-factor-setup.html", _totp_setup_context(device))


def paxalia_2fa_verify(request):
    user = _pending_user(request)
    if user is None:
        return redirect("paxalia:auth_login")
    if not otp_ready():
        return redirect("paxalia:auth_2fa_setup")
    TOTPDevice = _otp_model()
    devices = TOTPDevice.objects.filter(
        user=user, confirmed=True, name__in=PAXALIA_TOTP_DEVICE_NAMES
    )
    if not devices.exists():
        return redirect("paxalia:auth_2fa_setup")
    if request.method == "POST":
        limit = get_config().get("SECURITY_2FA_RATE_LIMIT_ATTEMPTS", 5)
        window = get_config().get("SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS", 300)
        ok, _rate_meta = rate_allowed("2fa", limit, window, _client_ip(request), user.pk)
        if not ok:
            paxalia_log("Administrator 2FA rate limited", level="WARNING", source="Security", category="authentication", action="admin_2fa_rate_limited", request=request)
            return _render_auth(request, "paxalia_auth/two-factor.html", {"rate_limited": True}, status=429)
        token = request.POST.get("token", "").strip()
        recovery = request.POST.get("recovery_code", "").strip()
        verified = False
        recovery_used = False
        recovery_row = None
        with transaction.atomic():
            locked_devices = list(devices.select_for_update())
            if token:
                verified = any(device.verify_token(token) for device in locked_devices)
            if not verified and recovery:
                recovery_row = _check_recovery_code(user, recovery)
                if recovery_row is not None:
                    locked_recovery = PaxaliaRecoveryCode.objects.select_for_update().get(pk=recovery_row.pk)
                    if locked_recovery.used_at is None and locked_recovery.revoked_at is None:
                        locked_recovery.used_at = timezone.now()
                        locked_recovery.save(update_fields=["used_at"])
                        verified = True
                        recovery_used = True
        if recovery_used:
            paxalia_log("Administrator recovery code used", level="WARNING", source="Security", category="authentication", action="admin_recovery_used", request=request, metadata={"admin": True})
            log_action(request, "security.admin_recovery_used")
        if verified:
            rate_clear("2fa", _client_ip(request), user.pk)
            set_2fa_verified(request)
            set_device_stage(request)
            paxalia_log("Administrator 2FA verified", level="INFO", source="Security", category="authentication", action="admin_2fa_success", request=request, metadata={"admin": True})
            return redirect("paxalia:auth_device_login")
        paxalia_log("Administrator 2FA failed", level="WARNING", source="Security", category="authentication", action="admin_2fa_failed", request=request, metadata={"admin": True})
    return _render_auth(request, "paxalia_auth/two-factor.html", {"recovery_available": PaxaliaRecoveryCode.objects.filter(user=user, used_at__isnull=True, revoked_at__isnull=True).exists()})


def paxalia_2fa_reset(request):
    """Require the current privileged session and current TOTP before re-enrollment."""
    if not admin_session_is_valid(request):
        raise PermissionDenied
    if request.method != "POST":
        return redirect("paxalia:security_authentication")
    TOTPDevice = _otp_model()
    if TOTPDevice is None:
        return _render_auth(request, "paxalia_auth/two-factor-setup.html", {
            "configuration_error": True, "required_apps": True,
        }, status=503)
    limit = get_config().get("SECURITY_2FA_RATE_LIMIT_ATTEMPTS", 5)
    window = get_config().get("SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS", 300)
    ip = _client_ip(request)
    ok, _rate_meta = rate_allowed("2fa-reset", limit, window, ip, request.user.pk)
    if not ok:
        return _render_auth(request, "paxalia_auth/two-factor.html", {"rate_limited": True}, status=429)
    token = request.POST.get("token", "").strip()
    devices = TOTPDevice.objects.filter(
        user=request.user, confirmed=True, name__in=PAXALIA_TOTP_DEVICE_NAMES
    )
    if not token or not any(device.verify_token(token) for device in devices):
        paxalia_log("Administrator 2FA reset failed", level="WARNING", source="Security", category="authentication", action="admin_2fa_reset_failed", request=request)
        return _render_auth(request, "paxalia_auth/two-factor.html", {"reset_requested": True, "recovery_available": False})

    now = timezone.now()
    TOTPDevice.objects.filter(
        user=request.user, name__in=PAXALIA_TOTP_DEVICE_NAMES
    ).delete()
    PaxaliaRecoveryCode.objects.filter(user=request.user, used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
    backend = authentication_backend_for(request, request.user, required=True)
    next_url = request.session.get(ADMIN_NEXT_KEY) or reverse("paxalia:dashboard")
    set_pending_primary(request, request.user, backend=backend, next_url=next_url)
    rate_clear("2fa-reset", ip, request.user.pk)
    paxalia_log("Administrator 2FA reset initiated", level="WARNING", source="Security", category="authentication", action="admin_2fa_reset", request=request)
    log_action(request, "security.admin_2fa_reset")
    return redirect("paxalia:auth_2fa_setup")


def paxalia_recovery_regenerate(request):
    if not admin_session_is_valid(request):
        raise PermissionDenied
    if request.method != "POST":
        return redirect("paxalia:security_authentication")
    codes = _generate_recovery_codes(request.user)
    log_action(request, "security.recovery_codes_regenerated")
    paxalia_log("Administrator recovery codes regenerated", level="WARNING", source="Security", category="authentication", action="admin_recovery_regenerated", request=request)
    return _render_auth(request, "paxalia_auth/recovery-codes.html", {"recovery_codes": codes, "manage_mode": True})


def paxalia_device_login(request):
    user = _pending_user(request)
    if user is None:
        return redirect("paxalia:auth_login")
    if request.session.get(ADMIN_STAGE_KEY) not in {STAGE_2FA, STAGE_DEVICE}:
        return redirect("paxalia:auth_2fa_verify")
    if not PaxaliaDeviceCredential.objects.filter(device__user=user, device__status="active").exists():
        return redirect("paxalia:auth_device_register")
    if request.method == "GET":
        context = {
            "device_count": PaxaliaDeviceCredential.objects.filter(device__user=user, device__status="active").count(),
            "webauthn_available": webauthn_available(),
        }
        context.update(_webauthn_configuration_context(request))
        return _render_auth(request, "paxalia_auth/device-verify.html", context)
    return _render_auth(request, "paxalia_auth/device-verify.html")


def paxalia_device_login_options(request):
    user = _pending_user(request)
    if user is None or request.session.get(ADMIN_STAGE_KEY) not in {STAGE_2FA, STAGE_DEVICE}:
        return JsonResponse({"detail": _("Verification required.")}, status=401)
    limit = get_config().get("SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS", 5)
    window = get_config().get("SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS", 300)
    ok, _rate_meta = rate_allowed("device-options", limit, window, _client_ip(request), user.pk)
    if not ok:
        return JsonResponse({"detail": _("Too many authenticator attempts. Please wait and try again.")}, status=429)
    if not webauthn_available():
        return JsonResponse({
            "detail": _("The WebAuthn server dependency is not installed. Install the supported 'webauthn' package before verifying an authorized device.")
        }, status=503)
    try:
        configuration_for_request(request)
    except ValueError:
        return JsonResponse({"detail": _webauthn_configuration_error_detail(request)}, status=400)
    try:
        challenge, options = authentication_options(request, user)
        return JsonResponse({"challenge_id": str(challenge.pk), "options": options})
    except Exception as exc:
        paxalia_log("Administrator device challenge could not start", level="WARNING", source="Security", category="authentication", action="admin_device_challenge_failed", request=request, metadata={"reason": exc.__class__.__name__})
        return JsonResponse({"detail": _("The authenticator challenge could not be prepared.")}, status=503)


@require_POST
def paxalia_device_login_verify(request):
    user = _pending_user(request)
    if user is None or request.session.get(ADMIN_STAGE_KEY) not in {STAGE_2FA, STAGE_DEVICE}:
        return JsonResponse({"detail": _("Verification required.")}, status=401)
    limit = get_config().get("SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS", 5)
    window = get_config().get("SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS", 300)
    rate_ok, _rate_meta = rate_allowed("device-verify", limit, window, _client_ip(request), user.pk)
    if not rate_ok:
        paxalia_log(
            "Administrator device verification rate limited",
            level="WARNING",
            source="Security",
            category="authentication",
            action="admin_device_rate_limited",
            request=request,
            metadata={"admin": True},
        )
        return JsonResponse({"detail": _("Too many authenticator attempts. Please wait and try again.")}, status=429)

    # The WebAuthn browser client posts a JSON envelope:
    # {"challenge_id": "...", "credential": {...}}
    request_data = _request_data(request)
    challenge_id = request_data.get("challenge_id") or request.headers.get("X-Paxalia-Challenge")
    payload = request_data.get("credential") if isinstance(request_data, dict) else None
    if not challenge_id or not isinstance(payload, dict):
        return JsonResponse({"detail": _("Invalid authenticator response.")}, status=400)

    try:
        with transaction.atomic():
            challenge = PaxaliaWebAuthnChallenge.objects.select_for_update().get(
                pk=challenge_id,
                user=user,
                kind="authentication",
                used_at__isnull=True,
                session_key=getattr(request.session, "session_key", ""),
                expires_at__gt=timezone.now(),
            )
            credential = verify_authentication(
                request, user, challenge=challenge, payload=payload
            )
            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])

        rate_clear("device-options", _client_ip(request), user.pk)
        rate_clear("device-verify", _client_ip(request), user.pk)
        finalize_admin_session(
            request,
            user,
            credential,
            backend=request.session.get(ADMIN_BACKEND_KEY),
        )
        if not host_authentication_enabled():
            _record_isolated_admin_login(request, user, credential)
        else:
            # The host-login signal fires during login(), before the device key
            # is set. Attach the verified device to the newly-created event.
            session_key = request.session.session_key
            event = (
                LoginEvent.objects.filter(
                    user=user,
                    event_type="login",
                    result="success",
                    session_key=session_key,
                )
                .order_by("-created_at")
                .first()
            )
            if event:
                event.admin_device = credential.device
                event.save(update_fields=["admin_device"])

        paxalia_log(
            "Administrator device authenticated",
            level="INFO",
            source="Security",
            category="authentication",
            action="admin_device_authenticated",
            request=request,
            metadata={"device_id": str(credential.device_id)},
        )
        paxalia_log(
            "Administrator session created",
            level="INFO",
            source="Authentication",
            category="authentication",
            action="admin_session_created",
            request=request,
            metadata={"device_id": str(credential.device_id)},
        )
        log_action(
            request,
            "security.admin_session_created",
            detail=f"device={credential.device.display_name}",
        )
        response = JsonResponse({"ok": True, "redirect": _safe_next(request)})
        return _clear_host_handoff_cookie(response)
    except Exception as exc:
        paxalia_log(
            "Administrator device verification rejected",
            level="WARNING",
            source="Security",
            category="authentication",
            action="admin_device_rejected",
            request=request,
            metadata={"reason": exc.__class__.__name__},
        )
        return JsonResponse({"detail": _("This authenticator could not be verified.")}, status=401)


def paxalia_device_register(request):
    user = _pending_user(request)
    final = bool(admin_session_is_valid(request))
    if user is None and final:
        user = request.user
    if user is None:
        return redirect("paxalia:auth_login")
    if not final and request.session.get(ADMIN_STAGE_KEY) not in {STAGE_2FA, STAGE_DEVICE}:
        return redirect("paxalia:auth_2fa_verify")
    max_devices = max(1, int(get_config().get("ADMIN_MAX_DEVICES", 5)))
    active_count = PaxaliaDevice.objects.filter(user=user, status="active").count()
    if active_count >= max_devices and not final:
        return redirect("paxalia:auth_device_login")
    server_webauthn_available = webauthn_available()
    webauthn_config_context = _webauthn_configuration_context(request)
    if request.method == "GET":
        context = {
            "active_count": active_count,
            "max_devices": max_devices,
            "final_mode": final,
            "webauthn_available": server_webauthn_available,
        }
        context.update(webauthn_config_context)
        return _render_auth(request, "paxalia_auth/device-register.html", context)
    if not server_webauthn_available:
        return JsonResponse({
            "detail": _("The WebAuthn server dependency is not installed. Install the supported 'webauthn' package before registering an authorized device.")
        }, status=503)
    if webauthn_config_context.get("webauthn_configuration_error"):
        return JsonResponse({"detail": _webauthn_configuration_error_detail(request)}, status=400)

    limit = get_config().get("SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS", 5)
    window = get_config().get("SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS", 300)
    ok, _rate_meta = rate_allowed("device-register", limit, window, _client_ip(request), user.pk)
    if not ok:
        paxalia_log("Administrator device registration rate limited", level="WARNING", source="Security", category="authentication", action="admin_device_rate_limited", request=request, metadata={"admin": True})
        return _render_auth(request, "paxalia_auth/device-register.html", {
            "active_count": active_count, "max_devices": max_devices, "final_mode": final, "rate_limited": True,
        }, status=429)

    request_data = _request_data(request)
    name = str(request_data.get("device_name", "") or "").strip()[:120] or PAXALIA_TOTP_DEVICE_NAME
    request.session[ADMIN_DEVICE_NAME_KEY] = name
    request.session.modified = True
    try:
        challenge, options = registration_options(request, user, device_name=name)
        return JsonResponse({"challenge_id": str(challenge.pk), "options": options})
    except Exception as exc:
        paxalia_log("Administrator device registration could not start", level="WARNING", source="Security", category="authentication", action="admin_device_challenge_failed", request=request, metadata={"reason": exc.__class__.__name__})
        return JsonResponse({"detail": _("The authenticator registration challenge could not be prepared.")}, status=503)


@require_POST
def paxalia_device_register_verify(request):
    user = None
    try:
        user = _pending_user(request)
        if user is None and admin_session_is_valid(request):
            user = request.user
        if user is None:
            return JsonResponse({"detail": _("Verification required.")}, status=401)
        if not request.session.get(ADMIN_FINAL_KEY) and request.session.get(ADMIN_STAGE_KEY) not in {STAGE_2FA, STAGE_DEVICE}:
            return JsonResponse({"detail": "Second-factor verification is required."}, status=401)
        request_data = _request_data(request)
        challenge_id = request_data.get("challenge_id") or request.headers.get("X-Paxalia-Challenge")
        payload = request_data.get("credential") if isinstance(request_data, dict) else None
        if not challenge_id or not isinstance(payload, dict):
            return JsonResponse({"detail": _("Invalid authenticator response.")}, status=400)

        limit = get_config().get("SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS", 5)
        window = get_config().get("SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS", 300)
        rate_ok, rate_meta = rate_allowed("device-register-verify", limit, window, _client_ip(request), user.pk)
        if not rate_ok:
            paxalia_log("Administrator device registration verification rate limited", level="WARNING", source="Security", category="authentication", action="admin_device_rate_limited", request=request, metadata={"admin": True})
            return JsonResponse({"detail": _("Too many authenticator attempts. Please wait and try again.")}, status=429)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            try:
                challenge = PaxaliaWebAuthnChallenge.objects.select_for_update().get(pk=challenge_id, user=user, kind="registration", used_at__isnull=True, session_key=getattr(request.session, "session_key", ""), expires_at__gt=timezone.now())
            except PaxaliaWebAuthnChallenge.DoesNotExist as exc:
                recent = list(PaxaliaWebAuthnChallenge.objects.filter(user=user, kind="registration").values("id", "used_at", "expires_at", "session_key").order_by("-created_at")[:5])
                raise ValueError("The WebAuthn registration challenge could not be matched to this browser session.") from exc
            credential = verify_registration(request, user, challenge=challenge, payload=payload, device_name=request.session.get(ADMIN_DEVICE_NAME_KEY) or PAXALIA_TOTP_DEVICE_NAME)
            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])
        paxalia_log("Administrator device registered", level="INFO", source="Security", category="authentication", action="admin_device_registered", request=request, metadata={"device_id": str(credential.device_id)})
        log_action(request, "security.admin_device_registered", detail=f"device={credential.device.display_name}")
        if request.session.get(ADMIN_FINAL_KEY):
            return JsonResponse({"ok": True, "redirect": reverse("paxalia:admin_devices")})
        set_device_stage(request)
        backend = request.session.get(ADMIN_BACKEND_KEY)
        finalize_admin_session(request, user, credential, backend=backend)
        if not host_authentication_enabled():
            _record_isolated_admin_login(request, user, credential)
        else:
            session_key = request.session.session_key
            event = LoginEvent.objects.filter(user=user, event_type="login", result="success", session_key=session_key).order_by("-created_at").first()
            if event:
                event.admin_device = credential.device
                event.save(update_fields=["admin_device"])
        paxalia_log("Administrator session created", level="INFO", source="Authentication", category="authentication", action="admin_session_created", request=request, metadata={"device_id": str(credential.device_id)})
        log_action(request, "security.admin_session_created", detail=f"device={credential.device.display_name}")
        redirect_target = _safe_next(request)
        response = JsonResponse({"ok": True, "redirect": redirect_target})
        return _clear_host_handoff_cookie(response)
    except Exception as exc:
        paxalia_log("Administrator device registration rejected", level="WARNING", source="Security", category="authentication", action="admin_device_rejected", request=request, metadata={"reason": exc.__class__.__name__})
        return JsonResponse({"detail": _("This authenticator could not be registered.")}, status=400)


def paxalia_session_expired(request):
    return _render_auth(request, "paxalia_auth/session-expired.html", status=401)


def paxalia_access_denied(request):
    return _render_auth(request, "paxalia_auth/access-denied.html", status=403)
