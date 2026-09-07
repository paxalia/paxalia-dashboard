# analytics/views/api_docs.py
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from .utils import section_enabled


@staff_member_required
def api_docs(request):
    if not section_enabled('api_keys'):
        raise Http404

    base_url = request.build_absolute_uri('/paxalia-api/v1/')

    context = {
        'active_page': 'api_docs',
        'page_title': _('Paxalia API Reference'),
        'page_subtitle': _('Server-to-server event ingestion and read access'),
        'base_url': base_url,
        'show_search': False,
    }
    return render(request, 'analytics/api_docs.html', context)
