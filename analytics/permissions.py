# analytics/permissions.py
"""
Granular per-section dashboard permissions, built on Django's standard
auth Permission model (via the DashboardAccess marker model in
models.py) rather than a parallel role system — so granting/revoking
access uses the Group and User "permissions" screens Django admin
already provides, nothing new to learn.

SCOPE (deliberate, not an oversight): applied to a chosen subset of
the most sensitive sections — Billing, Security Center, Backups,
Sites, and Server monitoring — rather than swept mechanically across
every dashboard view. Every other section (Overview, Pages, Traffic,
Events, Goals, etc.) stays staff-wide, gated only by
@staff_member_required as before. This matches how most teams
actually want access split: broad visibility into general traffic
analytics, narrower access to billing/security/infrastructure detail.
To restrict another view the same way, add its section codename to
DashboardAccess.Meta.permissions in models.py (migration required),
then decorate the view with @require_section_permission('that_codename').
"""
from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied


def require_section_permission(section_codename):
    """
    Stacks on top of @staff_member_required (still applied here, so a
    view decorated with only this still requires staff status first).
    Superusers always pass. A staff user additionally needs
    'analytics.view_<section_codename>', granted via Django's normal
    Group/User permission admin screens against the DashboardAccess
    model.
    """
    perm = f'analytics.view_{section_codename}'

    def decorator(view_func):
        @staff_member_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not (request.user.is_superuser or request.user.has_perm(perm)):
                raise PermissionDenied("You don't have access to this section.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
