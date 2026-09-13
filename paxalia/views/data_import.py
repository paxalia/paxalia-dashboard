# paxalia/views/data_import.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from ..data_import import import_daily_stats, parse_analytics_csv
from ..models import Site
from ..settings import get_config
from ..security_audit import log_action
from .utils import section_enabled, get_current_site


@staff_member_required
def data_import_page(request):
    if not section_enabled('data_import'):
        raise Http404

    result = None
    warnings = []

    if request.method == 'POST':
        upload = request.FILES.get('csv_file')
        source = request.POST.get('source', 'csv')
        overwrite = request.POST.get('overwrite') == 'on'
        site_id = request.POST.get('site') or None
        current_site = get_current_site(request)
        requested_site = Site.objects.filter(id=site_id).first() if site_id else None
        if current_site is not None and requested_site is not None and requested_site.pk != current_site.pk:
            requested_site = current_site
        site = requested_site if site_id else current_site

        if source not in {'ga', 'plausible', 'csv'}:
            messages.error(request, _('Invalid import source.'))
            source = None

        max_bytes = int(get_config().get('DATA_IMPORT_MAX_FILE_SIZE_MB', 100) or 0) * 1024 * 1024
        if upload and max_bytes and upload.size > max_bytes:
            messages.error(request, _('CSV file exceeds the maximum allowed size (%(mb)d MB).') % {'mb': max_bytes // (1024 * 1024)})
            upload = None

        if not upload:
            messages.error(request, _('Choose a CSV file to upload.'))
        else:
            try:
                text = upload.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                messages.error(request, _('Could not read that file as UTF-8 text — is it really a CSV export?'))
                text = None

            if text is not None:
                rows, warnings = parse_analytics_csv(text)
                if not rows:
                    messages.error(request, _('No usable rows found in that file — see the warnings below.'))
                else:
                    result = import_daily_stats(rows, site=site, source=source, overwrite=overwrite)
                    log_action(
                        request, 'data_import.csv_imported',
                        detail=f'source={source} site={site} created={result["created"]} '
                               f'updated={result["updated"]} skipped={result["skipped_existing"]}',
                    )
                    messages.success(
                        request,
                        _('Imported: %(created)d created, %(updated)d updated, %(skipped)d skipped (already had data).') % {
                            'created': result['created'], 'updated': result['updated'], 'skipped': result['skipped_existing'],
                        },
                    )

    context = {
        'active_page': 'data_import',
        'page_title': _('Data Import'),
        'page_subtitle': _('Import historical daily stats from a Google Analytics or Plausible CSV export'),
        'sites': Site.objects.all(),
        'result': result,
        'warnings': warnings,
    }
    return render(request, 'paxalia/data_import.html', context)

