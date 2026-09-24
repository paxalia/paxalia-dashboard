"""
Chunked, resumable file upload for the admin dashboard.

Designed for moving large build artifacts onto the server over HTTPS when
other transfer methods (SSH/rsync/raw HTTP) are unreliable on the admin's
network.

All settings come from the project's PAXALIA_DASHBOARD dict — see
conf_uploads.py.

Flow:
  1. POST /insights/releases/upload/init/
  2. POST /insights/releases/upload/chunk/<id>/
  3. POST /insights/releases/upload/complete/<id>/
"""

import os

from ..admin_security import admin_security_preflight, admin_security_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from honeypot.decorators import honeypot_exempt

from ..models import FileUpload
from ..conf_uploads import (
    get_uploads_incoming_root,
    get_upload_chunk_size_bytes,
    get_upload_max_file_size_bytes,
    get_upload_blocked_extensions,
    get_upload_allowed_extensions,
)


def _get_temp_dir():
    """Return the temporary upload directory, creating it if necessary."""
    temp_dir = os.path.join(get_uploads_incoming_root(), '.tmp')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def _safe_filename(name):
    """Strip path components as defense in depth against path traversal."""
    return os.path.basename(name).replace('..', '')


def _extension_error(filename):
    """
    Return an error string if filename's extension is rejected, else
    None. Checked once at upload_init, before any bytes are written —
    see conf_uploads.py for the blocklist/allowlist config.
    """
    ext = os.path.splitext(filename)[1].lower()

    blocked = get_upload_blocked_extensions()
    if ext in blocked:
        return f'Files with extension "{ext}" are not allowed.'

    allowed = get_upload_allowed_extensions()
    if allowed is not None and ext not in allowed:
        return f'Extension "{ext}" is not in the allowed list for this deployment.'

    return None



def _upload_init_preflight(request, *args, **kwargs):
    """Validate upload-init inputs before the privileged gate runs.

    This preserves the API's established 400/413 validation contract while
    still requiring the completed Paxalia administrator session before any
    valid upload state is created.
    """
    if request.method != 'POST':
        return None

    filename = _safe_filename(request.POST.get('filename', ''))
    total_size = request.POST.get('total_size')
    chunk_size = request.POST.get('chunk_size')

    if not filename or not total_size:
        return JsonResponse({'error': 'filename and total_size are required'}, status=400)

    ext_error = _extension_error(filename)
    if ext_error:
        return JsonResponse({'error': ext_error}, status=400)

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

    if chunk_size:
        try:
            chunk_size = int(chunk_size)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'chunk_size must be an integer'}, status=400)
    else:
        chunk_size = get_upload_chunk_size_bytes()

    configured_chunk_size = get_upload_chunk_size_bytes()
    if chunk_size <= 0:
        return JsonResponse({'error': 'chunk_size must be positive'}, status=400)
    if chunk_size > configured_chunk_size:
        return JsonResponse({'error': 'chunk_size exceeds the configured maximum'}, status=413)

    return None



def _upload_chunk_preflight(request, upload_id, *args, **kwargs):
    """Return size errors before the privileged gate, without leaking access."""
    if request.method != 'POST' or not request.user.is_authenticated:
        return None

    upload = _get_owned_upload(request, upload_id)
    if upload is None:
        return None

    chunk_index_raw = request.POST.get('chunk_index')
    chunk_file = request.FILES.get('chunk')
    if chunk_index_raw is None or chunk_file is None:
        return None
    try:
        chunk_index = int(chunk_index_raw)
    except (TypeError, ValueError):
        return None
    if chunk_index < 0 or chunk_index >= upload.total_chunks:
        return None

    configured_chunk_size = get_upload_chunk_size_bytes()
    expected_size = (
        upload.chunk_size
        if chunk_index < upload.total_chunks - 1
        else upload.total_size - upload.chunk_size * (upload.total_chunks - 1)
    )
    if expected_size <= 0 or chunk_file.size != expected_size or chunk_file.size > configured_chunk_size:
        return JsonResponse({'error': 'Invalid chunk size'}, status=413)
    if upload.bytes_received + chunk_file.size > upload.total_size:
        return JsonResponse({'error': 'Chunk exceeds declared upload size'}, status=413)
    return None



def _get_owned_upload(request, upload_id, *, lock=False):
    """Return an upload session the current staff user may manage."""
    qs = FileUpload.objects.filter(id=upload_id)
    if not request.user.is_superuser:
        qs = qs.filter(uploaded_by=request.user)
    if lock:
        qs = qs.select_for_update()
    return qs.first()


def _public_upload(upload):
    """Serialize upload metadata without leaking a server filesystem path."""
    return {
        'id': str(upload.id),
        'filename': upload.original_filename,
        'status': upload.status,
        'progress_percent': upload.progress_percent,
        'total_size': upload.total_size,
        'created_at': upload.created_at.isoformat(),
        'completed_at': upload.completed_at.isoformat() if upload.completed_at else None,
        'uploaded_by': str(upload.uploaded_by) if upload.uploaded_by else None,
    }


@admin_security_required
@admin_security_preflight(_upload_init_preflight)
@honeypot_exempt
@require_POST
def upload_init(request):
    filename = _safe_filename(request.POST.get('filename', ''))
    total_size = request.POST.get('total_size')
    chunk_size = request.POST.get('chunk_size')

    if not filename or not total_size:
        return JsonResponse({'error': 'filename and total_size are required'}, status=400)

    ext_error = _extension_error(filename)
    if ext_error:
        return JsonResponse({'error': ext_error}, status=400)

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

    if chunk_size:
        try:
            chunk_size = int(chunk_size)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'chunk_size must be an integer'}, status=400)
    else:
        chunk_size = get_upload_chunk_size_bytes()

    configured_chunk_size = get_upload_chunk_size_bytes()
    if chunk_size <= 0:
        return JsonResponse({'error': 'chunk_size must be positive'}, status=400)
    if chunk_size > configured_chunk_size:
        return JsonResponse({'error': 'chunk_size exceeds the configured maximum'}, status=413)

    total_chunks = (total_size + chunk_size - 1) // chunk_size

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


@admin_security_required
@admin_security_preflight(_upload_chunk_preflight)
@honeypot_exempt
@require_POST
def upload_chunk(request, upload_id):
    upload = _get_owned_upload(request, upload_id)
    if upload is None:
        return JsonResponse({'error': 'Upload session not found'}, status=404)
    if upload.status == 'completed':
        return JsonResponse({'error': 'Upload already completed'}, status=400)
    if upload.status == 'failed':
        return JsonResponse({'error': 'Upload session has failed'}, status=409)

    chunk_index_raw = request.POST.get('chunk_index')
    chunk_file = request.FILES.get('chunk')
    if chunk_index_raw is None or chunk_file is None:
        return JsonResponse({'error': 'chunk_index and chunk file are required'}, status=400)
    try:
        chunk_index = int(chunk_index_raw)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'chunk_index must be an integer'}, status=400)
    if chunk_index < 0 or chunk_index >= upload.total_chunks:
        return JsonResponse({'error': 'chunk_index out of range'}, status=400)

    expected_index = upload.chunks_received
    if chunk_index != expected_index:
        return JsonResponse({
            'error': f'Expected chunk {expected_index}, got {chunk_index}. Chunks must arrive in order.'
        }, status=409)

    configured_chunk_size = get_upload_chunk_size_bytes()
    expected_size = (
        upload.chunk_size
        if chunk_index < upload.total_chunks - 1
        else upload.total_size - upload.chunk_size * (upload.total_chunks - 1)
    )
    if expected_size <= 0 or chunk_file.size != expected_size or chunk_file.size > configured_chunk_size:
        return JsonResponse({'error': 'Invalid chunk size'}, status=413)
    if upload.bytes_received + chunk_file.size > upload.total_size:
        return JsonResponse({'error': 'Chunk exceeds declared upload size'}, status=413)

    temp_path = os.path.join(_get_temp_dir(), str(upload.id))
    try:
        with transaction.atomic():
            locked = _get_owned_upload(request, upload_id, lock=True)
            if locked is None:
                return JsonResponse({'error': 'Upload session not found'}, status=404)
            if locked.status == 'completed':
                return JsonResponse({'error': 'Upload already completed'}, status=400)
            if locked.chunks_received != expected_index:
                return JsonResponse({'error': 'Upload state changed; retry this chunk'}, status=409)
            with open(temp_path, 'ab') as stream:
                for piece in chunk_file.chunks():
                    stream.write(piece)
            locked.bytes_received += chunk_file.size
            locked.chunks_received += 1
            locked.status = 'uploading'
            locked.save(update_fields=['bytes_received', 'chunks_received', 'status', 'updated_at'])
            upload = locked
    except OSError as exc:
        upload.status = 'failed'
        upload.error_message = f'Disk write error: {exc}'[:500]
        upload.save(update_fields=['status', 'error_message', 'updated_at'])
        return JsonResponse({'error': 'Failed to write chunk to disk'}, status=500)

    return JsonResponse({
        'chunks_received': upload.chunks_received,
        'total_chunks': upload.total_chunks,
        'bytes_received': upload.bytes_received,
        'progress_percent': upload.progress_percent,
    })


@admin_security_required
@honeypot_exempt
@require_POST
def upload_complete(request, upload_id):
    with transaction.atomic():
        upload = _get_owned_upload(request, upload_id, lock=True)
        if upload is None:
            return JsonResponse({'error': 'Upload session not found'}, status=404)
        if upload.status == 'completed':
            return JsonResponse({'upload': _public_upload(upload), 'already_completed': True})
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
        final_path = os.path.join(final_dir, f'{upload.id}_{upload.original_filename}')
        try:
            os.replace(temp_path, final_path)
        except OSError as exc:
            upload.status = 'failed'
            upload.error_message = f'Failed to move file to final location: {exc}'[:500]
            upload.save(update_fields=['status', 'error_message', 'updated_at'])
            return JsonResponse({'error': 'Failed to finalize upload'}, status=500)

        upload.status = 'completed'
        upload.storage_path = final_path
        upload.completed_at = timezone.now()
        upload.save(update_fields=['status', 'storage_path', 'completed_at', 'updated_at'])
        return JsonResponse({'upload': _public_upload(upload), 'already_completed': False})


@admin_security_required
def upload_list(request):
    uploads = FileUpload.objects.all() if request.user.is_superuser else FileUpload.objects.filter(uploaded_by=request.user)
    data = [_public_upload(u) for u in uploads[:100]]
    return JsonResponse({'uploads': data})


@admin_security_required
@honeypot_exempt
@require_POST
def upload_delete(request, upload_id):
    upload = _get_owned_upload(request, upload_id)
    if upload is None:
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
