# analytics/security_audit.py
"""
log_action() is the single entry point views should use to record an
admin action into SecurityAuditLog. Never raises — an audit-log failure
must never break the action being logged.

Usage:
    from analytics.security_audit import log_action
    log_action(request, 'backup.created', detail=f'archive={archive.filename}')
"""
import logging

from .middleware import AnalyticsMiddleware
from .models import SecurityAuditLog

logger = logging.getLogger('analytics.security')


def log_action(request, action, detail=''):
    try:
        user = getattr(request, 'user', None)
        ip = AnalyticsMiddleware._get_ip(request) if request is not None else None
        SecurityAuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action=action,
            detail=detail[:2000] if detail else '',
            ip_address=ip or None,
        )
    except Exception:
        logger.exception('Failed to write SecurityAuditLog entry for action=%s', action)
