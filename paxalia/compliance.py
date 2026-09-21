# paxalia/compliance.py
"""
"Forget this visitor" — bulk deletion across every model that carries
a visitor's session_id or IP, for compliance/data-subject-request
purposes. Used by views/compliance.py.

Real deletion, not symbolic: AnalyticsSettings.anonymize_ip defaults
off (see Phase 0), so PageView/AnalyticsEvent.ip_hash normally holds a
raw IP address, not a hash — deleting by IP here actually removes
identifying data, it isn't just marking rows as "forgotten" while the
IP sits there.

KNOWN GAP: JSError has a session_id field but no IP field (see that
model's docstring, Phase 11) — it can only be purged by session_id,
not by IP. Documented here and in the README rather than silently
leaving JSError rows behind on an IP-based request.
"""
import hashlib

from .models import AnalyticsEvent, JSError, PageView, PaxaliaLogEvent


def forget_by_session(session_id):
    """Delete every row carrying this exact session_id. Returns
    {model_name: deleted_count}."""
    return {
        'PageView': PageView.objects.filter(session_id=session_id).delete()[0],
        'AnalyticsEvent': AnalyticsEvent.objects.filter(session_id=session_id).delete()[0],
        'JSError': JSError.objects.filter(session_id=session_id).delete()[0],
        'PaxaliaLogEvent': PaxaliaLogEvent.objects.filter(session_id=session_id).delete()[0],
    }


def forget_by_ip(ip_address):
    """
    Delete every row carrying this IP. Matches both the raw IP and its
    SHA-256 hash, since ip_hash holds whichever representation
    AnalyticsSettings.anonymize_ip was set to *at write time* — a
    deployment that toggled anonymize_ip partway through its history
    could have both forms stored for the same real visitor, and both
    need to go. JSError has no IP field, so it isn't included here —
    see this module's docstring.
    """
    hashed = hashlib.sha256(ip_address.encode()).hexdigest()
    return {
        'PageView': PageView.objects.filter(ip_hash__in=[ip_address, hashed]).delete()[0],
        'AnalyticsEvent': AnalyticsEvent.objects.filter(ip_hash__in=[ip_address, hashed]).delete()[0],
        'PaxaliaLogEvent': PaxaliaLogEvent.objects.filter(ip_address__in=[ip_address, hashed]).delete()[0],
    }
