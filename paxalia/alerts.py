"""Unified, best-effort Paxalia administrator alert delivery."""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.request

from django.core.cache import cache

from .settings import get_config

logger = logging.getLogger('paxalia.security')
_WEBHOOK_TIMEOUT_SECONDS = 3


def _safe_int(value, default, minimum=0, maximum=86400):
    try:
        value = int(value)
    except (TypeError, ValueError, OverflowError):
        value = default
    return max(minimum, min(maximum, value))


def _dedupe_cache_key(category, subject, site, dedupe_key):
    site_id = getattr(site, 'pk', '') if site is not None else ''
    material = f"{category}\0{site_id}\0{dedupe_key or subject}".encode('utf-8', 'replace')
    return 'paxalia:alert-dedupe:' + hashlib.sha256(material).hexdigest()


def _should_send(config, category, subject, site, dedupe_key, cooldown_seconds):
    if not config.get('ALERT_DEDUPLICATION_ENABLED', True) or not dedupe_key:
        return True
    cooldown = _safe_int(
        cooldown_seconds if cooldown_seconds is not None else config.get('ALERT_DEFAULT_COOLDOWN_SECONDS', 300),
        300,
        minimum=1,
        maximum=86400,
    )
    try:
        return bool(cache.add(_dedupe_cache_key(category, subject, site, dedupe_key), '1', timeout=cooldown))
    except Exception:
        logger.error('Alert deduplication cache unavailable; delivering alert without suppression.')
        return True


def send_alert(subject, message, category='general', site=None, dedupe_key=None, cooldown_seconds=None):
    """Deliver one administrator alert without ever breaking its caller.

    Notification rows and external delivery are best-effort. Optional cache
    deduplication prevents repeated background workers from producing a
    notification storm for the same logical event.
    """
    config = get_config()
    subject = str(subject or '')[:255]
    message = str(message or '')[:12000]
    category = str(category or 'general')[:20]
    if not _should_send(config, category, subject, site, dedupe_key, cooldown_seconds):
        return False
    _create_notification(subject, message, category, site)
    _send_email_alert(config, subject, message, category)
    _send_webhook_alert(config, subject, message, category)
    return True


def send_security_alert(subject, message, alert_type='general'):
    """Backward-compatible security alert entry point."""
    send_alert(
        subject,
        message,
        category='security',
        dedupe_key=f'security:{str(alert_type or "general")}:{str(subject or "")}',
    )


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
            from_email=None,
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
        payload = json.dumps({
            'text': f'*[{category.capitalize()}] {subject}*\n{message}',
            'alert_type': category,
        }).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT_SECONDS)
    except Exception:
        logger.exception('Failed to send alert webhook: %s', subject)
