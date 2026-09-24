"""Production-safe Django error handlers for Paxalia Dashboard.

Root project URLconfs should assign::

    handler404 = "paxalia.error_handlers.paxalia_404"
    handler500 = "paxalia.error_handlers.paxalia_500"

The handlers render the packaged public-safe templates and never pass exception
objects, tracebacks, settings, or request internals into the template context.
"""
from __future__ import annotations

from django.shortcuts import render


def paxalia_404(request, exception=None):
    return render(request, "404.html", status=404)


def paxalia_500(request):
    return render(request, "500.html", status=500)


handler404 = paxalia_404
handler500 = paxalia_500
