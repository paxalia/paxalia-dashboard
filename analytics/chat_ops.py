# analytics/chat_ops.py
"""
Slack/Discord slash-command app — the inbound counterpart to the
outbound incoming-webhook alerting alerts.py has supported since
v2.2.0 (send_alert() posts a message OUT to a webhook URL; this module
receives a command IN from Slack/Discord and responds with data).

Both platforms POST to an endpoint you register with them
(views/chat_ops.py) and require the request to be cryptographically
verified before you trust anything in it — this module holds that
verification plus the shared logic (date-range keyword resolution,
response text formatting) both platforms' views call into.

SLACK verification needs only hmac/hashlib from the standard library
(HMAC-SHA256 over the request body) — no new dependency.

DISCORD verification needs Ed25519 signature checking, which the
standard library doesn't provide. Hand-rolling Ed25519 would mean
implementing real cryptography from scratch, which this package won't
do — instead PyNaCl is an OPTIONAL, guarded import (the same pattern
as django-otp/weasyprint): if it isn't installed, Discord support is
simply unavailable (verify_discord_signature() returns False, and
views/chat_ops.py responds accordingly) while Slack support works with
zero new dependencies either way.

SCOPE: one command surface — "give me today/yesterday/this week/this
month's traffic" — reusing reporting.py's compute_overview_snapshot(),
the same computation already shared by the scheduled email/PDF report
and the public share-link view. Commands are answered against the
combined (site=None) traffic; there's no per-site argument in this
version. A fuller app (per-site selection, other metrics, actual slash
command registration automation) is a natural follow-up, not something
this phase tries to front-load.
"""
import hashlib
import hmac
import time
from datetime import datetime, timedelta

from django.utils import timezone

try:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey
    _NACL_AVAILABLE = True
except ImportError:
    _NACL_AVAILABLE = False

# Slack rejects (and so do we) a request whose timestamp is older than
# this many seconds — stops a captured request from being replayed.
_MAX_TIMESTAMP_AGE_SECONDS = 60 * 5


def verify_slack_signature(body, timestamp, signature, signing_secret):
    """
    HMAC-SHA256 per Slack's documented scheme: sign 'v0:{timestamp}:{body}'
    with the app's signing secret and compare to the 'v0=...' signature
    header using a constant-time comparison. Returns False (never
    raises) on a missing/malformed signature, an expired timestamp, or
    a mismatch.
    """
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        if abs(time.time() - float(timestamp)) > _MAX_TIMESTAMP_AGE_SECONDS:
            return False
    except ValueError:
        return False

    basestring = f'v0:{timestamp}:{body.decode("utf-8") if isinstance(body, bytes) else body}'
    computed = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'), basestring.encode('utf-8'), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def verify_discord_signature(body, timestamp, signature, public_key):
    """
    Ed25519 verification per Discord's documented scheme. Returns
    False (never raises) if PyNaCl isn't installed, any argument is
    missing, or verification fails for any reason — a malformed
    signature/public key should look exactly like a bad signature to
    the caller, not a 500 error.
    """
    if not _NACL_AVAILABLE or not public_key or not timestamp or not signature:
        return False
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        message = timestamp.encode('utf-8') + (body if isinstance(body, bytes) else body.encode('utf-8'))
        verify_key.verify(message, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


_PERIOD_KEYWORDS = {
    'today': 0,
    'yesterday': 1,
    'week': 6,
    'month': 29,
}


def resolve_period(keyword):
    """
    Returns (start_dt, end_dt, label) for a command keyword — defaults
    to 'today' for an empty or unrecognized keyword rather than
    rejecting the command outright, since "/analytics" with no
    argument is a very likely real usage.
    """
    keyword = (keyword or '').strip().lower() or 'today'
    if keyword not in _PERIOD_KEYWORDS:
        keyword = 'today'

    today = timezone.now().date()
    if keyword == 'yesterday':
        day = today - timedelta(days=1)
        start_date = end_date = day
    else:
        end_date = today
        start_date = today - timedelta(days=_PERIOD_KEYWORDS[keyword])

    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    return start_dt, end_dt, keyword


def format_snapshot_text(snapshot, label):
    """
    Plain-text summary usable as-is by both Slack (mrkdwn) and Discord
    (its own markdown) — deliberately not using either platform's
    richer formatting (Block Kit / embeds), since a single shared
    format that renders reasonably on both is worth more here than a
    prettier response on only one of them.
    """
    lines = [
        f"*Traffic — {label}* ({snapshot['start_date']} to {snapshot['end_date']})",
        f"Views: {snapshot['total_views']}  |  Unique visitors: {snapshot['unique_visitors']}",
    ]
    if snapshot['top_pages']:
        lines.append('Top pages:')
        for row in snapshot['top_pages'][:5]:
            lines.append(f"  {row['path']} — {row['count']}")
    if snapshot['top_referrers']:
        lines.append('Top referrers:')
        for row in snapshot['top_referrers'][:5]:
            lines.append(f"  {row['referrer']} — {row['count']}")
    return '\n'.join(lines)
