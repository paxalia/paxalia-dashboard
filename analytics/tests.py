import urllib.error
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .bot_classification import classify_bot
from .conf_uploads import get_upload_blocked_extensions
from .models import BackupConfiguration, FileUpload, ServerMetricSnapshot, UptimeIncident, UptimeMonitor
from .queue_monitor import get_celery_app, get_queue_stats
from .revenue import _month_bounds, _shift_month
from .rum import _percentile, rate_metric
from .security_scorecard import run_scorecard_checks
from .uptime import compute_uptime_percentage, perform_check, record_check
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
