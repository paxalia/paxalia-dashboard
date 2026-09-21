"""Fail-fast but safe Paxalia Logs smoke test with concrete diagnostics."""
from __future__ import annotations

import logging
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from paxalia import log as paxalia_log
from paxalia.logging.handler import configure_logging, get_last_handler_diagnostic
from paxalia.logging.services import (
    build_from_log_record,
    get_last_persistence_error,
    persist_event,
)
from paxalia.models import PaxaliaLogEvent, PaxaliaLogGroup


class Command(BaseCommand):
    help = "Create and verify canonical Paxalia Logs events, reporting the exact failing layer."

    def add_arguments(self, parser):
        parser.add_argument("--keep", action="store_true", help="Keep self-test rows in PostgreSQL.")

    def handle(self, *args, **options):
        if not configure_logging():
            raise CommandError(
                "Paxalia standard logging capture is disabled: "
                "LOGGING_ENABLED or LOG_CAPTURE_STANDARD_LOGGING is false."
            )

        if not hasattr(connection, "vendor"):
            raise CommandError("Django database connection is unavailable.")

        required_tables = {
            PaxaliaLogGroup._meta.db_table,
            PaxaliaLogEvent._meta.db_table,
        }
        existing_tables = set(connection.introspection.table_names())
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            raise CommandError(
                "Paxalia Logs database tables are missing: " + ", ".join(missing_tables)
            )

        marker = uuid.uuid4().hex[:12]
        messages = [
            f"Paxalia logging self-test (stdlib) [{marker}]",
            f"Paxalia logging self-test (helper) [{marker}]",
        ]
        created_ids = []

        try:
            logger = logging.getLogger("paxalia.selftest")
            logger.error(messages[0])
            paxalia_log(
                messages[1],
                level="ERROR",
                category="system.self_test",
                action="helper_test",
            )

            rows = list(
                PaxaliaLogEvent.objects.filter(message__in=messages)
                .values("id", "message", "source", "severity", "category", "action")
            )
            found = {row["message"]: row for row in rows}
            created_ids.extend(str(row["id"]) for row in rows)

            missing = [message for message in messages if message not in found]
            if missing:
                handler_state = get_last_handler_diagnostic()
                persistence_state = get_last_persistence_error()
                raise CommandError(
                    "Paxalia Logs self-test failed. Missing: "
                    + ", ".join(missing)
                    + f"\nHandler diagnostic: {handler_state!r}"
                    + f"\nPersistence diagnostic: {persistence_state!r}"
                )

            # Exercise the canonical service directly as an independent third path.
            record = logging.LogRecord(
                name="paxalia.selftest.direct",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg=f"Paxalia logging self-test (direct persistence) [{marker}]",
                args=(),
                exc_info=None,
            )
            event = persist_event(build_from_log_record(record), raise_on_error=True)
            if event is None:
                raise CommandError(
                    "Direct persistence returned None. "
                    f"Persistence diagnostic: {get_last_persistence_error()!r}"
                )
            created_ids.append(str(event.id))

            self.stdout.write(
                self.style.SUCCESS(
                    f"PASS: Paxalia Logs canonical capture is working; marker={marker}; "
                    f"events={len(rows) + 1}."
                )
            )
            for row in rows:
                self.stdout.write(
                    f"  {row['severity']} {row['source']} "
                    f"{row['category']}:{row['action']} — {row['message']}"
                )
            self.stdout.write(
                f"  ERROR Application:system.self_test:direct_persistence — "
                f"Paxalia logging self-test (direct persistence) [{marker}]"
            )
        finally:
            if not options["keep"] and created_ids:
                touched_group_ids = list(
                    PaxaliaLogEvent.objects.filter(id__in=created_ids)
                    .exclude(group_id__isnull=True)
                    .values_list("group_id", flat=True)
                )
                PaxaliaLogEvent.objects.filter(id__in=created_ids).delete()
                if touched_group_ids:
                    PaxaliaLogGroup.objects.filter(
                        id__in=touched_group_ids, events__isnull=True
                    ).delete()
