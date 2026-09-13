# paxalia/views/chat_ops.py
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from paxalia.chat_ops import (
    format_snapshot_text,
    resolve_period,
    verify_discord_signature,
    verify_slack_signature,
)
from paxalia.reporting import compute_overview_snapshot
from paxalia.settings import get_config

logger = logging.getLogger('paxalia')


@csrf_exempt
@require_POST
def slack_command(request):
    """
    Slack slash-command endpoint — register this URL as your app's
    Request URL under Slash Commands. Not gated behind
    staff_member_required: Slack itself is the caller, authenticated
    by signature verification below, not by a Django session. See the
    README's "Slack/Discord App" section for setup.
    """
    signing_secret = get_config().get('SLACK_SIGNING_SECRET')
    if not signing_secret:
        logger.warning('chat_ops: Slack command received but SLACK_SIGNING_SECRET is not configured')
        return JsonResponse({'text': 'This Slack app is not configured on the server.'}, status=200)

    timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
    signature = request.headers.get('X-Slack-Signature', '')
    if not verify_slack_signature(request.body, timestamp, signature, signing_secret):
        logger.warning('chat_ops: rejected Slack command with invalid/missing signature')
        return JsonResponse({'error': 'invalid signature'}, status=401)

    text = request.POST.get('text', '')
    start_dt, end_dt, label = resolve_period(text)
    snapshot = compute_overview_snapshot(start_dt, end_dt, site=None)

    return JsonResponse({
        'response_type': 'in_channel',
        'text': format_snapshot_text(snapshot, label),
    })


@csrf_exempt
@require_POST
def discord_interaction(request):
    """
    Discord interactions endpoint — register this URL as your
    application's Interactions Endpoint URL. Discord requires every
    request (including the initial PING verification Discord sends
    when you save the URL) to pass Ed25519 signature verification, or
    Discord will refuse to save the endpoint at all.
    """
    public_key = get_config().get('DISCORD_PUBLIC_KEY')
    if not public_key:
        logger.warning('chat_ops: Discord interaction received but DISCORD_PUBLIC_KEY is not configured')
        return JsonResponse({'error': 'not configured'}, status=401)

    timestamp = request.headers.get('X-Signature-Timestamp', '')
    signature = request.headers.get('X-Signature-Ed25519', '')
    if not verify_discord_signature(request.body, timestamp, signature, public_key):
        logger.warning('chat_ops: rejected Discord interaction with invalid/missing signature')
        return JsonResponse({'error': 'invalid request signature'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid JSON'}, status=400)

    interaction_type = payload.get('type')

    if interaction_type == 1:  # PING — required for Discord to accept this URL
        return JsonResponse({'type': 1})

    if interaction_type == 2:  # APPLICATION_COMMAND
        options = {
            opt.get('name'): opt.get('value')
            for opt in (payload.get('data', {}).get('options') or [])
        }
        start_dt, end_dt, label = resolve_period(options.get('period'))
        snapshot = compute_overview_snapshot(start_dt, end_dt, site=None)
        return JsonResponse({
            'type': 4,
            'data': {'content': format_snapshot_text(snapshot, label)},
        })

    return JsonResponse({'error': f'unsupported interaction type {interaction_type}'}, status=400)
