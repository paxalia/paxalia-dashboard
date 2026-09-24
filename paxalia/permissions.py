# paxalia/permissions.py
"""
Granular per-section dashboard permissions, built on Django's standard
auth Permission model (via the DashboardAccess marker model in
models.py) rather than a parallel role system — so granting/revoking
access uses the Group and User "permissions" screens Django admin
already provides, nothing new to learn.

SCOPE: every privileged Paxalia Dashboard view is gated by
@admin_security_required, which enforces the completed three-layer administrator
session. The most sensitive sections additionally enforce the configured
Django model permissions below. This keeps authentication consistent across
navigation while still allowing narrower access to billing/security/
infrastructure detail.
To restrict another view the same way, add its section codename to
DashboardAccess.Meta.permissions in models.py (migration required),
then decorate the view with @require_section_permission('that_codename').
"""
from functools import wraps

from .admin_security import admin_security_required
from django.core.exceptions import PermissionDenied


def require_section_permission(section_codename):
    """
    Stacks on top of @admin_security_required (so a
    view decorated with only this still requires the completed three-layer
    Paxalia administrator session first).
    Superusers always pass. A staff user additionally needs
    'paxalia.view_<section_codename>', granted via Django's normal
    Group/User permission admin screens against the DashboardAccess
    model.
    """
    perm = f'paxalia.view_{section_codename}'

    def decorator(view_func):
        @admin_security_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not (request.user.is_superuser or request.user.has_perm(perm)):
                raise PermissionDenied("You don't have access to this section.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
