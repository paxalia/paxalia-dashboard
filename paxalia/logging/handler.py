"""Standard-library logging integration for Paxalia."""
from __future__ import annotations

import logging
import sys
import threading
import time

from django.apps import apps as django_apps

from .services import build_from_log_record, get_last_persistence_error, persist_event


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


class PaxaliaLogHandler(logging.Handler):
    """Persist Python/Django LogRecords through the canonical Paxalia store."""

    _paxalia_handler = True
    _fallback_lock = threading.Lock()
    _last_fallback = 0.0

    def emit(self, record):
        diagnostic = {
            "handler_id": id(self),
            "record_name": str(getattr(record, "name", "")),
            "record_level": logging.getLevelName(getattr(record, "levelno", 0)),
            "entered": True,
            "captured": False,
            "skipped": None,
            "persisted": False,
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
            payload = build_from_log_record(record)
            diagnostic["payload_built"] = bool(payload)
            if not payload:
                diagnostic["skipped"] = "empty_payload"
                _set_handler_diagnostic(**diagnostic)
                return

            event = persist_event(payload)
            if event is None:
                detail = get_last_persistence_error() or {}
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


def configure_logging():
    """Install Paxalia logging on root and Django's non-propagating logger boundaries."""
    try:
        from ..settings import get_config

        cfg = get_config()
        if not cfg.get("LOGGING_ENABLED", True) or not cfg.get("LOG_CAPTURE_STANDARD_LOGGING", True):
            return False

        level = getattr(logging, str(cfg.get("LOG_MIN_LEVEL", "INFO")).upper(), logging.INFO)
        handler = None

        def ensure(logger):
            nonlocal handler
            for existing in logger.handlers:
                if getattr(existing, "_paxalia_handler", False):
                    # Keep an already-installed handler usable even if the host
                    # logging configuration was re-applied after Paxalia startup.
                    existing.setLevel(level)
                    return existing
            if handler is None:
                handler = PaxaliaLogHandler(level=level)
            logger.addHandler(handler)
            return handler

        ensure(logging.getLogger())
        for name in (
            "django",
            "django.request",
            "django.server",
            "django.security",
            "paxalia",
        ):
            ensure(logging.getLogger(name))

        paxalia_application = logging.getLogger("paxalia.application")
        if paxalia_application.level == logging.NOTSET:
            paxalia_application.setLevel(level)
        return True
    except Exception:
        return False
