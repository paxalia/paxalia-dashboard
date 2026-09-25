# paxalia/views/api_docs.py
from ..admin_security import admin_security_required
from django.http import Http404
from django.urls import reverse
from django.shortcuts import render
from django.utils.translation import gettext as _

from .utils import section_enabled


@admin_security_required
def api_docs(request):
    if not section_enabled('api_keys'):
        raise Http404

    ingest_url = reverse('paxalia:paxalia_api_ingest')
    base_url = request.build_absolute_uri(ingest_url)
    base_url = base_url[:base_url.rfind('ingest/')]

    context = {
        'active_page': 'api_docs',
        'page_title': _('Paxalia API Reference'),
        'page_subtitle': _('Server-to-server event ingestion and read access'),
        'base_url': base_url,
        'show_search': False,
    }
    return render(request, 'paxalia/api_docs.html', context)
