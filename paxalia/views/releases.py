"""Backward-compatible alias for the merged Transfer Center.

Release artifact movement is handled by Transfer Center now. The legacy URL
remains available only as a compatibility redirect for existing bookmarks.
"""
from django.shortcuts import redirect

from ..admin_security import admin_security_required


@admin_security_required
def releases_page(request):
    return redirect("paxalia:transfer_center")
