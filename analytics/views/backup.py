import os
import threading
import logging
from datetime import datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, Http404, HttpResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext as _
from django.core.management import call_command
from django.views.decorators.http import require_POST
from django.utils import timezone
from ..models import BackupConfiguration, BackupArchive
from ..security_audit import log_action

logger = logging.getLogger(__name__)
CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


@staff_member_required
def backup_management(request):
    """
    Single page that combines backup configuration and archive listing.
    """
    config = BackupConfiguration.objects.first()
    backups = BackupArchive.objects.all()[:50]

    # Handle POST for configuration update
    if request.method == 'POST' and 'save_config' in request.POST:
        data = {
            'backup_paths': request.POST.get('backup_paths', ''),
            'storage_path': request.POST.get('storage_path', ''),
            'enabled': request.POST.get('enabled') == 'on',
            'schedule': request.POST.get('schedule', 'manual'),
            'retention_count': int(request.POST.get('retention_count', 5)),
        }
        if config:
            for key, val in data.items():
                setattr(config, key, val)
            config.save()
        else:
            BackupConfiguration.objects.create(**data)
        log_action(request, 'backup.config_updated', detail=f'storage_path={data["storage_path"]}')
        messages.success(request, _('Backup settings saved.'))
        return redirect('analytics:backups')

    context = {
        'active_page': 'backups',
        'page_title': _('Backups'),
        'page_subtitle': _('Configure and manage server backups'),
        'config': config,
        'backups': backups,
        'schedule_choices': BackupConfiguration._meta.get_field('schedule').choices,
    }
    return render(request, 'analytics/backups.html', context)


@staff_member_required
@require_POST
def backup_trigger(request):
    """Manually trigger a backup in a background thread."""
    config = BackupConfiguration.objects.first()
    if not config or not config.enabled:
        messages.error(request, _('Backup is disabled or not configured.'))
        return redirect('analytics:backups')

    if not config.storage_path:
        messages.error(request, _('Storage path is not set.'))
        return redirect('analytics:backups')

    if not config.get_backup_paths_list():
        messages.error(request, _('No backup paths defined.'))
        return redirect('analytics:backups')

    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f'backup_{timestamp}.tar.gz'
    archive = BackupArchive.objects.create(
        filename=filename,
        storage_path=os.path.join(config.storage_path, filename),
        status='pending'
    )
    messages.info(request, _('Backup started in the background. Refresh to see progress.'))

    def run_backup():
        try:
            call_command('create_backup', archive_id=str(archive.id))
        except Exception as e:
            logger.exception("Background backup failed")
            archive.status = 'failed'
            archive.error_message = str(e)[:500]
            archive.save()

    thread = threading.Thread(target=run_backup)
    thread.daemon = True
    thread.start()

    log_action(request, 'backup.triggered', detail=f'archive_id={archive.id} filename={filename}')
    return redirect('analytics:backups')


@staff_member_required
def backup_download_init(request, backup_id):
    """Chunked download init – return total size and chunk count."""
    backup = get_object_or_404(BackupArchive, id=backup_id)
    if backup.status != 'completed':
        return JsonResponse({'error': 'Backup not ready'}, status=400)
    if not os.path.exists(backup.storage_path):
        return JsonResponse({'error': 'Backup file missing'}, status=404)

    size = os.path.getsize(backup.storage_path)
    total_chunks = (size + CHUNK_SIZE - 1) // CHUNK_SIZE
    return JsonResponse({
        'total_size': size,
        'total_chunks': total_chunks,
        'chunk_size': CHUNK_SIZE,
        'filename': backup.filename,
    })


@staff_member_required
def backup_download_chunk(request, backup_id, chunk_index):
    """Return a specific chunk of the backup file."""
    backup = get_object_or_404(BackupArchive, id=backup_id)
    if backup.status != 'completed':
        return HttpResponse('Backup not ready', status=400)
    if not os.path.exists(backup.storage_path):
        return HttpResponse('Backup file missing', status=404)

    size = os.path.getsize(backup.storage_path)
    total_chunks = (size + CHUNK_SIZE - 1) // CHUNK_SIZE
    if chunk_index < 0 or chunk_index >= total_chunks:
        return HttpResponse('Chunk out of range', status=400)

    start = chunk_index * CHUNK_SIZE
    end = min(start + CHUNK_SIZE, size)

    with open(backup.storage_path, 'rb') as f:
        f.seek(start)
        chunk_data = f.read(end - start)

    response = HttpResponse(chunk_data, content_type='application/octet-stream')
    response['Content-Range'] = f'bytes {start}-{end-1}/{size}'
    response['Content-Length'] = str(end - start)
    return response


@staff_member_required
def backup_download_single(request, backup_id):
    """Simple whole-file download for browsers."""
    backup = get_object_or_404(BackupArchive, id=backup_id)
    if backup.status != 'completed':
        raise Http404
    if not os.path.exists(backup.storage_path):
        raise Http404

    log_action(request, 'backup.downloaded', detail=f'archive_id={backup.id} filename={backup.filename}')
    response = FileResponse(open(backup.storage_path, 'rb'), as_attachment=True, filename=backup.filename)
    return response


@staff_member_required
@require_POST
def backup_delete(request, backup_id):
    backup = get_object_or_404(BackupArchive, id=backup_id)
    if os.path.exists(backup.storage_path):
        try:
            os.remove(backup.storage_path)
        except OSError:
            pass
    log_action(request, 'backup.deleted', detail=f'archive_id={backup.id} filename={backup.filename}')
    backup.delete()
    messages.success(request, _('Backup deleted.'))
    return redirect('analytics:backups')