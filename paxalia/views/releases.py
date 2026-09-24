"""
NEW FILE: paxalia/views/releases.py

Mirrors the same opt-in pattern as the billing view: if 'releases' is
not present in ZAYDANY_ANALYTICS['SIDEBAR_SECTIONS'], this view returns
a 404 instead of rendering — "no errors, no broken pages" per the
billing precedent in the README.
"""
from ..admin_security import admin_security_required
from django.http import Http404
from django.shortcuts import render

from ..conf_uploads import is_releases_enabled, get_upload_chunk_size_bytes


@admin_security_required
def releases_page(request):
    if not is_releases_enabled():
        raise Http404("Releases section is not enabled. Add 'releases' to SIDEBAR_SECTIONS in ZAYDANY_ANALYTICS.")

    return render(request, 'paxalia/releases.html', {
        'upload_chunk_size': get_upload_chunk_size_bytes(),
        'active_page': 'releases',
    })