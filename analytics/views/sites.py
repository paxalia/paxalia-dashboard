# analytics/views/sites.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..models import Site
from ..security_audit import log_action
from .utils import section_enabled


@staff_member_required
def sites_management(request):
    """Single page combining the site list and an add-site form, same
    pattern as backup_management() and security_center()."""
    if not section_enabled('sites'):
        raise Http404

    if request.method == 'POST' and 'save_site' in request.POST:
        name = request.POST.get('name', '').strip()
        domain = request.POST.get('domain', '').strip().lower()
        if not name or not domain:
            messages.error(request, _('Name and domain are required.'))
        else:
            site, created = Site.objects.get_or_create(
                domain=domain, defaults={'name': name}
            )
            if not created:
                site.name = name
                site.save(update_fields=['name'])
            log_action(
                request, 'site.created' if created else 'site.updated',
                detail=f'domain={domain} name={name}',
            )
            messages.success(request, _('Site saved.'))
        return redirect('analytics:sites')

    sites = Site.objects.all()
    context = {
        'active_page': 'sites',
        'page_title': _('Sites'),
        'page_subtitle': _('Manage the properties tracked by this dashboard'),
        'sites': sites,
    }
    return render(request, 'analytics/sites.html', context)


@staff_member_required
@require_POST
def site_toggle_active(request, site_id):
    site = get_object_or_404(Site, id=site_id)
    site.is_active = not site.is_active
    site.save(update_fields=['is_active'])
    log_action(request, 'site.toggled', detail=f'domain={site.domain} is_active={site.is_active}')
    messages.success(request, _('Site updated.'))
    return redirect('analytics:sites')


@staff_member_required
@require_POST
def site_delete(request, site_id):
    site = get_object_or_404(Site, id=site_id)
    domain = site.domain
    site.delete()
    log_action(request, 'site.deleted', detail=f'domain={domain}')
    messages.success(request, _('Site deleted. Historical data for it is kept but shown as unassigned.'))
    return redirect('analytics:sites')
