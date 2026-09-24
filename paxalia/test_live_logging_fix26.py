from pathlib import Path
import logging
import unittest

ROOT = Path(__file__).resolve().parent


class LiveLoggingSourceContractTests(unittest.TestCase):
    def test_ansi_sequences_are_stripped(self):
        from .logging.redaction import strip_ansi

        self.assertEqual(strip_ansi("INFO hello\x1b[m"), "INFO hello")
        self.assertEqual(strip_ansi("\x1b[31mERROR\x1b[0m failed"), "ERROR failed")

    def test_live_buffer_is_bounded_to_2000(self):
        from .logging.handler import PaxaliaLiveLogBuffer

        PaxaliaLiveLogBuffer.clear()
        logger = logging.getLogger("paxalia.live-test")
        for idx in range(2100):
            record = logger.makeRecord(logger.name, logging.INFO, __file__, 1, "line %s", (idx,), None)
            PaxaliaLiveLogBuffer.append(record)
        payload = PaxaliaLiveLogBuffer.snapshot(limit=2000)
        self.assertEqual(len(payload["entries"]), 2000)
        self.assertEqual(payload["entries"][0]["message"], "line 100")
        self.assertEqual(payload["entries"][-1]["message"], "line 2099")
        PaxaliaLiveLogBuffer.clear()

    def test_live_buffer_supports_incremental_cursor(self):
        from .logging.handler import PaxaliaLiveLogBuffer

        PaxaliaLiveLogBuffer.clear()
        logger = logging.getLogger("paxalia.live-test")
        for idx in range(3):
            record = logger.makeRecord(logger.name, logging.DEBUG, __file__, 1, "DEBUG row %s", (idx,), None)
            PaxaliaLiveLogBuffer.append(record)
        first = PaxaliaLiveLogBuffer.snapshot(limit=2000)
        cursor = first["latest_sequence"]
        record = logger.makeRecord(logger.name, logging.DEBUG, __file__, 1, "DEBUG next", (), None)
        PaxaliaLiveLogBuffer.append(record)
        delta = PaxaliaLiveLogBuffer.snapshot(since=cursor, limit=2000)
        self.assertEqual(len(delta["entries"]), 1)
        self.assertEqual(delta["entries"][0]["message"], "DEBUG next")
        PaxaliaLiveLogBuffer.clear()

    def test_security_pages_have_distinct_active_keys(self):
        source = (ROOT / "views/admin_security.py").read_text(encoding="utf-8")
        expectations = {
            "security_overview": '"active_page": "security_overview"',
            "security_authentication": '"active_page": "security_authentication"',
            "admin_devices": '"active_page": "admin_devices"',
            "admin_sessions": '"active_page": "admin_sessions"',
        }
        for func, token in expectations.items():
            start = source.index(f"def {func}(request):")
            end = source.find("\n\n@", start)
            segment = source[start:end if end != -1 else None]
            self.assertIn(token, segment, func)

    def test_administration_uses_standard_group_geometry(self):
        source = (ROOT / "static/paxalia/styles/components/sidebar.css").read_text(encoding="utf-8")
        start = source.index('.sidebar-group--administration {')
        end = source.index('\n.sidebar-account {', start)
        segment = source[start:end]
        self.assertIn('padding: 0;', segment)
        self.assertIn('border: 0;', segment)
        self.assertIn('box-shadow: none;', segment)
        self.assertIn('margin: 0 0 4px 8px;', segment)

    def test_account_summary_tag_is_closed(self):
        source = (ROOT / "templates/paxalia/base.html").read_text(encoding="utf-8")
        self.assertIn('<summary class="sidebar-account__summary" data-sidebar-account-toggle>', source)


if __name__ == "__main__":
    unittest.main()
