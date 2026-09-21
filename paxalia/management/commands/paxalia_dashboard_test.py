"""Comprehensive Paxalia Dashboard logging diagnostics.

This command intentionally avoids ``makemigrations``. The v4 development
branch uses the already-finalized migration chain and this command tests the
runtime logging pipeline against the existing database schema.
"""

from __future__ import annotations

import json
import logging
import traceback
import uuid
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import paxalia
from django.apps import apps
from django.core.management import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from paxalia import log as paxalia_log
from paxalia.logging.handler import (
    PaxaliaLogHandler,
    configure_logging,
    get_last_handler_diagnostic,
)
from paxalia.logging.services import (
    _base_payload,
    build_from_log_record,
    get_last_persistence_error,
    persist_event,
)
from paxalia.models import PaxaliaLogEvent, PaxaliaLogGroup, Site
from paxalia.settings import get_config


class _RollbackProbe(Exception):
    """Expected exception used to roll back the direct model probe."""


class _DiagnosticUser(SimpleNamespace):
    """Minimal Django-compatible authenticated staff user for view probes."""

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = True
    is_superuser = True
    pk = None
    username = "paxalia-diagnostic"

    def has_perm(self, _perm, obj=None):
        return True

    def has_perms(self, _perms, obj=None):
        return True

    def has_module_perms(self, _app_label):
        return True

    def get_username(self):
        return self.username


class Command(BaseCommand):
    help = "Run complete Paxalia logging, persistence, request, and dashboard diagnostics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Keep diagnostic rows in PostgreSQL.",
        )
        parser.add_argument(
            "--quiet-pass",
            action="store_true",
            help="Suppress successful checks.",
        )
        parser.add_argument(
            "--no-ui",
            action="store_true",
            help="Skip dashboard HTML and JSON feed visibility checks.",
        )

    def handle(self, *args, **options):
        keep = bool(options["keep"])
        quiet = bool(options["quiet_pass"])
        no_ui = bool(options["no_ui"])

        failures = 0
        warnings = 0
        created_ids: list[str] = []
        marker = uuid.uuid4().hex[:12]

        self.stdout.write(f"Paxalia Dashboard diagnostics: marker={marker}")

        def check(name, func, *, warn=False):
            nonlocal failures, warnings
            try:
                detail = func()
                if warn:
                    warnings += 1
                    prefix = "WARN"
                else:
                    prefix = "PASS"

                if not quiet or warn:
                    suffix = f": {detail}" if detail else ""
                    self.stdout.write(f"[{prefix}] {name}{suffix}")
                return detail
            except Exception as exc:  # noqa: BLE001
                failures += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"[FAIL] {name}: {exc.__class__.__name__}: {exc}"
                    )
                )
                self.stderr.write(traceback.format_exc())
                return None

        config = get_config()

        check("Installed Paxalia package", self._check_package)
        check("Django settings module", self._check_settings_module)
        check("Paxalia logging configuration", lambda: self._check_config(config))
        check("Django app registry", self._check_registry)
        check("Database connection", self._check_connection)
        check("Database transaction state", self._check_transaction_state)
        check("Paxalia observability tables", self._check_tables)
        check("Paxalia model/database columns", self._check_columns)
        check("Paxalia indexes and constraints", self._check_indexes)
        check("Paxalia migrations", self._check_migrations)
        check("Logging global gate", self._check_logging_global_gate)
        check("Logging handler topology", self._check_handlers)
        check(
            "Logger routing topology",
            lambda: self._check_logger_routing(config),
        )
        check("Handler levels and logger enablement", self._check_handler_levels)
        check("Direct model insert/read rollback", self._round_trip)

        direct_id = check(
            "Canonical persist_event() path",
            lambda: self._direct_persistence(marker),
        )
        if direct_id:
            created_ids.append(direct_id)

        handler_id = check(
            "Direct PaxaliaLogHandler.handle() dispatch",
            lambda: self._direct_handler_capture(marker),
        )
        if handler_id:
            created_ids.append(handler_id)

        stdlib_id = check(
            "Normal stdlib logger dispatch",
            lambda: self._stdlib_capture(marker),
        )
        if stdlib_id:
            created_ids.append(stdlib_id)

        helper_id = check(
            "paxalia.log() helper dispatch",
            lambda: self._helper_capture(marker),
        )
        if helper_id:
            created_ids.append(helper_id)

        request_log_id = check(
            "Django request logger dispatch",
            lambda: self._django_request_capture(marker),
        )
        if request_log_id:
            created_ids.append(request_log_id)

        security_id = check(
            "Paxalia security logger dispatch",
            lambda: self._security_logger_capture(marker),
        )
        if security_id:
            created_ids.append(security_id)

        middleware_id = check(
            "HTTP middleware error capture",
            lambda: self._middleware_probe(marker),
        )
        if middleware_id:
            created_ids.append(middleware_id)

        context_id = check(
            "Request-context/site resolution",
            lambda: self._request_context_probe(marker),
        )
        if context_id:
            created_ids.append(context_id)

        if not no_ui:
            check(
                "Paxalia Logs dashboard visibility",
                lambda: self._ui_visibility_probe(marker),
            )
            check(
                "Paxalia Logs feed visibility",
                lambda: self._feed_visibility_probe(marker),
            )

        check(
            "Current handler diagnostic state",
            self._handler_state_report,
            warn=True,
        )
        check(
            "Final persistence diagnostic state",
            self._persistence_state_report,
            warn=True,
        )

        if not keep:
            marker_events = PaxaliaLogEvent.objects.filter(
                message__icontains=marker,
            )
            marker_group_ids = set(
                marker_events
                .exclude(group_id__isnull=True)
                .values_list("group_id", flat=True)
            )
            marker_events.delete()

            if created_ids:
                PaxaliaLogEvent.objects.filter(id__in=created_ids).delete()

            if marker_group_ids:
                PaxaliaLogGroup.objects.filter(
                    id__in=marker_group_ids,
                    events__isnull=True,
                ).delete()
        elif created_ids:
            self.stdout.write(
                self.style.WARNING(
                    f"[INFO] Kept {len(created_ids)} diagnostic event rows."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Paxalia Dashboard diagnostics completed: "
                f"{failures} failures, {warnings} warnings."
            )
        )

        if failures:
            raise CommandError(
                "Paxalia Dashboard diagnostics found runtime failures. "
                "Read the [FAIL] sections above."
            )

    @staticmethod
    def _check_package():
        try:
            version = metadata.version("paxalia-dashboard")
        except Exception:
            version = "unknown"

        path = Path(getattr(paxalia, "__file__", "unknown")).resolve()
        return f"version={version} path={path}"

    @staticmethod
    def _check_settings_module():
        import os

        value = os.environ.get("DJANGO_SETTINGS_MODULE") or "<unset>"
        return f"DJANGO_SETTINGS_MODULE={value}"

    @staticmethod
    def _check_config(config):
        enabled = bool(config.get("LOGGING_ENABLED", True))
        capture = bool(config.get("LOG_CAPTURE_STANDARD_LOGGING", True))
        minimum = str(config.get("LOG_MIN_LEVEL", "INFO")).upper()

        if not enabled:
            raise RuntimeError("LOGGING_ENABLED is false")
        if not capture:
            raise RuntimeError("LOG_CAPTURE_STANDARD_LOGGING is false")

        return (
            f"enabled={enabled} capture={capture} min_level={minimum} "
            f"success_requests={bool(config.get('LOG_REQUEST_SUCCESSES', False))}"
        )

    @staticmethod
    def _check_registry():
        if not apps.ready:
            raise RuntimeError("Django app registry is not ready")
        return "ready=True"

    @staticmethod
    def _check_connection():
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            value = cursor.fetchone()[0]

        return (
            f"vendor={connection.vendor} "
            f"database={connection.settings_dict.get('NAME')} "
            f"probe={value}"
        )

    @staticmethod
    def _check_transaction_state():
        if connection.in_atomic_block:
            raise RuntimeError(
                "diagnostic began inside an existing atomic transaction"
            )
        if not connection.get_autocommit():
            raise RuntimeError("database autocommit is disabled")

        return "autocommit=True atomic_block=False"

    @staticmethod
    def _check_tables():
        names = set(connection.introspection.table_names())
        required = {
            PaxaliaLogGroup._meta.db_table,
            PaxaliaLogEvent._meta.db_table,
        }
        missing = sorted(required - names)

        if missing:
            raise RuntimeError("missing tables: " + ", ".join(missing))

        return ", ".join(sorted(required))

    @staticmethod
    def _check_columns():
        names = set(connection.introspection.table_names())
        missing = []

        for model in (PaxaliaLogGroup, PaxaliaLogEvent):
            table = model._meta.db_table
            if table not in names:
                missing.append(table)
                continue

            with connection.cursor() as cursor:
                actual = {
                    column.name
                    for column in connection.introspection.get_table_description(
                        cursor, table
                    )
                }

            expected = {
                field.column
                for field in model._meta.concrete_fields
            }

            missing.extend(
                f"{table}.{column}"
                for column in sorted(expected - actual)
            )

        if missing:
            raise RuntimeError(
                "missing database columns: " + ", ".join(missing)
            )

        return "concrete model columns match database schema"

    @staticmethod
    def _check_indexes():
        required = {
            PaxaliaLogGroup._meta.db_table: {
                index.name
                for index in PaxaliaLogGroup._meta.indexes
                if index.name
            },
            PaxaliaLogEvent._meta.db_table: {
                index.name
                for index in PaxaliaLogEvent._meta.indexes
                if index.name
            },
        }

        missing = []

        with connection.cursor() as cursor:
            for table, expected_names in required.items():
                constraints = connection.introspection.get_constraints(
                    cursor,
                    table,
                )
                actual = set(constraints)
                missing.extend(
                    f"{table}:{name}"
                    for name in sorted(expected_names - actual)
                )

        if missing:
            raise RuntimeError(
                "missing database indexes/constraints: "
                + ", ".join(missing)
            )

        return "declared Paxalia indexes present"

    @staticmethod
    def _check_migrations():
        executor = MigrationExecutor(connection)
        leaves = [
            node
            for node in executor.loader.graph.leaf_nodes()
            if node[0] == "paxalia"
        ]

        plan = executor.migration_plan(leaves)
        pending = [
            migration.name
            for migration, backwards in plan
            if not backwards
        ]

        if pending:
            raise RuntimeError(
                "pending Paxalia migrations: " + ", ".join(pending)
            )

        return "no pending Paxalia migrations"

    @staticmethod
    def _check_logging_global_gate():
        manager = logging.root.manager

        if manager.disable >= logging.ERROR:
            raise RuntimeError(
                "logging.disable blocks ERROR records: "
                f"manager.disable={manager.disable}"
            )

        return (
            f"manager.disable={manager.disable} "
            f"logging.raiseExceptions={logging.raiseExceptions}"
        )

    @staticmethod
    def _target_loggers():
        return (
            logging.getLogger(),
            logging.getLogger("paxalia"),
            logging.getLogger("paxalia.application"),
            logging.getLogger("paxalia.security"),
            logging.getLogger("paxalia.dashboard_test"),
            logging.getLogger("django"),
            logging.getLogger("django.request"),
            logging.getLogger("django.security"),
            logging.getLogger("django.server"),
        )

    @classmethod
    def _check_handlers(cls):
        configure_logging()

        details = []
        installed = []

        for logger in cls._target_loggers():
            found = [
                handler
                for handler in logger.handlers
                if getattr(handler, "_paxalia_handler", False)
            ]

            if found:
                installed.extend(found)
                details.append(
                    f"{logger.name or 'root'}="
                    f"{len(found)} Paxalia handler(s)"
                )

        if not installed:
            raise RuntimeError(
                "No PaxaliaLogHandler is installed on any diagnostic logger"
            )

        return "; ".join(details)

    @classmethod
    def _check_logger_routing(cls, config):
        configure_logging()

        errors = []
        details = []

        for logger in cls._target_loggers():
            effective = logger.getEffectiveLevel()

            details.append(
                f"{logger.name or 'root'}:"
                f"level={logging.getLevelName(logger.level)}/"
                f"effective={logging.getLevelName(effective)}/"
                f"enabled_error={logger.isEnabledFor(logging.ERROR)}/"
                f"disabled={logger.disabled}/"
                f"propagate={getattr(logger, 'propagate', False)}/"
                f"handlers={len(logger.handlers)}"
            )

            if not logger.isEnabledFor(logging.ERROR):
                errors.append(
                    f"{logger.name or 'root'} does not enable ERROR"
                )

        if errors:
            raise RuntimeError("; ".join(errors))

        configured_min = str(
            config.get("LOG_MIN_LEVEL", "INFO")
        ).upper()

        return (
            f"configured_min={configured_min}; "
            + " | ".join(details)
        )

    @classmethod
    def _check_handler_levels(cls):
        configure_logging()
        bad = []

        for logger in cls._target_loggers():
            for handler in logger.handlers:
                if not getattr(handler, "_paxalia_handler", False):
                    continue
                if handler.level > logging.ERROR:
                    bad.append(
                        f"{logger.name or 'root'}:"
                        f"{logging.getLevelName(handler.level)}"
                    )

        if bad:
            raise RuntimeError(
                "Paxalia handlers block ERROR: " + ", ".join(bad)
            )

        return "ERROR enabled at installed Paxalia handlers"

    @staticmethod
    def _round_trip():
        fingerprint = uuid.uuid4().hex * 2
        fingerprint = fingerprint[:64]
        now = timezone.now()

        try:
            with transaction.atomic():
                group = PaxaliaLogGroup.objects.create(
                    fingerprint=fingerprint,
                    severity="ERROR",
                    source="Application",
                    category="system.diagnostic",
                    exception_type="",
                    normalized_message="Paxalia direct model diagnostic",
                    first_seen=now,
                    last_seen=now,
                    occurrence_count=1,
                    suppressed_count=0,
                    window_started_at=now,
                    sample_count=0,
                )

                event = PaxaliaLogEvent.objects.create(
                    id=uuid.uuid4(),
                    severity="ERROR",
                    source="Application",
                    category="system.diagnostic",
                    action="direct_model_round_trip",
                    logger_name="paxalia.dashboard_test",
                    message="Paxalia direct model diagnostic",
                    fingerprint=fingerprint,
                    group_id=group.id,
                )

                if not PaxaliaLogEvent.objects.filter(
                    pk=event.pk
                ).exists():
                    raise RuntimeError(
                        "event row could not be read back"
                    )

                raise _RollbackProbe()

        except _RollbackProbe:
            return "insert/read succeeded; transaction rolled back"

    @staticmethod
    def _find_message(message):
        return (
            PaxaliaLogEvent.objects
            .filter(message=message)
            .order_by("-timestamp")
            .first()
        )

    @classmethod
    def _direct_persistence(cls, marker):
        record = logging.LogRecord(
            name="paxalia.dashboard_test.direct",
            level=logging.ERROR,
            pathname=__file__,
            lineno=0,
            msg=f"Paxalia dashboard direct persistence [{marker}]",
            args=(),
            exc_info=None,
        )

        event = persist_event(
            build_from_log_record(record),
            raise_on_error=True,
        )

        if event is None:
            detail = get_last_persistence_error() or {}
            raise RuntimeError(
                "persist_event returned None: "
                f"{detail.get('stage', 'unknown')} "
                f"{detail.get('type', 'unknown')}: "
                f"{detail.get('message', '')}"
            )

        return str(event.id)

    @classmethod
    def _direct_handler_capture(cls, marker):
        configure_logging()

        handler = next(
            (
                handler
                for logger in cls._target_loggers()
                for handler in logger.handlers
                if getattr(handler, "_paxalia_handler", False)
            ),
            None,
        )

        if handler is None:
            raise RuntimeError("No PaxaliaLogHandler is installed")

        message = f"Paxalia dashboard direct handler [{marker}]"
        record = logging.LogRecord(
            name="paxalia.dashboard_test.direct_handler",
            level=logging.ERROR,
            pathname=__file__,
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        handler.handle(record)

        row = cls._find_message(message)
        state = get_last_handler_diagnostic()

        if row is None:
            raise RuntimeError(
                "handler.handle() did not persist record; "
                f"handler_state={state}; "
                f"persistence={get_last_persistence_error()}"
            )

        return str(row.id)

    @classmethod
    def _stdlib_capture(cls, marker):
        configure_logging()

        message = f"Paxalia dashboard stdlib logger [{marker}]"
        logger = logging.getLogger("paxalia.dashboard_test")

        if not logger.isEnabledFor(logging.ERROR):
            raise RuntimeError(
                "paxalia.dashboard_test does not enable ERROR"
            )

        logger.error(message)

        row = cls._find_message(message)
        if row is None:
            raise RuntimeError(
                "logger.error() did not persist; "
                f"handler_state={get_last_handler_diagnostic()}; "
                f"persistence={get_last_persistence_error()}"
            )

        return str(row.id)

    @classmethod
    def _helper_capture(cls, marker):
        configure_logging()

        message = f"Paxalia dashboard helper [{marker}]"

        paxalia_log(
            message,
            level="ERROR",
            category="system.self_test",
            action="helper_test",
        )

        row = cls._find_message(message)

        if row is None:
            raise RuntimeError(
                "paxalia.log() did not persist; "
                f"handler_state={get_last_handler_diagnostic()}; "
                f"persistence={get_last_persistence_error()}"
            )

        return str(row.id)

    @classmethod
    def _django_request_capture(cls, marker):
        configure_logging()

        message = f"Paxalia dashboard django.request [{marker}]"
        logger = logging.getLogger("django.request")
        logger.error(message)

        row = cls._find_message(message)

        if row is None:
            raise RuntimeError(
                "django.request did not persist; "
                f"handler_state={get_last_handler_diagnostic()}; "
                f"persistence={get_last_persistence_error()}"
            )

        if row.source != "HTTP":
            raise RuntimeError(
                f"django.request stored source={row.source!r}, expected 'HTTP'"
            )

        return str(row.id)

    @classmethod
    def _security_logger_capture(cls, marker):
        configure_logging()

        message = f"Paxalia dashboard paxalia.security [{marker}]"
        logger = logging.getLogger("paxalia.security")
        logger.error(message)

        row = cls._find_message(message)

        if row is None:
            raise RuntimeError(
                "paxalia.security did not persist; "
                f"handler_state={get_last_handler_diagnostic()}; "
                f"persistence={get_last_persistence_error()}"
            )

        if row.source != "Authentication":
            raise RuntimeError(
                "paxalia.security stored unexpected source="
                f"{row.source!r}"
            )

        return str(row.id)

    @classmethod
    def _middleware_probe(cls, marker):
        from paxalia.logging.middleware import PaxaliaLoggingMiddleware

        path = f"/paxalia-diagnostic/{marker}/"

        def get_response(_request):
            return HttpResponse("diagnostic", status=404)

        request = RequestFactory().get(
            path,
            HTTP_HOST="testserver",
        )
        request.user = _DiagnosticUser()

        response = PaxaliaLoggingMiddleware(get_response)(request)

        if response.status_code != 404:
            raise RuntimeError(
                f"middleware returned {response.status_code}, expected 404"
            )

        row = (
            PaxaliaLogEvent.objects
            .filter(
                source="HTTP",
                category="request",
                action="response",
                request_path=path,
                response_status=404,
            )
            .order_by("-timestamp")
            .first()
        )

        if row is None:
            raise RuntimeError(
                "PaxaliaLoggingMiddleware produced 404 but no HTTP "
                "failure event was persisted; "
                f"persistence={get_last_persistence_error()}"
            )

        return str(row.id)

    @classmethod
    def _request_context_probe(cls, marker):
        active_site = (
            Site.objects
            .filter(is_active=True)
            .order_by("name")
            .first()
        )

        domain = getattr(active_site, "domain", None) or "testserver"

        request = RequestFactory().get(
            "/paxalia-diagnostic-context/",
            HTTP_HOST=domain,
        )
        request.user = _DiagnosticUser()

        payload = _base_payload(
            message=f"Paxalia dashboard site context [{marker}]",
            severity="ERROR",
            source="Application",
            category="system.diagnostic",
            action="request_context",
            logger_name="paxalia.dashboard_test",
            request=request,
        )

        expected_site_id = active_site.id if active_site else None

        if payload.get("site_id") != expected_site_id:
            raise RuntimeError(
                "site resolution mismatch: "
                f"expected={expected_site_id} "
                f"got={payload.get('site_id')}"
            )

        if not payload.get("request_id"):
            raise RuntimeError("request_id was not generated")

        if not payload.get("correlation_id"):
            raise RuntimeError("correlation_id was not generated")

        event = persist_event(payload, raise_on_error=True)

        if event is None:
            raise RuntimeError(
                "request-context event did not persist"
            )

        row = PaxaliaLogEvent.objects.get(pk=event.id)

        if row.site_id != expected_site_id:
            raise RuntimeError(
                "stored site_id mismatch: "
                f"expected={expected_site_id} "
                f"got={row.site_id}"
            )

        if not row.request_id:
            raise RuntimeError("stored request_id is empty")

        if not row.correlation_id:
            raise RuntimeError("stored correlation_id is empty")

        return str(row.id)

    @staticmethod
    def _ui_request(site=None):
        from django.contrib.sessions.middleware import SessionMiddleware
        from paxalia.views.logs import logs_overview, log_feed

        request = RequestFactory().get("/logs/")

        request.user = _DiagnosticUser()

        SessionMiddleware(
            lambda _request: HttpResponse()
        ).process_request(request)

        request.session.save()

        if site is not None:
            request.GET = request.GET.copy()
            request.GET["site"] = str(site.id)

        request.csp_nonce = "diagnostic"

        return request, logs_overview, log_feed

    @classmethod
    def _ui_visibility_probe(cls, marker):
        message = f"Paxalia dashboard UI visibility [{marker}]"

        active_site = (
            Site.objects
            .filter(is_active=True)
            .order_by("name")
            .first()
        )

        request, logs_view, _feed = cls._ui_request(active_site)

        payload = _base_payload(
            message=message,
            severity="ERROR",
            source="Application",
            category="system.diagnostic",
            action="ui_visibility",
            logger_name="paxalia.dashboard_test",
            request=request,
        )

        event = persist_event(payload, raise_on_error=True)

        if event is None:
            raise RuntimeError(
                "UI visibility event did not persist"
            )

        response = logs_view(request)

        if response.status_code != 200:
            raise RuntimeError(
                f"Paxalia Logs view returned HTTP {response.status_code}"
            )

        body = response.content.decode("utf-8", "replace")

        if message not in body:
            raise RuntimeError(
                "Paxalia Logs page returned 200 but did not render "
                "the diagnostic event"
            )

        return (
            "HTTP 200; diagnostic event rendered; "
            f"site={active_site or 'All Sites'}"
        )

    @classmethod
    def _feed_visibility_probe(cls, marker):
        message = f"Paxalia dashboard feed visibility [{marker}]"

        active_site = (
            Site.objects
            .filter(is_active=True)
            .order_by("name")
            .first()
        )

        request, _view, feed_view = cls._ui_request(active_site)

        payload = _base_payload(
            message=message,
            severity="ERROR",
            source="Application",
            category="system.diagnostic",
            action="feed_visibility",
            logger_name="paxalia.dashboard_test",
            request=request,
        )

        event = persist_event(payload, raise_on_error=True)

        if event is None:
            raise RuntimeError(
                "feed visibility event did not persist"
            )

        response = feed_view(request)

        if response.status_code != 200:
            raise RuntimeError(
                f"Paxalia Logs feed returned HTTP {response.status_code}"
            )

        body = response.content.decode("utf-8", "replace")

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Paxalia Logs feed returned invalid JSON: {exc}"
            ) from exc

        events = data.get("events", [])

        if not any(
            isinstance(row, dict)
            and row.get("message") == message
            for row in events
        ):
            raise RuntimeError(
                "Paxalia Logs feed returned 200 but omitted "
                "the diagnostic event"
            )

        return "HTTP 200; diagnostic event present in JSON feed"

    @staticmethod
    def _handler_state_report():
        state = get_last_handler_diagnostic()

        if not state:
            raise RuntimeError(
                "PaxaliaLogHandler has not processed any record"
            )

        if (
            state.get("captured")
            and not state.get("persisted")
            and not state.get("handler_exception")
        ):
            raise RuntimeError(
                f"handler processed but did not persist: {state}"
            )

        return str(state)

    @staticmethod
    def _persistence_state_report():
        state = get_last_persistence_error()

        if state:
            return str(state)

        return "no outstanding persistence error"


if __name__ == "__main__":
    Command()
