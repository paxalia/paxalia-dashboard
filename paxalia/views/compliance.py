# paxalia/views/compliance.py
import hashlib

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from paxalia.permissions import require_section_permission

from ..compliance import forget_by_ip, forget_by_session
from ..security_audit import log_action
from ..settings import get_config
from .utils import section_enabled


@require_section_permission('compliance')
def compliance_overview(request):
    if not section_enabled('compliance'):
        raise Http404

    if request.method == 'POST' and 'forget_visitor' in request.POST:
        identifier_type = request.POST.get('identifier_type', 'session')
        identifier = request.POST.get('identifier', '').strip()

        if not identifier:
            messages.error(request, _('Enter a session ID or IP address.'))
            return redirect('paxalia:compliance')

        if identifier_type == 'ip':
            results = forget_by_ip(identifier)
        else:
            results = forget_by_session(identifier)

        total = sum(results.values())
        # The audit log records that a deletion happened and how much
        # was deleted, but NOT the raw identifier that was requested to
        # be forgotten — logging the exact thing someone asked to have
        # forgotten, in plaintext, in a different table would defeat
        # the point. A short hash is kept only so an operator can
        # correlate a support request against this log entry.
        audit_ref = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        log_action(
            request, 'compliance.forget_visitor',
            detail=f'type={identifier_type} ref={audit_ref} total_deleted={total} breakdown={results}',
        )
        messages.success(
            request,
            _('Deleted %(total)d row(s) across %(tables)d table(s).') % {'total': total, 'tables': len(results)},
        )
        return redirect('paxalia:compliance')

    config = get_config()
    context = {
        'active_page': 'compliance',
        'page_title': _('Compliance'),
        'page_subtitle': _('Consent mode, data retention, and visitor deletion'),
        'consent_enabled': config['CONSENT_MODE_ENABLED'],
        'consent_cookie_name': config['CONSENT_COOKIE_NAME'],
        'consent_granted_value': config['CONSENT_COOKIE_GRANTED_VALUE'],
        'data_retention_days': config['DATA_RETENTION_DAYS'] or {},
        'security_log_retention_days': config.get('SECURITY_LOG_RETENTION_DAYS'),
        'server_metric_retention_days': config.get('SERVER_METRIC_RETENTION_DAYS'),
    }
    return render(request, 'paxalia/compliance.html', context)
