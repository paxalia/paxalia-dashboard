"""Read-only, evidence-based Security Overview checks."""
from __future__ import annotations

from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext as _

from .models import PaxaliaDevice, PaxaliaDeviceCredential
from .settings import get_config

PASS = "PASS"
WARNING = "WARNING"
DANGER = "DANGER"
DISABLED = "DISABLED"
NOT_CONFIGURED = "NOT CONFIGURED"
NOT_APPLICABLE = "NOT APPLICABLE"

_STATUS_CLASS = {
    PASS: "pass",
    WARNING: "warning",
    DANGER: "danger",
    DISABLED: "disabled",
    NOT_CONFIGURED: "not-configured",
    NOT_APPLICABLE: "not-applicable",
}

_STATUS_ICON = {
    PASS: "✓",
    WARNING: "!",
    DANGER: "×",
    DISABLED: "–",
    NOT_CONFIGURED: "?",
    NOT_APPLICABLE: "•",
}


def _check(key, label, status, current, expected, why, source, action, *, href=None):
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_class": _STATUS_CLASS[status],
        "icon": _STATUS_ICON[status],
        "current": current,
        "expected": expected,
        "why": why,
        "source": source,
        "action": action,
        "href": href,
    }


def _middleware_names():
    return {str(item).rsplit(".", 1)[-1] for item in (getattr(settings, "MIDDLEWARE", []) or [])}


def _setting_secret_is_configured():
    value = str(getattr(settings, "SECRET_KEY", "") or "")
    return bool(value and len(value) >= 32 and "django-insecure" not in value.lower())


def _otp_available():
    try:
        import_module("django_otp.plugins.otp_totp.models")
        apps = set(getattr(settings, "INSTALLED_APPS", []) or [])
        return "django_otp" in apps and "django_otp.plugins.otp_totp" in apps
    except Exception:
        return False


def _webauthn_available():
    try:
        import_module("webauthn")
        return True
    except Exception:
        return False


def _href(name, **kwargs):
    try:
        return reverse(name, kwargs=kwargs or None)
    except Exception:
        return None


def _admin_queryset(user_model):
    """Return the effective default administrator population for diagnostics."""
    manager = user_model._default_manager
    try:
        return manager.filter(Q(is_staff=True) | Q(is_superuser=True), is_active=True)
    except Exception:
        return manager.none()


def _effective_secure_request(request):
    if request is None:
        return None
    try:
        return bool(request.is_secure())
    except Exception:
        return None


def run_security_health_checks(request=None):
    config = get_config()
    middleware = _middleware_names()
    checks = []
    user_model = get_user_model()

    backends = list(getattr(settings, "AUTHENTICATION_BACKENDS", []) or [])
    checks.append(_check(
        "authentication", _("Authentication configuration"),
        PASS if backends else DANGER,
        _("%d authentication backend(s) configured.") % len(backends) if backends else _("No authentication backend is configured."),
        _("At least one supported Django authentication backend."),
        _("Dashboard access uses the host project's authentication system."),
        _("Django AUTHENTICATION_BACKENDS"),
        _("Configure a working Django authentication backend."),
        href=_href("paxalia:security_authentication"),
    ))

    session_middleware_ok = "SessionMiddleware" in middleware and "AuthenticationMiddleware" in middleware
    checks.append(_check(
        "session-middleware", _("Authentication session middleware"),
        PASS if session_middleware_ok else DANGER,
        _("SessionMiddleware and AuthenticationMiddleware are installed.") if session_middleware_ok else _("One or more required authentication session middleware components are missing."),
        _("Django SessionMiddleware followed by AuthenticationMiddleware."),
        _("The final administrator session must use Django's session framework."),
        _("Django MIDDLEWARE"),
        _("Add SessionMiddleware and AuthenticationMiddleware in the documented Django order."),
        href=_href("paxalia:security_authentication"),
    ))

    session_engine = str(getattr(settings, "SESSION_ENGINE", "django.contrib.sessions.backends.db"))
    if session_engine == "django.contrib.sessions.backends.db":
        session_status = PASS
        session_current = _("Database-backed Django sessions are enabled.")
    elif session_engine:
        session_status = WARNING
        session_current = _("Session engine: %s. Server-side session revocation is backend-dependent.") % session_engine
    else:
        session_status = DANGER
        session_current = _("No Django session engine is configured.")
    checks.append(_check(
        "session-engine", _("Admin session revocation support"), session_status, session_current,
        _("A Django session backend whose sessions can be revoked by the deployment."),
        _("Device and session revocation must never depend on stale browser state."),
        _("Django SESSION_ENGINE"),
        _("Prefer Django's database-backed session engine when immediate server-side session revocation is required."),
        href=_href("paxalia:admin_sessions"),
    ))

    otp_configured = _otp_available()
    checks.append(_check(
        "admin-2fa", _("Administrator 2FA"),
        PASS if otp_configured else DANGER,
        _("Mandatory TOTP enrollment and verification are available.") if otp_configured else _("django-otp TOTP is not configured."),
        _("django_otp and django_otp.plugins.otp_totp must be installed and migrated."),
        _("Layer 2 is mandatory for Paxalia Dashboard administrator access."),
        _("Paxalia administrator authentication configuration"),
        _("Install django-otp, add the TOTP plugin to INSTALLED_APPS, and migrate."),
        href=_href("paxalia:security_authentication"),
    ))

    admins = _admin_queryset(user_model)
    try:
        admin_total = admins.count()
    except Exception:
        admin_total = 0

    enrolled = 0
    if otp_configured:
        try:
            TOTPDevice = import_module("django_otp.plugins.otp_totp.models").TOTPDevice
            enrolled = TOTPDevice.objects.filter(user__in=admins, confirmed=True).values("user_id").distinct().count()
        except Exception:
            enrolled = 0

        if admin_total == 0:
            otp_status = NOT_APPLICABLE
            otp_current = _("No active staff or superuser administrator accounts were found.")
        elif enrolled == admin_total:
            otp_status = PASS
            otp_current = _("%d of %d administrator account(s) have confirmed 2FA.") % (enrolled, admin_total)
        else:
            otp_status = DANGER
            otp_current = _("%d of %d administrator account(s) have confirmed 2FA.") % (enrolled, admin_total)
        checks.append(_check(
            "admin-2fa-enrollment", _("Admin 2FA enrollment"), otp_status,
            otp_current, _("Every active administrator must have a confirmed second factor."),
            _("Password-only administrator access must not be possible."),
            _("Paxalia TOTP devices"),
            _("Complete 2FA enrollment for every administrator."),
            href=_href("paxalia:security_authentication"),
        ))

    webauthn_ok = _webauthn_available()
    checks.append(_check(
        "webauthn", _("Authorized device verification"),
        PASS if webauthn_ok else DANGER,
        _("WebAuthn server verification is available.") if webauthn_ok else _("The required WebAuthn library is not available."),
        _("The maintained Python WebAuthn implementation must be installed."),
        _("Layer 3 verifies an authorized credential; IP and browser fingerprints are not the security boundary."),
        _("Paxalia WebAuthn integration"),
        _("Install the supported webauthn dependency."),
        href=_href("paxalia:admin_devices"),
    ))

    if webauthn_ok and request is not None:
        try:
            from .webauthn_services import configuration_for_request
            rp_id, origin = configuration_for_request(request)
            checks.append(_check(
                "webauthn-config", _("WebAuthn origin and relying-party configuration"), PASS,
                _("RP ID=%(rp)s; origin=%(origin)s.") % {"rp": rp_id, "origin": origin},
                _("The RP ID must match the actual browser origin host or be a valid parent domain; production must use HTTPS."),
                _("Incorrect origin/RP binding can prevent valid authenticators from verifying and can weaken the intended deployment binding."),
                _("Paxalia WEBAUTHN_RP_ID / WEBAUTHN_ORIGIN and current request"),
                _("Configure the deployed origin and RP ID explicitly when the default derived values are not correct."),
                href=_href("paxalia:admin_devices"),
            ))
        except Exception as exc:
            checks.append(_check(
                "webauthn-config", _("WebAuthn origin and relying-party configuration"), DANGER,
                _("The effective WebAuthn configuration could not be validated: %s") % exc.__class__.__name__,
                _("A valid deployed browser origin and compatible RP ID."),
                _("Layer 3 must not silently fall back to a mismatched WebAuthn origin or relying-party configuration."),
                _("Paxalia WebAuthn runtime configuration"),
                _("Correct WEBAUTHN_RP_ID / WEBAUTHN_ORIGIN and deployment TLS configuration."),
                href=_href("paxalia:admin_devices"),
            ))

    secure_context = _effective_secure_request(request)
    production = not bool(getattr(settings, "DEBUG", False))
    if production:
        if secure_context is True:
            https_status = PASS
            https_current = _("The current administrator request is HTTPS.")
        elif getattr(settings, "SECURE_SSL_REDIRECT", False):
            https_status = PASS
            https_current = _("SECURE_SSL_REDIRECT is enabled; administrator requests are configured to use HTTPS.")
        else:
            https_status = DANGER
            https_current = _("Production HTTPS could not be confirmed for the current deployment.")
    else:
        https_status = WARNING if secure_context is False else PASS
        https_current = _("Development mode: the current request is HTTP.") if secure_context is False else _("Development mode; production HTTPS enforcement is not evaluated as a failure.")
    checks.append(_check(
        "https", _("HTTPS"), https_status, https_current,
        _("Production administrator authentication must run over HTTPS."),
        _("WebAuthn and administrator credentials require an appropriate secure browser context."),
        _("request.is_secure / SECURE_SSL_REDIRECT"),
        _("Configure TLS and, when applicable, SECURE_PROXY_SSL_HEADER."),
    ))

    secure_cookies = bool(getattr(settings, "SESSION_COOKIE_SECURE", False)) and bool(getattr(settings, "CSRF_COOKIE_SECURE", False))
    if production and secure_cookies:
        cookie_status = PASS
        cookie_current = _("Session and CSRF cookies are marked Secure.")
    elif production:
        cookie_status = DANGER
        cookie_current = _("One or more security-sensitive cookies are not marked Secure.")
    else:
        cookie_status = WARNING
        cookie_current = _("Development mode: Secure cookie flags are not required by this diagnostic." )
    checks.append(_check(
        "secure-cookies", _("Secure cookies"), cookie_status, cookie_current,
        _("SESSION_COOKIE_SECURE=True and CSRF_COOKIE_SECURE=True in production."),
        _("Protect authentication/session cookies from plaintext transport."),
        _("Django cookie settings"),
        _("Enable secure cookie settings for production."),
    ))

    samesite = str(getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax") or "").lower()
    samesite_status = PASS if samesite in {"lax", "strict"} else WARNING
    checks.append(_check(
        "session-samesite", _("Session SameSite policy"), samesite_status,
        _("SESSION_COOKIE_SAMESITE=%s.") % samesite if samesite else _("SESSION_COOKIE_SAMESITE is empty."),
        _("Lax or Strict unless the host application has a documented cross-site requirement."),
        _("SameSite limits cross-site request attachment of the administrator session cookie."),
        _("Django SESSION_COOKIE_SAMESITE"),
        _("Prefer Lax or Strict for the administrator session when compatible with the host application."),
    ))

    checks.append(_check(
        "csrf", _("CSRF protection"), PASS if "CsrfViewMiddleware" in middleware else DANGER,
        _("Django CSRF middleware is installed.") if "CsrfViewMiddleware" in middleware else _("CsrfViewMiddleware is missing."),
        _("CsrfViewMiddleware in MIDDLEWARE."),
        _("Authentication, device registration, and admin mutations must be CSRF protected."),
        _("Django MIDDLEWARE"),
        _("Add django.middleware.csrf.CsrfViewMiddleware."),
    ))

    checks.append(_check(
        "security-middleware", _("Django SecurityMiddleware"), PASS if "SecurityMiddleware" in middleware else DANGER,
        _("SecurityMiddleware is installed.") if "SecurityMiddleware" in middleware else _("SecurityMiddleware is missing."),
        _("django.middleware.security.SecurityMiddleware in MIDDLEWARE."),
        _("Django's baseline security response protections should remain active."),
        _("Django MIDDLEWARE"),
        _("Add SecurityMiddleware to MIDDLEWARE."),
    ))

    login_limit = int(config.get("SECURITY_LOGIN_RATE_LIMIT_ATTEMPTS", 0) or 0)
    login_window = int(config.get("SECURITY_LOGIN_RATE_LIMIT_WINDOW_SECONDS", 0) or 0)
    checks.append(_check(
        "login-rate-limit", _("Login rate limiting"), PASS if login_limit > 0 and login_window > 0 else DANGER,
        _("%d attempts per %d seconds.") % (login_limit, login_window) if login_limit and login_window else _("No explicit Paxalia login rate limit is configured."),
        _("A positive limit and bounded window."),
        _("Slow down repeated credential attacks before authentication attempts become an operational flood."),
        _("PAXALIA_DASHBOARD authentication policy"),
        _("Configure a positive administrator/login rate limit."),
    ))

    twofa_limit = int(config.get("SECURITY_2FA_RATE_LIMIT_ATTEMPTS", 0) or 0)
    twofa_window = int(config.get("SECURITY_2FA_RATE_LIMIT_WINDOW_SECONDS", 0) or 0)
    checks.append(_check(
        "twofa-rate-limit", _("2FA verification rate limiting"), PASS if twofa_limit > 0 and twofa_window > 0 else DANGER,
        _("%d attempts per %d seconds.") % (twofa_limit, twofa_window) if twofa_limit and twofa_window else _("No explicit Paxalia 2FA rate limit is configured."),
        _("A positive limit and bounded window."),
        _("Repeated second-factor guessing must be throttled."),
        _("PAXALIA_DASHBOARD 2FA policy"),
        _("Configure a positive 2FA rate limit."),
        href=_href("paxalia:security_authentication"),
    ))

    device_limit = int(config.get("SECURITY_DEVICE_RATE_LIMIT_ATTEMPTS", 0) or 0)
    device_window = int(config.get("SECURITY_DEVICE_RATE_LIMIT_WINDOW_SECONDS", 0) or 0)
    checks.append(_check(
        "device-rate-limit", _("Device verification rate limiting"), PASS if device_limit > 0 and device_window > 0 else DANGER,
        _("%d attempts per %d seconds.") % (device_limit, device_window) if device_limit and device_window else _("No explicit Paxalia device-verification rate limit is configured."),
        _("A positive limit and bounded window."),
        _("WebAuthn verification and challenge creation should not be an unlimited guessing or resource-exhaustion path."),
        _("PAXALIA_DASHBOARD device policy"),
        _("Configure a positive device-verification rate limit."),
        href=_href("paxalia:admin_devices"),
    ))

    threshold = int(config.get("SECURITY_FAILED_LOGIN_THRESHOLD", 0) or 0)
    window = int(config.get("SECURITY_FAILED_LOGIN_WINDOW_MINUTES", 0) or 0)
    checks.append(_check(
        "bruteforce", _("Brute-force monitoring"), PASS if threshold > 0 and window > 0 else DANGER,
        _("Alert threshold %d failures / %d minutes.") % (threshold, window) if threshold and window else _("Brute-force alerting is not configured."),
        _("A positive threshold and bounded window."),
        _("Persistent failed-login monitoring complements request-level throttling."),
        _("PAXALIA_DASHBOARD failed-login policy"),
        _("Configure SECURITY_FAILED_LOGIN_THRESHOLD and SECURITY_FAILED_LOGIN_WINDOW_MINUTES."),
        href=_href("paxalia:failed_login_activity"),
    ))

    allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
    if settings.DEBUG:
        host_status = WARNING if "*" in allowed_hosts else PASS
        host_current = _("Development mode: ALLOWED_HOSTS=%r") % allowed_hosts
    else:
        host_status = DANGER if not allowed_hosts or "*" in allowed_hosts else PASS
        host_current = _("ALLOWED_HOSTS is explicitly configured.") if host_status == PASS else _("ALLOWED_HOSTS is empty or contains '*'.")
    checks.append(_check(
        "allowed-hosts", _("ALLOWED_HOSTS"), host_status, host_current,
        _("Explicit production hostnames."),
        _("Reject unintended Host headers at the Django layer."),
        _("Django ALLOWED_HOSTS"),
        _("Set explicit production hostnames."),
    ))

    checks.append(_check(
        "debug", _("DEBUG"), WARNING if settings.DEBUG else PASS,
        _("DEBUG=True.") if settings.DEBUG else _("DEBUG=False."),
        _("DEBUG=False for production."),
        _("Django debug responses can expose internal diagnostics."),
        _("Django DEBUG"),
        _("Disable DEBUG in production."),
    ))

    checks.append(_check(
        "secret-key", _("Secret key configuration"), PASS if _setting_secret_is_configured() else DANGER,
        _("A non-placeholder SECRET_KEY is configured.") if _setting_secret_is_configured() else _("SECRET_KEY is missing or appears to be a development placeholder."),
        _("A strong, deployment-specific secret key."),
        _("Django signing, session, password-reset, and other security primitives depend on SECRET_KEY."),
        _("Django SECRET_KEY"),
        _("Configure a private production SECRET_KEY and keep it out of source control."),
    ))

    csp_present = any("csp" in name.lower() for name in middleware)
    checks.append(_check(
        "csp", _("Content Security Policy"), PASS if csp_present else WARNING,
        _("A CSP middleware appears to be installed.") if csp_present else _("No CSP middleware was detected by name."),
        _("A CSP appropriate to the host application and its assets."),
        _("CSP reduces the impact of several browser-side injection classes."),
        _("Host project's MIDDLEWARE"),
        _("Configure and verify the host project's CSP."),
    ))

    block_present = "SecurityBlockMiddleware" in middleware
    checks.append(_check(
        "security-block", _("Security blocking middleware"), PASS if block_present else NOT_APPLICABLE,
        _("SecurityBlockMiddleware is installed.") if block_present else _("No optional IP-blocking middleware is enabled."),
        _("Enabled when this deployment uses Paxalia's IP blocklist enforcement."),
        _("Provides an application-level blocking layer for configured addresses."),
        _("Paxalia middleware configuration"),
        _("Enable only when this deployment needs Paxalia IP blocking."),
    ))

    logging_ok = bool(config.get("LOGGING_ENABLED", False)) and bool(config.get("LOG_CAPTURE_STANDARD_LOGGING", False))
    checks.append(_check(
        "paxalia-logging", _("Paxalia persistent logging"), PASS if logging_ok else DANGER,
        _("Persistent logging and standard Python/Django capture are enabled.") if logging_ok else _("Paxalia persistent logging/capture is disabled."),
        _("Paxalia logging enabled with standard logging capture."),
        _("Authentication, security, and operational events need one persistent investigation surface."),
        _("PAXALIA_DASHBOARD logging configuration"),
        _("Enable Paxalia logging and standard capture."),
        href=_href("paxalia:logs"),
    ))

    retention = config.get("LOG_RETENTION_DAYS", {}) or {}
    security_retention = int(retention.get("security", 0) or 0)
    login_retention = int(retention.get("login", 0) or 0)
    checks.append(_check(
        "log-retention", _("Security log retention"), PASS if security_retention > 0 and login_retention > 0 else DANGER,
        _("Security=%d days; login=%d days.") % (security_retention, login_retention),
        _("Both security and login retention periods must be positive."),
        _("Security history must remain available for operational investigation while remaining bounded."),
        _("PAXALIA_DASHBOARD LOG_RETENTION_DAYS"),
        _("Configure positive login/security retention windows."),
        href=_href("paxalia:logs"),
    ))

    protected_exports = bool(config.get("PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED", False))
    checks.append(_check(
        "protected-exports", _("Protected export encryption"), PASS if protected_exports else DANGER,
        _("Protected-model exports require encryption.") if protected_exports else _("Protected-model exports can be produced without required encryption."),
        _("PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED=True."),
        _("Protected administrative data should not silently leave the application unencrypted."),
        _("PAXALIA_DASHBOARD package policy"),
        _("Require encryption for protected models."),
        href=_href("paxalia:admin_packages"),
    ))

    sensitive_fields = list(config.get("ADMIN_SENSITIVE_FIELDS", []) or [])
    checks.append(_check(
        "sensitive-fields", _("Sensitive-field protection"), PASS if sensitive_fields else DANGER,
        _("%d sensitive field name(s) are protected by default.") % len(sensitive_fields),
        _("A non-empty protected-field policy."),
        _("Paxalia Admin should not render credential-like fields as ordinary values."),
        _("PAXALIA_DASHBOARD ADMIN_SENSITIVE_FIELDS"),
        _("Keep the sensitive-field policy populated and review project-specific additions."),
        href=_href("paxalia:admin_home"),
    ))

    admin_gate = False
    try:
        # Check the actual privileged entry points, not merely that the
        # decorator module can be imported. A callable decorator by itself
        # does not prove that every administrative surface is protected.
        from .admin_center import package_views, views as admin_views
        required_views = (
            admin_views.admin_home,
            admin_views.admin_models,
            admin_views.admin_audit,
            admin_views.model_overview,
            admin_views.model_changelist,
            admin_views.model_action,
            admin_views.model_add,
            admin_views.model_change,
            admin_views.model_detail,
            admin_views.model_delete,
            admin_views.model_bulk_delete,
            admin_views.model_history,
            admin_views.model_stats,
            package_views.package_center,
            package_views.package_history,
            package_views.package_export_center,
            package_views.package_import_center,
            package_views.model_export,
            package_views.model_import,
            package_views.model_localization,
            package_views.package_failure_report,
            package_views.package_retry,
        )
        admin_gate = bool(required_views) and all(
            bool(getattr(view, "paxalia_gate", False)) for view in required_views
        )
    except Exception:
        admin_gate = False
    checks.append(_check(
        "admin-gate", _("Paxalia Admin mandatory security gate"), PASS if admin_gate else DANGER,
        _("Privileged Paxalia views use the central Layer 1 + Layer 2 + Layer 3 gate.") if admin_gate else _("Central administrator security gate is unavailable."),
        _("Layer 1 + Layer 2 + Layer 3 before privileged dashboard access."),
        _("A hidden button or frontend check must never be the only admin security boundary."),
        _("Paxalia admin_security module"),
        _("Restore the central admin security decorator on privileged views."),
        href=_href("paxalia:security_overview"),
    ))

    max_session = int(config.get("ADMIN_SESSION_MAX_AGE_SECONDS", 0) or 0)
    checks.append(_check(
        "admin-session", _("Admin session security"), PASS if max_session > 0 else DANGER,
        _("Paxalia administrator sessions have a bounded verification age of %d seconds.") % max_session if max_session > 0 else _("No positive privileged session verification lifetime is configured."),
        _("A positive bounded administrator verification lifetime."),
        _("A stale privileged session must not remain trusted indefinitely."),
        _("PAXALIA_DASHBOARD ADMIN_SESSION_MAX_AGE_SECONDS"),
        _("Configure a positive admin session verification lifetime."),
        href=_href("paxalia:admin_sessions"),
    ))

    active_admin_credentials = 0
    active_admin_devices = 0
    try:
        admin_ids = admins.values("pk")
        active_admin_devices = PaxaliaDevice.objects.filter(user_id__in=admin_ids, status="active").count()
        active_admin_credentials = PaxaliaDeviceCredential.objects.filter(
            device__user_id__in=admin_ids, device__status="active"
        ).count()
        covered_admins = PaxaliaDeviceCredential.objects.filter(
            device__user_id__in=admin_ids, device__status="active"
        ).values("device__user_id").distinct().count()
        if admin_total == 0:
            device_status = NOT_APPLICABLE
        elif webauthn_ok and covered_admins == admin_total:
            device_status = PASS
        else:
            device_status = DANGER
        device_current = _("%d of %d administrator account(s) have at least one active authorized credential; %d active device record(s) and %d active WebAuthn credential(s) exist.") % (
            covered_admins, admin_total, active_admin_devices, active_admin_credentials
        )
    except Exception:
        device_status = WARNING
        device_current = _("WebAuthn is available, but registered-device state could not be fully inspected.")
    checks.append(_check(
        "admin-device", _("Authorized admin device"), device_status, device_current,
        _("Every administrator must have at least one active authorized credential."),
        _("Layer 3 binds privileged access to a registered WebAuthn credential."),
        _("Paxalia device registry"),
        _("Register an authorized authenticator for every administrator."),
        href=_href("paxalia:admin_devices"),
    ))

    max_devices = int(config.get("ADMIN_MAX_DEVICES", 0) or 0)
    checks.append(_check(
        "admin-device-limit", _("Administrator device limit"), PASS if max_devices > 0 else DANGER,
        _("Up to %d active authorized device(s) per administrator.") % max_devices if max_devices > 0 else _("No positive active-device limit is configured."),
        _("A positive configurable maximum for active device credentials."),
        _("Bounded credential enrollment limits reduce administrative sprawl and help keep recovery manageable."),
        _("PAXALIA_DASHBOARD ADMIN_MAX_DEVICES"),
        _("Configure a positive maximum number of active administrator devices."),
        href=_href("paxalia:admin_devices"),
    ))

    challenge_ttl = int(config.get("WEBAUTHN_CHALLENGE_TTL_SECONDS", 0) or 0)
    challenge_status = PASS if webauthn_ok and 30 <= challenge_ttl <= 15 * 60 else (WARNING if challenge_ttl > 0 else DANGER)
    checks.append(_check(
        "webauthn-challenge", _("WebAuthn challenge lifecycle"), challenge_status,
        _("Challenges expire after %d seconds and are stored server-side as one-time state.") % challenge_ttl if challenge_ttl > 0 else _("No WebAuthn challenge TTL is configured."),
        _("A short positive TTL with single-use server-side challenge state."),
        _("Short-lived, single-use challenges are the replay boundary for Layer 3."),
        _("PAXALIA_DASHBOARD WEBAUTHN_CHALLENGE_TTL_SECONDS"),
        _("Keep the challenge lifetime short and never reuse a challenge as a credential."),
        href=_href("paxalia:admin_devices"),
    ))

    proxy = getattr(settings, "SECURE_PROXY_SSL_HEADER", None)
    if proxy:
        proxy_valid = isinstance(proxy, (tuple, list)) and len(proxy) == 2 and all(proxy)
        proxy_status = PASS if proxy_valid else DANGER
        proxy_current = _("SECURE_PROXY_SSL_HEADER is configured.") if proxy_valid else _("SECURE_PROXY_SSL_HEADER is malformed.")
    else:
        proxy_status = NOT_APPLICABLE
        proxy_current = _("No forwarded TLS header is configured; this is only required when TLS terminates at a trusted proxy.")
    checks.append(_check(
        "trusted-proxy", _("Trusted proxy HTTPS configuration"), proxy_status, proxy_current,
        _("A correct SECURE_PROXY_SSL_HEADER only when TLS is terminated by a trusted proxy."),
        _("Incorrect proxy trust can make request security state unreliable."),
        _("Django SECURE_PROXY_SSL_HEADER"),
        _("Configure the trusted proxy header only for infrastructure you control."),
    ))

    summary = {
        status: sum(1 for check in checks if check["status"] == status)
        for status in [PASS, WARNING, DANGER, DISABLED, NOT_CONFIGURED, NOT_APPLICABLE]
    }
    return {
        "checks": checks,
        "summary": summary,
        "total": len(checks),
    }
