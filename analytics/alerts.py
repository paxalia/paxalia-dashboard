# analytics/alerts.py
"""
send_alert() is the single entry point for notifying admins of any
notable event — security-relevant (new-location login, brute-force,
backup downloaded) or otherwise (a traffic anomaly, a scheduled report
failure, anything else). It does three things, all best-effort — a
notification failure must never break the request/job that triggered
it:
  1. Stores a Notification row (see models.py), so it shows up in the
     in-dashboard notification center regardless of whether email or
     webhook delivery is configured or succeeds.
  2. Sends an email, if SECURITY_ALERT_EMAILS is configured.
  3. Posts to a webhook, if SECURITY_ALERT_WEBHOOK_URL is configured.

send_security_alert() is kept as a thin, byte-for-byte-compatible
wrapper around send_alert(category='security') — every existing call
site (signals.py, views/backup.py) is unchanged; the settings key
names (SECURITY_ALERT_EMAILS / SECURITY_ALERT_WEBHOOK_URL) are
likewise unchanged despite the alerts they gate no longer being
exclusively security-related, since renaming a public setting key
would be a breaking change for no functional benefit.

Wire-up is intentionally synchronous + minimal (stdlib urllib for the
webhook, Django's email backend for mail) to avoid adding a hard
dependency on this package. If you're sending a lot of alerts, wrap
calls to this function in your own Celery task / background job.
"""
import json
import logging
import urllib.request

from .settings import get_config

logger = logging.getLogger('analytics.security')

_WEBHOOK_TIMEOUT_SECONDS = 3


def send_alert(subject, message, category='general', site=None):
    config = get_config()
    _create_notification(subject, message, category, site)
    _send_email_alert(config, subject, message, category)
    _send_webhook_alert(config, subject, message, category)


def send_security_alert(subject, message, alert_type='general'):
    """Backward-compatible wrapper for security-specific call sites —
    unchanged behavior and signature, now also creates a Notification."""
    send_alert(subject, message, category='security')


def _create_notification(subject, message, category, site):
    try:
        from .models import Notification
        Notification.objects.create(site=site, category=category, subject=subject, message=message)
    except Exception:
        logger.exception('Failed to create in-dashboard notification: %s', subject)


def _send_email_alert(config, subject, message, category):
    recipients = config.get('SECURITY_ALERT_EMAILS') or []
    if not recipients:
        return
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=f'[{category.capitalize()}] {subject}',
            message=message,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=list(recipients),
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send alert email: %s', subject)


def _send_webhook_alert(config, subject, message, category):
    webhook_url = config.get('SECURITY_ALERT_WEBHOOK_URL')
    if not webhook_url:
        return
    try:
        # Slack/Discord-compatible incoming-webhook payload shape.
        # Field kept named `alert_type` (not `category`) for backward
        # compatibility with anything already parsing this payload.
        payload = json.dumps({
            'text': f'*[{category.capitalize()}] {subject}*\n{message}',
            'alert_type': category,
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
        logger.exception('Failed to send alert webhook: %s', subject)
