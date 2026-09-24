from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.http import HttpResponse

from . import admin_security


class Fix21SecurityUxTests(TestCase):
    def _request_with_session(self, user):
        request = RequestFactory().get('/insights/')
        SessionMiddleware(lambda req: HttpResponse('ok')).process_request(request)
        request.session.save()
        request.user = user
        return request

    def test_pending_layer2_state_is_resumed_instead_of_reset(self):
        user = get_user_model().objects.create_user(username='fix21-layer2', password='pw', is_staff=True)
        request = self._request_with_session(user)
        request.session[admin_security.ADMIN_USER_KEY] = str(user.pk)
        request.session[admin_security.ADMIN_STAGE_KEY] = admin_security.STAGE_PRIMARY
        request.session[admin_security.ADMIN_INTENT_KEY] = True
        request.session[admin_security.ADMIN_NEXT_KEY] = '/insights/'
        request.session[admin_security.ADMIN_BACKEND_KEY] = 'django.contrib.auth.backends.ModelBackend'
        request.session.save()

        response = admin_security.begin_admin_verification(request, '/insights/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('paxalia:auth_2fa_setup'))
        self.assertEqual(request.session[admin_security.ADMIN_STAGE_KEY], admin_security.STAGE_PRIMARY)

    def test_pending_layer3_state_is_resumed_instead_of_reset(self):
        user = get_user_model().objects.create_user(username='fix21-layer3', password='pw', is_staff=True)
        request = self._request_with_session(user)
        request.session[admin_security.ADMIN_USER_KEY] = str(user.pk)
        request.session[admin_security.ADMIN_STAGE_KEY] = admin_security.STAGE_DEVICE
        request.session[admin_security.ADMIN_INTENT_KEY] = True
        request.session[admin_security.ADMIN_NEXT_KEY] = '/insights/'
        request.session[admin_security.ADMIN_BACKEND_KEY] = 'django.contrib.auth.backends.ModelBackend'
        request.session.save()

        response = admin_security.begin_admin_verification(request, '/insights/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('paxalia:auth_device_login'))
        self.assertEqual(request.session[admin_security.ADMIN_STAGE_KEY], admin_security.STAGE_DEVICE)

    def test_dashboard_base_removes_duplicate_topbar_brand_and_exposes_account_menu(self):
        source = (Path(__file__).resolve().parent / 'templates/paxalia/base.html').read_text(encoding='utf-8')
        self.assertNotIn('dashboard-topbar__brand', source)
        self.assertIn('data-sidebar-account-toggle', source)
        self.assertIn("{% url 'paxalia:auth_logout' %}", source)

    def test_security_sidebar_exposes_admin_security_pages(self):
        source = (Path(__file__).resolve().parent / 'templates/paxalia/base.html').read_text(encoding='utf-8')
        for name in ('security_overview', 'security_admins', 'security_authentication', 'admin_devices', 'admin_sessions', 'admin_login_activity', 'failed_login_activity'):
            self.assertIn(f"paxalia:{name}", source)

    def test_administrator_security_page_is_routed_and_contains_layer_columns(self):
        urls = (Path(__file__).resolve().parent / 'urls.py').read_text(encoding='utf-8')
        template = (Path(__file__).resolve().parent / 'templates/paxalia/security_admins.html').read_text(encoding='utf-8')
        self.assertIn("name='security_admins'", urls)
        self.assertIn('{% trans "Layer 1" %}', template)
        self.assertIn('{% trans "Layer 2" %}', template)
        self.assertIn('{% trans "Layer 3" %}', template)
        self.assertIn('{% trans "Last admin login" %}', template)

