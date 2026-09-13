# paxalia/api_keys.py
"""
Generation and verification for Paxalia API keys — the credential used
by the server-to-server ingestion endpoint and the read API (see
paxalia/views/paxalia_api.py). Never used by the browser-facing
public event endpoint (analytics_event_api), which stays anonymous on
purpose: a secret key embedded in client-side JS isn't secret.
"""
import hashlib
import secrets

from django.utils import timezone

KEY_PREFIX = 'pxa_'
_PREFIX_DISPLAY_LEN = 16  # how much of the key is safe to show in the UI


def generate_key():
    """Returns (full_key, key_prefix, key_hash). full_key is shown to
    the person exactly once — only key_hash is ever persisted."""
    secret = secrets.token_urlsafe(32)
    full_key = f'{KEY_PREFIX}{secret}'
    key_prefix = full_key[:_PREFIX_DISPLAY_LEN]
    key_hash = hash_key(full_key)
    return full_key, key_prefix, key_hash


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def authenticate_request(request, required_scope):
    """
    Returns the PaxaliaAPIKey for a valid `Authorization: Bearer pxa_...`
    header with the required scope and is_active=True, or None.

    required_scope is 'ingest' or 'read'. Updates last_used_at
    best-effort (a failure there should never break the request it's
    piggybacking on).
    """
    from .models import PaxaliaAPIKey

    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None
    raw_key = auth_header[len('Bearer '):].strip()
    if not raw_key.startswith(KEY_PREFIX):
        return None

    try:
        api_key = PaxaliaAPIKey.objects.get(key_hash=hash_key(raw_key), is_active=True)
    except PaxaliaAPIKey.DoesNotExist:
        return None

    if required_scope == 'ingest' and not api_key.scope_ingest:
        return None
    if required_scope == 'read' and not api_key.scope_read:
        return None

    try:
        PaxaliaAPIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
    except Exception:
        pass

    return api_key
