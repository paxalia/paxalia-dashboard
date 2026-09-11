from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .bot_classification import classify_bot
from .conf_uploads import get_upload_blocked_extensions
from .models import BackupConfiguration, FileUpload
from .revenue import _month_bounds, _shift_month
from .security_scorecard import run_scorecard_checks


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
