from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .conf_uploads import get_upload_blocked_extensions
from .models import BackupConfiguration, FileUpload
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
