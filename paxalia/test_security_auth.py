"""Security/auth regression coverage for Paxalia's final administrator gate."""
from __future__ import annotations

from datetime import timedelta
import ast
import importlib.util
from importlib import import_module
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest import skipUnless
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from . import admin_security
from .security_health import DANGER, PASS, run_security_health_checks
from .settings import DEFAULTS


def dashboard_path() -> str:
    return urlsplit(reverse("paxalia:dashboard")).path.rstrip("/") or "/"


def dashboard_url() -> str:
    return reverse("paxalia:dashboard")


def logs_url() -> str:
    return reverse("paxalia:logs")


def dashboard_auth_path(suffix: str = "") -> str:
    base = dashboard_path()
    suffix = suffix.lstrip("/")
    return base if not suffix else f"{base}/{suffix}"


class DashboardAuthenticationIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_superuser(
            username="paxalia-gate-admin",
            email="gate-admin@example.com",
            password="test-password",
        )

    def test_dashboard_unauthenticated_redirects_to_host_login(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        with override_settings(PAXALIA_DASHBOARD=config):
            response = self.client.get(reverse("paxalia:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response["Location"])
        self.assertIn("next=", response["Location"])

    def test_incomplete_host_admin_session_preserves_host_login_and_starts_paxalia_verification(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        self.client.force_login(self.admin_user)
        session_before = self.client.session.get("_auth_user_id")

        with override_settings(PAXALIA_DASHBOARD=config):
            response = self.client.get(reverse("paxalia:logs"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("paxalia:auth_2fa_setup"), response["Location"])
        self.assertEqual(self.client.session.get("_auth_user_id"), session_before)
        self.assertEqual(
            self.client.session.get(admin_security.ADMIN_INTENT_KEY),
            True,
        )
        self.assertEqual(
            self.client.session.get(admin_security.ADMIN_USER_KEY),
            str(self.admin_user.pk),
        )
        self.assertEqual(
            self.client.session.get(admin_security.ADMIN_STAGE_KEY),
            admin_security.STAGE_PRIMARY,
        )

    def test_paxalia_login_entry_point_reuses_host_login(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        with override_settings(PAXALIA_DASHBOARD=config):
            response = self.client.get(
                reverse("paxalia:auth_login"),
                {"next": reverse("paxalia:logs")},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response["Location"])
        self.assertIn("next=", response["Location"])


    def test_direct_private_dashboard_login_is_always_paxalia_admin_flow(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = False
        with override_settings(PAXALIA_DASHBOARD=config):
            response = self.client.get(reverse("paxalia:auth_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator sign in")
        self.assertNotIn(reverse("core:login"), response.get("Location", ""))

    def test_paxalia_login_isolated_by_default_configuration(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.pop("AUTH_USE_HOST_LOGIN", None)
        with override_settings(PAXALIA_DASHBOARD=config):
            response = self.client.get(
                reverse("paxalia:auth_login"),
                {"next": reverse("paxalia:logs")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(reverse("core:login"), response.get("Location", ""))

    def test_host_login_bridge_is_disabled_in_isolated_mode(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": False,
            "AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",),
            "AUTH_ADMIN_HOME_URL": dashboard_url(),
        })
        request = self._host_2fa_bridge_request(next_url=logs_url())
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware = __import__(
                "paxalia.admin_auth_middleware",
                fromlist=["PaxaliaAdminHost2FARedirectMiddleware"],
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/login/")
            )
            response = middleware(request)
        self.assertEqual(response["Location"], "/login/")

    def test_isolated_admin_session_finalization_does_not_log_into_host(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        class TestSession(dict):
            session_key = "isolated-session-key"

        request = RequestFactory().get(dashboard_url())
        request.session = TestSession()
        request.session[admin_security.ADMIN_BACKEND_KEY] = "django.contrib.auth.backends.ModelBackend"

        credential = SimpleNamespace(pk="credential-1")
        user = self.admin_user

        with override_settings(
            PAXALIA_DASHBOARD={
                **dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {}),
                "AUTH_USE_HOST_LOGIN": False,
            }
        ), patch("django.contrib.auth.login") as host_login:
            admin_security.finalize_admin_session(request, user, credential, backend="django.contrib.auth.backends.ModelBackend")

        host_login.assert_not_called()
        self.assertEqual(request.session.get(admin_security.ADMIN_USER_KEY), str(user.pk))
        self.assertTrue(request.session.get(admin_security.ADMIN_FINAL_KEY))
        self.assertEqual(
            request.session.get(admin_security.ADMIN_ISOLATED_SESSION_KEY),
            request.session.session_key,
        )

    def test_paxalia_login_entry_point_uses_bundled_paxalia_flow_when_host_login_disabled(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = False
        with override_settings(PAXALIA_DASHBOARD=config):
            response = self.client.get(
                reverse("paxalia:auth_login"),
                {"next": reverse("paxalia:logs")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(reverse("core:login"), response.get("Location", ""))

    def test_isolated_authentication_backends_exclude_axes_by_default(self):
        from .forms import PaxaliaAuthenticationForm

        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({"AUTH_USE_HOST_LOGIN": False, "AUTH_ISOLATED_AUTHENTICATION_BACKENDS": None})
        with override_settings(
            AUTHENTICATION_BACKENDS=(
                "axes.backends.AxesStandaloneBackend",
                "users.backends.EmailOrUsernameBackend",
                "django.contrib.auth.backends.ModelBackend",
            ),
            PAXALIA_DASHBOARD=config,
        ):
            paths = PaxaliaAuthenticationForm._isolated_backend_paths()

        self.assertEqual(paths, ("django.contrib.auth.backends.ModelBackend",))

    def test_paxalia_auth_resolve_url_uses_django_shortcuts(self):
        from django.shortcuts import resolve_url
        from paxalia.views import auth as auth_views
        self.assertIs(auth_views.resolve_url, resolve_url)

    def test_admin_home_url_is_server_side_and_used_as_safe_fallback(self):
        from paxalia.views import auth as auth_views
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = False
        config["AUTH_ADMIN_HOME_URL"] = dashboard_url()
        with override_settings(PAXALIA_DASHBOARD=config):
            request = RequestFactory().get(dashboard_auth_path("auth/login/"), HTTP_HOST="testserver")
            request.session = {}
            self.assertEqual(admin_security.admin_home_url(request), dashboard_url())
            self.assertEqual(auth_views._safe_next(request, ""), dashboard_url())

    def test_admin_home_url_rejects_external_values(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_ADMIN_HOME_URL"] = "https://example.com/secret"
        with override_settings(PAXALIA_DASHBOARD=config):
            request = RequestFactory().get(dashboard_url(), HTTP_HOST="testserver")
            request.session = {}
            self.assertEqual(admin_security.admin_home_url(request), reverse("paxalia:dashboard"))

    def test_webauthn_client_does_not_fallback_to_public_root(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        source = (root / "static/paxalia/scripts/webauthn.js").read_text(encoding="utf-8")
        self.assertNotIn("result.redirect || '/'", source)
        self.assertIn("The server did not provide a valid Paxalia administrator destination", source)
        self.assertNotIn("AUTH_ADMIN_HOME_URL", source)

    def test_paxalia_auth_login_template_is_available_from_installed_package(self):
        from django.template.loader import get_template
        from pathlib import Path

        root = Path(__file__).resolve().parent
        self.assertTrue((root / "templates/paxalia_auth/login.html").exists())
        template = get_template("paxalia_auth/login.html")
        self.assertIn("Administrator sign in", template.template.source)

    def test_paxalia_auth_templates_are_namespaced_away_from_host_registration_templates(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent
        source = (root / "views/auth.py").read_text(encoding="utf-8")
        self.assertNotIn('"registration/', source)
        self.assertNotIn("'registration/", source)
        auth_templates = root.joinpath("templates/paxalia_auth")
        required = {
            "access-denied.html", "device-register.html", "device-verify.html",
            "forgot-password.html", "login.html", "password_change.html",
            "password_change_done.html", "password_reset_complete.html",
            "password_reset_done.html", "password_reset_email.html",
            "password_reset_subject.html", "recovery-codes.html",
            "reset-password.html", "session-expired.html", "signup.html",
            "two-factor-setup.html", "two-factor.html",
        }
        self.assertTrue(required.issubset({p.name for p in auth_templates.glob("*")}))

    def test_admin_home_config_is_not_exposed_by_auth_render_context(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        source = (root / "views/auth.py").read_text(encoding="utf-8")
        self.assertIn("admin_home_url(request)", source)
        self.assertNotIn('context.setdefault("auth_admin_home_url"', source)

    def test_authenticated_host_user_does_not_enter_isolated_paxalia_flow_automatically(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = False
        with override_settings(PAXALIA_DASHBOARD=config):
            self.client.force_login(self.admin_user)
            response = self.client.get(
                reverse("paxalia:auth_login"),
                {"next": reverse("paxalia:logs")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator sign in")
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_completed_paxalia_session_does_not_restart_from_login_entry(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        with override_settings(PAXALIA_DASHBOARD=config):
            self.client.force_login(self.admin_user)
            session = self.client.session
            session[admin_security.ADMIN_FINAL_KEY] = True
            session[admin_security.ADMIN_STAGE_KEY] = admin_security.STAGE_COMPLETE
            session[admin_security.ADMIN_AUTH_AT_KEY] = timezone.now().isoformat()
            session[admin_security.ADMIN_NEXT_KEY] = reverse("paxalia:logs")
            session.save()
            response = self.client.get(reverse("paxalia:auth_login"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("paxalia:logs"), response["Location"])
        self.assertEqual(
            self.client.session.get(admin_security.ADMIN_STAGE_KEY),
            admin_security.STAGE_COMPLETE,
        )

    def _host_2fa_bridge_request(self, *, pending=True, next_url=None, resolver=True):
        from django.contrib.sessions.middleware import SessionMiddleware

        next_url = next_url or dashboard_url()
        request = RequestFactory().post("/login/2fa/")
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = self.admin_user
        if resolver:
            request.resolver_match = SimpleNamespace(view_name="core:login-2fa", url_name="login-2fa")
        if pending:
            request.session[admin_security.ADMIN_INTENT_KEY] = True
            request.session[admin_security.ADMIN_NEXT_KEY] = next_url
            request.session[admin_security.ADMIN_HOST_AUTH_PENDING_KEY] = True
            request.session[admin_security.ADMIN_HOST_2FA_PENDING_KEY] = timezone.now().timestamp()
            request.session.save()
        return request

    def test_host_2fa_success_redirects_back_to_saved_admin_destination(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": True,
            "AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",),
            "AUTH_HOST_2FA_INTENT_TTL_SECONDS": 600,
            "AUTH_ADMIN_HOME_URL": dashboard_url(),
        })
        request = self._host_2fa_bridge_request(next_url=logs_url())
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )
            response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], logs_url())
        self.assertFalse(request.session.get(admin_security.ADMIN_HOST_2FA_PENDING_KEY))
        self.assertTrue(request.session.get(admin_security.ADMIN_INTENT_KEY))

    def test_host_2fa_bridge_resolves_configured_path_without_resolver_match(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({"AUTH_USE_HOST_LOGIN": True, "AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",)})
        request = self._host_2fa_bridge_request(next_url=logs_url(), resolver=False)
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware_module = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            )
            middleware = middleware_module.PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/login/")
            )
            with patch.object(
                middleware_module,
                "resolve",
                return_value=SimpleNamespace(view_name="core:login-2fa", url_name="login-2fa"),
            ):
                response = middleware(request)
        self.assertEqual(response["Location"], logs_url())
        self.assertTrue(request.session.get(admin_security.ADMIN_INTENT_KEY))
        self.assertFalse(request.session.get(admin_security.ADMIN_HOST_2FA_PENDING_KEY))

    def test_host_login_fallback_redirects_authenticated_admin_back_to_paxalia(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": True,
            "AUTH_LOGIN_URL": "core:login",
            "AUTH_HOST_2FA_INTENT_TTL_SECONDS": 600,
            "AUTH_ADMIN_HOME_URL": dashboard_url(),
        })
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get("/login/")
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = self.admin_user
        with override_settings(PAXALIA_DASHBOARD=config):
            admin_security.mark_admin_intent(request, logs_url())
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )
            response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], logs_url())
        self.assertTrue(request.session.get(admin_security.ADMIN_INTENT_KEY))
        self.assertFalse(request.session.get(admin_security.ADMIN_HOST_2FA_PENDING_KEY))

    def test_host_login_redirect_arms_signed_handoff_cookie(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": True,
            "AUTH_LOGIN_URL": "core:login",
            "AUTH_HOST_2FA_INTENT_TTL_SECONDS": 600,
        })
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get(dashboard_auth_path("auth/login/"))
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        with override_settings(PAXALIA_DASHBOARD=config):
            admin_security.mark_admin_intent(request, logs_url())
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/login/?next=" + logs_url().lstrip("/"))
            )
            response = middleware(request)
        self.assertIn("paxalia_admin_handoff", response.cookies)
        self.assertTrue(response.cookies["paxalia_admin_handoff"]["httponly"])
        self.assertEqual(response.cookies["paxalia_admin_handoff"]["samesite"], "Lax")

    def test_host_2fa_bridge_survives_host_session_rotation(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": True,
            "AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",),
            "AUTH_HOST_2FA_INTENT_TTL_SECONDS": 600,
            "AUTH_ADMIN_HOME_URL": dashboard_url(),
        })
        from django.contrib.sessions.middleware import SessionMiddleware
        handoff_request = RequestFactory().get(dashboard_auth_path("auth/login/"))
        SessionMiddleware(lambda req: None).process_request(handoff_request)
        handoff_request.session.save()
        with override_settings(PAXALIA_DASHBOARD=config):
            admin_security.mark_admin_intent(handoff_request, logs_url())
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/login/?next=" + dashboard_url().lstrip("/"))
            )
            armed = middleware(handoff_request)

            rotated = RequestFactory().post("/login/2fa/")
            SessionMiddleware(lambda req: None).process_request(rotated)
            rotated.session.save()
            rotated.user = self.admin_user
            rotated.COOKIES["paxalia_admin_handoff"] = armed.cookies["paxalia_admin_handoff"].value
            rotated.resolver_match = SimpleNamespace(view_name="core:login-2fa", url_name="login-2fa")
            response = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )(rotated)
        self.assertEqual(response["Location"], logs_url())
        # The signed cookie must survive the host 2FA boundary so session
        # rotation / overlapping browser requests cannot consume the handoff.
        self.assertNotIn("paxalia_admin_handoff", response.cookies)

    def test_paxalia_logout_clears_unfinished_host_handoff_cookie(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().post(dashboard_auth_path("auth/logout/"))
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = self.admin_user
        with override_settings(PAXALIA_DASHBOARD=config):
            response = __import__("paxalia.views.auth", fromlist=["paxalia_logout"]).paxalia_logout(request)
        self.assertIn("paxalia_admin_handoff", response.cookies)
        self.assertEqual(response.cookies["paxalia_admin_handoff"]["max-age"], 0)

    def test_host_login_fallback_does_not_change_normal_authenticated_login_redirects(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({"AUTH_USE_HOST_LOGIN": True, "AUTH_LOGIN_URL": "core:login"})
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get("/login/")
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        request.user = self.admin_user
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )
            response = middleware(request)
        self.assertEqual(response["Location"], "/")

    def test_host_2fa_bridge_does_not_change_normal_login_redirects(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({"AUTH_USE_HOST_LOGIN": True, "AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",)})
        request = self._host_2fa_bridge_request(pending=False)
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )
            response = middleware(request)
        self.assertEqual(response["Location"], "/")

    def test_host_2fa_bridge_rejects_expired_admin_intent(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": True,"AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",), "AUTH_HOST_2FA_INTENT_TTL_SECONDS": 600})
        request = self._host_2fa_bridge_request()
        request.session[admin_security.ADMIN_HOST_2FA_PENDING_KEY] = (timezone.now() - timedelta(minutes=11)).timestamp()
        request.session.save()
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )
            response = middleware(request)
        self.assertEqual(response["Location"], "/")
        self.assertFalse(request.session.get(admin_security.ADMIN_HOST_2FA_PENDING_KEY))

    def test_host_2fa_bridge_keeps_internal_destination_safe(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config.update({
            "AUTH_USE_HOST_LOGIN": True,"AUTH_HOST_2FA_URL_NAMES": ("core:login-2fa",), "AUTH_ADMIN_HOME_URL": dashboard_url()})
        request = self._host_2fa_bridge_request(next_url="https://evil.example/steal")
        with override_settings(PAXALIA_DASHBOARD=config):
            middleware = __import__(
                "paxalia.admin_auth_middleware", fromlist=["PaxaliaAdminHost2FARedirectMiddleware"]
            ).PaxaliaAdminHost2FARedirectMiddleware(
                lambda req: HttpResponseRedirect("/")
            )
            response = middleware(request)
        self.assertEqual(response["Location"], dashboard_url())

    def test_webauthn_device_templates_do_not_expose_admin_home_context(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent / "templates/paxalia_auth"
        for filename in ("device-register.html", "device-verify.html"):
            source = (root / filename).read_text(encoding="utf-8")
            self.assertNotIn("auth_admin_home_url", source)

    @override_settings(LOGIN_URL="paxalia:auth_login")
    def test_login_url_self_reference_does_not_recurse_forever(self):
        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        with override_settings(PAXALIA_DASHBOARD=config):
            self.client.force_login(self.admin_user)
            response = self.client.get(
                reverse("paxalia:auth_login"),
                {"next": reverse("paxalia:logs")},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("paxalia:auth_2fa_setup"), response["Location"])


class IsolatedAuthenticationMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_superuser(
            username="paxalia-isolated-admin",
            email="isolated-admin@example.com",
            password="test-password",
        )

    def setUp(self):
        self.config = {
            **dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {}),
            "AUTH_USE_HOST_LOGIN": False,
            "AUTH_ADMIN_HOME_URL": dashboard_url(),
            "AUTH_ISOLATED_SESSION_COOKIE_NAME": "paxalia_test_isolated_session",
        }

    def _host_request(self, path=None):
        path = path or dashboard_url()
        from django.contrib.sessions.middleware import SessionMiddleware

        request = RequestFactory().get(path)
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def test_isolated_session_uses_distinct_cookie_and_preserves_host_session(self):
        from importlib import import_module
        from paxalia.auth_middleware import (
            PaxaliaIsolatedSessionMiddleware,
            isolated_session_cookie_name,
        )

        request = self._host_request()
        host_session = request.session
        host_session["host_marker"] = "host-value"
        host_session.save()
        host_session_key = host_session.session_key

        seen = {}

        def downstream(req):
            seen["host_marker"] = req.session.get("host_marker")
            req.session["package_marker"] = "package-value"
            req.session.save()
            seen["package_session_key"] = req.session.session_key
            return HttpResponse("ok")

        with override_settings(PAXALIA_DASHBOARD=self.config):
            package_cookie = isolated_session_cookie_name()
            response = PaxaliaIsolatedSessionMiddleware(downstream)(request)

        self.assertIs(request.session, host_session)
        self.assertEqual(request.session.session_key, host_session_key)
        self.assertEqual(request.session.get("host_marker"), "host-value")
        self.assertIsNone(seen["host_marker"])
        self.assertTrue(seen["package_session_key"])
        self.assertNotEqual(seen["package_session_key"], host_session_key)
        self.assertIn(package_cookie, response.cookies)
        self.assertTrue(response.cookies[package_cookie]["httponly"])
        self.assertEqual(response.cookies[package_cookie]["path"], dashboard_path())

        store = import_module(settings.SESSION_ENGINE).SessionStore(seen["package_session_key"])
        self.assertEqual(store.get("package_marker"), "package-value")
        self.assertEqual(store.get("host_marker"), None)

    def test_host_login_session_is_not_seen_by_host_2fa_inside_dashboard(self):
        from django.contrib.auth.middleware import AuthenticationMiddleware
        from django.contrib.auth.models import AnonymousUser
        from paxalia.auth_middleware import PaxaliaIsolatedSessionMiddleware

        request = self._host_request()
        host_session = request.session
        host_session["_auth_user_id"] = str(self.admin_user.pk)
        host_session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        host_session["_auth_user_hash"] = self.admin_user.get_session_auth_hash()
        host_session.save()
        host_session_key = host_session.session_key
        request.COOKIES = {
            settings.SESSION_COOKIE_NAME: host_session_key,
        }

        seen = {}

        def host_2fa_boundary(req):
            seen["user"] = req.user
            # Force Django's SimpleLazyObject to resolve while the isolated
            # Paxalia session is active. This is the exact boundary the host
            # 2FA middleware operates inside during a real dashboard request.
            seen["user_is_authenticated"] = bool(req.user.is_authenticated)
            seen["auth_user_id"] = req.session.get("_auth_user_id")
            return HttpResponse("host boundary")

        def with_authentication(req):
            AuthenticationMiddleware(lambda inner: host_2fa_boundary(inner)).process_request(req)
            return host_2fa_boundary(req)

        with override_settings(PAXALIA_DASHBOARD=self.config):
            PaxaliaIsolatedSessionMiddleware(with_authentication)(request)

        self.assertIsInstance(seen["user"], AnonymousUser)
        self.assertFalse(seen["user_is_authenticated"])
        self.assertIsNone(seen["auth_user_id"])

        # The isolated middleware is allowed to reopen the original host
        # SessionStore after nested middleware touched its object. What must
        # remain invariant is the host session identity and its stored data.
        self.assertEqual(request.session.session_key, host_session_key)
        self.assertEqual(request.session.get("_auth_user_id"), str(self.admin_user.pk))
        self.assertEqual(
            request.session.get("_auth_user_hash"),
            self.admin_user.get_session_auth_hash(),
        )

        # Verify the actual host-session row/key survived the dashboard boundary.
        host_store = import_module(settings.SESSION_ENGINE).SessionStore(host_session_key)
        self.assertEqual(host_store.get("_auth_user_id"), str(self.admin_user.pk))
        self.assertEqual(host_store.get("_auth_user_backend"), "django.contrib.auth.backends.ModelBackend")

    def test_isolated_logout_does_not_flush_host_session(self):
        from importlib import import_module
        from paxalia.views.auth import paxalia_logout

        # Logout is a POST-only endpoint. _host_request() intentionally creates
        # GET requests for the other middleware tests, so build the logout
        # request explicitly as POST here.
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().post(dashboard_auth_path("auth/logout/"))
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        host_session = request.session
        host_session["host_marker"] = "keep-me"
        host_session.save()
        host_session_key = host_session.session_key

        store = import_module(settings.SESSION_ENGINE).SessionStore()
        store[admin_security.ADMIN_FINAL_KEY] = True
        store[admin_security.ADMIN_STAGE_KEY] = admin_security.STAGE_COMPLETE
        store[admin_security.ADMIN_USER_KEY] = str(self.admin_user.pk)
        store[admin_security.ADMIN_ISOLATED_SESSION_KEY] = "pending"
        store.create()
        package_session_key = store.session_key
        store[admin_security.ADMIN_ISOLATED_SESSION_KEY] = package_session_key
        store.save()

        request.session = store
        request.user = self.admin_user

        with override_settings(PAXALIA_DASHBOARD=self.config):
            response = paxalia_logout(request)

        self.assertEqual(response.status_code, 302)

        # The privileged Paxalia store must no longer expose any privileged
        # state after logout.
        self.assertIsNone(store.get(admin_security.ADMIN_FINAL_KEY))
        self.assertIsNone(store.get(admin_security.ADMIN_STAGE_KEY))
        self.assertIsNone(store.get(admin_security.ADMIN_USER_KEY))
        self.assertIsNone(store.get(admin_security.ADMIN_ISOLATED_SESSION_KEY))

        # The request must now point at a fresh anonymous Paxalia session, not
        # the revoked privileged store.
        self.assertIsNot(request.session, store)
        self.assertIsNone(request.session.session_key)
        self.assertIsNone(request.session.get(admin_security.ADMIN_FINAL_KEY))
        self.assertIsNone(request.session.get(admin_security.ADMIN_STAGE_KEY))
        self.assertIsNone(request.session.get(admin_security.ADMIN_USER_KEY))
        self.assertIsNone(request.session.get(admin_security.ADMIN_ISOLATED_SESSION_KEY))

        # The host website session is a different session and must survive.
        reloaded_host = import_module(settings.SESSION_ENGINE).SessionStore(host_session_key)
        self.assertEqual(reloaded_host.get("host_marker"), "keep-me")

    def test_completed_isolated_session_exposes_package_user_only_on_dashboard(self):
        from paxalia.auth_middleware import PaxaliaIsolatedAdminAuthenticationMiddleware

        request = RequestFactory().get(dashboard_url())
        request.session = {
            admin_security.ADMIN_FINAL_KEY: True,
            admin_security.ADMIN_STAGE_KEY: admin_security.STAGE_COMPLETE,
            admin_security.ADMIN_USER_KEY: str(self.admin_user.pk),
        }
        request.user = SimpleNamespace(is_authenticated=False)

        seen = {}

        def downstream(req):
            seen["user"] = req.user
            return HttpResponseRedirect("/ok/")

        with override_settings(PAXALIA_DASHBOARD=self.config):
            response = PaxaliaIsolatedAdminAuthenticationMiddleware(downstream)(request)

        self.assertEqual(seen["user"].pk, self.admin_user.pk)
        self.assertEqual(response["Location"], "/ok/")

class SecurityPolicyContractTests(SimpleTestCase):
    def test_admin_security_uses_django_compatibility_imports(self):
        from django.urls import NoReverseMatch

        self.assertIs(admin_security.NoReverseMatch, NoReverseMatch)

    def test_completed_admin_responses_are_never_cacheable(self):
        from django.http import HttpResponse
        from unittest.mock import patch
        from .admin_security import admin_security_required

        request = RequestFactory().get(dashboard_url())
        request.user = SimpleNamespace(is_authenticated=True, is_active=True, is_staff=True, is_superuser=True, pk=1)
        request.session = {}

        @admin_security_required
        def view(req):
            return HttpResponse("private")

        with patch("paxalia.admin_security.host_authentication_enabled", return_value=False), \
             patch("paxalia.admin_security.admin_session_is_valid", return_value=True):
            response = view(request)

        self.assertIn("no-store", response["Cache-Control"] )
        self.assertEqual(response.content, b"private")

    def test_admin_security_preflight_is_available(self):
        self.assertTrue(callable(admin_security.admin_security_preflight))
        self.assertEqual(
            admin_security.PAXALIA_SECURITY_PREFLIGHT_ATTR,
            "_paxalia_security_preflight",
        )

    def test_mandatory_admin_security_has_no_disable_switch(self):
        self.assertNotIn("ADMIN_SECURITY_ENABLED", DEFAULTS)

    def test_intermediate_stage_is_not_complete(self):
        request = RequestFactory().get("/")
        request.session = {
            admin_security.ADMIN_FINAL_KEY: False,
            admin_security.ADMIN_STAGE_KEY: admin_security.STAGE_2FA,
        }
        request.user = SimpleNamespace(is_authenticated=True, is_active=True, pk=1)
        self.assertFalse(admin_security.admin_session_is_valid(request))

    def test_totp_secret_formatting_is_copy_friendly(self):
        from .views.auth import _format_totp_secret
        self.assertEqual(_format_totp_secret("JBSWY3DPEHPK3PXP"), "JBSW Y3DP EHPK 3PXP")

    def test_totp_manual_key_is_canonical_base32_from_hex_storage(self):
        import base64
        from types import SimpleNamespace
        from .views.auth import _totp_base32_secret

        raw = bytes.fromhex("3132333435363738393031323334353637383930")
        device = SimpleNamespace(key=raw.hex(), bin_key=raw, config_url="")
        expected = base64.b32encode(raw).decode("ascii").rstrip("=")
        result = _totp_base32_secret(device)
        self.assertEqual(result, expected)
        self.assertRegex(result, r"^[A-Z2-7]+$")

    def test_totp_setup_template_displays_unspaced_manual_key(self):
        from pathlib import Path
        template = (
            Path(__file__).resolve().parent
            / "templates/paxalia_auth/two-factor-setup.html"
        ).read_text(encoding="utf-8")
        self.assertIn('<code id="paxaliaTotpSecret" class="paxalia-auth-secret__value"', template)
        self.assertIn("Enter a setup key", template)
        self.assertIn("Time-based", template)
        self.assertNotIn("{{ formatted_totp_secret }}", template)

    def test_totp_setup_visuals_generate_matching_uri_and_qr(self):
        import base64
        from types import SimpleNamespace
        from urllib.parse import parse_qs, urlsplit
        from .views.auth import _totp_setup_visuals

        raw = bytes.fromhex("3132333435363738393031323334353637383930")
        user = SimpleNamespace(get_username=lambda: "test@example.com")
        device = SimpleNamespace(
            user=user,
            key=raw.hex(),
            bin_key=raw,
            digits=6,
            step=30,
            config_url="otpauth://totp/legacy?secret=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA&issuer=Legacy",
        )
        result = _totp_setup_visuals(device)
        expected = base64.b32encode(raw).decode("ascii").rstrip("=")
        query = parse_qs(urlsplit(result["otpauth_url"]).query)

        self.assertEqual(result["totp_secret"], expected)
        self.assertEqual(query["secret"][0], expected)
        self.assertEqual(query["issuer"][0], "Paxalia")
        self.assertEqual(query["algorithm"][0], "SHA1")
        self.assertEqual(query["digits"][0], "6")
        self.assertEqual(query["period"][0], "30")
        self.assertTrue(result["qr_code_data_uri"].startswith("data:image/png;base64,"))

    def test_admin_security_preflight_can_return_response_before_gate(self):
        from django.http import JsonResponse
        from .admin_security import admin_security_preflight, admin_security_required

        request = RequestFactory().get("/uploads/init/")
        request.user = SimpleNamespace(is_authenticated=True, is_staff=True, is_superuser=False)
        request.session = {}

        def preflight(req, *args, **kwargs):
            return JsonResponse({"error": "invalid upload"}, status=400)

        @admin_security_required
        @admin_security_preflight(preflight)
        def gated_view(req, *args, **kwargs):
            return JsonResponse({"ok": True})

        config = dict(getattr(settings, "PAXALIA_DASHBOARD", {}) or {})
        config["AUTH_USE_HOST_LOGIN"] = True
        with override_settings(PAXALIA_DASHBOARD=config), \
             patch("paxalia.admin_security.admin_session_is_valid", return_value=False), \
             patch("paxalia.admin_security.begin_admin_verification") as begin:
            response = gated_view(request)

        self.assertEqual(response.status_code, 400)
        begin.assert_not_called()

    def test_external_next_value_is_not_accepted(self):
        request = RequestFactory().get("/dashboard/")
        request.META["HTTP_HOST"] = "dashboard.example.test"
        request.user = SimpleNamespace(is_authenticated=False)
        from django.urls import reverse
        self.assertEqual(
            admin_security._safe_path("https://evil.example/steal", request),
            reverse("paxalia:dashboard"),
        )


@skipUnless(importlib.util.find_spec("django_otp"), "django-otp is required for the live gate test")
class LiveGateContractTests(SimpleTestCase):
    @override_settings(DEBUG=False, SESSION_ENGINE="django.contrib.sessions.backends.db")
    def test_complete_session_requires_totp_device_and_active_credential(self):
        factory = RequestFactory()
        request = factory.get("/dashboard/")
        class TestSession(dict):
            session_key = "test-admin-session"

        request.session = TestSession({
            admin_security.ADMIN_FINAL_KEY: True,
            admin_security.ADMIN_STAGE_KEY: admin_security.STAGE_COMPLETE,
            admin_security.ADMIN_AUTH_AT_KEY: timezone.now().isoformat(),
            admin_security.ADMIN_DEVICE_KEY: "credential-1",
            admin_security.ADMIN_USER_KEY: "7",
        })
        request.user = SimpleNamespace(is_authenticated=True, is_active=True, pk=7)
        request._paxalia_isolated_auth = True

        fake_device = SimpleNamespace(user_id=7, status="active")
        fake_credential = SimpleNamespace(device=fake_device)
        totp_manager = MagicMock()
        totp_manager.filter.return_value.exists.return_value = True
        credential_manager = MagicMock()
        credential_manager.select_related.return_value.get.return_value = fake_credential
        login_event_manager = MagicMock()
        login_event_manager.filter.return_value.exists.return_value = True
        with patch("paxalia.admin_security.admin_user", return_value=True), \
             patch("django_otp.plugins.otp_totp.models.TOTPDevice.objects", totp_manager), \
             patch("paxalia.admin_security.PaxaliaDeviceCredential.objects", credential_manager), \
             patch("paxalia.admin_security.LoginEvent.objects", login_event_manager):
            self.assertTrue(admin_security.admin_session_is_valid(request))


class SecurityHealthShapeTests(TestCase):
    @override_settings(
        AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.ModelBackend"],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
        ],
        SECRET_KEY="x" * 64,
        DEBUG=False,
        ALLOWED_HOSTS=["example.test"],
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_ENGINE="django.contrib.sessions.backends.db",
    )
    def test_health_result_has_required_structured_status_fields(self):
        request = RequestFactory().get("/", secure=True, HTTP_HOST="example.test")
        result = run_security_health_checks(request)
        self.assertIn("summary", result)
        self.assertIn("checks", result)
        self.assertEqual(result["total"], len(result["checks"]))
        for check in result["checks"]:
            self.assertIn(check["status"], {PASS, "WARNING", DANGER, "DISABLED", "NOT CONFIGURED", "NOT APPLICABLE"})
            self.assertIn("current", check)
            self.assertIn("expected", check)
            self.assertIn("why", check)
            self.assertIn("source", check)
            self.assertIn("action", check)


class SecurityTemplateContractTests(SimpleTestCase):
    def test_settings_source_has_no_accidental_python_marker(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "settings.py").read_text(encoding="utf-8")
        self.assertNotEqual(source.splitlines()[0].strip(), "python")

    def test_dashboard_view_functions_do_not_fall_back_to_host_staff_login(self):
        root = __import__("pathlib").Path(__file__).resolve().parent / "views"
        violations = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    if (
                        isinstance(decorator, ast.Name)
                        and decorator.id == "staff_member_required"
                    ):
                        violations.append(f"{path.name}:{node.name}")
        self.assertEqual(violations, [])

    def test_privileged_admin_entry_points_are_gated(self):
        from .admin_center import package_views, views as admin_views

        required_views = (
            admin_views.admin_home, admin_views.admin_models, admin_views.admin_audit,
            admin_views.model_overview, admin_views.model_changelist, admin_views.model_action,
            admin_views.model_add, admin_views.model_change, admin_views.model_detail,
            admin_views.model_delete, admin_views.model_bulk_delete, admin_views.model_history,
            admin_views.model_stats, package_views.package_center, package_views.package_history,
            package_views.package_export_center, package_views.package_import_center,
            package_views.model_export, package_views.model_import, package_views.model_localization,
            package_views.package_failure_report, package_views.package_retry,
        )
        self.assertTrue(all(getattr(view, "paxalia_gate", False) for view in required_views))

    def test_error_pages_do_not_render_debug_context(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent / "templates"
        for filename in ("404.html", "500.html"):
            text = (root / filename).read_text(encoding="utf-8")
            self.assertNotIn("{{ exception", text)
            self.assertNotIn("{{ traceback", text)
            self.assertNotIn("{{ sql", text.lower())

    def test_three_layer_labels_are_present(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parent / "templates/paxalia/security_authentication.html").read_text(encoding="utf-8")
        for text in ("Layer 1", "Layer 2", "Layer 3", "Activate 2FA", "authorized devices"):
            self.assertIn(text, template)

    def test_error_handlers_are_exposed_by_the_package(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        source = (root / "error_handlers.py").read_text(encoding="utf-8")
        self.assertIn("def paxalia_404", source)
        self.assertIn("def paxalia_500", source)
        self.assertIn("handler404 = paxalia_404", source)
        self.assertIn("handler500 = paxalia_500", source)

    def test_legacy_mfa_disable_route_is_not_a_bypass(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/mfa.py").read_text(encoding="utf-8")
        self.assertIn("administrator 2FA cannot be disabled", source)

    def test_auth_rate_limit_unpacking_does_not_shadow_gettext(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/auth.py").read_text(encoding="utf-8")
        self.assertNotIn('ok, _ = rate_allowed(', source)
        self.assertNotIn('ip_ok, _ = rate_allowed(', source)
        self.assertNotIn('identifier_ok, _ = rate_allowed(', source)
        self.assertNotIn('rate_ok, _ = rate_allowed(', source)

    def test_layer_2_uses_security_icon_and_auth_shell_uses_brand_icon(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        setup = (root / "templates/paxalia_auth/two-factor-setup.html").read_text(encoding="utf-8")
        auth_base = (root / "templates/paxalia/auth_base.html").read_text(encoding="utf-8")
        self.assertIn('<path d="M8 10V7a4 4 0 0 1 8 0v3"', setup)
        self.assertNotIn("paxalia-auth-brand-icon", setup)
        self.assertIn("paxalia/icons/brand/icon-brand.svg", auth_base)

    def test_webauthn_accepts_localhost_and_rejects_loopback_ip(self):
        from .webauthn_services import configuration_for_request, localhost_url_for_request

        rf = RequestFactory()
        with override_settings(DEBUG=True, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]):
            localhost_request = rf.get(dashboard_auth_path("auth/device/register/"), HTTP_HOST="localhost:8000")
            rp_id, origin = configuration_for_request(localhost_request)
            self.assertEqual(rp_id, "localhost")
            self.assertEqual(origin, "http://localhost:8000")

            loopback_request = rf.get(dashboard_auth_path("auth/device/register/"), HTTP_HOST="127.0.0.1:8000")
            with self.assertRaisesMessage(ValueError, "http://localhost"):
                configuration_for_request(loopback_request)
            self.assertEqual(
                localhost_url_for_request(loopback_request),
                f"http://localhost:8000{dashboard_auth_path('auth/device/register/')}",
            )

    def test_webauthn_contract_explains_localhost_requirement(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        source = (root / "webauthn_services.py").read_text(encoding="utf-8")
        template = (root / "templates/paxalia_auth/device-register.html").read_text(encoding="utf-8")
        script = (root / "static/paxalia/scripts/webauthn.js").read_text(encoding="utf-8")
        self.assertIn("is_local_web_authn_request", source)
        self.assertIn("localhost_url_for_request", source)
        self.assertIn("data-webauthn-localhost-required", template)
        self.assertIn("localhost-required", script)

    def test_webauthn_backup_eligibility_has_single_definition(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "webauthn_services.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def _authentication_backup_eligibility("), 1)

    def test_webauthn_backup_eligibility_bit_is_detected_without_bypassing_malformed_data(self):
        import base64
        from .webauthn_services import _authentication_backup_eligibility

        def encode(value):
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

        base = bytearray(37)
        base[32] = 0x04  # UV only.
        self.assertFalse(
            _authentication_backup_eligibility({
                "response": {"authenticatorData": encode(bytes(base))}
            })
        )

        base[32] = 0x0C  # UV + BE (backup eligible / multi-device).
        self.assertTrue(
            _authentication_backup_eligibility({
                "response": {"authenticatorData": encode(bytes(base))}
            })
        )

        self.assertFalse(_authentication_backup_eligibility({"response": {}}))

    def test_auth_spacing_contracts_cover_recovery_and_layer_3(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        css = (root / "static/paxalia/styles/components/auth.css").read_text(encoding="utf-8")
        recovery = (root / "templates/paxalia_auth/recovery-codes.html").read_text(encoding="utf-8")
        register = (root / "templates/paxalia_auth/device-register.html").read_text(encoding="utf-8")
        verify = (root / "templates/paxalia_auth/device-verify.html").read_text(encoding="utf-8")
        self.assertIn(".paxalia-auth-stack", css)
        self.assertIn(".paxalia-auth-actions", css)
        self.assertIn("paxalia-auth-recovery-stack", recovery)
        self.assertIn("paxalia-auth-device-stack", register)
        self.assertIn("paxalia-auth-device-stack", verify)

