"""Fine-grained Django permissions for Paxalia Server Files."""
from django.core.exceptions import PermissionDenied

from .policy import has_capability


def require_capability(user, codename: str):
    if not has_capability(user, codename):
        raise PermissionDenied("You do not have permission to perform this Server Files operation.")
