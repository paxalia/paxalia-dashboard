"""
NEW FILE: analytics/views/uploads.py

Chunked, resumable file upload for the admin dashboard. Designed for
moving large build artifacts onto the server over HTTPS when other
transfer methods (SSH/rsync/raw HTTP) are unreliable on the admin's
network.

All settings (storage location, chunk size, max file size, and whether
this feature is enabled at all) come from the project's ZAYDANY_ANALYTICS
dict — see conf_uploads.py. If 'releases' is not listed in
SIDEBAR_SECTIONS, these endpoints still function (no harm in leaving
them reachable), but the dashboard page/nav link simply won't appear,
matching the same opt-in pattern used by the billing section.

Flow:
  1. POST /insights/releases/upload/init/      -> create session, get upload_id
  2. POST /insights/releases/upload/chunk/<id>/  (repeated, in order)
  3. POST /insights/releases/upload/complete/<id>/ -> verify + finalize
"""
import os

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from honeypot.decorators import honeypot_exempt

from ..models import FileUpload
from ..conf_uploads import (
    get_uploads_incoming_root,
    get_upload_chunk_size_bytes,
    get_upload_max_file_size_bytes,
)


def _get_temp_dir():
    """In-progress uploads live in a .tmp subfolder so partial/failed
    uploads are visually and physically separate from completed ones."""
    temp_dir = os.path.join(get_uploads_incoming_root(), '.tmp')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def _safe_filename(name):
    """Strip any path components — defence in depth against path
    traversal via a crafted original_filename."""
    return os.path.basename(name).replace('..', '')


# ── Init ─────────────────────────────────────────────────────────────────
@staff_member_required
@csrf_exempt
@honeypot_exempt
@require_POST
def upload_init(request):
    filename = _safe_filename(request.POST.get('filename', ''))
    total_size = request.POST.get('total_size')
    chunk_size = request.POST.get('chunk_size')

    if not filename or not total_size:
        return JsonResponse({'error': 'filename and total_size are required'}, status=400)

    try:
        total_size = int(total_size)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'total_size must be an integer'}, status=400)

    if total_size <= 0:
        return JsonResponse({'error': 'total_size must be positive'}, status=400)

    max_size = get_upload_max_file_size_bytes()
    if max_size is not None and total_size > max_size:
        return JsonResponse({
            'error': f'File exceeds maximum allowed size ({max_size // (1024*1024)} MB)'
        }, status=413)

    # Chunk size: client may suggest one, but the server's configured
    # default is authoritative if the client doesn't specify, ensuring
    # consistent chunking regardless of which client/widget version
    # is calling this endpoint.
    if chunk_size:
        try:
            chunk_size = int(chunk_size)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'chunk_size must be an integer'}, status=400)
    else:
        chunk_size = get_upload_chunk_size_bytes()

    if chunk_size <= 0:
        return JsonResponse({'error': 'chunk_size must be positive'}, status=400)

    total_chunks = (total_size + chunk_size - 1) // chunk_size  # ceil division

    upload = FileUpload.objects.create(
        uploaded_by=request.user,
        original_filename=filename,
        total_size=total_size,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        status='pending',
    )

    return JsonResponse({
        'upload_id': str(upload.id),
        'total_chunks': total_chunks,
        'chunk_size': chunk_size,
    })


# ── Chunk ────────────────────────────────────────────────────────────────
@staff_member_required
@csrf_exempt
@honeypot_exempt
@require_POST
def upload_chunk(request, upload_id):
    try:
        upload = FileUpload.objects.get(id=upload_id)
    except (FileUpload.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Upload session not found'}, status=404)

    if upload.status == 'completed':
        return JsonResponse({'error': 'Upload already completed'}, status=400)

    chunk_index = request.POST.get('chunk_index')
    chunk_file = request.FILES.get('chunk')

    if chunk_index is None or chunk_file is None:
        return JsonResponse({'error': 'chunk_index and chunk file are required'}, status=400)

    try:
        chunk_index = int(chunk_index)
    except ValueError:
        return JsonResponse({'error': 'chunk_index must be an integer'}, status=400)

    if chunk_index < 0 or chunk_index >= upload.total_chunks:
        return JsonResponse({'error': 'chunk_index out of range'}, status=400)

    temp_path = os.path.join(_get_temp_dir(), str(upload.id))

    # Chunks MUST arrive in order for this simple append-only approach to
    # work correctly. The client (upload-widget.js) is responsible for
    # sequential upload with retry-on-failure for the SAME chunk index —
    # it does not skip ahead.
    expected_index = upload.chunks_received
    if chunk_index != expected_index:
        return JsonResponse({
            'error': f'Expected chunk {expected_index}, got {chunk_index}. Chunks must arrive in order.'
        }, status=409)

    try:
        with open(temp_path, 'ab') as f:
            for piece in chunk_file.chunks():
                f.write(piece)
    except OSError as e:
        upload.status = 'failed'
        upload.error_message = f'Disk write error: {e}'
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
        return JsonResponse({'error': 'Failed to write chunk to disk'}, status=500)

    upload.bytes_received += chunk_file.size
    upload.chunks_received += 1
    upload.status = 'uploading'
    upload.save(update_fields=['bytes_received', 'chunks_received', 'status', 'updated_at'])

    return JsonResponse({
        'chunks_received': upload.chunks_received,
        'total_chunks': upload.total_chunks,
        'bytes_received': upload.bytes_received,
        'progress_percent': upload.progress_percent,
    })


# ── Complete ─────────────────────────────────────────────────────────────
@staff_member_required
@csrf_exempt
@honeypot_exempt
@require_POST
def upload_complete(request, upload_id):
    try:
        upload = FileUpload.objects.get(id=upload_id)
    except (FileUpload.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Upload session not found'}, status=404)

    if upload.status == 'completed':
        return JsonResponse({'storage_path': upload.storage_path, 'already_completed': True})

    if upload.chunks_received != upload.total_chunks:
        return JsonResponse({
            'error': f'Not all chunks received ({upload.chunks_received}/{upload.total_chunks})'
        }, status=400)

    temp_path = os.path.join(_get_temp_dir(), str(upload.id))

    if not os.path.exists(temp_path):
        upload.status = 'failed'
        upload.error_message = 'Temp file missing at completion time'
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
        return JsonResponse({'error': 'Temp file missing'}, status=500)

    actual_size = os.path.getsize(temp_path)
    if actual_size != upload.total_size:
        upload.status = 'failed'
        upload.error_message = f'Size mismatch: expected {upload.total_size}, got {actual_size}'
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
        return JsonResponse({'error': upload.error_message}, status=400)

    final_dir = get_uploads_incoming_root()
    final_name = f"{upload.id}_{upload.original_filename}"
    final_path = os.path.join(final_dir, final_name)

    try:
        os.rename(temp_path, final_path)
    except OSError as e:
        upload.status = 'failed'
        upload.error_message = f'Failed to move file to final location: {e}'
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
        return JsonResponse({'error': 'Failed to finalize upload'}, status=500)

    upload.status = 'completed'
    upload.storage_path = final_path
    upload.completed_at = timezone.now()
    upload.save(update_fields=['status', 'storage_path', 'completed_at', 'updated_at'])

    return JsonResponse({'storage_path': final_path, 'already_completed': False})


# ── List (for the dashboard page) ────────────────────────────────────────
@staff_member_required
def upload_list(request):
    uploads = FileUpload.objects.all()[:100]
    data = [
        {
            'id': str(u.id),
            'filename': u.original_filename,
            'status': u.status,
            'progress_percent': u.progress_percent,
            'total_size': u.total_size,
            'storage_path': u.storage_path,
            'created_at': u.created_at.isoformat(),
            'completed_at': u.completed_at.isoformat() if u.completed_at else None,
            'uploaded_by': u.uploaded_by.username if u.uploaded_by else None,
        }
        for u in uploads
    ]
    return JsonResponse({'uploads': data})


# ── Delete (cleanup) ──────────────────────────────────────────────────────
@staff_member_required
@csrf_exempt
@honeypot_exempt
@require_POST
def upload_delete(request, upload_id):
    try:
        upload = FileUpload.objects.get(id=upload_id)
    except (FileUpload.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Upload session not found'}, status=404)

    paths_to_try = [upload.storage_path, os.path.join(_get_temp_dir(), str(upload.id))]
    for path in paths_to_try:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    upload.delete()
    return JsonResponse({'deleted': True})