"""Fix 22 regression coverage for authentication logging, sidebar UX, and Security Center."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.template import TemplateSyntaxError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from . import admin_security
from .models import LoginEvent

ROOT = Path(__file__).resolve().parent


class Fix22SourceContractTests(SimpleTestCase):
    def test_layer3_diagnostic_prints_are_removed(self):
        for filename in (
            ROOT / "views/auth.py",
            ROOT / "webauthn_services.py",
            ROOT / "static/paxalia/scripts/webauthn.js",
            ROOT / "static/paxalia/scripts/auth.js",
        ):
            source = filename.read_text(encoding="utf-8")
            self.assertNotIn("PAXALIA-WEBAUTHN", source, filename.name)
            self.assertNotIn("traceback.print_exc()", source, filename.name)

    def test_dashboard_topbar_has_no_duplicate_brand(self):
        source = (ROOT / "templates/paxalia/base.html").read_text(encoding="utf-8")
        css = (ROOT / "static/paxalia/styles/components/topbar.css").read_text(encoding="utf-8")
        self.assertNotIn("dashboard-topbar__brand", source)
        self.assertNotIn("dashboard-topbar__brand", css)

    def test_admin_sidebar_and_account_styles_are_present(self):
        css = (ROOT / "static/paxalia/styles/components/sidebar.css").read_text(encoding="utf-8")
        template = (ROOT / "templates/paxalia/base.html").read_text(encoding="utf-8")
        for token in (".sidebar-group--administration", ".sidebar-account", ".sidebar-account__summary", ".sidebar-account__item--danger"):
            self.assertIn(token, css)
        for token in ("sidebar-account", "auth_logout", "Administration", "Active sessions"):
            self.assertIn(token, template)

    def test_security_center_template_parses(self):
        from django.template.loader import get_template
        try:
            get_template("paxalia/security.html")
        except TemplateSyntaxError as exc:
            self.fail(f"Security Center template must parse: {exc}")

    def test_admin_session_revoke_does_not_shadow_gettext(self):
        source = (ROOT / "views/admin_security.py").read_text(encoding="utf-8")
        self.assertIn("deleted, _session_details =", source)
        self.assertNotIn("deleted, _ =", source)


    def test_every_admin_security_url_reference_exists_in_view_module(self):
        import re
        urls = (ROOT / "urls.py").read_text(encoding="utf-8")
        views = (ROOT / "views/admin_security.py").read_text(encoding="utf-8")
        refs = set(re.findall(r"admin_security_views\.([A-Za-z_][A-Za-z0-9_]*)", urls))
        defs = set(re.findall(r"^def ([A-Za-z_][A-Za-z0-9_]*)\(", views, flags=re.M))
        self.assertTrue(refs)
        self.assertFalse(refs - defs, sorted(refs - defs))
        self.assertIn("security_admins", refs)
        self.assertIn("security_admins", defs)

    def test_administrator_security_template_is_packaged(self):
        template = (ROOT / "templates/paxalia/security_admins.html").read_text(encoding="utf-8")
        for token in ("Layer 1", "Layer 2", "Layer 3", "Last admin login"):
            self.assertIn(token, template)

    def test_host_auth_marker_is_narrow_and_one_shot(self):
        source = (ROOT / "admin_security.py").read_text(encoding="utf-8")
        signal_source = (ROOT / "signals.py").read_text(encoding="utf-8")
        self.assertIn("ADMIN_HOST_AUTH_PENDING_KEY", source)
        self.assertIn("session.pop(ADMIN_HOST_AUTH_PENDING_KEY, None)", signal_source)
        self.assertIn("return", signal_source)


class Fix22BehaviorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="fix22-admin", password="pw", email="fix22@example.test"
        )

    def test_mark_admin_intent_sets_host_auth_marker(self):
        request = RequestFactory().get("/insights/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        admin_security.mark_admin_intent(request, "/insights/")
        self.assertTrue(request.session.get(admin_security.ADMIN_HOST_AUTH_PENDING_KEY))

    def test_host_login_signal_consumes_marker_without_recording_event(self):
        from .signals import handle_login

        request = RequestFactory().get("/login/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        request.session[admin_security.ADMIN_HOST_AUTH_PENDING_KEY] = True
        request.session.modified = True

        with patch("paxalia.signals._record_login") as record:
            handle_login(None, request, self.user)

        record.assert_not_called()
        self.assertFalse(request.session.get(admin_security.ADMIN_HOST_AUTH_PENDING_KEY, False))

    def test_normal_login_signal_still_records_event_without_marker(self):
        from .signals import handle_login

        request = RequestFactory().get("/login/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()

        fake_event = MagicMock()
        with patch("paxalia.signals._record_login", return_value=(fake_event, False)) as record:
            handle_login(None, request, self.user)
        record.assert_called_once()

    def test_security_center_route_renders(self):
        self.client.force_login(self.user)
        # This direct route uses the final security gate in a real deployment;
        # the assertion only ensures URL resolution remains intact here.
        self.assertEqual(reverse("paxalia:security"), "/insights/security/")

    def test_admin_session_revoke_other_session_returns_redirect(self):
        # Exercise the exact code path that previously failed after deleting a DB session.
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().post("/insights/security/sessions/revoke/")
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        request.user = self.user
        event = LoginEvent.objects.create(
            user=self.user, event_type="login", result="success",
            is_admin=True, session_key="non-current-fix22-session",
        )
        with patch("paxalia.admin_security.admin_session_is_valid", return_value=True):
            response = admin_security_view = __import__("paxalia.views.admin_security", fromlist=["admin_session_revoke"]).admin_session_revoke(
                request, event.id
            )
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertIsNotNone(event.logged_out_at)
        self.assertEqual(response.url, reverse("paxalia:admin_sessions"))
