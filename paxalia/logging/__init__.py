"""Paxalia Observability public API."""
import logging as _stdlib_logging


_LEVELS = {
    "DEBUG": _stdlib_logging.DEBUG,
    "INFO": _stdlib_logging.INFO,
    "WARNING": _stdlib_logging.WARNING,
    "WARN": _stdlib_logging.WARNING,
    "ERROR": _stdlib_logging.ERROR,
    "CRITICAL": _stdlib_logging.CRITICAL,
}


def log(message, *, level="INFO", category="", action="", metadata=None,
        source="Application", request=None, request_id=None,
        correlation_id=None, trace_id=None, exc_info=None):
    """Branded helper built on Python's standard logging system.

    It intentionally never raises to the caller.
    """
    try:
        level_no = _LEVELS.get(str(level).upper(), _stdlib_logging.INFO)
        logger = _stdlib_logging.getLogger("paxalia.application")
        extra = {
            "paxalia": {
                "source": source,
                "category": category,
                "action": action,
                "metadata": metadata or {},
                "request": request,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "trace_id": trace_id,
            }
        }
        logger.log(level_no, str(message), extra=extra, exc_info=exc_info)
    except Exception:
        # Public logging is best-effort by design.
        pass
