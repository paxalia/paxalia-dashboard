"""Database-backed regression tests for Paxalia canonical logging."""
from __future__ import annotations

import logging
import uuid

from django.test import RequestFactory, TestCase

from paxalia import log as paxalia_log
from paxalia.logging.handler import PaxaliaLogHandler, configure_logging
from paxalia.logging.services import build_from_log_record, persist_event
from paxalia.models import PaxaliaLogEvent


class PaxaliaLoggingTests(TestCase):
    def test_direct_persistence_writes_event(self):
        marker = uuid.uuid4().hex
        record = logging.LogRecord(
            name="paxalia.test.direct",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=f"direct persistence {marker}",
            args=(),
            exc_info=None,
        )
        event = persist_event(build_from_log_record(record), raise_on_error=True)
        self.assertIsNotNone(event)
        self.assertEqual(event.request_id, "")
        self.assertEqual(event.correlation_id, "")
        self.assertEqual(event.trace_id, "")
        self.assertEqual(PaxaliaLogEvent.objects.filter(pk=event.pk).count(), 1)

    def test_handler_dispatch_writes_event(self):
        handler = PaxaliaLogHandler(level=logging.ERROR)
        marker = uuid.uuid4().hex
        message = f"handler dispatch {marker}"
        handler.handle(
            logging.LogRecord(
                name="paxalia.test.handler",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg=message,
                args=(),
                exc_info=None,
            )
        )
        self.assertTrue(PaxaliaLogEvent.objects.filter(message=message).exists())

    def test_stdlib_logger_dispatch_writes_event(self):
        configure_logging()
        marker = uuid.uuid4().hex
        message = f"stdlib logger dispatch {marker}"
        logging.getLogger("paxalia.test.stdlib").error(message)
        self.assertTrue(PaxaliaLogEvent.objects.filter(message=message).exists())

    def test_public_helper_dispatch_writes_event(self):
        configure_logging()
        marker = uuid.uuid4().hex
        message = f"helper dispatch {marker}"
        paxalia_log(message, level="ERROR", category="test", action="helper")
        self.assertTrue(PaxaliaLogEvent.objects.filter(message=message).exists())

