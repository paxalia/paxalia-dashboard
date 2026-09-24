"""Standard-library logging integration for Paxalia.

The canonical store is deliberately asynchronous when the handler is invoked
from an ASGI event-loop thread. Logging must never add database latency to the
request that produced the log record.
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import queue
import sys
import threading
import time
from django.apps import apps as django_apps
from django.db import connections

from .services import build_from_log_record, get_last_persistence_error, persist_event
from .redaction import redact_text, strip_ansi


_NOISY_LOGGER_PREFIXES = (
    "daphne.",
    "twisted.",
    "autobahn.",
)

_NOISY_LOGGER_NAMES = {
    "django.db.backends",
}

_HANDLER_STATE = threading.local()


def get_last_handler_diagnostic():
    """Return details about the most recent record processed on this thread."""
    return dict(getattr(_HANDLER_STATE, "diagnostic", {}) or {})


def _set_handler_diagnostic(**values):
    _HANDLER_STATE.diagnostic = dict(values)


def _should_capture(record):
    """Return whether this LogRecord belongs in the canonical Paxalia store."""
    name = str(getattr(record, "name", "") or "").lower()

    if any(name.startswith(prefix) for prefix in _NOISY_LOGGER_PREFIXES):
        return False

    if name in _NOISY_LOGGER_NAMES:
        return False

    if name == "django.server" and record.levelno < logging.WARNING:
        return False

    return True


class PaxaliaLiveLogBuffer:
    """Process-local bounded stream of sanitized runtime log lines.

    This buffer is intentionally separate from PaxaliaLogEvent. It is for
    console-style diagnostics, not canonical persistence. A process restart
    starts a fresh buffer.
    """

    MAX_ENTRIES = 2000
    _lock = threading.RLock()
    _entries = __import__("collections").deque(maxlen=MAX_ENTRIES)
    _sequence = 0

    @classmethod
    def append(cls, record):
        if getattr(record, "_paxalia_live_buffered", False):
            return
        setattr(record, "_paxalia_live_buffered", True)
        try:
            message = record.getMessage()
        except Exception:
            try:
                message = str(getattr(record, "msg", ""))
            except Exception:
                message = ""
        message = redact_text(strip_ansi(message))[:4000]
        if not message:
            return
        level = str(logging.getLevelName(getattr(record, "levelno", logging.INFO))).upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            level = "INFO"
        logger_name = str(getattr(record, "name", "") or "")[:255]
        timestamp = float(getattr(record, "created", time.time()))
        with cls._lock:
            cls._sequence += 1
            cls._entries.append({
                "sequence": cls._sequence,
                "timestamp": timestamp,
                "level": level,
                "logger": logger_name,
                "message": message,
                "text": f"{level} {message}",
            })

    @classmethod
    def snapshot(cls, *, since=None, limit=MAX_ENTRIES):
        try:
            limit = max(1, min(cls.MAX_ENTRIES, int(limit)))
        except (TypeError, ValueError):
            limit = cls.MAX_ENTRIES
        try:
            since_value = None if since in (None, "") else int(since)
        except (TypeError, ValueError):
            since_value = None

        with cls._lock:
            entries = list(cls._entries)
            latest = cls._sequence
            oldest = entries[0]["sequence"] if entries else latest
            reset = bool(
                since_value is not None
                and entries
                and since_value < oldest - 1
            )
            if since_value is None or reset:
                selected = entries[-limit:]
            else:
                selected = [item for item in entries if item["sequence"] > since_value][-limit:]
            return {
                "entries": selected,
                "latest_sequence": latest,
                "oldest_sequence": oldest,
                "reset": reset,
                "limit": limit,
            }

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._entries.clear()


def get_live_log_buffer():
    return PaxaliaLiveLogBuffer


class PaxaliaLiveLogHandler(logging.Handler):
    """Capture emitted records into the bounded live console buffer only."""

    _paxalia_live_handler = True

    def __init__(self):
        super().__init__(level=logging.DEBUG)

    def emit(self, record):
        try:
            PaxaliaLiveLogBuffer.append(record)
        except Exception:
            # Live observability must never affect application logging.
            pass


class PaxaliaLogHandler(logging.Handler):
    """Persist Python/Django LogRecords through the canonical Paxalia store.

    ASGI request threads never wait for canonical persistence. A bounded
    single-worker queue provides backpressure so a logging storm cannot
    consume the whole PostgreSQL connection pool or the application's memory.
    Synchronous callers (including ordinary management commands and regression
    tests) still persist inline so their observable behavior remains stable.
    """

    _paxalia_handler = True
    _fallback_lock = threading.Lock()
    _last_fallback = 0.0
    _async_queue = queue.Queue(maxsize=128)
    _async_worker = None
    _async_worker_lock = threading.Lock()
    _ASYNC_QUEUE_MAXSIZE = 128

    @staticmethod
    def _in_async_context():
        try:
            return asyncio.get_running_loop().is_running()
        except RuntimeError:
            return False

    @staticmethod
    def _capture_record(record):
        payload = build_from_log_record(record)
        if not payload:
            return None, False, None
        event = persist_event(payload)
        return event, True, get_last_persistence_error()

    @classmethod
    def _ensure_async_worker(cls):
        with cls._async_worker_lock:
            worker = cls._async_worker
            if worker is not None and worker.is_alive():
                return
            worker = threading.Thread(
                target=cls._async_worker_loop,
                name="paxalia-log",
                daemon=True,
            )
            cls._async_worker = worker
            worker.start()

    @classmethod
    def _async_worker_loop(cls):
        while True:
            item = cls._async_queue.get()
            try:
                if item is None:
                    return
                handler, record = item
                try:
                    event, payload_built, persistence_detail = handler._capture_record(record)
                    if not payload_built:
                        continue
                    if event is None and record.levelno >= logging.WARNING:
                        detail = persistence_detail or get_last_persistence_error() or {}
                        if detail:
                            message = (
                                "Paxalia logging persistence failed "
                                f"({detail.get('stage', 'unknown')}): "
                                f"{detail.get('type', 'Exception')}: {detail.get('message', '')}"
                            )
                        else:
                            message = "Paxalia logging persistence failed or logging is disabled"
                        handler._fallback(message)
                except Exception as exc:  # noqa: BLE001 - logging must never be fatal
                    handler._fallback(f"Paxalia logging handler failed: {exc!r}")
            finally:
                try:
                    connections.close_all()
                except Exception:
                    pass
                cls._async_queue.task_done()

    @classmethod
    def flush_async(cls, timeout=5.0):
        """Wait briefly for queued records; return False if the deadline expires."""
        try:
            timeout = max(0.0, float(timeout))
        except (TypeError, ValueError):
            timeout = 5.0
        deadline = time.monotonic() + timeout
        while cls._async_queue.unfinished_tasks:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True

    @classmethod
    def shutdown_async_worker(cls, timeout=2.0):
        """Best-effort worker shutdown used during interpreter/process exit."""
        worker = cls._async_worker
        if worker is None or not worker.is_alive():
            return
        try:
            cls._async_queue.put_nowait(None)
        except queue.Full:
            return
        worker.join(max(0.0, float(timeout)))

    def emit(self, record):
        diagnostic = {
            "handler_id": id(self),
            "record_name": str(getattr(record, "name", "")),
            "record_level": logging.getLevelName(getattr(record, "levelno", 0)),
            "entered": True,
            "captured": False,
            "skipped": None,
            "persisted": False,
            "queued": False,
            "event_id": None,
        }
        _set_handler_diagnostic(**diagnostic)

        if not _should_capture(record):
            diagnostic["skipped"] = "filtered_logger"
            _set_handler_diagnostic(**diagnostic)
            return

        if not django_apps.ready:
            diagnostic["skipped"] = "django_apps_not_ready"
            _set_handler_diagnostic(**diagnostic)
            return

        if getattr(record, "_paxalia_canonical_captured", False):
            diagnostic["skipped"] = "record_already_captured"
            _set_handler_diagnostic(**diagnostic)
            return

        setattr(record, "_paxalia_canonical_captured", True)
        diagnostic["captured"] = True

        try:
            if self._in_async_context():
                self._ensure_async_worker()
                try:
                    self._async_queue.put_nowait((self, record))
                except queue.Full:
                    diagnostic["skipped"] = "async_queue_full"
                    self._fallback("Paxalia logging queue is full; the newest record was dropped")
                    _set_handler_diagnostic(**diagnostic)
                    return
                diagnostic["queued"] = True
                diagnostic["queue_size"] = self._async_queue.qsize()
                _set_handler_diagnostic(**diagnostic)
                return

            event, payload_built, persistence_detail = self._capture_record(record)
            diagnostic["payload_built"] = bool(payload_built)
            if not payload_built:
                diagnostic["skipped"] = "empty_payload"
                _set_handler_diagnostic(**diagnostic)
                return

            if event is None:
                detail = persistence_detail or get_last_persistence_error() or {}
                diagnostic.update({
                    "persistence_error": detail,
                    "persisted": False,
                })
                if record.levelno >= logging.WARNING:
                    if detail:
                        message = (
                            "Paxalia logging persistence failed "
                            f"({detail.get('stage', 'unknown')}): "
                            f"{detail.get('type', 'Exception')}: {detail.get('message', '')}"
                        )
                    else:
                        message = "Paxalia logging persistence failed or logging is disabled"
                    self._fallback(message)
            else:
                diagnostic["persisted"] = True
                diagnostic["event_id"] = str(getattr(event, "id", ""))
                detail = get_last_persistence_error()
                if detail:
                    diagnostic["nonfatal_persistence_note"] = detail
        except Exception as exc:  # noqa: BLE001 - logging must never be fatal
            diagnostic["handler_exception"] = {
                "type": exc.__class__.__name__,
                "message": str(exc) or repr(exc),
            }
            _set_handler_diagnostic(**diagnostic)
            self._fallback(f"Paxalia logging handler failed: {exc!r}")
            return

        _set_handler_diagnostic(**diagnostic)

    @classmethod
    def _fallback(cls, message):
        now = time.monotonic()
        with cls._fallback_lock:
            if now - cls._last_fallback < 1:
                return
            cls._last_fallback = now
            try:
                sys.stderr.write(message + "\n")
            except Exception:
                pass


def _shutdown_logging_worker():
    try:
        PaxaliaLogHandler.shutdown_async_worker(timeout=2.0)
    except Exception:
        pass


atexit.register(_shutdown_logging_worker)


def configure_logging():
    """Install canonical Paxalia logging and the bounded live console stream."""
    try:
        from ..settings import get_config

        cfg = get_config()
        if not cfg.get("LOGGING_ENABLED", True) or not cfg.get("LOG_CAPTURE_STANDARD_LOGGING", True):
            return False

        level = getattr(logging, str(cfg.get("LOG_MIN_LEVEL", "INFO")).upper(), logging.INFO)
        handler = None
        live_handler = None

        def ensure(logger):
            nonlocal handler
            for existing in logger.handlers:
                if getattr(existing, "_paxalia_handler", False):
                    existing.setLevel(level)
                    return existing
            if handler is None:
                handler = PaxaliaLogHandler(level=level)
            logger.addHandler(handler)
            return handler

        def ensure_live(logger):
            nonlocal live_handler
            for existing in logger.handlers:
                if getattr(existing, "_paxalia_live_handler", False):
                    existing.setLevel(logging.DEBUG)
                    return existing
            if live_handler is None:
                live_handler = PaxaliaLiveLogHandler()
            logger.addHandler(live_handler)
            return live_handler

        target_loggers = (
            "django",
            "django.request",
            "django.server",
            "django.security",
            "paxalia",
            "daphne",
            "twisted",
            "autobahn",
            "channels",
            "channels.server",
            "channels.http",
        )

        ensure(logging.getLogger())
        ensure_live(logging.getLogger())
        for name in target_loggers:
            logger = logging.getLogger(name)
            ensure(logger)
            ensure_live(logger)

        paxalia_application = logging.getLogger("paxalia.application")
        if paxalia_application.level == logging.NOTSET:
            paxalia_application.setLevel(level)
        return True
    except Exception:
        return False
