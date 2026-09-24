"""Bridge the host application's authentication redirects back to Paxalia.

The host application owns Layer 1 authentication. Its login/2FA flow may use
its global LOGIN_REDIRECT_URL, which is correct for normal users but wrong for
an administrator flow that started inside the hidden Paxalia Dashboard.

This middleware only rewrites redirects associated with the configured host
login / 2FA endpoints while a short-lived Paxalia administrator intent is
present. It never changes normal login redirects and never grants privileged
access by itself.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import resolve_url
from django.urls import NoReverseMatch, resolve, reverse
from django.utils import timezone

from .admin_security import (
    ADMIN_HOST_2FA_PENDING_KEY,
    ADMIN_INTENT_KEY,
    ADMIN_NEXT_KEY,
    admin_home_url,
    admin_user,
    _safe_path,
)
from .settings import get_config


logger = logging.getLogger(__name__)


class PaxaliaAdminHost2FARedirectMiddleware:
    """Return successful host-admin authentication responses to Paxalia."""

    _REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
    _HANDOFF_COOKIE_SALT = "paxalia.admin.host_2fa_handoff.v1"

    @classmethod
    def _handoff_cookie_name(cls):
        name = get_config().get("AUTH_HOST_2FA_HANDOFF_COOKIE_NAME")
        return str(name or "paxalia_admin_handoff").strip() or "paxalia_admin_handoff"

    @classmethod
    def _handoff_ttl(cls):
        return max(30, int(get_config().get("AUTH_HOST_2FA_INTENT_TTL_SECONDS", 600)))

    @classmethod
    def _handoff_signer(cls):
        return TimestampSigner(salt=cls._HANDOFF_COOKIE_SALT)

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _configured_view_names():
        names = get_config().get("AUTH_HOST_2FA_URL_NAMES") or ()
        if isinstance(names, str):
            names = (names,)
        return {str(name).strip() for name in names if str(name).strip()}

    @staticmethod
    def _resolved_path(value) -> str:
        """Resolve a configured route/view name to its request path.

        Django URL names such as ``core:login-2fa`` must be resolved with
        ``reverse()``. ``resolve_url()`` is intentionally only the fallback
        for literal URLs/paths because it may legitimately return an
        un-resolved string when a named route cannot be reversed.
        """
        raw = str(value or "").strip()
        if not raw:
            return "/"
        if ":" in raw and not raw.startswith(("/", "http://", "https://")):
            try:
                raw = reverse(raw)
            except (NoReverseMatch, TypeError, ValueError):
                pass
        try:
            raw = resolve_url(raw)
        except Exception:
            pass
        return urlsplit(str(raw)).path.rstrip("/") or "/"

    @classmethod
    def _is_host_2fa_request(cls, request) -> bool:
        if request.method != "POST":
            return False

        configured = cls._configured_view_names()
        request_path = str(getattr(request, "path_info", "") or request.path).rstrip("/") or "/"

        # First use the actual resolver. This works with namespaced host URL
        # configurations even when resolver_match has not yet been attached.
        try:
            matched = resolve(request_path)
        except Exception:
            matched = None
        if matched is not None and configured:
            candidates = {
                str(getattr(matched, "view_name", "") or ""),
                str(getattr(matched, "url_name", "") or ""),
            }
            if configured.intersection(candidates):
                return True

        # A configured Django URL name is the preferred explicit contract.
        for name in configured:
            try:
                if cls._resolved_path(name) == request_path:
                    return True
            except Exception:
                continue

        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is not None and configured:
            candidates = {
                str(getattr(resolver_match, "view_name", "") or ""),
                str(getattr(resolver_match, "url_name", "") or ""),
            }
            if configured.intersection(candidates):
                return True

        # Last-resort compatibility for hosts that rotate sessions or run a
        # middleware stack without resolver metadata. This is intentionally
        # narrow: the request must already carry a live Paxalia admin handoff,
        # and the path must have a conventional 2FA/MFA final segment.
        final_segment = request_path.strip("/").rsplit("/", 1)[-1].lower()
        if final_segment in {"2fa", "mfa", "two-factor", "two_factor"}:
            session = getattr(request, "session", None)
            has_session_handoff = bool(
                session is not None
                and session.get(ADMIN_INTENT_KEY)
                and session.get(ADMIN_HOST_2FA_PENDING_KEY)
            )
            has_signed_handoff = bool(request.COOKIES.get(cls._handoff_cookie_name()))
            if has_session_handoff or has_signed_handoff:
                return True

        return False

    @classmethod
    def _host_login_path(cls, request) -> str | None:
        target = get_config().get("AUTH_LOGIN_URL") or getattr(request, "_paxalia_login_url", None)
        if not target:
            try:
                from django.conf import settings
                target = getattr(settings, "LOGIN_URL", None)
            except Exception:
                target = None
        if not target:
            return None
        try:
            return cls._resolved_path(target)
        except Exception:
            return None

    @classmethod
    def _is_host_login_location(cls, request, location) -> bool:
        configured_path = cls._host_login_path(request)
        if not configured_path or not location:
            return False
        return (urlsplit(str(location)).path.rstrip("/") or "/") == configured_path

    @classmethod
    def _is_host_login_request(cls, request) -> bool:
        if request.method != "GET":
            return False
        configured_path = cls._host_login_path(request)
        if not configured_path:
            return False
        request_path = str(getattr(request, "path_info", "") or request.path).rstrip("/") or "/"
        return request_path == configured_path

    @classmethod
    def _signed_handoff_value(cls, request):
        session = getattr(request, "session", None)
        if session is None or not session.get(ADMIN_INTENT_KEY):
            return None
        target = cls._safe_admin_destination(request)
        if not target:
            return None
        try:
            return cls._handoff_signer().sign_object({"next": target})
        except Exception:
            return None

    @classmethod
    def _cookie_handoff_target(cls, request):
        raw = request.COOKIES.get(cls._handoff_cookie_name())
        if not raw:
            return None
        try:
            payload = cls._handoff_signer().unsign_object(raw, max_age=cls._handoff_ttl())
        except (BadSignature, SignatureExpired, TypeError, ValueError):
            return None
        candidate = payload.get("next") if isinstance(payload, dict) else None
        if not candidate:
            return None
        return _safe_path(str(candidate), request, default=admin_home_url(request))

    @classmethod
    def _set_handoff_cookie(cls, request, response):
        value = cls._signed_handoff_value(request)
        if not value:
            return response
        response.set_cookie(
            cls._handoff_cookie_name(),
            value,
            max_age=cls._handoff_ttl(),
            httponly=True,
            secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)) and request.is_secure(),
            samesite="Lax",
            path="/",
        )
        return response

    @classmethod
    def _delete_handoff_cookie(cls, response):
        response.delete_cookie(cls._handoff_cookie_name(), path="/")

    @classmethod
    def _pending_admin_intent_is_fresh(cls, request) -> bool:
        session = getattr(request, "session", None)
        has_signed_cookie = bool(request.COOKIES.get(cls._handoff_cookie_name()))
        if session is None or not session.get(ADMIN_INTENT_KEY):
            # The host application's login implementation may rotate/replace
            # the Django session at the Layer-1 boundary. The signed cookie is
            # the surviving one-shot handoff marker in that case.
            valid = cls._cookie_handoff_target(request) is not None if has_signed_cookie else False
            if valid:
                logger.debug("Paxalia admin host-auth handoff recovered from signed cookie")
            return valid

        raw = session.get(ADMIN_HOST_2FA_PENDING_KEY)
        try:
            issued_at = float(raw)
        except (TypeError, ValueError):
            if has_signed_cookie and cls._cookie_handoff_target(request) is not None:
                return True
            session.pop(ADMIN_HOST_2FA_PENDING_KEY, None)
            session.modified = True
            return False

        now = timezone.now().timestamp()
        ttl = cls._handoff_ttl()
        age = now - issued_at
        if age < 0 or age > ttl:
            if has_signed_cookie and cls._cookie_handoff_target(request) is not None:
                return True
            session.pop(ADMIN_HOST_2FA_PENDING_KEY, None)
            session.modified = True
            return False
        return True

    @classmethod
    def _safe_admin_destination(cls, request) -> str:
        candidate = request.session.get(ADMIN_NEXT_KEY)
        if candidate:
            return _safe_path(candidate, request, default=admin_home_url(request))
        cookie_target = cls._cookie_handoff_target(request)
        if cookie_target:
            return cookie_target
        return admin_home_url(request)

    @classmethod
    def _consume_handoff(cls, request) -> str:
        target = cls._safe_admin_destination(request)
        session = getattr(request, "session", None)
        if session is not None:
            session.pop(ADMIN_HOST_2FA_PENDING_KEY, None)
            # Keep ADMIN_INTENT_KEY through the redirect. The destination is
            # immediately re-entered through Paxalia's protected view, which
            # establishes the non-privileged Layer 2 pending state.
            #
            # Do not delete the signed cookie here. The cookie intentionally
            # survives the host 2FA boundary so a host session rotation or an
            # overlapping browser request cannot lose the Paxalia handoff. It
            # is deleted when the privileged Paxalia session is finalized or
            # when Paxalia logout occurs.
            session.modified = True
        return target

    def __call__(self, request):
        response = self.get_response(request)

        # Host-login bridging is an explicit compatibility mode. In the
        # default isolated mode Paxalia never participates in the host site's
        # /login/ or /login/2fa/ flow.
        if not bool(get_config().get("AUTH_USE_HOST_LOGIN", False)):
            return response

        if not self._pending_admin_intent_is_fresh(request):
            return response

        user = getattr(request, "user", None)
        host_2fa_request = self._is_host_2fa_request(request)
        host_login_request = self._is_host_login_request(request)

        # Primary handoff: successful host 2FA response. A valid signed handoff
        # is sufficient to route back to the protected Paxalia entry point;
        # this middleware never grants dashboard access by itself.
        if host_2fa_request and response.status_code in self._REDIRECT_STATUSES:
            if response.get("Location"):
                if admin_user(user):
                    logger.debug("Paxalia admin host-auth 2FA handoff redirect: %s -> %s", request.path, self._safe_admin_destination(request))
                else:
                    logger.debug("Paxalia admin host-auth 2FA handoff recovered without active Django user: %s -> %s", request.path, self._safe_admin_destination(request))
                response["Location"] = self._consume_handoff(request)
            return response

        # Fallback handoff: the host 2FA implementation may redirect to its
        # normal /login/ endpoint before that endpoint redirects to HOME. This
        # is deliberately based on the signed handoff, not request.user,
        # because the host may have rotated the Django session during 2FA.
        if host_login_request and response.status_code in self._REDIRECT_STATUSES:
            if response.get("Location"):
                logger.debug("Paxalia admin host-auth fallback handoff redirect: %s -> %s", request.path, self._safe_admin_destination(request))
                response["Location"] = self._consume_handoff(request)
            return response

        # Persist the one-shot admin handoff outside the Django session before
        # the host login flow gets a chance to rotate/replace that session. The
        # value is signed and short-lived; it contains only a safe internal
        # dashboard destination and is never exposed to JavaScript. This check
        # intentionally happens after host 2FA handling so a successful 2FA
        # response that redirects to /login/ is consumed as the 2FA handoff
        # rather than merely arming another cookie.
        if response.status_code in self._REDIRECT_STATUSES and self._is_host_login_location(request, response.get("Location")):
            logger.debug("Paxalia admin host-auth handoff armed for host login redirect")
            return self._set_handoff_cookie(request, response)

        return response
