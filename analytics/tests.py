import urllib.error
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .bot_classification import classify_bot
from .conf_uploads import get_upload_blocked_extensions
from .chat_ops import format_snapshot_text, resolve_period, verify_discord_signature, verify_slack_signature
from .compliance import forget_by_ip, forget_by_session
from .data_import import import_daily_stats, parse_analytics_csv
from .middleware import AnalyticsMiddleware
from .models import (
    AnalyticsEvent, BackupConfiguration, DailySiteStats, FileUpload, JSError, PageView,
    ServerMetricSnapshot, UptimeIncident, UptimeMonitor,
)
from .queue_monitor import get_celery_app, get_queue_stats
from .revenue import _month_bounds, _shift_month
from .rum import _percentile, rate_metric
from .security_scorecard import run_scorecard_checks
from .uptime import compute_uptime_percentage, perform_check, record_check, validate_monitor_url
from .views.events import _clean_int


class FileUploadModelTests(TestCase):
    def test_file_upload_uses_configured_user_model(self):
        field = FileUpload._meta.get_field('uploaded_by')
        self.assertEqual(field.remote_field.model, get_user_model())

    def test_uploaded_by_field_is_nullable_and_uses_set_null(self):
        field = FileUpload._meta.get_field('uploaded_by')
        self.assertTrue(field.null)
        self.assertEqual(field.remote_field.on_delete.__name__, 'SET_NULL')


class ServerAccessTests(TestCase):
    def test_server_overview_requires_staff(self):
        response = self.client.get(reverse('server_overview'))
        self.assertIn(response.status_code, (302, 403))

    def test_server_metrics_requires_staff(self):
        response = self.client.get(reverse('api_server_metrics'))
        self.assertIn(response.status_code, (302, 403))


class BackupPathOverlapTests(TestCase):
    """Phase 8 — audit finding #1a."""

    def test_no_overlap_returns_none(self):
        config = BackupConfiguration(storage_path='/var/backups/analytics', backup_paths='/srv/app\n/etc/app')
        self.assertIsNone(config.get_path_overlap_warning())

    def test_storage_path_equal_to_backup_path_is_flagged(self):
        config = BackupConfiguration(storage_path='/srv/app', backup_paths='/srv/app')
        self.assertIsNotNone(config.get_path_overlap_warning())

    def test_storage_path_inside_backup_path_is_flagged(self):
        config = BackupConfiguration(storage_path='/srv/app/backups', backup_paths='/srv/app')
        self.assertIsNotNone(config.get_path_overlap_warning())

    def test_backup_path_inside_storage_path_is_flagged(self):
        config = BackupConfiguration(storage_path='/srv/app', backup_paths='/srv/app/media')
        self.assertIsNotNone(config.get_path_overlap_warning())

    def test_unconfigured_storage_path_returns_none(self):
        config = BackupConfiguration(storage_path='', backup_paths='/srv/app')
        self.assertIsNone(config.get_path_overlap_warning())


class UploadExtensionValidationTests(TestCase):
    """Phase 8 — audit finding #2."""

    def test_default_blocklist_rejects_php(self):
        self.assertIn('.php', get_upload_blocked_extensions())

    def test_upload_init_rejects_blocked_extension(self):
        user = get_user_model().objects.create_user(username='staffer', password='pw', is_staff=True)
        self.client.force_login(user)
        response = self.client.post(reverse('upload_init'), {
            'filename': 'shell.php', 'total_size': '10',
        })
        self.assertEqual(response.status_code, 400)

    @override_settings(PAXALIA_DASHBOARD={'UPLOAD_ALLOWED_EXTENSIONS': ['.zip']})
    def test_upload_init_enforces_strict_allowlist_when_configured(self):
        user = get_user_model().objects.create_user(username='staffer2', password='pw', is_staff=True)
        self.client.force_login(user)
        response = self.client.post(reverse('upload_init'), {
            'filename': 'build.tar.gz', 'total_size': '10',
        })
        self.assertEqual(response.status_code, 400)


class SecurityScorecardTests(TestCase):
    def test_scorecard_runs_and_summarizes(self):
        result = run_scorecard_checks()
        self.assertIn('django', result)
        self.assertIn('package', result)
        total = result['summary']['pass'] + result['summary']['warn'] + result['summary']['fail']
        self.assertEqual(total, result['summary']['total'])
        self.assertEqual(total, len(result['django']) + len(result['package']))


class RevenueDateMathTests(TestCase):
    """
    Phase 9 — the pure date-math helpers behind MRR trend / churn.
    compute_monthly_revenue_trend/compute_churn/compute_dunning
    themselves need a real Invoice model (see revenue.py's docstring on
    the documented billing contract) which only exists in a consuming
    project, so they're exercised there — this covers the month
    arithmetic they're built on, including year wraparound.
    """

    def test_month_bounds_regular_month(self):
        start, end = _month_bounds(2026, 4)
        self.assertEqual((start.day, end.day), (1, 30))

    def test_month_bounds_december(self):
        start, end = _month_bounds(2026, 12)
        self.assertEqual(end.month, 12)
        self.assertEqual(end.day, 31)

    def test_shift_month_forward_across_year_boundary(self):
        self.assertEqual(_shift_month(2026, 11, 2), (2027, 1))

    def test_shift_month_backward_across_year_boundary(self):
        self.assertEqual(_shift_month(2026, 1, -1), (2025, 12))

    def test_shift_month_backward_two_from_january(self):
        self.assertEqual(_shift_month(2026, 1, -2), (2025, 11))

    def test_shift_month_zero_is_identity(self):
        self.assertEqual(_shift_month(2026, 6, 0), (2026, 6))


class BotClassificationTests(TestCase):
    """Phase 10."""

    def test_malicious_path_wins_regardless_of_user_agent(self):
        # A scanner spoofing Googlebot's UA while hitting a known
        # attack-probe path is still 'malicious' — the path match
        # always overrides a UA claim, see bot_classification.py.
        self.assertEqual(
            classify_bot(True, 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'),
            'malicious',
        )

    def test_search_engine_crawler(self):
        self.assertEqual(
            classify_bot(False, 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'),
            'search_engine',
        )
        self.assertEqual(classify_bot(False, 'Mozilla/5.0 (compatible; bingbot/2.0)'), 'search_engine')

    def test_ai_crawler(self):
        self.assertEqual(classify_bot(False, 'Mozilla/5.0 (compatible; GPTBot/1.0)'), 'ai_crawler')
        self.assertEqual(classify_bot(False, 'ClaudeBot/1.0'), 'ai_crawler')

    def test_social_preview_bot(self):
        self.assertEqual(classify_bot(False, 'facebookexternalhit/1.1'), 'social_preview')

    def test_seo_tool(self):
        self.assertEqual(classify_bot(False, 'Mozilla/5.0 (compatible; AhrefsBot/7.0)'), 'seo_tool')

    def test_generic_bot_heuristic(self):
        self.assertEqual(classify_bot(False, 'curl/8.4.0'), 'unknown')
        self.assertEqual(classify_bot(False, 'python-requests/2.31.0'), 'unknown')

    def test_empty_user_agent_is_unknown(self):
        self.assertEqual(classify_bot(False, ''), 'unknown')

    def test_ordinary_browser_is_not_a_bot(self):
        self.assertEqual(
            classify_bot(False, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'),
            '',
        )


class WebVitalsTests(TestCase):
    """Phase 11."""

    def test_percentile_of_empty_list_is_none(self):
        self.assertIsNone(_percentile([], 75))

    def test_percentile_single_value(self):
        self.assertEqual(_percentile([42], 75), 42)

    def test_percentile_75_matches_known_case(self):
        # Sorted 1..10 — the 75th percentile via linear interpolation
        # is 7.75 (matches numpy's default 'linear' method).
        self.assertAlmostEqual(_percentile(list(range(1, 11)), 75), 7.75)

    def test_rate_metric_lcp_thresholds(self):
        self.assertEqual(rate_metric('LCP', 2000), 'good')
        self.assertEqual(rate_metric('LCP', 3000), 'needs-improvement')
        self.assertEqual(rate_metric('LCP', 5000), 'poor')

    def test_rate_metric_cls_thresholds(self):
        self.assertEqual(rate_metric('CLS', 0.05), 'good')
        self.assertEqual(rate_metric('CLS', 0.2), 'needs-improvement')
        self.assertEqual(rate_metric('CLS', 0.4), 'poor')

    def test_rate_metric_unknown_metric_is_none(self):
        self.assertIsNone(rate_metric('FID', 100))

    def test_rate_metric_none_value_is_none(self):
        self.assertIsNone(rate_metric('LCP', None))


class JsErrorHelperTests(TestCase):
    """Phase 11 — the small int-coercion helper used by the JS error API."""

    def test_clean_int_valid(self):
        self.assertEqual(_clean_int('42'), 42)
        self.assertEqual(_clean_int(42), 42)

    def test_clean_int_none(self):
        self.assertIsNone(_clean_int(None))

    def test_clean_int_garbage_does_not_raise(self):
        self.assertIsNone(_clean_int('not-a-number'))
        self.assertIsNone(_clean_int({}))


class UptimeCheckTests(TestCase):
    """
    Phase 12. perform_check() is mocked at the urllib layer so these
    never make a real network call; record_check()'s incident
    state-machine is exercised against real DB rows since this
    package owns the UptimeMonitor/UptimeCheck/UptimeIncident tables
    (unlike the billing models in RevenueDateMathTests' neighbors).
    """

    def _monitor(self, **kwargs):
        defaults = dict(name='Example', url='https://example.com/', expected_status_code=200, timeout_seconds=5)
        defaults.update(kwargs)
        return UptimeMonitor.objects.create(**defaults)

    def test_perform_check_success(self):
        monitor = self._monitor()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch('analytics.uptime.urllib.request.urlopen', return_value=mock_resp):
            result = perform_check(monitor)
        self.assertEqual(result['status'], 'up')
        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['error_message'], '')

    def test_perform_check_wrong_status_code_is_down(self):
        monitor = self._monitor(expected_status_code=200)
        mock_resp = MagicMock()
        mock_resp.status = 503
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch('analytics.uptime.urllib.request.urlopen', return_value=mock_resp):
            result = perform_check(monitor)
        self.assertEqual(result['status'], 'down')
        self.assertIn('503', result['error_message'])

    def test_perform_check_http_error_with_matching_expected_code_is_up(self):
        # A monitor that expects a 404 (checking a "not found" page
        # stays not found, say) should treat urllib's HTTPError(404)
        # as success, not failure.
        monitor = self._monitor(expected_status_code=404)
        err = urllib.error.HTTPError(url='https://example.com/', code=404, msg='Not Found', hdrs=None, fp=None)
        with patch('analytics.uptime.urllib.request.urlopen', side_effect=err):
            result = perform_check(monitor)
        self.assertEqual(result['status'], 'up')
        self.assertEqual(result['status_code'], 404)

    def test_perform_check_connection_error_is_down(self):
        monitor = self._monitor()
        err = urllib.error.URLError('Connection refused')
        with patch('analytics.uptime.urllib.request.urlopen', side_effect=err):
            result = perform_check(monitor)
        self.assertEqual(result['status'], 'down')
        self.assertIsNone(result['status_code'])
        self.assertIn('Connection refused', result['error_message'])

    def test_record_check_opens_incident_on_first_failure(self):
        monitor = self._monitor()
        record_check(monitor, {'status': 'down', 'status_code': 500, 'response_time_ms': 100, 'error_message': 'boom'})
        self.assertEqual(UptimeIncident.objects.filter(monitor=monitor, resolved_at__isnull=True).count(), 1)

    def test_record_check_does_not_open_second_incident_while_still_down(self):
        monitor = self._monitor()
        record_check(monitor, {'status': 'down', 'status_code': 500, 'response_time_ms': 100, 'error_message': 'boom'})
        record_check(monitor, {'status': 'down', 'status_code': 500, 'response_time_ms': 100, 'error_message': 'boom again'})
        self.assertEqual(UptimeIncident.objects.filter(monitor=monitor).count(), 1)

    def test_record_check_resolves_incident_on_recovery(self):
        monitor = self._monitor()
        record_check(monitor, {'status': 'down', 'status_code': 500, 'response_time_ms': 100, 'error_message': 'boom'})
        record_check(monitor, {'status': 'up', 'status_code': 200, 'response_time_ms': 50, 'error_message': ''})
        incident = UptimeIncident.objects.get(monitor=monitor)
        self.assertIsNotNone(incident.resolved_at)

    def test_compute_uptime_percentage_no_checks_is_none(self):
        monitor = self._monitor()
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        self.assertIsNone(compute_uptime_percentage(monitor, now - timedelta(days=1), now))

    def test_compute_uptime_percentage_mixed_checks(self):
        monitor = self._monitor()
        record_check(monitor, {'status': 'up', 'status_code': 200, 'response_time_ms': 50, 'error_message': ''})
        record_check(monitor, {'status': 'up', 'status_code': 200, 'response_time_ms': 50, 'error_message': ''})
        record_check(monitor, {'status': 'down', 'status_code': 500, 'response_time_ms': 50, 'error_message': 'x'})
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        pct = compute_uptime_percentage(monitor, now - timedelta(days=1), now + timedelta(minutes=1))
        self.assertAlmostEqual(pct, 66.67, places=1)


class ServerHistoryTests(TestCase):
    """Phase 13 — api_server_history now reads real ServerMetricSnapshot
    rows instead of generating synthetic random.randint() data."""

    def test_history_empty_when_no_snapshots(self):
        user = get_user_model().objects.create_superuser(username='root', password='pw', email='r@example.com')
        self.client.force_login(user)
        response = self.client.get(reverse('api_server_history'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_history_computes_deltas_between_snapshots(self):
        from django.utils import timezone

        user = get_user_model().objects.create_superuser(username='root2', password='pw', email='r2@example.com')
        self.client.force_login(user)

        now = timezone.now()
        ServerMetricSnapshot.objects.create(
            recorded_at=now - timezone.timedelta(minutes=2), cpu_percent=10, memory_percent=20,
            disk_io_read_bytes=1000, disk_io_write_bytes=500, network_in_bytes=2000, network_out_bytes=1000,
        )
        ServerMetricSnapshot.objects.create(
            recorded_at=now - timezone.timedelta(minutes=1), cpu_percent=15, memory_percent=25,
            disk_io_read_bytes=1500, disk_io_write_bytes=700, network_in_bytes=2500, network_out_bytes=1400,
        )

        response = self.client.get(reverse('api_server_history'))
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['disk_io_read'], 0)  # first snapshot has no prior point to diff against
        self.assertEqual(data[1]['disk_io_read'], 500)  # 1500 - 1000
        self.assertEqual(data[1]['network_out'], 400)  # 1400 - 1000

    def test_history_guards_against_counter_reset(self):
        # A service restart resets psutil's cumulative counters to a
        # small number — the delta must never go negative.
        from django.utils import timezone

        user = get_user_model().objects.create_superuser(username='root3', password='pw', email='r3@example.com')
        self.client.force_login(user)

        now = timezone.now()
        ServerMetricSnapshot.objects.create(
            recorded_at=now - timezone.timedelta(minutes=2), cpu_percent=10, memory_percent=20,
            disk_io_read_bytes=100000, disk_io_write_bytes=0, network_in_bytes=0, network_out_bytes=0,
        )
        ServerMetricSnapshot.objects.create(
            recorded_at=now - timezone.timedelta(minutes=1), cpu_percent=10, memory_percent=20,
            disk_io_read_bytes=50, disk_io_write_bytes=0, network_in_bytes=0, network_out_bytes=0,  # reset!
        )

        response = self.client.get(reverse('api_server_history'))
        data = response.json()
        self.assertEqual(data[1]['disk_io_read'], 0)  # guarded, not a negative number


class QueueMonitorTests(TestCase):
    """Phase 13 — Celery introspection via a dotted-path config, same
    pattern as the billing integration."""

    @override_settings(PAXALIA_DASHBOARD={})
    def test_no_app_configured_returns_none(self):
        self.assertIsNone(get_celery_app())
        self.assertIsNone(get_queue_stats())

    @override_settings(PAXALIA_DASHBOARD={'CELERY_APP_PATH': 'not.a.real.module.app'})
    def test_unimportable_path_returns_none_not_raise(self):
        self.assertIsNone(get_celery_app())
        self.assertIsNone(get_queue_stats())


class ConsentModeTests(TestCase):
    """Phase 14 — server-side consent gate on the public event endpoints."""

    @override_settings(PAXALIA_DASHBOARD={'CONSENT_MODE_ENABLED': False})
    def test_event_api_works_normally_when_consent_mode_disabled(self):
        response = self.client.post(
            reverse('event_api'),
            data='{"category": "test", "action": "click"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AnalyticsEvent.objects.filter(category='test').count(), 1)

    @override_settings(PAXALIA_DASHBOARD={
        'CONSENT_MODE_ENABLED': True, 'CONSENT_COOKIE_NAME': 'analytics_consent',
        'CONSENT_COOKIE_GRANTED_VALUE': 'granted',
    })
    def test_event_api_skips_write_without_consent_cookie(self):
        response = self.client.post(
            reverse('event_api'),
            data='{"category": "test2", "action": "click"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'skipped')
        self.assertEqual(AnalyticsEvent.objects.filter(category='test2').count(), 0)

    @override_settings(PAXALIA_DASHBOARD={
        'CONSENT_MODE_ENABLED': True, 'CONSENT_COOKIE_NAME': 'analytics_consent',
        'CONSENT_COOKIE_GRANTED_VALUE': 'granted',
    })
    def test_event_api_writes_once_consent_cookie_present(self):
        self.client.cookies['analytics_consent'] = 'granted'
        response = self.client.post(
            reverse('event_api'),
            data='{"category": "test3", "action": "click"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AnalyticsEvent.objects.filter(category='test3').count(), 1)


class ForgetVisitorTests(TestCase):
    """Phase 14 — bulk deletion by session_id or IP."""

    def test_forget_by_session_deletes_across_models(self):
        PageView.objects.create(path='/', method='GET', status_code=200, session_id='sess-1', ip_hash='1.2.3.4')
        AnalyticsEvent.objects.create(category='c', action='a', session_id='sess-1')
        JSError.objects.create(message='boom', session_id='sess-1')
        # A different session shouldn't be touched.
        PageView.objects.create(path='/', method='GET', status_code=200, session_id='sess-2', ip_hash='5.6.7.8')

        results = forget_by_session('sess-1')

        self.assertEqual(results['PageView'], 1)
        self.assertEqual(results['AnalyticsEvent'], 1)
        self.assertEqual(results['JSError'], 1)
        self.assertEqual(PageView.objects.filter(session_id='sess-2').count(), 1)

    def test_forget_by_ip_matches_raw_and_hashed_forms(self):
        import hashlib
        raw_ip = '9.9.9.9'
        hashed_ip = hashlib.sha256(raw_ip.encode()).hexdigest()
        PageView.objects.create(path='/', method='GET', status_code=200, session_id='s1', ip_hash=raw_ip)
        PageView.objects.create(path='/', method='GET', status_code=200, session_id='s2', ip_hash=hashed_ip)
        PageView.objects.create(path='/', method='GET', status_code=200, session_id='s3', ip_hash='not-this-one')

        results = forget_by_ip(raw_ip)

        self.assertEqual(results['PageView'], 2)
        self.assertEqual(PageView.objects.filter(session_id='s3').count(), 1)


class DataImportTests(TestCase):
    """Phase 15 — the shared GA/Plausible CSV parser and importer."""

    def test_parse_plausible_csv(self):
        csv_text = "date,visitors,pageviews,bounce_rate,visit_duration\n2024-01-01,120,340,55%,90\n2024-01-02,95,280,60%,80\n"
        rows, warnings = parse_analytics_csv(csv_text)
        self.assertEqual(warnings, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['views'], 340.0)
        self.assertEqual(rows[0]['visitors'], 120.0)
        self.assertEqual(rows[0]['bounce_rate_pct'], 55.0)

    def test_parse_ga_csv_with_preamble_and_totals_footer(self):
        csv_text = (
            "# ----------------------------------------\n"
            "# Traffic acquisition\n"
            "# 2024-01-01 - 2024-01-31\n"
            "# ----------------------------------------\n"
            "\n"
            "Date,Sessions,Engaged sessions,Engagement rate,Views\n"
            "20240101,120,80,0.66,340\n"
            "20240102,95,60,0.63,280\n"
            "\n"
            "Totals,215,140,0.65,620\n"
        )
        rows, warnings = parse_analytics_csv(csv_text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['date'].isoformat(), '2024-01-01')
        self.assertEqual(rows[0]['sessions'], 120.0)
        self.assertEqual(rows[0]['views'], 340.0)
        self.assertEqual(len(warnings), 1)
        self.assertIn('Totals', warnings[0])

    def test_parse_csv_with_no_recognizable_header_returns_empty_with_warning(self):
        rows, warnings = parse_analytics_csv("foo,bar\n1,2\n")
        self.assertEqual(rows, [])
        self.assertTrue(warnings)

    def test_import_creates_new_rows(self):
        rows, _ = parse_analytics_csv("date,visitors,pageviews\n2024-01-01,10,50\n")
        summary = import_daily_stats(rows, source='plausible')
        self.assertEqual(summary, {'created': 1, 'updated': 0, 'skipped_existing': 0})
        stats = DailySiteStats.objects.get(date='2024-01-01', site=None)
        self.assertEqual(stats.total_views, 50)
        self.assertEqual(stats.unique_ips, 10)
        self.assertEqual(stats.imported_from, 'plausible')

    def test_import_skips_existing_day_by_default(self):
        DailySiteStats.objects.create(site=None, date='2024-01-01', total_views=999)
        rows, _ = parse_analytics_csv("date,visitors,pageviews\n2024-01-01,10,50\n")
        summary = import_daily_stats(rows, source='ga')
        self.assertEqual(summary, {'created': 0, 'updated': 0, 'skipped_existing': 1})
        self.assertEqual(DailySiteStats.objects.get(date='2024-01-01').total_views, 999)

    def test_import_overwrite_true_updates_existing_day(self):
        DailySiteStats.objects.create(site=None, date='2024-01-01', total_views=999)
        rows, _ = parse_analytics_csv("date,visitors,pageviews\n2024-01-01,10,50\n")
        summary = import_daily_stats(rows, source='ga', overwrite=True)
        self.assertEqual(summary, {'created': 0, 'updated': 1, 'skipped_existing': 0})
        self.assertEqual(DailySiteStats.objects.get(date='2024-01-01').total_views, 50)

    def test_bounces_computed_from_bounce_rate_and_sessions(self):
        rows, _ = parse_analytics_csv("date,sessions,bounce_rate\n2024-01-01,200,50%\n")
        summary = import_daily_stats(rows, source='ga')
        self.assertEqual(summary['created'], 1)
        stats = DailySiteStats.objects.get(date='2024-01-01')
        self.assertEqual(stats.bounces, 100)


class ChatOpsTests(TestCase):
    """Phase 16 — Slack/Discord slash-command app."""

    def test_slack_signature_valid(self):
        import hashlib
        import hmac
        import time
        secret = 'testsecret'
        ts = str(int(time.time()))
        body = b'command=/analytics&text=today'
        basestring = f'v0:{ts}:{body.decode()}'
        sig = 'v0=' + hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(verify_slack_signature(body, ts, sig, secret))

    def test_slack_signature_wrong_secret(self):
        import hashlib
        import hmac
        import time
        ts = str(int(time.time()))
        body = b'command=/analytics&text=today'
        basestring = f'v0:{ts}:{body.decode()}'
        sig = 'v0=' + hmac.new(b'testsecret', basestring.encode(), hashlib.sha256).hexdigest()
        self.assertFalse(verify_slack_signature(body, ts, sig, 'wrong-secret'))

    def test_slack_signature_expired_timestamp(self):
        import hashlib
        import hmac
        import time
        secret = 'testsecret'
        ts = str(int(time.time()) - 1000)
        body = b'command=/analytics&text=today'
        basestring = f'v0:{ts}:{body.decode()}'
        sig = 'v0=' + hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
        self.assertFalse(verify_slack_signature(body, ts, sig, secret))

    def test_slack_signature_missing_pieces(self):
        self.assertFalse(verify_slack_signature(b'x', '123', 'v0=abc', None))
        self.assertFalse(verify_slack_signature(b'x', '', 'v0=abc', 'secret'))
        self.assertFalse(verify_slack_signature(b'x', '123', '', 'secret'))

    def test_discord_signature_missing_pieces_is_false(self):
        self.assertFalse(verify_discord_signature(b'x', '123', 'ab', None))
        self.assertFalse(verify_discord_signature(b'x', None, 'ab', 'deadbeef'))
        self.assertFalse(verify_discord_signature(b'x', '123', None, 'deadbeef'))

    def test_discord_signature_garbage_never_raises(self):
        # Malformed hex, wrong lengths — verify_discord_signature must
        # normalize every failure mode to False, never propagate an
        # exception from nacl/bytes.fromhex.
        self.assertFalse(verify_discord_signature(b'x', '123', 'not-hex!!', 'also-not-hex'))

    def test_resolve_period_today_default(self):
        start, end, label = resolve_period('')
        self.assertEqual(label, 'today')
        self.assertEqual(start.date(), end.date())

    def test_resolve_period_unrecognized_falls_back_to_today(self):
        _, _, label = resolve_period('bogus')
        self.assertEqual(label, 'today')

    def test_resolve_period_week_spans_seven_days(self):
        start, end, label = resolve_period('week')
        self.assertEqual(label, 'week')
        self.assertEqual((end.date() - start.date()).days, 6)

    def test_format_snapshot_text_includes_core_numbers(self):
        snapshot = {
            'start_date': '2024-01-01', 'end_date': '2024-01-01',
            'total_views': 42, 'unique_visitors': 10,
            'top_pages': [{'path': '/', 'count': 20}],
            'top_referrers': [{'referrer': 'google.com', 'count': 5}],
        }
        text = format_snapshot_text(snapshot, 'today')
        self.assertIn('42', text)
        self.assertIn('10', text)
        self.assertIn('/', text)
        self.assertIn('google.com', text)


class ChatOpsViewTests(TestCase):
    """Phase 16 — the actual endpoints, signature-gated."""

    @override_settings(PAXALIA_DASHBOARD={'SLACK_SIGNING_SECRET': None})
    def test_slack_command_not_configured(self):
        response = self.client.post(reverse('slack_command'), {'text': 'today'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('not configured', response.json()['text'])

    @override_settings(PAXALIA_DASHBOARD={'SLACK_SIGNING_SECRET': 'testsecret'})
    def test_slack_command_rejects_bad_signature(self):
        response = self.client.post(
            reverse('slack_command'), {'text': 'today'},
            HTTP_X_SLACK_REQUEST_TIMESTAMP='123', HTTP_X_SLACK_SIGNATURE='v0=bad',
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(PAXALIA_DASHBOARD={'DISCORD_PUBLIC_KEY': None})
    def test_discord_interaction_not_configured(self):
        response = self.client.post(
            reverse('discord_interactions'), data='{"type": 1}', content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)



class V3HardeningRegressionTests(TestCase):
    """Regression coverage for the v3.0.0 stabilization fixes."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='v3-staff', password='test-password', is_staff=True
        )
        self.client.force_login(self.staff)

    def test_only_intended_0018_is_source_leaf(self):
        from pathlib import Path
        migration_dir = Path(__file__).resolve().parent / 'migrations'
        names = sorted(p.name for p in migration_dir.glob('0018_*.py'))
        self.assertEqual(names, ['0018_fix_dailysitestats_duplicates.py'])

    def test_daily_stats_increment_helper_preserves_consecutive_increments(self):
        from django.utils import timezone
        AnalyticsMiddleware._increment_daily_stats(None, timezone.localdate(), False, False)
        AnalyticsMiddleware._increment_daily_stats(None, timezone.localdate(), False, False)
        row = DailySiteStats.objects.get(site=None, date=timezone.localdate())
        self.assertEqual(row.total_views, 2)

    def test_private_uptime_target_is_rejected(self):
        valid, reason = validate_monitor_url('http://127.0.0.1:8000/')
        self.assertFalse(valid)
        self.assertTrue(reason)

    def test_share_link_uses_secure_hash_and_accepts_legacy_hash(self):
        from django.contrib.auth.hashers import make_password
        from analytics.views.share_links import _hash_password, _check_password

        encoded = _hash_password('secret')
        self.assertNotEqual(len(encoded), 64)
        self.assertTrue(_check_password('secret', encoded)[0])
        legacy = __import__('hashlib').sha256(b'secret').hexdigest()
        self.assertEqual(_check_password('secret', legacy), (True, True))

    def test_upload_chunk_cannot_exceed_declared_chunk_size(self):
        upload = FileUpload.objects.create(
            uploaded_by=self.staff, original_filename='build.zip', total_size=4,
            chunk_size=2, total_chunks=2, status='pending',
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(
            reverse('upload_chunk', kwargs={'upload_id': upload.id}),
            {'chunk_index': '0', 'chunk': SimpleUploadedFile('x.bin', b'123')},
        )
        self.assertEqual(response.status_code, 413)
        upload.refresh_from_db()
        self.assertEqual(upload.bytes_received, 0)

    def test_api_end_date_is_inclusive(self):
        from django.utils import timezone
        from datetime import datetime, timedelta
        from .views.paxalia_api import _parse_date_range

        request = self.client.get('/')
        request.GET = request.GET.copy()
        request.GET['start_date'] = '2026-09-12'
        request.GET['end_date'] = '2026-09-12'
        start, end = _parse_date_range(request)
        self.assertEqual(start.date().isoformat(), '2026-09-12')
        self.assertEqual(end.date().isoformat(), '2026-09-13')

