"""Regression tests for Paxalia Server Files.

These tests deliberately exercise the policy and filesystem service directly;
the repository's existing admin-security tests remain authoritative for the
mandatory password/2FA/device session gate applied to the views.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from .server_files import service
from .server_files.exceptions import (
    ServerFilesAlreadyExists,
    ServerFilesBinaryFile,
    ServerFilesDenied,
    ServerFilesInvalidPath,
    ServerFilesNotFound,
    ServerFilesTooLarge,
    ServerFilesUnsupportedPreview,
)
from .server_files.policy import _supported_dirfd_operations, get_roots, has_capability, split_relative_path, validate_name


class ServerFilesPolicyTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "allowed"
        self.root.mkdir()

    def config(self, **extra):
        values = {
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_ALLOWED_ROOTS": [{"name": "Application", "path": str(self.root)}],
            "FILE_MANAGER_DENIED_PATHS": ["private-area"],
            "FILE_MANAGER_SENSITIVE_PATTERNS": None,
            "FILE_MANAGER_ALLOW_SENSITIVE_MUTATIONS": False,
        }
        values.update(extra)
        # None means use defaults for sensitive patterns.
        if values["FILE_MANAGER_SENSITIVE_PATTERNS"] is None:
            values.pop("FILE_MANAGER_SENSITIVE_PATTERNS")
        return override_settings(PAXALIA_DASHBOARD=values)

    def test_allowed_root_is_explicit_and_named(self):
        with self.config():
            roots = get_roots()
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].id, "root-0")
        self.assertEqual(roots[0].name, "Application")
        self.assertEqual(Path(roots[0].path), self.root)

    def test_disabled_feature_fails_closed(self):
        with self.config(FILE_MANAGER_ENABLED=False):
            from .server_files.exceptions import ServerFilesDisabled
            with self.assertRaises(ServerFilesDisabled):
                get_roots()

    def test_empty_root_list_never_defaults_to_filesystem_root(self):
        with self.config(FILE_MANAGER_ALLOWED_ROOTS=[]):
            self.assertEqual(get_roots(), [])

    def test_sensitive_directory_cannot_be_configured_as_root(self):
        sensitive_root = self.root.parent / "secrets"
        sensitive_root.mkdir()
        with self.config(FILE_MANAGER_ALLOWED_ROOTS=[str(sensitive_root)]):
            from .server_files.exceptions import ServerFilesConfigurationError
            with self.assertRaises(ServerFilesConfigurationError):
                get_roots()

    def test_filesystem_root_is_rejected(self):
        with self.config(FILE_MANAGER_ALLOWED_ROOTS=[os.path.abspath(os.sep)]):
            from .server_files.exceptions import ServerFilesConfigurationError
            with self.assertRaises(ServerFilesConfigurationError):
                get_roots()

    def test_overlapping_roots_are_rejected(self):
        child = self.root / "child"
        child.mkdir()
        with self.config(FILE_MANAGER_ALLOWED_ROOTS=[str(self.root), str(child)]):
            from .server_files.exceptions import ServerFilesConfigurationError
            with self.assertRaises(ServerFilesConfigurationError):
                get_roots()

    def test_relative_path_rejects_traversal_and_alternate_encodings(self):
        for value in ("../etc/passwd", "a/../../secret", "/etc/passwd", "%2e%2e/secret", "%252e%252e", "a\\..\\b", "a//b", "./a", "a/.", "a:\\b", "nul\x00byte"):
            with self.subTest(value=value), self.assertRaises(ServerFilesInvalidPath):
                split_relative_path(value)

    def test_filename_validation_rejects_traversal(self):
        for value in ("..", ".", "", "../evil", "a/b", "a\\b", "%2e%2e", "nul\x00"):
            with self.subTest(value=value), self.assertRaises(ServerFilesInvalidPath):
                split_relative_path(value, allow_empty=False) if value == "" else validate_name(value)

    def test_denied_path_is_matched_as_a_path_prefix(self):
        from .server_files.policy import ServerFilesRoot, is_denied
        fake = ServerFilesRoot("root-0", "test", str(self.root), 1, 1)
        with self.config():
            self.assertTrue(is_denied(fake, ("private-area", "x.txt")))
            self.assertFalse(is_denied(fake, ("private-area-old", "x.txt")))


class ServerFilesServiceTests(TestCase):
    def setUp(self):
        if not _supported_dirfd_operations():
            self.skipTest("Secure descriptor-relative filesystem operations are unavailable on this platform")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root_path = Path(self.temp.name) / "root"
        self.root_path.mkdir()
        self.user = get_user_model().objects.create_superuser(
            username="server-files-test", email="server-files@example.invalid", password="not-used"
        )

    def config(self, **extra):
        values = {
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_ALLOWED_ROOTS": [{"name": "Test Root", "path": str(self.root_path)}],
            "FILE_MANAGER_DENIED_PATHS": ["private"],
            "FILE_MANAGER_MAX_UPLOAD_SIZE_MB": 1,
            "FILE_MANAGER_MAX_DOWNLOAD_SIZE_MB": 2,
            "FILE_MANAGER_PREVIEW_MAX_BYTES": 16,
            "FILE_MANAGER_DIRECTORY_PAGE_SIZE": 2,
            "FILE_MANAGER_MAX_DIRECTORY_ENTRIES": 20,
            "FILE_MANAGER_MAX_COPY_SIZE_MB": 1,
            "FILE_MANAGER_MAX_MUTATIONS_PER_MINUTE": 100,
            "FILE_MANAGER_MAX_READS_PER_MINUTE": 100,
            "FILE_MANAGER_RATE_LIMIT_WINDOW_SECONDS": 60,
        }
        values.update(extra)
        return override_settings(PAXALIA_DASHBOARD=values)

    def _read(self, relative):
        return (self.root_path / relative).read_bytes()

    def test_list_directory_is_bounded_and_paginates(self):
        for number in range(5):
            (self.root_path / f"file-{number}.txt").write_text(str(number))
        with self.config():
            page = service.list_directory("root-0", "", self.user, page=2)
        self.assertEqual(page["page_size"], 2)
        self.assertEqual(len(page["items"]), 2)
        self.assertEqual(page["page_count"], 3)

    def test_hidden_files_are_not_shown_by_default(self):
        (self.root_path / ".hidden").write_text("secret")
        (self.root_path / "visible.txt").write_text("visible")
        with self.config():
            page = service.list_directory("root-0", "", self.user)
        self.assertEqual([row["name"] for row in page["items"]], ["visible.txt"])

    def test_hidden_files_require_explicit_configuration(self):
        (self.root_path / ".hidden").write_text("secret")
        with self.config(FILE_MANAGER_ALLOW_HIDDEN=True):
            page = service.list_directory("root-0", "", self.user, show_hidden=True)
        self.assertEqual([row["name"] for row in page["items"]], [".hidden"])

    def test_symlink_is_never_followed(self):
        outside = Path(self.temp.name) / "outside.txt"
        outside.write_text("do not read")
        try:
            (self.root_path / "escape.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        with self.config():
            rows = service.list_directory("root-0", "", self.user)["items"]
            self.assertEqual(rows[0]["kind"], "symlink")
            with self.assertRaises(ServerFilesDenied):
                service.open_download("root-0", "escape.txt", self.user)

    def test_denied_path_cannot_be_listed_or_read(self):
        private = self.root_path / "private"
        private.mkdir()
        (private / "secret.txt").write_text("secret")
        with self.config():
            with self.assertRaises(ServerFilesDenied):
                service.list_directory("root-0", "private", self.user)
            with self.assertRaises(ServerFilesDenied):
                service.open_download("root-0", "private/secret.txt", self.user)

    def test_sensitive_files_are_hidden_from_non_privileged_users(self):
        (self.root_path / ".env").write_text("SECRET=value")
        regular = get_user_model().objects.create_user(username="regular")
        regular.user_permissions.add(*Permission.objects.filter(
            codename__in=("view_server_files", "download_server_files"),
            content_type__app_label="paxalia",
        ))
        with self.config():
            page = service.list_directory("root-0", "", regular)
            self.assertNotIn(".env", [row["name"] for row in page["items"]])
            with self.assertRaises(ServerFilesDenied):
                service.open_download("root-0", ".env", regular)

    def test_create_directory_and_empty_directory_delete(self):
        with self.config():
            result = service.create_directory("root-0", "", "reports", self.user)
            self.assertTrue((self.root_path / "reports").is_dir())
            service.delete_item("root-0", result["path"], self.user)
        self.assertFalse((self.root_path / "reports").exists())

    def test_non_empty_directory_cannot_be_deleted(self):
        folder = self.root_path / "folder"
        folder.mkdir()
        (folder / "keep.txt").write_text("keep")
        with self.config():
            with self.assertRaises(ServerFilesDenied):
                service.delete_item("root-0", "folder", self.user)
        self.assertTrue((folder / "keep.txt").exists())

    def test_upload_is_size_bounded_and_does_not_overwrite(self):
        upload = SimpleUploadedFile("report.txt", b"hello")
        with self.config():
            service.upload_file("root-0", "", upload.name, upload, self.user)
            self.assertEqual(self._read("report.txt"), b"hello")
            with self.assertRaises(ServerFilesAlreadyExists):
                service.upload_file("root-0", "", "report.txt", SimpleUploadedFile("report.txt", b"again"), self.user)
            too_large = SimpleUploadedFile("large.bin", b"x" * (1024 * 1024 + 1))
            with self.assertRaises(ServerFilesTooLarge):
                service.upload_file("root-0", "", "large.bin", too_large, self.user)

    def test_preview_is_bounded_and_reports_truncation(self):
        (self.root_path / "long.txt").write_text("0123456789abcdefghij", encoding="utf-8")
        with self.config():
            result = service.preview_file("root-0", "long.txt", self.user)
        self.assertEqual(result["content"], "0123456789abcdef")
        self.assertTrue(result["truncated"])
        self.assertEqual(result["preview_limit"], 16)

    def test_json_preview_redacts_secret_keys_even_in_ordinary_filename(self):
        (self.root_path / "config.json").write_text(
            '{"debug": false, "SECRET_KEY": "do-not-show", "nested": {"api_token": "also-secret"}}',
            encoding="utf-8",
        )
        with self.config(FILE_MANAGER_PREVIEW_MAX_BYTES=4096):
            result = service.preview_file("root-0", "config.json", self.user)
        self.assertNotIn("do-not-show", result["content"])
        self.assertNotIn("also-secret", result["content"])
        self.assertIn("[REDACTED]", result["content"])

    def test_yaml_preview_redacts_sensitive_block_scalars(self):
        (self.root_path / "config.yaml").write_text(
            "private_key: |\n  -----BEGIN PRIVATE KEY-----\n  do-not-show\nnext: visible\n",
            encoding="utf-8",
        )
        with self.config(FILE_MANAGER_PREVIEW_MAX_BYTES=4096):
            result = service.preview_file("root-0", "config.yaml", self.user)
        self.assertNotIn("do-not-show", result["content"])
        self.assertNotIn("BEGIN PRIVATE KEY", result["content"])
        self.assertIn("next: visible", result["content"])

    def test_sensitive_entries_require_explicit_show_flag(self):
        (self.root_path / "settings.py").write_text('SECRET_KEY = "do-not-show"')
        with self.config():
            self.assertEqual(service.list_directory("root-0", "", self.user)["items"], [])
            listing = service.list_directory("root-0", "", self.user, show_sensitive=True)
        self.assertEqual([item["name"] for item in listing["items"]], ["settings.py"])

    def test_service_operations_enforce_permissions_not_only_views(self):
        from django.core.exceptions import PermissionDenied
        regular = get_user_model().objects.create_user(username="service-permission-test")
        with self.config():
            with self.assertRaises(PermissionDenied):
                service.create_directory("root-0", "", "nope", regular)
            with self.assertRaises(PermissionDenied):
                service.open_download("root-0", "missing.txt", regular)

    def test_preview_rejects_binary_and_unsupported_types(self):
        (self.root_path / "blob.txt").write_bytes(b"\x00\x01\x02")
        (self.root_path / "blob.bin").write_bytes(b"plain")
        with self.config():
            with self.assertRaises(ServerFilesBinaryFile):
                service.preview_file("root-0", "blob.txt", self.user)
            with self.assertRaises(ServerFilesUnsupportedPreview):
                service.preview_file("root-0", "blob.bin", self.user)

    @skipUnless(__import__("sys").platform.startswith("linux"), "Safe no-overwrite rename uses Linux renameat2")
    def test_rename_and_move_never_overwrite(self):
        (self.root_path / "old.txt").write_text("old")
        (self.root_path / "taken.txt").write_text("keep")
        with self.config():
            with self.assertRaises(ServerFilesAlreadyExists):
                service.rename_or_move("root-0", "old.txt", "root-0", "", "taken.txt", self.user)
            result = service.rename_or_move("root-0", "old.txt", "root-0", "", "new.txt", self.user)
        self.assertTrue((self.root_path / result["path"]).exists())
        self.assertFalse((self.root_path / "old.txt").exists())
        self.assertEqual(self._read("taken.txt"), b"keep")

    @skipUnless(__import__("sys").platform.startswith("linux"), "Safe no-overwrite rename uses Linux renameat2")
    def test_directory_cannot_be_moved_into_itself(self):
        (self.root_path / "a").mkdir()
        with self.config():
            with self.assertRaises(ServerFilesInvalidPath):
                service.rename_or_move("root-0", "a", "root-0", "a/child", "a", self.user)

    def test_download_reader_never_exceeds_authorized_initial_size(self):
        from io import BytesIO
        reader = service._BoundedFileReader(BytesIO(b"abcdefghij"), 4)
        self.assertEqual(reader.read(3), b"abc")
        self.assertEqual(reader.read(10), b"d")
        self.assertEqual(reader.read(10), b"")
        reader.close()

    def test_copy_regular_file(self):
        (self.root_path / "source.txt").write_bytes(b"copy me")
        with self.config():
            result = service.copy_file("root-0", "source.txt", "root-0", "", "copy.txt", self.user)
        self.assertEqual(result["size"], 7)
        self.assertEqual(self._read("copy.txt"), b"copy me")

    def test_copying_sensitive_source_requires_sensitive_mutation_policy(self):
        (self.root_path / ".env").write_text("SECRET=value")
        with self.config():
            with self.assertRaises(ServerFilesDenied):
                service.copy_file("root-0", ".env", "root-0", "", "public-copy.txt", self.user)
        self.assertFalse((self.root_path / "public-copy.txt").exists())

    def test_permission_helper_requires_named_permission_for_non_superusers(self):
        regular = get_user_model().objects.create_user(username="permission-test")
        with self.config():
            self.assertFalse(has_capability(regular, "delete_server_files"))
            self.assertTrue(has_capability(self.user, "delete_server_files"))
            permission = Permission.objects.get(codename="download_server_files", content_type__app_label="paxalia")
            regular.user_permissions.add(permission)
            regular.refresh_from_db()
            self.assertTrue(has_capability(regular, "download_server_files"))

    def test_empty_file_upload_is_supported(self):
        with self.config():
            service.upload_file("root-0", "", "empty.txt", SimpleUploadedFile("empty.txt", b""), self.user)
        self.assertEqual(self._read("empty.txt"), b"")

    def test_intermediate_symlink_escape_is_blocked(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "outside.txt").write_text("secret")
        try:
            (self.root_path / "linkdir").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable")
        with self.config():
            with self.assertRaises(ServerFilesDenied):
                service.open_download("root-0", "linkdir/outside.txt", self.user)

    def test_scan_limit_is_bounded_and_reported(self):
        for number in range(10):
            (self.root_path / f"f-{number}.txt").write_text("x")
        with self.config(FILE_MANAGER_MAX_DIRECTORY_ENTRIES=5):
            listing = service.list_directory("root-0", "", self.user)
        self.assertTrue(listing["truncated"])
        self.assertLessEqual(listing["total"], 5)

    def test_operation_history_redacts_sensitive_paths(self):
        from django.test import RequestFactory
        from .server_files.audit import begin_operation
        request = RequestFactory().get("/")
        request.user = self.user
        with self.config():
            row = begin_operation(request, "download", root_id="root-0", path=".env", required=True)
        self.assertEqual(row.path, "[protected]")
        self.assertEqual(row.status, "started")


class ServerFilesRequestLimitMiddlewareTests(SimpleTestCase):
    """Verify request bodies are rejected before Django parses form data."""

    class Request:
        def __init__(self, path, content_length=None, method="POST"):
            self.path_info = path
            self.method = method
            self.META = {}
            if content_length is not None:
                self.META["CONTENT_LENGTH"] = str(content_length)

    def test_upload_above_limit_is_rejected_without_calling_downstream(self):
        from django.http import HttpResponse
        from .server_files.middleware import ServerFilesRequestLimitMiddleware

        called = []
        middleware = ServerFilesRequestLimitMiddleware(
            lambda request: called.append(request) or HttpResponse("ok")
        )
        request = self.Request("/paxalia/server-files/operation/", 2 * 1024 * 1024 + 1)
        with override_settings(PAXALIA_DASHBOARD={
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_MAX_UPLOAD_SIZE_MB": 1,
        }):
            response = middleware(request)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(called, [])
        self.assertIn("no-store", response["Cache-Control"])

    def test_missing_upload_content_length_is_rejected(self):
        from django.http import HttpResponse
        from .server_files.middleware import ServerFilesRequestLimitMiddleware

        middleware = ServerFilesRequestLimitMiddleware(lambda request: HttpResponse("called", status=200))
        with override_settings(PAXALIA_DASHBOARD={
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_MAX_UPLOAD_SIZE_MB": 1,
        }):
            response = middleware(self.Request("/paxalia/server-files/operation/"))
        self.assertEqual(response.status_code, 411)

    def test_oversized_reauthentication_body_is_rejected(self):
        from django.http import HttpResponse
        from .server_files.middleware import ServerFilesRequestLimitMiddleware

        middleware = ServerFilesRequestLimitMiddleware(lambda request: HttpResponse("called", status=200))
        with override_settings(PAXALIA_DASHBOARD={"FILE_MANAGER_ENABLED": True}):
            response = middleware(self.Request("/paxalia/server-files/reauth/", 8193))
        self.assertEqual(response.status_code, 413)

    def test_disabled_feature_does_not_intercept_requests(self):
        from django.http import HttpResponse
        from .server_files.middleware import ServerFilesRequestLimitMiddleware

        middleware = ServerFilesRequestLimitMiddleware(lambda request: HttpResponse("called", status=200))
        with override_settings(PAXALIA_DASHBOARD={"FILE_MANAGER_ENABLED": False}):
            response = middleware(self.Request("/paxalia/server-files/operation/"))
        self.assertEqual(response.status_code, 200)


class ServerFilesPruneCommandTests(TestCase):
    def setUp(self):
        from .server_files.models import ServerFileOperation
        self.model = ServerFileOperation
        self.user = get_user_model().objects.create_superuser(
            username="server-files-prune-test", email="prune@example.invalid", password="not-used"
        )

    def _create(self, operation, created_at):
        return self.model.objects.create(
            actor=self.user, operation=operation, path="sample.txt", status="success", created_at=created_at
        )

    def test_each_cleanup_invocation_is_globally_bounded(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        old = timezone.now() - timedelta(days=10)
        for index in range(5):
            self._create("download", old + timedelta(seconds=index))
        with override_settings(PAXALIA_DASHBOARD={
            "FILE_MANAGER_OPERATION_RETENTION_DAYS": 1,
            "FILE_MANAGER_MAX_OPERATION_RECORDS": 100,
            "FILE_MANAGER_CLEANUP_BATCH_SIZE": 2,
        }):
            call_command("paxalia_server_files_prune", batch_size=2, verbosity=0)
        self.assertEqual(self.model.objects.count(), 3)

    def test_count_cap_cleanup_removes_low_value_rows_first_and_in_one_batch(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        now = timezone.now()
        for index in range(5):
            self._create("list", now - timedelta(seconds=10 - index))
        for index in range(2):
            self._create("delete", now - timedelta(seconds=index))
        with override_settings(PAXALIA_DASHBOARD={
            "FILE_MANAGER_OPERATION_RETENTION_DAYS": 90,
            "FILE_MANAGER_MAX_OPERATION_RECORDS": 4,
            "FILE_MANAGER_CLEANUP_BATCH_SIZE": 2,
        }):
            call_command("paxalia_server_files_prune", batch_size=2, verbosity=0)
        self.assertEqual(self.model.objects.count(), 5)
        self.assertEqual(self.model.objects.filter(operation="delete").count(), 2)



class ServerFilesSchemaRegressionTests(TestCase):
    """Catch model/migration/schema drift that caused the prune failure."""

    def test_model_is_registered_in_the_paxalia_app(self):
        from django.apps import apps
        from .server_files.models import ServerFileOperation

        registered = apps.get_model("paxalia", "ServerFileOperation")
        self.assertIs(registered, ServerFileOperation)
        self.assertEqual(registered._meta.db_table, "paxalia_serverfileoperation")

    def test_latest_migration_state_contains_operation_model(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        state = MigrationLoader(connection, ignore_no_migrations=True).project_state()
        self.assertIn(("paxalia", "serverfileoperation"), state.models)

    def test_operation_history_table_exists_after_migrations(self):
        from django.db import connection
        from .server_files.models import ServerFileOperation

        self.assertIn(
            ServerFileOperation._meta.db_table,
            connection.introspection.table_names(),
        )


class ServerFilesPruneSchemaGuardTests(SimpleTestCase):
    def test_missing_table_has_actionable_command_error(self):
        from unittest.mock import Mock
        from django.core.management.base import CommandError
        from .management.commands.paxalia_server_files_prune import require_operation_table

        database = Mock()
        database.introspection.table_names.return_value = []
        with self.assertRaisesMessage(CommandError, "operation-history table is missing"):
            require_operation_table(database)

    def test_schema_inspection_failure_is_wrapped(self):
        from unittest.mock import Mock
        from django.core.management.base import CommandError
        from .management.commands.paxalia_server_files_prune import require_operation_table

        database = Mock()
        database.introspection.table_names.side_effect = RuntimeError("backend detail must not leak")
        with self.assertRaisesMessage(CommandError, "Unable to inspect the database schema") as raised:
            require_operation_table(database)
        self.assertNotIn("backend detail", str(raised.exception))



class ServerFilesIntegrationRegressionTests(SimpleTestCase):
    """Regression coverage for Phase 1 package integration."""

    def test_server_files_urls_are_registered(self):
        from django.urls import reverse

        expected_suffixes = {
            "server_files": "/server-files/",
            "server_files_preview": "/server-files/preview/",
            "server_files_download": "/server-files/download/",
            "server_files_operation": "/server-files/operation/",
            "server_files_history": "/server-files/history/",
            "server_files_reauth": "/server-files/reauth/",
        }
        for name, suffix in expected_suffixes.items():
            self.assertTrue(
                reverse(f"paxalia:{name}").endswith(suffix),
                msg=f"paxalia:{name} is not registered with the expected route suffix",
            )

    def test_sidebar_template_compiles(self):
        from django.template.loader import get_template

        get_template("paxalia/base.html")

    def test_server_files_page_templates_compile(self):
        from django.template.loader import get_template

        get_template("paxalia/server_files.html")
        get_template("paxalia/server_files_history.html")
        get_template("paxalia/server_files_preview.html")
        get_template("paxalia/server_files_reauth.html")
        get_template("paxalia/server_files_error.html")

    def test_authenticated_post_views_are_honeypot_exempt(self):
        from .server_files.views import server_files_operation, server_files_reauth

        self.assertTrue(getattr(server_files_operation, "honeypot_exempt", False))
        self.assertTrue(getattr(server_files_reauth, "honeypot_exempt", False))

    def test_manage_panel_is_defined_before_entries_table(self):
        template_path = Path(__file__).resolve().parent / "templates" / "paxalia" / "server_files.html"
        source = template_path.read_text(encoding="utf-8")
        self.assertLess(
            source.index('id="sf-management-panel"'),
            source.index('id="sf-entries-title"'),
        )
        self.assertIn("data-sf-manage", source)

    def test_server_files_model_is_imported_by_root_models_module(self):
        from django.apps import apps
        from .server_files.models import ServerFileOperation

        self.assertIs(apps.get_model("paxalia", "ServerFileOperation"), ServerFileOperation)



class ServerFilesPermissionCacheRegressionTests(TestCase):
    def test_capability_reflects_permission_added_after_negative_check(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from .server_files.policy import has_capability

        user = get_user_model().objects.create_user(username="permission-cache-regression")
        with self.settings(PAXALIA_DASHBOARD={
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_ALLOWED_ROOTS": [],
        }):
            self.assertFalse(has_capability(user, "download_server_files"))
            permission = Permission.objects.get(
                codename="download_server_files",
                content_type__app_label="paxalia",
            )
            user.user_permissions.add(permission)
            self.assertTrue(has_capability(user, "download_server_files"))


class ServerFilesConfigurationIntegrationTests(SimpleTestCase):
    def test_package_defaults_are_fail_closed(self):
        from .settings import DEFAULTS

        self.assertFalse(DEFAULTS["FILE_MANAGER_ENABLED"])
        self.assertEqual(DEFAULTS["FILE_MANAGER_ALLOWED_ROOTS"], [])

    def test_sidebar_template_uses_the_registered_server_files_route(self):
        template_path = Path(__file__).resolve().parent / "templates" / "paxalia" / "base.html"
        source = template_path.read_text(encoding="utf-8")
        self.assertIn("paxalia:server_files", source)
        self.assertIn("sidebar-group--server-files", source)
        self.assertIn("analytics_config.FILE_MANAGER_ENABLED", source)
        self.assertNotIn("or ('server_files' in", source)

class ServerFilesHistoryViewRegressionTests(TestCase):
    """Regression coverage for the live history endpoint and its template."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="server-files-history-test",
            email="server-files-history@example.invalid",
            password="not-used",
        )

    def test_history_view_renders_with_a_real_operation_row(self):
        import inspect
        from django.http import HttpResponse
        from django.test import RequestFactory
        from unittest.mock import patch

        from .server_files.models import ServerFileOperation
        from .server_files.views import server_files_history

        request = RequestFactory().get("/server-files/history/")
        request.user = self.user
        request.paxalia_request_id = "history-regression"
        ServerFileOperation.objects.create(
            actor=self.user,
            operation="list",
            root_id="root-0",
            path="",
            status="success",
            request_id="history-regression",
        )

        with self.settings(PAXALIA_DASHBOARD={
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_ALLOWED_ROOTS": [],
            "FILE_MANAGER_HISTORY_PAGE_SIZE": 50,
        }):
            with patch("paxalia.server_files.views._enforce_rate_limit"),                  patch("paxalia.server_files.views._audit", return_value=None),                  patch("paxalia.server_files.views.finish_operation"),                  patch("paxalia.server_files.views.render", return_value=HttpResponse("ok")):
                response = inspect.unwrap(server_files_history)(request)

        self.assertEqual(response.status_code, 200)

