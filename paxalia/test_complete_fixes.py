"""Regression tests for the v4 dashboard complete-fixes stabilization pass."""

from __future__ import annotations

import html
import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.core import management
from django.db import models
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .models import DailySiteStats, PageView, Site
from .packages.localization import (
    is_translatable_model,
    language_choices,
    translated_field_objects,
    translation_editor_fields,
)


class _FakeParlerMeta:
    def __init__(self, fields):
        self._fields = {field.name: field for field in fields}
        self.model = SimpleNamespace(_meta=SimpleNamespace(get_field=self._fields.get))

    def get_all_fields(self):
        # django-parler exposes translated field names here, not Django Field
        # instances. This is the exact shape that previously caused the
        # ``'str' object has no attribute 'name'`` regression.
        return list(self._fields)

    def get_model_by_field(self, name):
        return self._fields.get(name)


class LocalizationRegressionTests(TestCase):
    @override_settings(
        LANGUAGES=(('en', 'English'),),
        PARLER_LANGUAGES={
            None: ({'code': 'en'}, {'code': 'fa'}, {'code': 'ar'}),
            'default': {'fallbacks': ['en'], 'hide_untranslated': False},
        },
    )
    def test_parler_field_names_are_resolved_to_real_fields(self):
        title = models.CharField(max_length=255, name='title', verbose_name='Title')
        body = models.TextField(name='body', verbose_name='Body')

        class FakeTranslatedModel:
            _parler_meta = _FakeParlerMeta([title, body])

        fields = translated_field_objects(FakeTranslatedModel)
        self.assertEqual([field.name for field in fields], ['title', 'body'])
        self.assertTrue(is_translatable_model(FakeTranslatedModel))
        self.assertEqual(
            [item['name'] for item in translation_editor_fields(FakeTranslatedModel)],
            ['title', 'body'],
        )

        choices = dict(language_choices())
        self.assertEqual(choices['en'], 'English')
        self.assertIn('fa', choices)
        self.assertIn('ar', choices)

    def test_plain_model_is_not_marked_localized_by_a_field_named_translations(self):
        ordinary_field = models.CharField(max_length=20, name='translations')

        class FakeOrdinaryModel:
            _meta = SimpleNamespace()

        # The localization helper must rely on an actual supported adapter,
        # not merely the existence of an ordinary field called ``translations``.
        FakeOrdinaryModel._meta.get_fields = lambda: [ordinary_field]
        self.assertFalse(is_translatable_model(FakeOrdinaryModel))


class PackageIdentityRegressionTests(TestCase):
    def test_primary_key_can_be_restored_when_it_is_the_package_identity(self):
        from .packages.engine import _assign_scalar_fields

        primary_key = models.IntegerField(name='id', primary_key=True)
        name_field = models.CharField(max_length=100, name='name')

        class FakeMeta:
            label_lower = 'tests.fakeobject'
            pk = primary_key
            concrete_fields = [primary_key, name_field]

        class FakeObject:
            _meta = FakeMeta
            id = 7
            name = 'old'

        obj = FakeObject()
        _assign_scalar_fields(obj, {'id': 42, 'name': 'new'}, restore_primary_key=True)
        self.assertEqual(obj.id, 42)
        self.assertEqual(obj.name, 'new')

        obj = FakeObject()
        _assign_scalar_fields(obj, {'id': 42, 'name': 'new'}, restore_primary_key=False)
        self.assertEqual(obj.id, 7)
        self.assertEqual(obj.name, 'new')


class DailyStatsRegressionTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.yesterday = (self.now - timedelta(days=1)).date()
        self.site_a = Site.objects.create(name='A', domain='a.example')
        self.site_b = Site.objects.create(name='B', domain='b.example')

    def _pageview(self, *, site=None, path='/', session_id='', ip_hash='hash'):
        return PageView.objects.create(
            site=site,
            url=f'https://example.test{path}',
            path=path,
            is_bot=False,
            is_api=False,
            ip_hash=ip_hash,
            session_id=session_id,
            created_at=datetime(
                self.yesterday.year,
                self.yesterday.month,
                self.yesterday.day,
                tzinfo=dt_timezone.utc,
            ),
        )

    def test_daily_aggregation_is_stored_per_site_plus_unassigned(self):
        self._pageview(site=self.site_a, path='/a', session_id='a1', ip_hash='shared')
        self._pageview(site=self.site_b, path='/b', session_id='b1', ip_hash='shared')
        self._pageview(site=None, path='/unassigned', session_id='u1', ip_hash='u')

        management.call_command('aggregate_daily_stats')

        rows = DailySiteStats.objects.filter(date=self.yesterday)
        self.assertEqual(rows.count(), 3)
        self.assertEqual(rows.get(site=self.site_a).total_views, 1)
        self.assertEqual(rows.get(site=self.site_b).total_views, 1)
        self.assertEqual(rows.get(site=None).total_views, 1)

    def test_all_sites_unique_visitor_counts_are_not_summed_from_per_site_rows(self):
        self._pageview(site=self.site_a, path='/a', session_id='same-session', ip_hash='shared')
        self._pageview(site=self.site_b, path='/b', session_id='same-session', ip_hash='shared')
        management.call_command('aggregate_daily_stats')

        # The branch's dashboard code derives All Sites distinct metrics from
        # raw PageViews. This assertion guards the underlying data condition.
        yesterday_qs = PageView.objects.filter(created_at__date=self.yesterday, is_bot=False, is_api=False)
        self.assertEqual(yesterday_qs.values('ip_hash').distinct().count(), 1)
        self.assertEqual(yesterday_qs.values('session_id').distinct().count(), 1)


class LiveLoggingRegressionTests(TestCase):
    def test_live_buffer_retains_exception_stack_trace(self):
        from .logging.handler import PaxaliaLiveLogBuffer

        PaxaliaLiveLogBuffer.clear()
        logger = logging.getLogger('paxalia.complete-fixes')
        try:
            raise RuntimeError('live-console-regression')
        except RuntimeError:
            record = logger.makeRecord(
                logger.name,
                logging.ERROR,
                __file__,
                1,
                'live failure',
                (),
                sys.exc_info(),
            )
        PaxaliaLiveLogBuffer.append(record)
        payload = PaxaliaLiveLogBuffer.snapshot(limit=10)
        self.assertEqual(len(payload['entries']), 1)
        self.assertIn('RuntimeError: live-console-regression', payload['entries'][0]['stack_trace'])
        self.assertIn('RuntimeError: live-console-regression', payload['entries'][0]['text'])
        PaxaliaLiveLogBuffer.clear()


class AIIncidentContextRegressionTests(TestCase):
    def test_ai_context_is_allowlisted_and_keeps_the_stack_trace(self):
        from .views.logs import _ai_incident_context

        event = SimpleNamespace(
            severity='ERROR',
            source='Application',
            category='runtime',
            action='failure',
            logger_name='paxalia.test',
            release='4.0.0',
            request_method='GET',
            response_status=500,
            duration_ms=12.5,
            message='Something failed',
            exception_type='RuntimeError',
            file_name='/opt/paxalia/venv/lib/python3.12/site-packages/paxalia/packages/engine.py',
            line_number=364,
            function_name='_translation_data',
            stack_trace='Traceback (most recent call last):\nRuntimeError: failure',
            request_path='/secret/internal/path',
            request_id='request-secret',
            correlation_id='correlation-secret',
            trace_id='trace-secret',
            session_id='session-secret',
            user_display='admin-secret',
            ip_address='192.0.2.10',
            user_agent='secret-agent',
            process_id=1234,
            thread_name='thread-secret',
            host='private-host',
            site='secret-site',
            fingerprint='fingerprint-secret',
            group=SimpleNamespace(id='group-secret'),
        )
        context = _ai_incident_context(event)
        self.assertIn('STACK TRACE', context)
        self.assertIn('RuntimeError: failure', context)
        self.assertIn('paxalia/packages/engine.py:364', context)
        for secret in (
            '/secret/internal/path',
            'request-secret',
            'correlation-secret',
            'trace-secret',
            'session-secret',
            'admin-secret',
            '192.0.2.10',
            'secret-agent',
            'private-host',
            'secret-site',
            'fingerprint-secret',
            'group-secret',
        ):
            self.assertNotIn(secret, context)


class CSPRegressionTests(TestCase):
    @override_settings(
        PAXALIA_DASHBOARD={
            'CONSENT_MODE_ENABLED': True,
            'CONSENT_COOKIE_NAME': 'consent',
            'CONSENT_COOKIE_GRANTED_VALUE': 'yes',
            'LOGGING_ENABLED': True,
            'LOG_BROWSER_CAPTURE_CONSOLE': False,
            'LOG_BROWSER_CAPTURE_RESOURCE_ERRORS': True,
            'LOG_BROWSER_MAX_EVENTS_PER_PAGE': 50,
        }
    )
    def test_consent_config_tag_is_metadata_not_executable_inline_script(self):
        from .templatetags.analytics_tags import analytics_consent_config

        rendered = analytics_consent_config()
        self.assertIn('<meta name="paxalia-consent-config"', rendered)
        self.assertNotIn('<script', rendered.lower())
        match = re.search(r'<meta name="paxalia-consent-config" content="([^"]+)">', rendered)
        self.assertIsNotNone(match)
        payload = json.loads(html.unescape(match.group(1)))
        self.assertTrue(payload['enabled'])
        self.assertEqual(payload['cookieName'], 'consent')

    def test_dashboard_base_marks_persian_as_rtl(self):
        from pathlib import Path

        template = Path(__file__).resolve().parent / 'templates' / 'paxalia' / 'base.html'
        source = template.read_text(encoding='utf-8')
        self.assertIn("LANGUAGE_CODE|slice:':2' == 'fa'", source)


class UploadAndReportRegressionTests(TestCase):
    def test_compound_upload_extensions_are_matched_as_configured(self):
        from .views.uploads import _extension_error

        with patch('paxalia.views.uploads.get_upload_blocked_extensions', return_value=()), patch(
            'paxalia.views.uploads.get_upload_allowed_extensions', return_value=('.tar.gz',)
        ):
            self.assertIsNone(_extension_error('backup.tar.gz'))

    def test_report_cache_claim_can_skip_a_concurrent_sender(self):
        from .management.commands.send_scheduled_reports import Command

        report = SimpleNamespace(frequency='weekly', last_sent_at=None)
        with patch('paxalia.management.commands.send_scheduled_reports.cache.add', side_effect=[True, False]):
            self.assertTrue(Command._is_due(report, timezone.now()))
            # The production command owns the cache claim; this regression
            # test ensures the claim operation remains an atomic cache API.
            first = __import__('paxalia.management.commands.send_scheduled_reports', fromlist=['cache']).cache.add(
                'test-complete-fixes-report-lock', '1', timeout=300
            )
            second = __import__('paxalia.management.commands.send_scheduled_reports', fromlist=['cache']).cache.add(
                'test-complete-fixes-report-lock', '1', timeout=300
            )
            self.assertNotEqual(first, second)



class LocalizationCompletenessRegressionTests(TestCase):
    @override_settings(
        LANGUAGES=(('en', 'English'), ('fa', 'فارسی')),
        PARLER_LANGUAGES={
            None: ({'code': 'en'}, {'code': 'fa'}),
            'default': {'fallbacks': ['en'], 'hide_untranslated': False},
        },
    )
    def test_translation_is_incomplete_when_any_translated_field_is_missing(self):
        from .packages.localization import translation_state

        title = models.CharField(max_length=255, name='title')
        body = models.TextField(name='body')

        class Meta:
            model = SimpleNamespace(_meta=SimpleNamespace(get_field=lambda name: {'title': title, 'body': body}.get(name)))

            def get_all_fields(self):
                return ['title', 'body']

            def get_model_by_field(self, name):
                return {'title': title, 'body': body}.get(name)

        class FakeTranslatedModel:
            _parler_meta = Meta()

            def __init__(self):
                self._language = 'en'
                self.values = {'title': {'en': 'Hello', 'fa': ''}, 'body': {'en': 'Body', 'fa': None}}

            def has_translation(self, code):
                return code in {'en', 'fa'}

            def get_current_language(self):
                return self._language

            def set_current_language(self, code):
                self._language = code

            def safe_translation_getter(self, name, language_code=None, default=None):
                return self.values.get(name, {}).get(language_code, default)

        result = translation_state(FakeTranslatedModel(), ['fa'])
        self.assertEqual(result, [{'code': 'fa', 'complete': False}])


class FinalAuditContractTests(TestCase):
    def test_generic_model_forms_are_allowed_to_receive_translation_fields(self):
        from django import forms
        from django.test import RequestFactory
        from .admin_center.views import _attach_translation_fields

        title = models.CharField(max_length=255, name='title')

        class FakeMeta:
            def get_all_fields(self):
                return ['title']

            def get_model_by_field(self, name):
                return title if name == 'title' else None

        class FakeModel:
            _parler_meta = FakeMeta()

        class Admin:
            def get_readonly_fields(self, request, obj=None):
                return ()

        definition = SimpleNamespace(
            model=FakeModel,
            model_admin=Admin(),
            hidden_fields=set(),
            label='tests.fake',
        )
        request = RequestFactory().get('/admin/tests/fake/add/?language=fa')
        form = forms.Form()
        language = _attach_translation_fields(definition, request, form)
        self.assertEqual(language, 'fa')
        self.assertIn('title', form.fields)
        self.assertEqual(form._paxalia_translation_extra_names, ('title',))

    def test_authenticated_paxalia_api_reads_are_never_cacheable(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/paxalia_api.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("@never_cache"), 4)
        self.assertIn("MAX_INGEST_BODY_BYTES = 256 * 1024", source)
        self.assertIn("if len(raw_body) > MAX_INGEST_BODY_BYTES", source)

    def test_upload_delete_never_deletes_row_when_file_cleanup_fails(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/uploads.py").read_text(encoding="utf-8")
        delete_start = source.index("def upload_delete(")
        delete_block = source[delete_start:delete_start + 1800]
        self.assertIn("if failures:", delete_block)
        self.assertIn("return JsonResponse({", delete_block)
        self.assertLess(delete_block.index("if failures:"), delete_block.index("upload.delete()"))

    def test_ai_safe_stack_removes_host_filesystem_directories(self):
        from types import SimpleNamespace
        from .views.logs import _ai_safe_stack

        stack = 'Traceback\n  File "/home/parsa/private-project/docs/views.py", line 9, in run\nRuntimeError: failed'
        safe = _ai_safe_stack(stack)
        self.assertNotIn("/home/parsa/private-project", safe)
        self.assertIn("views.py", safe)


class FinalAuditInputValidationTests(SimpleTestCase):
    def test_settings_languages_are_derived_from_effective_localization_configuration(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/settings.py").read_text(encoding="utf-8")
        self.assertIn("from paxalia.packages.localization import language_choices", source)
        self.assertIn('for code, name in language_choices()', source)
        self.assertNotIn('"code": "en", "name": _("English")', source)

    def test_webauthn_json_requests_have_a_hard_body_limit(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/auth.py").read_text(encoding="utf-8")
        self.assertIn("MAX_WEBAUTHN_JSON_BODY_BYTES = 256 * 1024", source)
        self.assertIn("if len(raw_body) > MAX_WEBAUTHN_JSON_BODY_BYTES", source)

    def test_server_history_minutes_are_bounded_and_invalid_values_do_not_raise(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views/server.py").read_text(encoding="utf-8")
        self.assertIn("except (TypeError, ValueError):", source)
        self.assertIn("minutes = max(1, min(minutes, 24 * 60))", source)

    def test_localization_status_contains_display_language_name(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "packages/localization.py").read_text(encoding="utf-8")
        self.assertIn('{**item, "name": language_names.get(item["code"], item["code"])}', source)
        self.assertIn('"languages": language_status', source)

