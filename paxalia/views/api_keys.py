# paxalia/views/api_keys.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from paxalia.api_keys import generate_key
from paxalia.models import PaxaliaAPIKey
from paxalia.security_audit import log_action

from .utils import section_enabled, get_current_site, scoped_object_or_404


@staff_member_required
def api_keys_management(request):
    if not section_enabled('api_keys'):
        raise Http404

    current_site = get_current_site(request)
    new_key_plaintext = None  # only ever set right after creation, shown once

    if request.method == 'POST' and 'save_key' in request.POST:
        name = request.POST.get('name', '').strip()
        scope_ingest = request.POST.get('scope_ingest') == 'on'
        scope_read = request.POST.get('scope_read') == 'on'

        if not name or not (scope_ingest or scope_read):
            messages.error(request, _('Name is required, and at least one scope must be selected.'))
        else:
            full_key, key_prefix, key_hash = generate_key()
            PaxaliaAPIKey.objects.create(
                site=current_site, name=name, key_prefix=key_prefix, key_hash=key_hash,
                scope_ingest=scope_ingest, scope_read=scope_read, created_by=request.user,
            )
            log_action(request, 'api_key.created', detail=f'name={name} prefix={key_prefix}')
            new_key_plaintext = full_key
            messages.success(request, _('API key created — copy it now, it will not be shown again.'))

    keys = PaxaliaAPIKey.objects.select_related('site', 'created_by')
    if current_site is not None:
        keys = keys.filter(site=current_site)

    context = {
        'active_page': 'api_keys',
        'page_title': _('Paxalia API Keys'),
        'page_subtitle': _('Credentials for server-to-server event ingestion and the read API'),
        'keys': keys,
        'new_key_plaintext': new_key_plaintext,
        'show_search': False,
    }
    return render(request, 'paxalia/api_keys.html', context)


@staff_member_required
@require_POST
def api_key_revoke(request, key_id):
    if not section_enabled('api_keys'):
        raise Http404
    key = scoped_object_or_404(PaxaliaAPIKey, request, key_id)
    key.is_active = False
    key.save(update_fields=['is_active'])
    log_action(request, 'api_key.revoked', detail=f'name={key.name} prefix={key.key_prefix}')
    messages.success(request, _('API key revoked.'))
    return redirect('paxalia:api_keys')


@staff_member_required
@require_POST
def api_key_delete(request, key_id):
    if not section_enabled('api_keys'):
        raise Http404
    key = scoped_object_or_404(PaxaliaAPIKey, request, key_id)
    name, prefix = key.name, key.key_prefix
    key.delete()
    log_action(request, 'api_key.deleted', detail=f'name={name} prefix={prefix}')
    messages.success(request, _('API key deleted.'))
    return redirect('paxalia:api_keys')

