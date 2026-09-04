# analytics/alerts.py
"""
send_security_alert() is the single entry point for notifying admins of a
security-relevant event (new-location login, failed-login threshold hit,
backup downloaded, etc.). Delivery is best-effort — a notification
failure must never break the request that triggered it.

Wire-up is intentionally synchronous + minimal (stdlib urllib for the
webhook, Django's email backend for mail) to avoid adding a hard
dependency on this package. If you're sending a lot of alerts, wrap
calls to this function in your own Celery task / background job.
"""
import json
import logging
import urllib.request

from django.core.mail import send_mail

from .settings import get_config

logger = logging.getLogger('analytics.security')

_WEBHOOK_TIMEOUT_SECONDS = 3


def send_security_alert(subject, message, alert_type='general'):
    config = get_config()
    _send_email_alert(config, subject, message)
    _send_webhook_alert(config, subject, message, alert_type)


def _send_email_alert(config, subject, message):
    recipients = config.get('SECURITY_ALERT_EMAILS') or []
    if not recipients:
        return
    try:
        send_mail(
            subject=f'[Security] {subject}',
            message=message,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=list(recipients),
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send security alert email: %s', subject)


def _send_webhook_alert(config, subject, message, alert_type):
    webhook_url = config.get('SECURITY_ALERT_WEBHOOK_URL')
    if not webhook_url:
        return
    try:
        # Slack/Discord-compatible incoming-webhook payload shape.
        payload = json.dumps({
            'text': f'*[Security] {subject}*\n{message}',
            'alert_type': alert_type,
        }).encode('utf-8')
        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT_SECONDS)
    except Exception:
        # Deliberately broad: a misbehaving/unreachable webhook must
        # never surface as an error to the user whose action triggered it.
        logger.exception('Failed to send security alert webhook: %s', subject)
