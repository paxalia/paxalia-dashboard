"""Canonical regression coverage for Transfers, Availability, and resource policies."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    DailySiteStats,
    FileUpload,
    PageView,
    PaxaliaLogEvent,
    PaxaliaTransfer,
    UptimeCheck,
    UptimeIncident,
    UptimeMonitor,
)
from .resource_policies import log_limits, log_storage_status, prune_log_events, realtime_limits
from .transfer_center import policy as transfer_policy
from .transfer_center.service import (
    complete_receive,
    create_receive_transfer,
    create_send_transfer,
    resume_receive_transfer,
    resume_send_transfer,
    pause_transfer,
    retry_transfer,
    sync_finalize_send,
)
from .transfer_center.views import _serialize_transfer, _service_error, _transfer_model_error_code
from .uptime import monitors_due_for_check, perform_check, record_check, validate_monitor_url


class OperationsConfigurationTests(TestCase):
    def test_transfer_root_cannot_overlap_server_files_root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        allowed = Path(temp.name) / "allowed"
        allowed.mkdir()
        with override_settings(PAXALIA_DASHBOARD={
            "TRANSFER_CENTER_ENABLED": True,
            "TRANSFER_ROOT": str(allowed / "paxalia-files"),
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_ALLOWED_ROOTS": [{"name": "Allowed", "path": str(allowed)}],
        }):
            with self.assertRaisesMessage(ValueError, "overlap a Server Files root"):
                transfer_policy.transfer_root()

    def test_inactive_superuser_does_not_bypass_server_file_capabilities(self):
        from django.contrib.auth import get_user_model
        from .server_files.policy import has_capability
        inactive = get_user_model().objects.create_superuser(username='inactive-ops', email='inactive-ops@example.invalid', password='unused')
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])
        self.assertFalse(has_capability(inactive, 'download_server_files'))

    def test_transfer_defaults_are_bounded(self):
        self.assertEqual(transfer_policy.max_transfer_bytes(), 2048 * 1024 * 1024)
        self.assertEqual(transfer_policy.chunk_size_bytes(), 5 * 1024 * 1024)
        self.assertGreaterEqual(transfer_policy.max_concurrent_transfers(), 1)

    def test_log_storage_warning_configuration_is_exposed(self):
        with override_settings(PAXALIA_DASHBOARD={
            "LOG_MAX_STORAGE_MB": 2,
            "LOG_STORAGE_WARNING_THRESHOLDS": (80, 90, 95),
        }):
            limits = log_limits()
        self.assertEqual(limits["warning_thresholds"], (80, 90, 95))
        self.assertEqual(limits["max_storage_bytes"], 2 * 1024 * 1024)


    def test_log_limits_are_configurable(self):
        with override_settings(PAXALIA_DASHBOARD={
            "LOG_MAX_RECORDS": 1234,
            "LOG_MAX_STORAGE_MB": 17,
            "LOG_BROWSER_MAX_REALTIME_EVENTS": 321,
            "LOG_BROWSER_MAX_REALTIME_BUFFER": 654,
            "LOG_BROWSER_MAX_EVENTS_PER_PAGE": 37,
        }):
            limits = log_limits()
            realtime = realtime_limits()
        self.assertEqual(limits["max_records"], 1234)
        self.assertEqual(limits["max_storage_bytes"], 17 * 1024 * 1024)
        self.assertEqual(realtime["display_events"], 321)
        self.assertEqual(realtime["buffer_events"], 654)
        self.assertEqual(realtime["events_per_page"], 37)


class OperationsTransferServiceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "allowed"
        self.root.mkdir()
        self.exchange = self.root / "paxalia_transfer"
        self.exchange.mkdir()
        self.user = get_user_model().objects.create_superuser(
            username="operations-transfer", email="operations-transfer@example.invalid", password="unused"
        )
        self.cfg = {
            "TRANSFER_CENTER_ENABLED": True,
            "TRANSFER_ROOT": str(Path(self.temp.name) / "paxalia-files"),
            "TRANSFER_MAX_FILE_SIZE_MB": 32,
            "TRANSFER_CHUNK_SIZE_MB": 1,
            "TRANSFER_MAX_CONCURRENT": 2,
            "TRANSFER_MAX_RETRIES": 4,
            "FILE_MANAGER_ENABLED": True,
            "FILE_MANAGER_ALLOWED_ROOTS": [{"name": "Operations", "path": str(self.root)}],
            "TRANSFER_EXCHANGE_ROOT": str(self.exchange),
            "FILE_MANAGER_ALLOW_SENSITIVE_MUTATIONS": False,
        }

    def config(self, **extra):
        values = dict(self.cfg)
        values.update(extra)
        return override_settings(PAXALIA_DASHBOARD=values)

    def mark_upload_complete(self, transfer, upload, payload):
        """Mirror the real FileUpload completion state before finalization tests."""
        from .transfer_center.service import safe_staging_path
        staging = safe_staging_path(transfer.staging_path)
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_bytes(payload)
        now = timezone.now()
        upload.status = "completed"
        upload.bytes_received = len(payload)
        upload.chunks_received = upload.total_chunks
        upload.storage_path = str(staging)
        upload.completed_at = now
        upload.save(update_fields=["status", "bytes_received", "chunks_received", "storage_path", "completed_at", "updated_at"])
        return staging

    def test_send_transfer_is_bounded_and_uses_existing_upload_engine(self):
        with self.config():
            transfer, upload = create_send_transfer(
                user=self.user,
                filename="artifact.bin",
                total_size=2 * 1024 * 1024,
                destination_root_id="root-0",
                destination_path="",
            )
        self.assertEqual(transfer.direction, "send")
        self.assertEqual(transfer.status, "preparing")
        self.assertEqual(upload.purpose, "transfer_send")
        self.assertEqual(upload.transfer_id, transfer.id)
        self.assertEqual(transfer.total_chunks, 2)
        self.assertTrue(str(transfer.staging_path).startswith(str(Path(self.temp.name) / "paxalia-files" / "send")))

    def test_transfer_exchange_is_required_and_fail_closed_when_unconfigured(self):
        config = dict(self.cfg)
        config.pop("TRANSFER_EXCHANGE_ROOT", None)
        with override_settings(PAXALIA_DASHBOARD=config):
            with self.assertRaisesMessage(ValueError, "not configured"):
                create_send_transfer(
                    user=self.user, filename="no-exchange.bin", total_size=10,
                    destination_root_id="root-0", destination_path="../../opt/secret",
                )

    def test_legacy_send_path_cannot_be_resumed_outside_current_exchange(self):
        with self.config():
            transfer, _upload = create_send_transfer(
                user=self.user, filename="legacy.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            transfer.server_relative_path = "outside/legacy.bin"
            transfer.save(update_fields=["server_relative_path", "updated_at"])
            with self.assertRaises(PermissionDenied):
                resume_send_transfer(transfer_id=str(transfer.id), user=self.user)

    def test_legacy_receive_path_cannot_be_read_outside_current_exchange(self):
        source = self.exchange / "fixed.bin"
        source.write_bytes(b"fixed exchange data")
        with self.config():
            transfer = create_receive_transfer(
                user=self.user, filename="fixed.bin", source_root_id="root-0", source_path="fixed.bin"
            )
            transfer.server_relative_path = "outside/fixed.bin"
            transfer.save(update_fields=["server_relative_path", "updated_at"])
            with self.assertRaises(PermissionDenied):
                from .transfer_center.service import read_receive_chunk
                read_receive_chunk(transfer, self.user, 0)

    def test_send_ignores_browser_destination_and_uses_fixed_exchange(self):
        with self.config():
            transfer, _upload = create_send_transfer(
                user=self.user, filename="fixed.bin", total_size=10,
                destination_root_id="not-authorized", destination_path="../../opt/secret",
            )
        self.assertEqual(transfer.server_relative_path, "paxalia_transfer/fixed.bin")

    def test_send_rejects_existing_exchange_target_before_upload_creation(self):
        from .server_files.exceptions import ServerFilesAlreadyExists
        (self.exchange / "already-there.bin").write_bytes(b"existing")
        with self.config():
            with self.assertRaisesMessage(ServerFilesAlreadyExists, "already exists in the transfer exchange"):
                create_send_transfer(
                    user=self.user, filename="already-there.bin", total_size=10,
                    destination_root_id="root-0", destination_path="",
                )
        self.assertEqual(PaxaliaTransfer.objects.filter(filename="already-there.bin").count(), 0)

    def test_empty_destination_path_is_valid(self):
        with self.config():
            transfer, _ = create_send_transfer(
                user=self.user, filename="root.txt", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
        self.assertEqual(transfer.server_relative_path, "paxalia_transfer/root.txt")

    def test_concurrent_transfer_limit_is_enforced(self):
        with self.config(TRANSFER_MAX_CONCURRENT=1):
            create_send_transfer(user=self.user, filename="a.bin", total_size=10, destination_root_id="root-0", destination_path="")
            with self.assertRaisesMessage(Exception, "concurrent transfer limit"):
                create_send_transfer(user=self.user, filename="b.bin", total_size=10, destination_root_id="root-0", destination_path="")

    def test_resume_returns_existing_upload_progress(self):
        with self.config():
            transfer, upload = create_send_transfer(
                user=self.user, filename="resume.bin", total_size=2 * 1024 * 1024,
                destination_root_id="root-0", destination_path="",
            )
            upload.chunks_received = 1
            upload.bytes_received = 1024 * 1024
            upload.status = "uploading"
            temp_path = transfer_policy.send_upload_temp_path(upload.id)
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(b"x" * (1024 * 1024))
            self.addCleanup(lambda: temp_path.unlink(missing_ok=True))
            upload.save(update_fields=["chunks_received", "bytes_received", "status", "updated_at"])
            resumed, resumed_upload = resume_send_transfer(transfer_id=str(transfer.id), user=self.user)
        self.assertEqual(resumed.id, transfer.id)
        self.assertEqual(resumed_upload.chunks_received, 1)
        self.assertEqual(resumed.bytes_transferred, 1024 * 1024)


    def test_failed_send_upload_cannot_be_resumed_as_an_active_transfer(self):
        with self.config():
            transfer, upload = create_send_transfer(
                user=self.user, filename="failed-resume.bin", total_size=1024,
                destination_root_id="root-0", destination_path="",
            )
            upload.status = "failed"
            upload.error_message = "integrity failure"
            upload.save(update_fields=["status", "error_message", "updated_at"])
            with self.assertRaisesMessage(ValueError, "upload session has failed"):
                resume_send_transfer(transfer_id=str(transfer.id), user=self.user)
            transfer.refresh_from_db()
            self.assertEqual(transfer.status, "preparing")

    def test_receive_mutations_require_create_transfer_capability(self):
        source = Path(__file__).resolve().parent / "transfer_center" / "service.py"
        text = source.read_text(encoding="utf-8")
        read_start = text.index("def read_receive_chunk")
        read_block = text[read_start:read_start + 240]
        self.assertIn('_check_capability(user, "create_transfers")', read_block)
        complete_start = text.index("def complete_receive")
        complete_block = text[complete_start:complete_start + 240]
        self.assertIn('_check_capability(user, "create_transfers")', complete_block)

    def test_server_files_errors_use_safe_public_status_in_transfer_views(self):
        from .server_files.exceptions import ServerFilesConfigurationError, ServerFilesDenied
        message, status = _service_error(ServerFilesConfigurationError("private details"))
        self.assertEqual(status, 503)
        self.assertEqual(message, ServerFilesConfigurationError.public_message)
        self.assertNotIn("private details", message)
        message, status = _service_error(ServerFilesDenied("/secret/internal/path"))
        self.assertEqual(status, 403)
        self.assertEqual(message, ServerFilesDenied.public_message)
        self.assertNotIn("/secret/internal/path", message)

    def test_pause_and_retry_preserve_resumable_send_state(self):
        with self.config(TRANSFER_MAX_RETRIES=2):
            transfer, upload = create_send_transfer(
                user=self.user, filename="pause.bin", total_size=2 * 1024 * 1024,
                destination_root_id="root-0", destination_path="",
            )
            from .transfer_center.policy import send_upload_temp_path
            staging = send_upload_temp_path(upload.id)
            staging.parent.mkdir(parents=True, exist_ok=True)
            staging.write_bytes(b"x" * 1024 * 1024)
            upload.chunks_received = 1
            upload.bytes_received = 1024 * 1024
            upload.status = "uploading"
            upload.save(update_fields=["chunks_received", "bytes_received", "status", "updated_at"])
            transfer.status = "transferring"
            transfer.bytes_transferred = 1024 * 1024
            transfer.save(update_fields=["status", "bytes_transferred", "updated_at"])
            paused = pause_transfer(transfer, self.user)
            retried = retry_transfer(paused, self.user)
        self.assertEqual(paused.status, "paused")
        self.assertEqual(retried.status, "transferring")
        self.assertEqual(retried.retry_count, 1)
        self.assertEqual(retried.bytes_transferred, 1024 * 1024)

    def test_fixed_exchange_routes_outbound_to_one_controlled_folder(self):
        exchange = self.root / "paxalia_transfer"
        with self.config(TRANSFER_EXCHANGE_ROOT=str(exchange)):
            transfer, _upload = create_send_transfer(
                user=self.user,
                filename="release.tar.gz",
                total_size=1024,
                destination_root_id="root-0",
                destination_path="anything/under/opt",
            )
        self.assertEqual(transfer.server_root_id, "root-0")
        self.assertEqual(transfer.server_relative_path, "paxalia_transfer/release.tar.gz")

    def test_receive_exchange_uses_filename_not_arbitrary_server_path(self):
        exchange = self.root / "paxalia_transfer"
        source = exchange / "download.tar.gz"
        source.write_bytes(b"exchange-artifact")
        with self.config(TRANSFER_EXCHANGE_ROOT=str(exchange)):
            transfer = create_receive_transfer(
                user=self.user,
                filename="download.tar.gz",
                source_root_id="root-0",
                source_path="not/used/by/exchange-mode",
            )
        self.assertEqual(transfer.filename, "download.tar.gz")
        self.assertEqual(transfer.server_relative_path, "paxalia_transfer/download.tar.gz")

    def test_exchange_listing_returns_only_regular_files_without_server_paths(self):
        exchange = self.root / "paxalia_transfer"
        (exchange / "one.bin").write_bytes(b"one")
        (exchange / "two.txt").write_text("two", encoding="utf-8")
        (exchange / "subdir").mkdir()
        (exchange / ".hidden").write_text("hidden", encoding="utf-8")
        with self.config(TRANSFER_EXCHANGE_ROOT=str(exchange)):
            from .transfer_center.service import list_transfer_exchange_files
            files = list_transfer_exchange_files(self.user)
        names = [item["name"] for item in files]
        self.assertEqual(names, ["one.bin", "two.txt"])
        self.assertTrue(all("path" not in item for item in files))

    def test_exchange_directory_must_be_inside_authorized_server_root(self):
        exchange = Path(self.temp.name) / "outside-exchange"
        exchange.mkdir()
        with self.config(TRANSFER_EXCHANGE_ROOT=str(exchange)):
            from .transfer_center.service import validate_transfer_exchange
            with self.assertRaisesMessage(ValueError, "inside exactly one configured Server Files root"):
                validate_transfer_exchange(self.user, write=True)

    def test_receive_transfer_can_resume_after_pause(self):
        from .transfer_center.service import create_receive_transfer
        source = self.exchange / "resume-receive.txt"
        source.write_bytes(b"hello")
        with self.config():
            transfer = create_receive_transfer(user=self.user, source_root_id="root-0", source_path="resume-receive.txt")
            paused = pause_transfer(transfer, self.user)
            resumed = resume_receive_transfer(transfer_id=str(paused.id), user=self.user)
        self.assertEqual(paused.status, "paused")
        self.assertEqual(resumed.status, "transferring")

    def test_failed_send_retry_is_rejected_when_upload_session_failed(self):
        with self.config():
            transfer, upload = create_send_transfer(
                user=self.user, filename="failed-upload.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            transfer.status = "failed"
            transfer.save(update_fields=["status", "updated_at"])
            upload.status = "failed"
            upload.save(update_fields=["status", "updated_at"])
            with self.assertRaisesMessage(ValueError, "upload session has failed"):
                retry_transfer(transfer, self.user)

    def test_retry_limit_is_enforced(self):
        with self.config(TRANSFER_MAX_RETRIES=1):
            transfer, _upload = create_send_transfer(
                user=self.user, filename="retry.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            transfer.status = "failed"
            transfer.retry_count = 1
            transfer.save(update_fields=["status", "retry_count", "updated_at"])
            with self.assertRaisesMessage(ValueError, "retry limit"):
                retry_transfer(transfer, self.user)

    def test_receive_checksum_matching_completes(self):
        source = self.exchange / "receive.txt"
        source.write_bytes(b"hello")
        with self.config():
            transfer = create_receive_transfer(user=self.user, source_root_id="root-0", source_path="receive.txt")
            from .transfer_center.service import read_receive_chunk
            read_receive_chunk(transfer, self.user, 0)
            completed = complete_receive(transfer, self.user, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.bytes_transferred, 5)

    def test_receive_checksum_mismatch_fails(self):
        source = self.exchange / "receive.txt"
        source.write_bytes(b"hello")
        with self.config():
            transfer = create_receive_transfer(user=self.user, source_root_id="root-0", source_path="receive.txt")
            from .transfer_center.service import read_receive_chunk
            read_receive_chunk(transfer, self.user, 0)
            failed = complete_receive(transfer, self.user, "0" * 64)
        self.assertEqual(failed.status, "failed")
        self.assertIn("checksums", failed.error_message)

    def test_small_receive_rechecks_server_source_at_completion(self):
        import hashlib
        source = self.exchange / "race.txt"
        source.write_bytes(b"hello")
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer = create_receive_transfer(user=self.user, source_root_id="root-0", source_path="race.txt")
            from .transfer_center.service import read_receive_chunk
            read_receive_chunk(transfer, self.user, 0)
            # Simulate the server file being modified after the browser downloaded
            # the original bytes but before it submits the completion checksum.
            source.write_bytes(b"changed-on-server")
            failed = complete_receive(transfer, self.user, hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.server_checksum, hashlib.sha256(b"changed-on-server").hexdigest())
        self.assertEqual(failed.checksum_status, "mismatch")

    def test_small_send_promotes_only_after_integrity_check(self):
        import hashlib
        from .transfer_center.service import sync_finalize_send, safe_staging_path
        payload = b"operations-transfer"
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(user=self.user, filename="artifact.txt", total_size=len(payload), destination_root_id="root-0", destination_path="")
            staging = self.mark_upload_complete(transfer, upload, payload)
            transfer.source_checksum = hashlib.sha256(payload).hexdigest()
            transfer.save(update_fields=["source_checksum", "updated_at"])
            completed = sync_finalize_send(transfer, self.user)
        self.assertEqual(completed.status, "completed")
        self.assertEqual((self.exchange / "artifact.txt").read_bytes(), payload)
        self.assertEqual(completed.destination_checksum, hashlib.sha256(payload).hexdigest())
        self.assertEqual(completed.client_checksum, completed.destination_checksum)
        self.assertEqual(completed.server_checksum_scope, "server_destination")
        self.assertEqual(completed.checksum_status, "verified")
        self.assertFalse(staging.exists())

    def test_completed_send_retires_upload_staging_reference(self):
        import hashlib
        from .transfer_center.service import sync_finalize_send, safe_staging_path
        payload = b"upload-retirement"
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="retire.txt", total_size=len(payload),
                destination_root_id="root-0", destination_path="",
            )
            staging = self.mark_upload_complete(transfer, upload, payload)
            transfer.source_checksum = hashlib.sha256(payload).hexdigest()
            transfer.save(update_fields=["source_checksum", "updated_at"])
            completed = sync_finalize_send(transfer, self.user)
            upload.refresh_from_db()
        self.assertEqual(completed.status, "completed")
        self.assertEqual(upload.status, "completed")
        self.assertEqual(upload.storage_path, "")
        self.assertIsNotNone(upload.completed_at)

    def test_send_promotion_uses_atomic_hidden_exchange_staging(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "transfer_center" / "service.py").read_text(encoding="utf-8")
        self.assertIn(".paxalia-transfer-", source)
        self.assertIn("os.link(", source)
        self.assertIn("os.fsync(parent_fd)", source)
        finalize_start = source.index("def sync_finalize_send")
        finalize_block = source[finalize_start:source.index("def maintenance", finalize_start)]
        self.assertNotIn("os.open(name,", finalize_block)

    def test_finalize_accepts_transfer_identifier(self):
        with self.config():
            transfer, upload = create_send_transfer(
                user=self.user, filename="identifier.bin", total_size=5,
                destination_root_id="root-0", destination_path="",
            )
            upload.status = "completed"
            upload.storage_path = str(transfer_policy.send_upload_temp_path(upload.id))
            staging = transfer_policy.send_upload_temp_path(upload.id)
            staging.parent.mkdir(parents=True, exist_ok=True)
            staging.write_bytes(b"value")
            upload.save(update_fields=["status", "storage_path", "updated_at"])
            result = sync_finalize_send(transfer.id, self.user)
        self.assertEqual(result.id, transfer.id)

    def test_same_content_destination_is_still_a_collision(self):
        from .transfer_center.service import sync_finalize_send

        payload = b"strict-collision-payload"
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="strict-collision.bin", total_size=len(payload),
                destination_root_id="root-0", destination_path="",
                source_checksum=hashlib.sha256(payload).hexdigest(),
            )
            self.mark_upload_complete(transfer, upload, payload)
            destination = self.exchange / "strict-collision.bin"
            destination.write_bytes(payload)

            result = sync_finalize_send(transfer.id, self.user)

        self.assertEqual(result.status, "failed")
        self.assertEqual(_transfer_model_error_code(result), "destination_exists")
        self.assertEqual(destination.read_bytes(), payload)

    def test_race_created_destination_fails_finalization_with_stable_collision_reason(self):
        from .transfer_center.service import sync_finalize_send
        payload = b"collision-at-finalize"
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="race.bin", total_size=len(payload),
                destination_root_id="root-0", destination_path="",
                source_checksum=hashlib.sha256(payload).hexdigest(),
            )
            self.mark_upload_complete(transfer, upload, payload)
            (self.exchange / "race.bin").write_bytes(b"another-operation")
            failed = sync_finalize_send(transfer, self.user)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(
            failed.error_message,
            "A file with this name already exists in the transfer exchange. Rename the local file and upload again.",
        )
        self.assertEqual(_transfer_model_error_code(failed), "destination_exists")

    def test_failed_send_integrity_check_retires_upload(self):
        import hashlib
        from .transfer_center.service import sync_finalize_send, safe_staging_path
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="retire-mismatch.txt", total_size=5,
                destination_root_id="root-0", destination_path="",
                source_checksum=hashlib.sha256(b"hello").hexdigest(),
            )
            staging = self.mark_upload_complete(transfer, upload, b"world")
            failed = sync_finalize_send(transfer, self.user)
            upload.refresh_from_db()
        self.assertEqual(failed.status, "failed")
        self.assertEqual(upload.status, "failed")
        self.assertEqual(upload.storage_path, "")
        self.assertIsNone(upload.completed_at)

    def test_paused_send_cannot_finalize_until_resumed(self):
        from .transfer_center.service import sync_finalize_send
        with self.config():
            transfer, _upload = create_send_transfer(
                user=self.user, filename="paused-finalize.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            paused = pause_transfer(transfer, self.user)
            with self.assertRaisesMessage(ValueError, "Transfer is paused"):
                sync_finalize_send(paused, self.user)

    def test_send_checksum_mismatch_does_not_claim_a_server_destination_hash(self):
        import hashlib
        from .transfer_center.service import sync_finalize_send, safe_staging_path
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="mismatch.txt", total_size=5,
                destination_root_id="root-0", destination_path="",
                source_checksum=hashlib.sha256(b"hello").hexdigest(),
            )
            staging = self.mark_upload_complete(transfer, upload, b"world")
            failed = sync_finalize_send(transfer, self.user)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.destination_checksum, "")
        self.assertEqual(failed.checksum_status, "pending")
        self.assertFalse((self.exchange / "mismatch.txt").exists())

    def test_send_promotion_failure_uses_safe_error_text(self):
        import hashlib
        from .transfer_center.service import sync_finalize_send, safe_staging_path
        payload = b"secret-promotion-payload"
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="secret.txt", total_size=len(payload),
                destination_root_id="root-0", destination_path="",
            )
            staging = self.mark_upload_complete(transfer, upload, payload)
            transfer.source_checksum = hashlib.sha256(payload).hexdigest()
            transfer.save(update_fields=["source_checksum", "updated_at"])
            with patch("paxalia.transfer_center.service.server_files_service._open_directory", side_effect=OSError("/very/secret/internal/path")):
                failed = sync_finalize_send(transfer, self.user)
        self.assertEqual(failed.status, "failed")
        self.assertNotIn("/very/secret/internal/path", failed.error_message)
        self.assertEqual(failed.error_message, "Transfer destination promotion failed; retry or inspect server logs.")
        upload = transfer.upload_session
        upload.refresh_from_db()
        self.assertTrue(staging.exists())
        self.assertEqual(upload.status, "completed")
        self.assertEqual(upload.storage_path, str(staging))

    def test_failed_send_promotion_keeps_verified_staging_for_retry(self):
        import hashlib
        from .transfer_center.service import sync_finalize_send
        payload = b"retryable-promotion"
        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            transfer, upload = create_send_transfer(
                user=self.user, filename="retryable.txt", total_size=len(payload),
                destination_root_id="root-0", destination_path="",
                source_checksum=hashlib.sha256(payload).hexdigest(),
            )
            staging = self.mark_upload_complete(transfer, upload, payload)
            with patch("paxalia.transfer_center.service.server_files_service._open_parent", side_effect=OSError("transient filesystem failure")):
                failed = sync_finalize_send(transfer, self.user)
            upload.refresh_from_db()
        self.assertEqual(failed.status, "failed")
        self.assertTrue(staging.exists())
        self.assertEqual(upload.status, "completed")
        self.assertEqual(upload.storage_path, str(staging))

        with self.config(TRANSFER_SYNC_VERIFY_MAX_MB=1):
            retried = retry_transfer(failed, self.user)
            completed = sync_finalize_send(retried, self.user)
        self.assertEqual(retried.status, "verifying")
        self.assertEqual(completed.status, "completed")
        self.assertEqual((self.exchange / "retryable.txt").read_bytes(), payload)


    def test_retry_of_failed_transfer_respects_global_concurrency_limit(self):
        with self.config(TRANSFER_MAX_CONCURRENT=1):
            create_send_transfer(
                user=self.user, filename="active.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            failed = PaxaliaTransfer.objects.create(
                actor=self.user, direction="send", filename="failed.bin", size=10,
                chunk_size=10, total_chunks=1, status="failed", server_root_id="root-0",
                server_relative_path="failed.bin", max_retries=2,
            )
            with self.assertRaisesMessage(PermissionDenied, "concurrent transfer limit"):
                retry_transfer(failed, self.user)
        failed.refresh_from_db()
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.retry_count, 0)

    def test_retry_of_interrupted_transfer_reserves_global_concurrency_slot(self):
        with self.config(TRANSFER_MAX_CONCURRENT=1):
            PaxaliaTransfer.objects.create(
                actor=self.user, direction="send", filename="active.bin", size=10,
                chunk_size=10, total_chunks=1, status="transferring", server_root_id="root-0",
                server_relative_path="active.bin", max_retries=2,
            )
            interrupted = PaxaliaTransfer.objects.create(
                actor=self.user, direction="send", filename="interrupted.bin", size=10,
                chunk_size=10, total_chunks=1, status="interrupted", server_root_id="root-0",
                server_relative_path="interrupted.bin", max_retries=2,
            )
            with self.assertRaisesMessage(PermissionDenied, "concurrent transfer limit"):
                retry_transfer(interrupted, self.user)
        interrupted.refresh_from_db()
        self.assertEqual(interrupted.status, "interrupted")
        self.assertEqual(interrupted.retry_count, 0)

    def test_cancel_removes_transfer_staging(self):
        from .transfer_center.service import cancel_transfer, safe_staging_path
        with self.config():
            transfer, _upload = create_send_transfer(user=self.user, filename="cancel.bin", total_size=10, destination_root_id="root-0", destination_path="")
            staging = safe_staging_path(transfer.staging_path)
            staging.parent.mkdir(parents=True, exist_ok=True)
            staging.write_bytes(b"1234567890")
            cancelled = cancel_transfer(transfer, self.user)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertFalse(staging.exists())


    def test_cancel_rejects_verification_in_progress(self):
        from .transfer_center.service import cancel_transfer

        with self.config():
            transfer, _upload = create_send_transfer(
                user=self.user, filename="verifying-cancel.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            transfer.status = "verifying"
            transfer.save(update_fields=["status", "updated_at"])
            with self.assertRaisesMessage(ValueError, "verification is in progress"):
                cancel_transfer(transfer, self.user)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, "verifying")

    def test_resume_rejects_other_user(self):
        other = get_user_model().objects.create_user(username="operations-transfer-other")
        with self.config():
            transfer, _ = create_send_transfer(user=self.user, filename="a.bin", total_size=10, destination_root_id="root-0", destination_path="")
            with self.assertRaises(Exception):
                resume_send_transfer(transfer_id=str(transfer.id), user=other)

    def test_resume_revalidates_current_server_files_target_policy(self):
        from .transfer_center.service import PermissionDenied as ServicePermissionDenied
        with self.config():
            transfer, _upload = create_send_transfer(
                user=self.user, filename="policy.bin", total_size=10,
                destination_root_id="root-0", destination_path="",
            )
            with override_settings(PAXALIA_DASHBOARD=self.cfg | {"FILE_MANAGER_ALLOWED_ROOTS": []}):
                with self.assertRaises(ServicePermissionDenied):
                    resume_send_transfer(transfer_id=str(transfer.id), user=self.user)

    def test_send_completion_stores_actual_server_destination_checksum(self):
        from .transfer_center.service import sync_finalize_send, safe_staging_path
        payload = b"verified payload"
        checksum = __import__('hashlib').sha256(payload).hexdigest()
        with self.config():
            transfer, upload = create_send_transfer(
                user=self.user, filename="verified.txt", total_size=len(payload),
                destination_root_id="root-0", destination_path="", source_checksum=checksum,
            )
            staging = self.mark_upload_complete(transfer, upload, payload)
            result = sync_finalize_send(transfer, self.user)
        self.assertEqual(result.status, 'completed')
        self.assertEqual(result.destination_checksum, checksum)

    def test_read_receive_chunk_rechecks_transfer_ownership_at_service_boundary(self):
        from .transfer_center.service import read_receive_chunk
        other = get_user_model().objects.create_user(username='receive-owner-other')
        source = self.exchange / 'owner-check.txt'
        source.write_bytes(b'hello')
        with self.config():
            transfer = create_receive_transfer(user=self.user, source_root_id='root-0', source_path='owner-check.txt')
            with self.assertRaises(PermissionDenied):
                read_receive_chunk(transfer, other, 0)

    def test_transfer_serialization_does_not_expose_server_filesystem_path(self):
        with self.config():
            transfer, _ = create_send_transfer(
                user=self.user, filename="path-secret.txt", total_size=10,
                destination_root_id="root-0", destination_path="private/data",
            )
            payload = _serialize_transfer(transfer)
        self.assertNotIn("server_relative_path", payload)

    def test_direction_neutral_checksum_serialization_reports_client_and_server_hashes(self):
        send_checksum = "a" * 64
        server_checksum = "b" * 64
        with self.config():
            transfer, _ = create_send_transfer(
                user=self.user, filename="checksums.bin", total_size=10,
                destination_root_id="root-0", destination_path="", source_checksum=send_checksum,
            )
            transfer.destination_checksum = server_checksum
            transfer.save(update_fields=["destination_checksum", "updated_at"])
            payload = _serialize_transfer(transfer)
        self.assertEqual(payload["client_checksum"], send_checksum)
        self.assertEqual(payload["server_checksum"], server_checksum)
        self.assertEqual(payload["checksum_status"], "mismatch")


class OperationsAvailabilityTests(TestCase):
    def test_due_scheduler_orders_oldest_last_check_before_scan_cap(self):
        from django.utils import timezone
        old = timezone.now() - timedelta(days=1)
        first = UptimeMonitor.objects.create(name="newer-first", url="https://example.com", check_interval_seconds=300)
        second = UptimeMonitor.objects.create(name="older-due", url="https://example.org", check_interval_seconds=300)
        UptimeCheck.objects.create(monitor=first, status="up", checked_at=timezone.now())
        UptimeCheck.objects.create(monitor=second, status="down", checked_at=old)
        with override_settings(PAXALIA_DASHBOARD={"AVAILABILITY_MAX_CHECKS_PER_RUN": 1, "AVAILABILITY_MAX_SCHEDULER_SCAN": 2}):
            due = monitors_due_for_check()
        self.assertEqual([item.pk for item in due], [second.pk])


    def make_monitor(self, **kwargs):
        defaults = {
            "name": "Health",
            "url": "https://example.invalid/health",
            "kind": "api",
            "method": "GET",
            "expected_status_code": 200,
            "timeout_seconds": 10,
            "check_interval_minutes": 5,
            "check_interval_seconds": 300,
            "failure_threshold": 2,
            "recovery_threshold": 2,
            "is_active": True,
        }
        defaults.update(kwargs)
        return UptimeMonitor.objects.create(**defaults)

    def test_invalid_monitor_configuration_is_unknown(self):
        monitor = self.make_monitor(url='http://127.0.0.1:8000/health')
        result = perform_check(monitor)
        self.assertEqual(result['status'], 'unknown')

    def test_due_monitor_scheduler_is_bounded(self):
        from .models import UptimeMonitor
        with override_settings(PAXALIA_DASHBOARD={'AVAILABILITY_MAX_CHECKS_PER_RUN': 3}):
            for index in range(8):
                UptimeMonitor.objects.create(name=f'bound-{index}', url='https://example.com')
            due = monitors_due_for_check()
        self.assertLessEqual(len(due), 3)

    def test_due_monitor_scheduler_has_an_independent_scan_cap(self):
        with override_settings(PAXALIA_DASHBOARD={
            'AVAILABILITY_MAX_CHECKS_PER_RUN': 2,
            'AVAILABILITY_MAX_SCHEDULER_SCAN': 2,
        }):
            for index in range(10):
                self.make_monitor(name=f'scan-{index}')
            due = monitors_due_for_check()
        self.assertLessEqual(len(due), 2)

    @patch("paxalia.uptime.socket.getaddrinfo")
    def test_ssrf_policy_rejects_private_targets(self, getaddrinfo):
        getaddrinfo.return_value = [(0, 0, 0, "", ("127.0.0.1", 80))]
        ok, reason = validate_monitor_url("http://internal.example/")
        self.assertFalse(ok)
        self.assertIn("private", reason.lower())

    @patch("paxalia.uptime.socket.getaddrinfo")
    def test_ssrf_policy_rejects_mixed_public_and_private_dns_answers(self, getaddrinfo):
        getaddrinfo.return_value = [
            (0, 0, 0, "", ("93.184.216.34", 80)),
            (0, 0, 0, "", ("127.0.0.1", 80)),
        ]
        ok, reason = validate_monitor_url("http://example.invalid/")
        self.assertFalse(ok)
        self.assertIn("private", reason.lower())

    @patch("paxalia.uptime.validate_monitor_url", return_value=(True, ""))
    @patch("paxalia.uptime.urllib.request.build_opener")
    def test_private_http_error_reports_elapsed_time_without_unbound_local(self, build_opener, _valid):
        from urllib.error import HTTPError
        opener = Mock()
        opener.open.side_effect = HTTPError('https://example.invalid/', 302, 'private address rejected', {}, None)
        build_opener.return_value = opener
        monitor = self.make_monitor(follow_redirects=False)
        result = perform_check(monitor)
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNotNone(result['response_time_ms'])

    @patch("paxalia.uptime.validate_monitor_url", return_value=(True, ""))
    @patch("paxalia.uptime.urllib.request.build_opener")
    def test_expected_content_type_uses_exact_media_type(self, build_opener, _valid):
        from .uptime import perform_check
        response = MagicMock(status=200)
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.read.return_value = b'{"ok":true}'
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        build_opener.return_value.open.return_value = response
        monitor = self.make_monitor(expected_content_type="application/json")
        result = perform_check(monitor)
        self.assertEqual(result["status"], "up")

    @patch("paxalia.uptime.validate_monitor_url", return_value=(True, ""))
    @patch("paxalia.uptime.urllib.request.build_opener")
    def test_http_error_response_still_runs_assertions(self, build_opener, _valid):
        from io import BytesIO
        from .uptime import perform_check
        error = __import__('urllib.error', fromlist=['HTTPError']).HTTPError(
            "https://example.invalid/", 404, "Not Found", {"Content-Type": "application/json"},
            BytesIO(b'{"status":"ok"}'),
        )
        build_opener.return_value.open.side_effect = error
        monitor = self.make_monitor(expected_status_code=404, response_assertions=[{"json_path":"status","equals":"ok"}])
        result = perform_check(monitor)
        self.assertEqual(result["status"], "up")

    @patch("paxalia.uptime.validate_monitor_url", return_value=(True, ""))
    def test_request_body_is_bounded_before_network_io(self, _valid):
        monitor = self.make_monitor(method="POST", request_body="x" * 70000)
        with override_settings(PAXALIA_DASHBOARD={"AVAILABILITY_MAX_REQUEST_BODY_BYTES": 65536}):
            with patch("paxalia.uptime.urllib.request.build_opener") as build_opener:
                result = perform_check(monitor)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("request body", result["error_message"].lower())
        build_opener.assert_not_called()

    def test_response_assertions_support_selected_json_fields(self):
        from .uptime import _check_assertions
        passed, results = _check_assertions(
            [{"json_path": "status.state", "equals": "ok"}],
            '{"status":{"state":"ok"}}',
            {},
        )
        self.assertTrue(passed)
        self.assertTrue(results[0]["passed"])

    @patch("paxalia.uptime.validate_monitor_url", return_value=(True, ""))
    @patch("paxalia.uptime.urllib.request.build_opener")
    @patch("paxalia.uptime.time.monotonic")
    def test_response_timing_includes_bounded_body_read(self, monotonic, build_opener, _valid):
        from .uptime import perform_check
        response = MagicMock(status=200)
        response.headers = {"Content-Type": "text/plain"}
        def read(_limit):
            monotonic.side_effect = None
            monotonic.return_value = 1.75
            return b"ok"
        response.read.side_effect = read
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        build_opener.return_value.open.return_value = response
        monotonic.side_effect = [0.0]
        monitor = self.make_monitor()
        result = perform_check(monitor)
        self.assertEqual(result["response_time_ms"], 1750)

    @patch("paxalia.uptime.validate_monitor_url", return_value=(True, ""))
    @patch("paxalia.uptime.urllib.request.build_opener")
    def test_timeout_and_failure_are_observed_as_down(self, build_opener, _valid):
        opener = Mock()
        opener.open.side_effect = TimeoutError("timed out")
        build_opener.return_value = opener
        monitor = self.make_monitor()
        result = perform_check(monitor)
        self.assertEqual(result["status"], "down")
        self.assertIsNone(result["status_code"])

    def test_failure_threshold_creates_incident_after_consecutive_down_observations(self):
        monitor = self.make_monitor(failure_threshold=2, recovery_threshold=2)
        first = record_check(monitor, {"status": "down", "status_code": 503, "response_time_ms": 100, "error_message": "unhealthy", "assertion_result": []})
        second = record_check(monitor, {"status": "down", "status_code": 503, "response_time_ms": 110, "error_message": "unhealthy", "assertion_result": []})
        self.assertEqual(first.status, "down")
        incident = UptimeIncident.objects.get(monitor=monitor)
        self.assertEqual(incident.state, "open")
        self.assertIsNotNone(incident.first_confirmed_failure_at)

    def test_unknown_observation_breaks_transition_streak(self):
        monitor = self.make_monitor(failure_threshold=2)
        record_check(monitor, {"status": "down", "status_code": 503, "response_time_ms": 100, "error_message": "down", "assertion_result": []})
        record_check(monitor, {"status": "unknown", "status_code": None, "response_time_ms": None, "error_message": "worker unavailable", "assertion_result": []})
        record_check(monitor, {"status": "down", "status_code": 503, "response_time_ms": 100, "error_message": "down", "assertion_result": []})
        self.assertFalse(UptimeIncident.objects.filter(monitor=monitor).exists())

    def test_monitor_model_supports_site_scoping(self):
        from .models import Site
        site = Site.objects.create(name="Operations Site", domain="operations.example.invalid")
        monitor = self.make_monitor(site=site)
        self.assertEqual(monitor.site_id, site.id)

    def test_recovery_threshold_closes_incident_with_observed_boundary(self):
        monitor = self.make_monitor(failure_threshold=1, recovery_threshold=2)
        record_check(monitor, {"status": "down", "status_code": 503, "response_time_ms": 100, "error_message": "down", "assertion_result": []})
        record_check(monitor, {"status": "up", "status_code": 200, "response_time_ms": 20, "error_message": "", "assertion_result": []})
        incident = UptimeIncident.objects.get(monitor=monitor)
        self.assertEqual(incident.state, "open")
        record_check(monitor, {"status": "up", "status_code": 200, "response_time_ms": 18, "error_message": "", "assertion_result": []})
        incident.refresh_from_db()
        self.assertEqual(incident.state, "recovered")
        self.assertIsNotNone(incident.first_confirmed_recovery_at)


class OperationsMigrationReconciliationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='migration-permission-user',
            email='migration-permission-user@example.invalid',
        )

    def test_permission_reconciliation_preserves_assignments(self):
        import importlib
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        migration = importlib.import_module('paxalia.migrations.0025_reconcile_v500_model_state')
        dashboard_ct = ContentType.objects.get(app_label='paxalia', model='dashboardaccess')
        operation_ct = ContentType.objects.get(app_label='paxalia', model='serverfileoperation')
        canonical, _ = Permission.objects.get_or_create(
            content_type=dashboard_ct,
            codename='view_server_files',
            defaults={'name': 'Can view Paxalia Server Files'},
        )
        legacy, _ = Permission.objects.get_or_create(
            content_type=operation_ct,
            codename='view_server_files',
            defaults={'name': 'Can view Paxalia Server Files'},
        )
        group = Group.objects.create(name='v5 server files migration')
        self.addCleanup(group.delete)
        self.user.user_permissions.add(legacy)
        group.permissions.add(legacy)

        class AppsProxy:
            def get_model(self, app_label, model_name):
                if (app_label, model_name) == ('auth', 'Permission'):
                    return Permission
                if (app_label, model_name) == ('contenttypes', 'ContentType'):
                    return ContentType
                raise LookupError((app_label, model_name))

        migration.remove_legacy_server_files_view_permission(AppsProxy(), None)
        self.user.refresh_from_db()
        self.assertTrue(self.user.user_permissions.filter(pk=canonical.pk).exists())
        self.assertTrue(group.permissions.filter(pk=canonical.pk).exists())
        self.assertEqual(
            Permission.objects.filter(
                codename='view_server_files',
                content_type__app_label='paxalia',
            ).count(),
            1,
        )


class OperationsResourcePolicyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="operations-resource", email="operations-resource@example.invalid", password="unused"
        )

    def test_max_record_cleanup_protects_critical_and_security(self):
        now = timezone.now()
        with override_settings(PAXALIA_DASHBOARD={
            "LOG_MAX_RECORDS": 3,
            "LOG_CLEANUP_BATCH_SIZE": 2,
            "LOG_MAX_STORAGE_MB": 0,
            "LOG_SEVERITY_RETENTION_DAYS": {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0},
        }):
            PaxaliaLogEvent.objects.create(severity="DEBUG", source="Application", category="debug", message="old", timestamp=now - timedelta(days=2))
            PaxaliaLogEvent.objects.create(severity="INFO", source="Application", category="info", message="old", timestamp=now - timedelta(days=2))
            PaxaliaLogEvent.objects.create(severity="ERROR", source="Application", category="error", message="old", timestamp=now - timedelta(days=2))
            PaxaliaLogEvent.objects.create(severity="CRITICAL", source="Application", category="error", message="critical", timestamp=now - timedelta(days=2))
            PaxaliaLogEvent.objects.create(severity="ERROR", source="Authentication", category="security", message="security", timestamp=now - timedelta(days=2))
            result = prune_log_events(batch_size=2)
        self.assertLessEqual(result["max_records"], 2)
        self.assertTrue(PaxaliaLogEvent.objects.filter(severity="CRITICAL").exists())
        self.assertTrue(PaxaliaLogEvent.objects.filter(source="Authentication").exists())

    def test_category_retention_can_override_severity_retention(self):
        now = timezone.now()
        old = now - timedelta(days=40)
        with override_settings(PAXALIA_DASHBOARD={
            "LOG_MAX_RECORDS": 100,
            "LOG_CLEANUP_BATCH_SIZE": 10,
            "LOG_MAX_STORAGE_MB": 0,
            "LOG_SEVERITY_RETENTION_DAYS": {"INFO": 90, "DEBUG": 90, "WARNING": 90, "ERROR": 90, "CRITICAL": 365},
            "LOG_RETENTION_DAYS": {"browser": 30},
        }):
            PaxaliaLogEvent.objects.create(severity="INFO", source="Application", category="browser", message="old-browser", timestamp=old)
            PaxaliaLogEvent.objects.create(severity="INFO", source="Application", category="application", message="old-app", timestamp=old)
            result = prune_log_events(batch_size=10)
        self.assertEqual(result["retention"], 1)
        self.assertFalse(PaxaliaLogEvent.objects.filter(category="browser").exists())
        self.assertTrue(PaxaliaLogEvent.objects.filter(category="application").exists())

    def test_high_volume_cleanup_is_bounded(self):
        rows = [
            PaxaliaLogEvent(severity="INFO", source="Application", category="system", message=f"event-{i}")
            for i in range(1000)
        ]
        PaxaliaLogEvent.objects.bulk_create(rows, batch_size=200)
        with override_settings(PAXALIA_DASHBOARD={"LOG_MAX_RECORDS": 10, "LOG_CLEANUP_BATCH_SIZE": 25, "LOG_MAX_STORAGE_MB": 0}):
            result = prune_log_events(batch_size=25)
        self.assertLessEqual(result["max_records"], 25)

    @skipUnless(os.environ.get("PAXALIA_RUN_STRESS") == "1", "set PAXALIA_RUN_STRESS=1 for 100k stress coverage")
    def test_stress_100k_log_population(self):
        PaxaliaLogEvent.objects.bulk_create(
            [PaxaliaLogEvent(severity="INFO", source="Application", category="stress", message="x") for _ in range(100000)],
            batch_size=5000,
        )
        with override_settings(PAXALIA_DASHBOARD={"LOG_MAX_RECORDS": 1000, "LOG_CLEANUP_BATCH_SIZE": 100, "LOG_MAX_STORAGE_MB": 0}):
            result = prune_log_events(batch_size=100)
        self.assertLessEqual(result["max_records"], 100)


class OperationsLiveBufferTests(SimpleTestCase):
    def test_live_buffer_uses_configured_runtime_bound(self):
        import logging
        from .logging.handler import PaxaliaLiveLogBuffer
        PaxaliaLiveLogBuffer.clear()
        with override_settings(PAXALIA_DASHBOARD={"LOG_BROWSER_MAX_REALTIME_BUFFER": 5}):
            for index in range(12):
                PaxaliaLiveLogBuffer.append(logging.LogRecord(
                    name="paxalia.operations.test", level=logging.INFO, pathname=__file__, lineno=index,
                    msg="event-%s", args=(index,), exc_info=None,
                ))
            payload = PaxaliaLiveLogBuffer.snapshot()
        self.assertLessEqual(len(payload["entries"]), 5)



class OperationsMaintenanceCommandTests(TestCase):
    def test_transfer_maintenance_dry_run_is_bounded(self):
        from io import StringIO
        out = StringIO()
        call_command("paxalia_transfer_maintenance", "--dry-run", stdout=out)
        self.assertIn("bounded", out.getvalue())


    def test_resource_prune_uses_transfer_maintenance_batch_size_keyword(self):
        from pathlib import Path
        source = Path(__file__).resolve().parent / "management" / "commands" / "paxalia_resource_prune.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn("transfer_maintenance(batch_size=", text)
        self.assertNotIn("transfer_maintenance(limit=", text)

    @patch("paxalia.management.commands.paxalia_resource_prune.notify_log_storage_warning")
    @patch("paxalia.management.commands.paxalia_resource_prune.log_storage_status", return_value={"percent": 0})
    @patch("paxalia.management.commands.paxalia_resource_prune.transfer_maintenance")
    @patch("paxalia.management.commands.paxalia_resource_prune.prune_log_events")
    def test_resource_prune_has_one_global_processing_budget(self, prune_logs, transfer_maintenance, _storage, _notify):
        prune_logs.return_value = {"retention": 3, "max_records": 0, "storage": 0, "groups": 0}
        from io import StringIO
        out = StringIO()
        call_command("paxalia_resource_prune", "--batch-size", "3", stdout=out)
        transfer_maintenance.assert_not_called()
        self.assertIn("processed=3", out.getvalue())

    def test_resource_prune_staging_scan_is_globally_bounded(self):
        from types import SimpleNamespace
        from paxalia.management.commands.paxalia_resource_prune import _find_stale_staging_candidates
        now = timezone.now()
        entries = []
        for _index in range(10):
            entry = MagicMock()
            entry.is_file.return_value = True
            entry.stat.return_value = SimpleNamespace(
                st_mtime=(now - timedelta(days=2)).timestamp()
            )
            entries.append(entry)
        root = MagicMock()
        root.iterdir.return_value = iter(entries)
        candidates, scanned = _find_stale_staging_candidates(
            [root],
            cutoff=now - timedelta(days=1),
            candidate_limit=10,
            scan_limit=3,
            is_referenced=lambda _path: False,
        )
        self.assertEqual(scanned, 3)
        self.assertEqual(len(candidates), 3)
        self.assertFalse(entries[3].is_file.called)

    def test_resource_prune_dry_run_is_non_destructive(self):
        from io import StringIO
        out = StringIO()
        call_command("paxalia_resource_prune", "--dry-run", stdout=out)
        self.assertIn("Paxalia resource maintenance", out.getvalue())

    def test_resource_prune_does_not_treat_active_upload_temp_files_as_orphans(self):
        source = Path(__file__).resolve().parent / "management" / "commands" / "paxalia_resource_prune.py"
        text = source.read_text(encoding="utf-8")
        start = text.index('def _is_staging_referenced')
        end = text.index('roots = staging_roots()', start)
        block = text[start:end]
        self.assertIn('send_upload_temp_path', text)
        self.assertIn('purpose="transfer_send"', block)
        self.assertIn('.upload-', block)

    def test_resource_prune_transfer_count_cap_retires_linked_upload_metadata(self):
        source = Path(__file__).resolve().parent / "management" / "commands" / "paxalia_resource_prune.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn('transfer_id__in=ids', text)
        self.assertIn("purpose='transfer_send'", text)
        self.assertIn('safe_staging_path(staging_path)', text)

    def test_resource_prune_has_explicit_orphan_transfer_upload_cleanup(self):
        from pathlib import Path
        source = Path(__file__).resolve().parent / "management" / "commands" / "paxalia_resource_prune.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn("Exists(transfer_exists)", text)
        self.assertIn("purpose='transfer_send'", text)
        self.assertIn("Orphan transfer upload metadata", text)


class OperationsIntegrationTests(TestCase):
    def test_urls_are_registered(self):
        expected = [
            ("transfer_center", {}, "/transfer-center/"),
            ("transfer_send_init", {}, "/transfer-center/send/init/"),
            ("transfer_send_resume", {}, "/transfer-center/send/resume/"),
            ("transfer_pause", {"transfer_id": "00000000-0000-0000-0000-000000000000"}, "/transfer-center/pause/00000000-0000-0000-0000-000000000000/"),
            ("transfer_retry", {"transfer_id": "00000000-0000-0000-0000-000000000000"}, "/transfer-center/retry/00000000-0000-0000-0000-000000000000/"),
            ("transfer_send_finalize", {"transfer_id": "00000000-0000-0000-0000-000000000000"}, "/transfer-center/send/00000000-0000-0000-0000-000000000000/finalize/"),
            ("transfer_receive_init", {}, "/transfer-center/receive/init/"),
            ("transfer_receive_resume", {}, "/transfer-center/receive/resume/"),
            ("availability", {}, "/availability/"),
            ("availability_incident_acknowledge", {"incident_id": 1}, "/availability/incidents/1/acknowledge/"),
        ]
        for name, kwargs, suffix in expected:
            self.assertTrue(reverse(f"paxalia:{name}", kwargs=kwargs).endswith(suffix))


    def test_transfer_center_uses_fixed_exchange_selection_contract(self):
        from pathlib import Path
        package = Path(__file__).resolve().parent
        template = (package / "templates" / "paxalia" / "transfer_center.html").read_text(encoding="utf-8")
        script = (package / "static" / "paxalia" / "scripts" / "transfer-center.js").read_text(encoding="utf-8")
        self.assertIn('data-receive-file', template)
        self.assertNotIn('data-send-root', template)
        self.assertNotIn('data-send-path', template)
        self.assertNotIn('data-receive-root', template)
        self.assertNotIn('data-receive-path', template)
        self.assertIn("form.append('filename', filename);", script)
        self.assertNotIn("form.append('server_path'", script)

    def test_release_center_is_merged_into_transfer_center(self):
        from pathlib import Path
        package = Path(__file__).resolve().parent
        releases = (package / "views" / "releases.py").read_text(encoding="utf-8")
        sidebar = (package / "templates" / "paxalia" / "base.html").read_text(encoding="utf-8")
        self.assertIn('redirect("paxalia:transfer_center")', releases)
        self.assertNotIn("url 'paxalia:releases'", sidebar)

    def test_templates_compile(self):
        from django.template.loader import get_template
        for template in [
            "paxalia/transfer_center.html",
            "paxalia/uptime.html",
            "paxalia/logs.html",
            "paxalia/settings.html",
            "paxalia/base.html",
        ]:
            get_template(template)

    def test_migration_state_contains_operations_models_and_fields(self):
        state = MigrationLoader(connection, ignore_no_migrations=True).project_state()
        self.assertIn(("paxalia", "paxaliatransfer"), state.models)
        self.assertIn(("paxalia", "paxaliatransferlock"), state.models)
        self.assertIn("received_chunks", state.models[("paxalia", "paxaliatransfer")].fields)
        self.assertIn("check_interval_seconds", state.models[("paxalia", "uptimemonitor")].fields)
        self.assertIn("assertion_result", state.models[("paxalia", "uptimecheck")].fields)
        self.assertIn("state", state.models[("paxalia", "uptimeincident")].fields)

    def test_no_terminal_endpoint_exists_in_operations_sources(self):
        from pathlib import Path
        package = Path(__file__).resolve().parent
        for relative in ["transfer_center/views.py", "uptime.py", "server_files/views.py"]:
            source = (package / relative).read_text(encoding="utf-8")
            self.assertNotIn("?command=", source)
            self.assertNotIn("os.system(", source)



class BotTrafficManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="bot-path-manager", email="bot-path-manager@example.invalid", password="unused"
        )
        # These tests exercise Bot/Scanner authorization and view behavior,
        # not the separate three-layer administrator ceremony. Keep the
        # production @admin_security_required gate intact while making the
        # gate itself a trusted test precondition. Endpoint tests explicitly
        # use host-login compatibility mode so force_login() controls
        # request.user, which is the identity the view authorizes.
        self._admin_session_patch = patch(
            "paxalia.admin_security.admin_session_is_valid",
            return_value=True,
        )
        self._admin_session_patch.start()
        self.addCleanup(self._admin_session_patch.stop)

    def test_marking_path_adds_rule_and_moves_only_matching_normal_pageviews_to_bot_traffic(self):
        from django.utils import timezone
        from .models import AnalyticsSettings
        from .bot_management import add_bot_path_prefix
        day = timezone.localdate()
        DailySiteStats.objects.create(date=day, total_views=2, bot_views=0)
        normal = PageView.objects.create(path="/.env", url="https://example.test/.env", is_bot=False, is_api=False)
        PageView.objects.create(path="/normal", url="https://example.test/normal", is_bot=False, is_api=False)
        with override_settings(PAXALIA_DASHBOARD={"DEFAULT_ANONYMIZE_IP": True}):
            result = add_bot_path_prefix(prefix="/.env", start_dt=timezone.now() - timedelta(minutes=1), end_dt=timezone.now() + timedelta(minutes=1))
        self.assertTrue(result["added"])
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["reclassified"], 1)
        normal.refresh_from_db()
        self.assertTrue(normal.is_bot)
        self.assertEqual(normal.bot_category, "malicious")
        self.assertTrue(PageView.objects.filter(path="/normal", is_bot=False).exists())
        stats = DailySiteStats.objects.get(date=day, site=None)
        self.assertEqual(stats.bot_views, 1)
        self.assertEqual(stats.total_views, 2)
        self.assertEqual(AnalyticsSettings.objects.get().bot_paths, "/.env")

    def test_root_prefix_is_rejected_as_destructive(self):
        from .bot_management import normalize_bot_path_prefix
        with self.assertRaisesMessage(ValueError, "root path"):
            normalize_bot_path_prefix("/")

    def test_mark_endpoint_requires_management_permission(self):
        from django.urls import reverse
        from .bot_management import can_manage_bot_paths
        user = get_user_model().objects.create_user(username="bot-reader", is_staff=True)
        self.assertFalse(can_manage_bot_paths(user))
        self.client.force_login(user)
        with override_settings(PAXALIA_DASHBOARD={"AUTH_USE_HOST_LOGIN": True}):
            response = self.client.post(reverse("paxalia:bot_path_mark"), {"path": "/wp-admin/"})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(can_manage_bot_paths(self.user))

    def test_bot_identity_identifies_search_engine_claim_without_calling_it_verified(self):
        from .bot_classification import classify_bot_identity
        identity = classify_bot_identity(False, "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        self.assertEqual(identity["category"], "search_engine")
        self.assertEqual(identity["provider"], "Google")
        self.assertEqual(identity["name"], "Googlebot")
        self.assertEqual(identity["confidence"], "claimed")

    def test_bots_view_groups_client_ip_and_requested_paths(self):
        from .models import PageView
        PageView.objects.create(path="/", url="https://example.test/", ip_hash="203.0.113.8", user_agent="Googlebot", is_bot=True, bot_category="search_engine", is_api=False)
        PageView.objects.create(path="/docs", url="https://example.test/docs", ip_hash="203.0.113.8", user_agent="Googlebot", is_bot=True, bot_category="search_engine", is_api=False)
        PageView.objects.create(path="/.env", url="https://example.test/.env", ip_hash="203.0.113.8", user_agent="curl/8.0", is_bot=True, bot_category="malicious", is_api=False)
        self.client.force_login(self.user)
        response = self.client.get(reverse("paxalia:bots"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ip_rows"][0]["ip_hash"], "203.0.113.8")
        self.assertEqual(response.context["ip_rows"][0]["unique_paths"], 3)
        self.assertEqual({row["path"] for row in response.context["ip_rows"][0]["paths"]}, {"/", "/docs", "/.env"})

    def test_broken_links_view_separates_normal_and_bot_404s(self):
        from .models import PageView
        PageView.objects.create(path="/missing", url="https://example.test/missing", ip_hash="198.51.100.4", status_code=404, is_bot=False, is_api=False)
        PageView.objects.create(path="/.env", url="https://example.test/.env", ip_hash="198.51.100.5", status_code=404, is_bot=True, bot_category="malicious", is_api=False)
        self.client.force_login(self.user)
        response = self.client.get(reverse("paxalia:broken_links"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["human_404s"], 1)
        self.assertEqual(response.context["bot_404s"], 1)
        self.assertEqual(response.context["top_broken_paths"][0]["path"], "/missing")
        self.assertEqual(response.context["scanner_paths"][0]["path"], "/.env")

    def test_mark_endpoint_rejects_external_return_target(self):
        from django.urls import reverse
        self.client.force_login(self.user)
        with override_settings(PAXALIA_DASHBOARD={"AUTH_USE_HOST_LOGIN": True}):
            response = self.client.post(
                reverse("paxalia:bot_path_mark"),
                {"path": "/wp-login.php", "remove_normal_views": "0", "return_to": "https://evil.example/"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("paxalia:bots"))

    def test_mark_endpoint_saves_rule_and_reclassifies_matching_normal_views(self):
        from django.urls import reverse
        from .models import AnalyticsSettings
        normal = PageView.objects.create(path="/wp-admin/install.php", url="https://example.test/wp-admin/install.php", is_bot=False, is_api=False)
        keep = PageView.objects.create(path="/", url="https://example.test/", is_bot=False, is_api=False)
        self.client.force_login(self.user)
        with override_settings(PAXALIA_DASHBOARD={"AUTH_USE_HOST_LOGIN": True}):
            response = self.client.post(
                reverse("paxalia:bot_path_mark"),
                {"path": "/wp-admin/install.php", "remove_normal_views": "1", "return_to": reverse("paxalia:pages")},
            )
        self.assertEqual(response.status_code, 302)
        normal.refresh_from_db()
        self.assertTrue(normal.is_bot)
        self.assertEqual(normal.bot_category, "malicious")
        self.assertTrue(PageView.objects.filter(pk=keep.pk).exists())
        self.assertIn("/wp-admin/install.php", AnalyticsSettings.objects.get().bot_paths.splitlines())


class PackageNamingTests(SimpleTestCase):
    def test_package_file_names_are_clean(self):
        from pathlib import Path
        package = Path(__file__).resolve().parent
        self.assertTrue((package / 'test_operations.py').exists())
        self.assertTrue((package / 'migrations' / '0024_operations.py').exists())
        self.assertTrue((package / 'migrations' / '0025_reconcile_v500_model_state.py').exists())
        # Migration filenames are immutable history. Only active package/source
        # filenames are checked for temporary engineering labels.
        bad_tokens = ('fix',)
        temporary_word = 'pha' + 'se'
        bad_paths = [
            path.as_posix()
            for path in package.rglob('*.py')
            if path.is_file()
            and 'migrations' not in path.parts
            and any(token in path.name.lower() for token in bad_tokens + (temporary_word,))
        ]
        self.assertEqual(bad_paths, [])

    def test_transfer_center_uses_safe_unexpected_error_logging(self):
        from pathlib import Path
        views = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        service = (Path(__file__).resolve().parent / 'transfer_center' / 'service.py').read_text(encoding='utf-8')
        for source in (views, service):
            self.assertNotIn('logger.exception(', source)
            self.assertNotIn('exc_info=True', source)
            self.assertIn('_log_unexpected(', source)
class PackageIntegrationHardeningTests(SimpleTestCase):
    def test_admin_fallback_registers_transfer_model(self):
        from pathlib import Path
        source = Path(__file__).resolve().parent / 'admin.py'
        text = source.read_text(encoding='utf-8')
        self.assertIn('PaxaliaTransfer', text)
        self.assertIn('@admin.register(PaxaliaTransfer)', text)

    def test_server_files_failure_notification_does_not_expose_paths(self):
        from pathlib import Path
        source = Path(__file__).resolve().parent / 'server_files' / 'views.py'
        text = source.read_text(encoding='utf-8')
        self.assertIn('Server Files operation failed', text)
        self.assertNotIn('record.path', text)


class AvailabilityPermissionContractTests(SimpleTestCase):
    def test_incident_acknowledgement_requires_management_permission(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "views" / "uptime.py").read_text(encoding="utf-8")
        start = source.index("def availability_incident_acknowledge")
        block = source[start:start + 600]
        self.assertIn("manage_availability", block)
        self.assertNotIn("view_incidents", block.split("def availability_incident_acknowledge", 1)[1].split("incident =", 1)[0])

    def test_acknowledge_control_is_hidden_from_view_only_users(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "templates" / "paxalia" / "uptime.html").read_text(encoding="utf-8")
        self.assertIn("{% if can_manage_availability and incident.is_ongoing %}", source)


class IntegrationContractTests(TestCase):

    def test_transfer_history_filters_before_slice_for_staff_users(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "transfer_center" / "views.py").read_text(encoding="utf-8")
        history_start = source.index("history = PaxaliaTransfer.objects.exclude")
        history_block = source[history_start:source.index("return render", history_start)]
        self.assertLess(history_block.index("history = history.filter(actor=request.user)"), history_block.index("history = history[:50]"))


    def test_receive_browser_download_waits_for_server_verification(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "static" / "paxalia" / "scripts" / "transfer-center.js").read_text(encoding="utf-8")
        self.assertIn("function triggerDownload()", source)
        self.assertIn("current.status === 'completed'", source)
        complete_start = source.index("function completeDownload()")
        next_start = source.index("function next(", complete_start)
        complete_block = source[complete_start:next_start]
        self.assertIn("complete.append('destination_checksum'", complete_block)
        self.assertIn("return waitForVerification().then(function(){", complete_block)
        self.assertLess(
            complete_block.index("complete.append('destination_checksum'"),
            complete_block.index("triggerDownload();"),
        )
        verification_start = source.index("function waitForVerification()")
        verification_end = source.index("function completeDownload()", verification_start)
        verification_block = source[verification_start:verification_end]
        self.assertIn("if (current.status === 'completed')", verification_block)
        self.assertNotIn("triggerDownload();", verification_block)

    def test_sidebar_exposes_availability_and_transfer_sections(self):
        source = (Path(__file__).resolve().parent / 'templates' / 'paxalia' / 'base.html').read_text(encoding='utf-8')
        self.assertIn("paxalia:availability", source)
        self.assertIn("paxalia:transfer_center", source)
        self.assertIn("paxalia:server_files", source)
        self.assertIn("perms.paxalia.view_availability", source)
        self.assertIn("perms.paxalia.view_transfers", source)
        self.assertIn("perms.paxalia.view_server_files", source)
        self.assertNotIn("{% trans \"Delivery\" %}", source)
        self.assertNotIn("{% trans \"Reliability\" %}", source)

    def test_transfer_receive_chunk_is_post_backed_because_delivery_updates_state(self):
        source = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        start = source.index('def transfer_receive_chunk')
        block = source[start:source.index('def transfer_receive_complete', start)]
        self.assertIn('@require_POST', source[source.rfind('@', 0, start):start])
        self.assertNotIn('@require_GET', source[source.rfind('@', 0, start):start])
        self.assertIn('read_receive_chunk', block)

    def test_transfer_receive_chunk_is_honeypot_exempt(self):
        from .transfer_center import views as transfer_views
        self.assertTrue(getattr(transfer_views.transfer_receive_chunk, 'honeypot_exempt', False))

    def test_transfer_status_polling_is_read_only(self):
        source = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        start = source.index('def transfer_status')
        block = source[start:source.index('def transfer_cancel', start)]
        self.assertNotIn('transfer.save(', block)
        self.assertIn('payload["bytes_transferred"]', block)

    def test_transfer_upload_endpoint_rechecks_section_and_mutation_permissions(self):
        source = (Path(__file__).resolve().parent / 'views' / 'uploads.py').read_text(encoding='utf-8')
        start = source.index('def _transfer_upload_error')
        block = source[start:source.index('def _public_upload', start)]
        self.assertIn("has_capability(request.user, 'view_transfers')", block)
        self.assertIn("has_capability(request.user, 'create_transfers')", block)
        self.assertIn("has_capability(request.user, 'upload_server_files')", block)
        self.assertIn('select_for_update()', block)


    def test_transfer_resume_client_does_not_replace_non_404_errors_with_new_transfer(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function initTransfer()')
        block = source[start:source.index('return initTransfer()', start)]
        self.assertIn('err.status !== 404', block)
        self.assertIn('if (!err || err.status !== 404) throw err;', block)

    def test_transfer_client_assets_use_release_cache_and_semantic_resume_state(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parent / "templates" / "paxalia" / "transfer_center.html").read_text(encoding="utf-8")
        script = (Path(__file__).resolve().parent / "static" / "paxalia" / "scripts" / "transfer-center.js").read_text(encoding="utf-8")
        self.assertIn("paxalia/styles/components/transfer-center.css", template)
        self.assertIn("paxalia/scripts/transfer-center.js", template)
        self.assertIn("?v=5.0.0", template)
        self.assertIn("paxalia-transfer:resume:", script)
        self.assertNotRegex(template + script, r"--v[0-9]+")
        self.assertNotRegex(script, r"paxalia-transfer:v[0-9]+:")


    def test_transfer_client_never_reloads_from_background_status_polling(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = script.index('function refreshActiveTransfers')
        block = script[start:script.index('refreshActiveTransfers();', start)]
        self.assertNotIn('window.location.reload()', block)
        self.assertIn('getJson(url)', block)
        self.assertIn('activePollInFlight', block)

    def test_transfer_receive_resume_returns_download_protocol_urls(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        start = source.index('def transfer_receive_resume')
        block = source[start:source.index('def transfer_receive_chunk', start)]
        self.assertIn('"chunk_url_template"', block)
        self.assertIn('"complete_url"', block)
        self.assertIn('transfer_receive_chunk', block)
        self.assertIn('transfer_receive_complete', block)

    def test_transfer_receive_client_requires_resume_protocol_urls(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function receiveFileFromInfo')
        block = source[start:source.index('function receiveFile(filename', start)]
        self.assertIn('info.chunk_url_template', block)
        self.assertIn('info.complete_url', block)

    def test_transfer_client_resume_namespace_is_stable(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "static" / "paxalia" / "scripts" / "transfer-center.js").read_text(encoding="utf-8")
        self.assertIn("paxalia-transfer:resume:", source)
        self.assertNotRegex(source, r"paxalia-transfer:v[0-9]+:")


    def test_transfer_client_clears_resume_state_after_server_accepts_background_verification(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function completeUpload()')
        block = source[start:source.index('function next(i)', start)]
        self.assertIn("result.transfer.status === 'verifying' || result.transfer.status === 'completed'", block)
        self.assertIn("window.localStorage.removeItem(storageKey)", block)

    def test_transfer_client_keeps_background_send_verification_non_blocking(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function handleSendVerificationState')
        block = source[start:source.index('function uploadSendFile', start)]
        self.assertIn('Server SHA-256 verification is running in the background; Active transfers will update automatically.', block)
        self.assertIn('return Promise.resolve(transfer);', block)
        self.assertNotIn('attempts >= 80', block)
        self.assertNotIn('Server verification is still pending', source)

    def test_receive_verification_has_no_fixed_poll_timeout(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function waitForVerification()')
        block = source[start:source.index('function completeDownload()', start)]
        self.assertNotIn('attempts >= 80', block)
        self.assertIn('download remains locked until verification completes', block)

    def test_transfer_client_uses_truthful_background_verification_message(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        self.assertIn('Server SHA-256 verification is running in the background', source)
        self.assertNotIn('Paxalia is completing server-side verification', source)

    def test_transfer_client_normalizes_success_response_shape_after_send(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function sendFile')
        block = source[start:source.index('function activeTransferRow', start)]
        self.assertIn('uploadSendFile(file, info, feedback, chunkSize, storageKey).then(function(transfer)', block)
        self.assertIn('return {transfer: transfer};', block)

    def test_transfer_client_materializes_and_polls_active_rows_without_reload(self):
        package = Path(__file__).resolve().parent
        source = (package / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        template = (package / 'templates' / 'paxalia' / 'transfer_center.html').read_text(encoding='utf-8')
        self.assertIn('function upsertActiveTransfer', source)
        self.assertIn('function createActiveTransferRow', source)
        self.assertIn('function updateActiveTransferProgress', source)
        self.assertIn('window.setInterval(refreshActiveTransfers, 2000)', source)
        self.assertIn('var activePollInFlight = false', source)
        self.assertIn('data-transfer-row-template="send"', template)
        self.assertIn('data-transfer-row-template="receive"', template)
        self.assertIn('data-active-count', template)
        self.assertIn('data-active-empty', template)
        start = source.index('function refreshActiveTransfers')
        block = source[start:source.index('refreshActiveTransfers();', start)]
        self.assertNotIn('window.location.reload()', block)
        self.assertIn('upsertActiveTransfer(t)', block)

    def test_transfer_client_updates_send_feedback_when_background_verification_finishes(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function refreshActiveTransfers')
        block = source[start:source.index('refreshActiveTransfers();', start)]
        self.assertIn("t.status === 'completed' && t.direction === 'send'", block)
        self.assertIn('Transfer completed and verified successfully.', block)


    def test_transfer_center_exposes_only_fixed_exchange_path_for_operator_context(self):
        package = Path(__file__).resolve().parent
        source = (package / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        template = (package / 'templates' / 'paxalia' / 'transfer_center.html').read_text(encoding='utf-8')
        self.assertIn('exchange_root, exchange_parts = validate_transfer_exchange', source)
        self.assertIn('exchange_path_display = str(Path(exchange_root.path).joinpath(*exchange_parts))', source)
        self.assertIn('"exchange_path_display": exchange_path_display', source)
        self.assertIn('{{ exchange_path_display }}', template)
        self.assertIn('Server location', template)
        self.assertNotIn('server_relative_path', template)

    def test_transfer_center_ui_has_spacing_scrolling_and_pending_integrity(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parent / "templates" / "paxalia" / "transfer_center.html").read_text(encoding="utf-8")
        css = (Path(__file__).resolve().parent / "static" / "paxalia" / "styles" / "components" / "transfer-center.css").read_text(encoding="utf-8")
        self.assertIn("transfer-exchange-list", template)
        self.assertIn("transfer-selection-summary", template)
        self.assertIn(".transfer-exchange-list", css)
        self.assertIn("margin: 30px 0 36px", css)
        self.assertIn("margin-bottom: 28px", css)
        self.assertIn("overflow-y: auto", css)
        self.assertIn(".transfer-integrity--pending::before", css)
        self.assertNotRegex(template + css, r"--v[0-9]+")


    def test_dependencies_sidebar_icon_uses_valid_svg_path(self):
        base = (Path(__file__).resolve().parent / 'templates' / 'paxalia' / 'base.html').read_text(encoding='utf-8')
        marker = '{% trans "Dependencies" %}'
        start = base.index(marker)
        block = base[max(0, start - 1200):start + 200]
        self.assertIn('d="M14.5 14.5 21 21"', block)
        self.assertIn('stroke-linecap="round"', block)
        self.assertNotIn('a2 2 0 1 0 0 4 2 2 0 0 0-4Z', block)


    def test_transfer_client_retries_only_transient_failures(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        retry_start = source.index('function retryableError')
        retry_block = source[retry_start:source.index('function handleSendVerificationState', retry_start)]
        self.assertIn('status === 408', retry_block)
        self.assertIn('status === 429', retry_block)
        self.assertIn('status >= 500', retry_block)
        self.assertIn('!retryableError(err)', retry_block)


    def test_transfer_client_retry_backoff_is_budget_independent_and_bounded(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia/scripts/transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function retry(')
        block = source[start:source.index('function handleSendVerificationState', start)]
        self.assertIn('retryIndex', block)
        self.assertNotIn('5-count', block)
        self.assertIn('Math.min(attemptIndex, 8)', block)

    def test_transfer_client_clears_terminal_collision_resume_state(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        self.assertIn("errorCode === 'destination_exists' || errorCode === 'verification_failed'", source)
        self.assertIn("window.localStorage.removeItem(storageKey)", source)

    def test_transfer_client_surfaces_terminal_finalize_failures(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        self.assertIn('function transferFailureFromResult', source)
        self.assertIn('transfer.error_message', source)
        self.assertIn('function transferFailureFromResult', source)
        self.assertIn('removeResumeStateForTransfer(transferId);', source)
        self.assertNotIn("state === 'failed' ? 'completed'", source)

    def test_transfer_failure_code_is_stable_for_terminal_failures(self):
        from types import SimpleNamespace
        failed = SimpleNamespace(
            status="failed",
            error_message="A file with this name already exists in the transfer exchange.",
        )
        self.assertEqual(_transfer_model_error_code(failed), "destination_exists")

    def test_transfer_client_uses_no_body_for_empty_post_endpoints(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        upload_start = source.index('function uploadSendFile')
        upload_block = source[upload_start:source.index('function sendFile', upload_start)]
        receive_start = source.index('function receiveFileFromInfo')
        receive_block = source[receive_start:source.index('function receiveFile(filename', receive_start)]
        self.assertIn('function postNoBody(url)', source)
        self.assertIn('postNoBody(info.upload_complete_url)', upload_block)
        self.assertIn('postBinary(url);', receive_block)
        self.assertNotIn('new FormData())', upload_block)
        self.assertNotIn('postBinary(url, form)', receive_block)

    def test_transfer_client_resume_hash_does_not_reference_uninitialized_progress(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        start = source.index('function primeHash(')
        block = source[start:source.index('function completeUpload()', start)]
        self.assertNotIn('bytes_transferred: received', block)
        self.assertIn('Math.min((i + 1) * actualChunk, file.size)', block)

    def test_transfer_client_rebuilds_formdata_for_each_chunk_retry(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        send_start = source.index('function uploadSendFile')
        send_block = source[send_start:source.index('function sendFile', send_start)]
        self.assertIn('var form = new FormData();', send_block)
        self.assertIn("form.append('chunk_index', String(i));", send_block)
        self.assertIn("form.append('chunk', blob, file.name + '.part');", send_block)

    def test_browser_telemetry_defaults_are_production_safe(self):
        from pathlib import Path
        settings_source = (Path(__file__).resolve().parent / "settings.py").read_text(encoding="utf-8")
        telemetry_source = (Path(__file__).resolve().parent / "static/paxalia/scripts/browser-telemetry.js").read_text(encoding="utf-8")
        self.assertIn("'LOG_BROWSER_CAPTURE_RESOURCE_ERRORS': False", settings_source)
        self.assertIn("getAttribute('data-paxalia-telemetry-resource-errors') === '1'", telemetry_source)
        self.assertNotIn("!== '0'", telemetry_source)

    def test_browser_telemetry_collector_is_loaded_and_bounded(self):
        package = Path(__file__).resolve().parent
        base = (package / "templates/paxalia/base.html").read_text(encoding="utf-8")
        script = (package / "static/paxalia/scripts/browser-telemetry.js").read_text(encoding="utf-8")
        self.assertRegex(base, r"browser-telemetry\.js['\"]\s*%}\?v=5\.0\.0")
        self.assertIn("chart.umd.js' %}?v=5.0.0", base)
        self.assertIn("data-paxalia-telemetry-url", base)
        self.assertIn("data-paxalia-telemetry-max-events", base)
        self.assertIn("keepalive: true", script)
        self.assertIn("safePath", script)
        self.assertIn("maxEvents", script)
        self.assertNotIn("document.cookie", script)
        self.assertNotIn("console[method]", script)

    def test_production_templates_expose_a_paxalia_favicon_and_early_telemetry_hook(self):
        package = Path(__file__).resolve().parent
        for relative in ("templates/paxalia/base.html", "templates/paxalia/auth_base.html"):
            source = (package / relative).read_text(encoding="utf-8")
            self.assertIn('rel="icon"', source)
            body_index = source.index("<body")
            telemetry_index = source.index("browser-telemetry.js")
            self.assertGreater(telemetry_index, body_index)

    def test_transfer_client_preserves_completion_sequence(self):
        from pathlib import Path
        package = Path(__file__).resolve().parent
        script = (package / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        upload_start = script.index('function uploadSendFile')
        upload_block = script[upload_start:script.index('function sendFile', upload_start)]
        self.assertIn('postNoBody(info.upload_complete_url)', upload_block)
        self.assertNotIn('post(info.upload_complete_url, new FormData())', upload_block)
        self.assertIn('post(info.finalize_url, finalize)', upload_block)
        receive_start = script.index('function receiveFileFromInfo')
        receive_block = script[receive_start:script.index('function receiveFile(filename', receive_start)]
        self.assertIn('postBinary(url)', receive_block)
        self.assertNotIn('postBinary(url, form)', receive_block)
        self.assertIn('post(info.complete_url, complete)', receive_block)

    def test_transfer_client_preserves_http_status_for_error_handling(self):
        source = (Path(__file__).resolve().parent / 'static' / 'paxalia' / 'scripts' / 'transfer-center.js').read_text(encoding='utf-8')
        self.assertIn('err.status = r.status', source)
        self.assertIn('err.data = data', source)

    def test_transfer_serialization_exposes_retry_budget(self):
        source = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        self.assertIn('"max_retries": transfer.max_retries', source)

    def test_transfer_serialization_exposes_two_direction_neutral_sha256_values(self):
        source = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        for field in ("client_checksum", "server_checksum", "checksum_status"):
            self.assertIn(field, source)

    def test_transfer_serialization_does_not_expose_server_relative_path(self):
        source = (Path(__file__).resolve().parent / 'transfer_center' / 'views.py').read_text(encoding='utf-8')
        self.assertNotIn('"server_relative_path": transfer.server_relative_path', source)

    def test_server_files_view_permission_is_reconciled_from_operation_state(self):
        package = Path(__file__).resolve().parent
        migration_0023 = (package / 'migrations' / '0023_server_file_operations.py').read_text(encoding='utf-8')
        migration_0025 = (package / 'migrations' / '0025_reconcile_v500_model_state.py').read_text(encoding='utf-8')
        models_source = (package / 'models.py').read_text(encoding='utf-8')
        # 0023 is historical state and must remain intact; 0025 deliberately
        # reconciles its stale permission for already-migrated databases.
        self.assertIn('("view_server_files",', migration_0023)
        self.assertNotIn('("view_server_files",', migration_0025)
        self.assertIn('remove_legacy_server_files_view_permission', migration_0025)
        server_operation_source = (
            package / 'server_files' / 'models.py'
        ).read_text(encoding='utf-8')
        operation_model = server_operation_source[
            server_operation_source.index('class ServerFileOperation') :
        ]
        self.assertNotIn('("view_server_files",', operation_model)
        self.assertNotIn("('view_server_files',", operation_model)
    def test_operations_entrypoint_contains_the_regression_suite(self):
        from pathlib import Path
        module = (Path(__file__).resolve().parent / "test_operations.py").read_text(encoding="utf-8")
        for marker in ("class OperationsConfigurationTests", "class OperationsTransferServiceTests", "class IntegrationContractTests"):
            self.assertIn(marker, module)


    def test_0025_is_a_deliberate_model_state_reconciliation(self):
        source = (Path(__file__).resolve().parent / 'migrations' / '0025_reconcile_v500_model_state.py').read_text(encoding='utf-8')
        self.assertIn('preserve_current_permission_state_on_reverse', source)
        self.assertIn('AlterField', source)
        self.assertNotIn('AlterModelOptions(\n            name="serverfileoperation"', source)

    def test_transfer_admin_hides_raw_filesystem_paths_and_uses_section_permission(self):
        source = (Path(__file__).resolve().parent / 'admin.py').read_text(encoding='utf-8')
        self.assertIn("exclude = ('server_relative_path', 'staging_path')", source)
        self.assertIn("has_perm('paxalia.view_transfers')", source)

    def test_0024_does_not_recreate_preexisting_uptime_monitor_index(self):
        source = (Path(__file__).resolve().parent / 'migrations' / '0024_operations.py').read_text(encoding='utf-8')
        self.assertNotIn("AddIndex(model_name='uptimecheck', index=models.Index(fields=['monitor', 'checked_at'], name='paxalia_upt_monitor_d38f8e_idx'))", source)

    def test_dashboard_access_contains_dedicated_availability_permission(self):
        from django.contrib.auth.models import Permission
        permission = Permission.objects.get(codename='view_availability', content_type__app_label='paxalia')
        self.assertEqual(permission.content_type.model, 'dashboardaccess')

    def test_0026_declares_bot_path_management_permission(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "migrations" / "0026_bot_path_management.py").read_text(encoding="utf-8")
        self.assertIn('"manage_bot_paths"', source)
        self.assertIn('"Can manage Bot/Scanner path rules and cleanup"', source)

    def test_dashboard_access_contains_bot_path_management_permission(self):
        from django.contrib.auth.models import Permission
        permission = Permission.objects.get(codename='manage_bot_paths', content_type__app_label='paxalia')
        self.assertEqual(permission.content_type.model, 'dashboardaccess')

    def test_transfer_concurrency_lock_is_singleton_model(self):
        from .transfer_center.models import PaxaliaTransferLock
        self.assertEqual(PaxaliaTransferLock._meta.pk.name, 'id')
        self.assertTrue(PaxaliaTransferLock._meta.get_field('id').primary_key)


