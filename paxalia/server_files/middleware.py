"""Early request-size guard for Paxalia Server Files operations.

Install this middleware before Django's CSRF middleware so multipart bodies
are rejected from Content-Length before CSRF inspection parses request.POST.
"""
from __future__ import annotations

from django.http import HttpResponse
from django.utils.translation import gettext as _

from .exceptions import ServerFilesError
from .policy import is_enabled, limits


class ServerFilesRequestLimitMiddleware:
    """Reject unbounded Server Files POST bodies before form parsing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = str(getattr(request, "path_info", "") or "").rstrip("/")
        if request.method == "POST" and is_enabled():
            if path.endswith("/server-files/operation"):
                try:
                    maximum = limits()["upload_bytes"] + 1024 * 1024
                except ServerFilesError:
                    return self._no_store(HttpResponse(
                        _("Paxalia Server Files is not configured safely."), status=503
                    ))
                response = self._check_length(request, maximum)
                if response is not None:
                    return self._no_store(response)
            elif path.endswith("/server-files/reauth"):
                response = self._check_length(request, 8192)
                if response is not None:
                    return self._no_store(response)
        return self.get_response(request)

    @staticmethod
    def _check_length(request, maximum):
        raw_length = request.META.get("CONTENT_LENGTH")
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError, OverflowError):
            return HttpResponse(_("A bounded request length is required."), status=411)
        if content_length < 0:
            return HttpResponse(_("A bounded request length is required."), status=411)
        if content_length > maximum:
            return HttpResponse(_("The request exceeds the configured Server Files limit."), status=413)
        return None

    @staticmethod
    def _no_store(response):
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response
