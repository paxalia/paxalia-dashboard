"""Isolate Paxalia administrator authentication from host-site authentication.

The default package mode keeps the host application's authentication boundary
separate from Paxalia's administrator authentication. Paxalia still uses the
host project's Django user model and configured authentication backend for
its bundled password form, but it stores the administrator flow in a separate
Django session cookie scoped to the dashboard URL.

Default isolated flow:
    host session cookie              Paxalia session cookie
            |                                |
        website auth                    dashboard auth
            |                                |
     /login/ + host 2FA          password -> TOTP -> WebAuthn

The two sessions use the same configured Django session engine/backend, so
there is no second identity database. They are simply separate session keys
and cookies. This prevents host login, host 2FA, session rotation, or host
logout middleware from changing Paxalia's administrator state.

When AUTH_USE_HOST_LOGIN=True, this middleware leaves the host session alone
and Paxalia can use the explicit host-authentication compatibility bridge.
"""
from __future__ import annotations

from importlib import import_module
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ImproperlyConfigured
from django.urls import NoReverseMatch, reverse
from django.utils.cache import patch_vary_headers

from .admin_security import (
    ADMIN_FINAL_KEY,
    ADMIN_STAGE_KEY,
    ADMIN_USER_KEY,
    STAGE_COMPLETE,
    admin_user,
)
from .settings import get_config


User = get_user_model()


def _isolated_mode() -> bool:
    return not bool(get_config().get("AUTH_USE_HOST_LOGIN", False))


def _dashboard_path() -> str:
    configured = str(get_config().get("DASHBOARD_URL") or "").strip()
    if configured:
        if not configured.startswith("/"):
            configured = "/" + configured
        return urlsplit(configured).path.rstrip("/") or "/"
    try:
        return urlsplit(reverse("paxalia:dashboard")).path.rstrip("/") or "/"
    except NoReverseMatch:
        return "/"


def _is_paxalia_request(request) -> bool:
    path = str(getattr(request, "path_info", "") or request.path).rstrip("/") or "/"
    dashboard = _dashboard_path()
    return path == dashboard or path.startswith(dashboard + "/")


def isolated_session_cookie_name() -> str:
    value = get_config().get("AUTH_ISOLATED_SESSION_COOKIE_NAME")
    return str(value or "paxalia_admin_session").strip() or "paxalia_admin_session"


def isolated_session_cookie_path() -> str:
    path = _dashboard_path()
    return path if path != "/" else "/"


def isolated_session_max_age() -> int:
    return max(
        60,
        int(get_config().get("ADMIN_SESSION_MAX_AGE_SECONDS", 8 * 60 * 60)),
    )


def _session_store_class():
    engine = str(getattr(settings, "SESSION_ENGINE", "") or "").strip()
    if not engine:
        raise ImproperlyConfigured("Django SESSION_ENGINE is required for Paxalia isolated sessions.")
    module = import_module(engine)
    store = getattr(module, "SessionStore", None)
    if store is None:
        raise ImproperlyConfigured(
            f"SESSION_ENGINE {engine!r} does not expose a SessionStore class."
        )
    return store


class PaxaliaIsolatedSessionMiddleware:
    """Give Paxalia dashboard requests their own Django session cookie.

    The host application's session is captured before entering the dashboard
    and restored after the package response has been finalized. This class is
    deliberately callable rather than inheriting ``SessionMiddleware`` so the
    isolation contract remains correct both inside Django's middleware chain
    and when exercised directly by integration tests.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _finish_response(self, request, response, package_session, cookie_name, cookie_path):
        response["Referrer-Policy"] = "same-origin"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"

        accessed = bool(getattr(package_session, "accessed", False))
        modified = bool(getattr(package_session, "modified", False))
        empty = bool(package_session.is_empty())

        if accessed:
            patch_vary_headers(response, ("Cookie",))

        if modified or bool(getattr(settings, "SESSION_SAVE_EVERY_REQUEST", False)):
            if package_session.session_key is None:
                if not empty:
                    package_session.create()
            else:
                package_session.save()

        if package_session.session_key is None or package_session.is_empty():
            response.delete_cookie(cookie_name, path=cookie_path)
        else:
            response.set_cookie(
                cookie_name,
                package_session.session_key,
                max_age=isolated_session_max_age(),
                httponly=True,
                secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
                samesite=str(
                    get_config().get("AUTH_ISOLATED_SESSION_COOKIE_SAMESITE")
                    or getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax")
                    or "Lax"
                ),
                domain=get_config().get("AUTH_ISOLATED_SESSION_COOKIE_DOMAIN")
                or getattr(settings, "SESSION_COOKIE_DOMAIN", None),
                path=cookie_path,
            )
        return response

    def __call__(self, request):
        if not _isolated_mode() or not _is_paxalia_request(request):
            return self.get_response(request)

        host_session = getattr(request, "session", None)
        host_session_key = getattr(host_session, "session_key", None) if host_session is not None else None
        request._paxalia_host_session = host_session
        request._paxalia_host_session_key = host_session_key

        cookie_name = isolated_session_cookie_name()
        cookie_path = isolated_session_cookie_path()
        session_key = request.COOKIES.get(cookie_name)
        package_session = _session_store_class()(session_key)

        request.session = package_session
        request._paxalia_isolated_session_active = True
        request._paxalia_isolated_session_cookie_name = cookie_name
        request._paxalia_isolated_session_cookie_path = cookie_path

        try:
            response = self.get_response(request)
            # Django AuthenticationMiddleware installs request.user as a
            # SimpleLazyObject. Materialize that value before restoring the
            # host session; otherwise the lazy object can be evaluated later
            # against the host session and expose the website user through a
            # dashboard request that was supposed to see only the isolated
            # Paxalia session.
            user = getattr(request, "user", None)
            if user is not None:
                try:
                    getattr(user, "is_authenticated", False)
                except Exception:
                    pass
            return self._finish_response(
                request,
                response,
                package_session,
                cookie_name,
                cookie_path,
            )
        finally:
            # Repeat the materialization on exceptional paths where possible.
            # It is deliberately best-effort: authentication must never turn
            # an otherwise valid response into an error during cleanup.
            user = getattr(request, "user", None)
            if user is not None:
                try:
                    getattr(user, "is_authenticated", False)
                except Exception:
                    pass
            # The isolated package session must never leak into the host
            # session boundary. If nested dashboard middleware unexpectedly
            # rotated/flushed the host SessionStore object, reopen the
            # original host session key before control returns to Django's
            # outer SessionMiddleware. This preserves the website session
            # even when a third-party middleware touches request.session.
            restored_host_session = host_session
            if host_session is not None and host_session_key:
                current_host_key = getattr(host_session, "session_key", None)
                if current_host_key != host_session_key:
                    try:
                        restored_host_session = _session_store_class()(host_session_key)
                    except Exception:
                        restored_host_session = host_session
            request.session = restored_host_session
            request._paxalia_host_session = restored_host_session



class PaxaliaIsolatedAdminAuthenticationMiddleware:
    """Expose the completed Paxalia administrator only on dashboard routes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _isolated_mode() and _is_paxalia_request(request):
            user = AnonymousUser()
            if request.session.get(ADMIN_FINAL_KEY) and request.session.get(ADMIN_STAGE_KEY) == STAGE_COMPLETE:
                user_id = request.session.get(ADMIN_USER_KEY)
                if user_id:
                    try:
                        candidate = User.objects.get(pk=user_id)
                        if getattr(candidate, "is_active", False) and admin_user(candidate):
                            user = candidate
                    except User.DoesNotExist:
                        pass
            request.user = user
            request._paxalia_isolated_auth = True
        return self.get_response(request)


class PaxaliaHostAuthIsolationMiddleware:
    """Compatibility safety net for stacks without isolated sessions.

    Normally the dedicated Paxalia session middleware already causes Django's
    AuthenticationMiddleware to see an anonymous package session before the
    host 2FA middleware runs. This class remains available for integrations
    that place the isolation hook later in their middleware stack.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _isolated_mode() or not _is_paxalia_request(request):
            return self.get_response(request)

        original_user = getattr(request, "user", AnonymousUser())
        request._paxalia_host_user = original_user
        request.user = AnonymousUser()
        try:
            return self.get_response(request)
        finally:
            request.user = original_user
