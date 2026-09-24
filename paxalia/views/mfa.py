"""Compatibility entry points for Paxalia mandatory administrator 2FA."""
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.shortcuts import redirect

from .auth import paxalia_2fa_setup


def mfa_enroll(request):
    return paxalia_2fa_setup(request)


@require_POST
def mfa_disable(request):
    # Layer 2 is mandatory for Paxalia Dashboard administration.  Retain the
    # old route so existing bookmarks fail closed instead of creating a dead URL.
    return HttpResponseForbidden("Paxalia Dashboard administrator 2FA cannot be disabled.")
