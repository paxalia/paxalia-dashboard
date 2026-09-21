"""Request correlation and HTTP response/error observability."""
import logging
import time

from django.http import HttpResponse

from ..settings import get_config
from .context import reset_context, set_context
from .services import build_request_context, emit_message

_logger = logging.getLogger("paxalia.request")


class PaxaliaLoggingMiddleware:
    """Capture request context and configured HTTP failures.

    Add this after Django's authentication/session middleware and before the
    application middleware whose failures you want to observe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        token = None
        try:
            ctx = build_request_context(request)
            token = set_context(ctx)
            request.paxalia_request_id = ctx.get("request_id")
            request.paxalia_correlation_id = ctx.get("correlation_id")
            try:
                response = self.get_response(request)
            except Exception as exc:  # observe, then preserve Django exception behavior
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                emit_message(
                    "Unhandled Django request exception",
                    level="ERROR", source="HTTP", category="request", action="exception",
                    request=request, exception=exc, response_status=500,
                    duration_ms=duration_ms, request_id=ctx.get("request_id"),
                    correlation_id=ctx.get("correlation_id"),
                )
                raise
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            self._record_response(request, response, duration_ms)
            header_name = get_config().get("LOG_REQUEST_ID_RESPONSE_HEADER", "X-Paxalia-Request-ID")
            if header_name and isinstance(response, HttpResponse):
                try:
                    response[header_name] = str(ctx.get("request_id", ""))
                except Exception:
                    pass
            return response
        finally:
            if token is not None:
                try:
                    reset_context(token)
                except Exception:
                    pass

    def _record_response(self, request, response, duration_ms):
        cfg = get_config()
        status = int(getattr(response, "status_code", 200) or 200)
        should_log = status >= 400 or bool(cfg.get("LOG_REQUEST_SUCCESSES", False))
        if not should_log:
            return
        if status >= 500:
            level = "ERROR"
        elif status >= 400:
            level = "WARNING"
        else:
            level = "INFO"
        emit_message(
            f"HTTP {request.method} {request.path} -> {status}",
            level=level, source="HTTP", category="request", action="response",
            request=request, response_status=status, duration_ms=duration_ms,
            metadata={"status_class": f"{status // 100}xx"},
            request_id=getattr(request, "paxalia_request_id", None),
            correlation_id=getattr(request, "paxalia_correlation_id", None),
        )
