from django.core.exceptions import PermissionDenied
from django.http import Http404


def require_staff(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_staff:
        raise PermissionDenied


def require_view(definition, request, obj=None):
    if not definition.model_admin.has_view_permission(request, obj):
        raise PermissionDenied


def require_add(definition, request):
    if not definition.model_admin.has_add_permission(request):
        raise PermissionDenied


def require_change(definition, request, obj=None):
    if not definition.model_admin.has_change_permission(request, obj):
        raise PermissionDenied


def require_delete(definition, request, obj=None):
    if not definition.model_admin.has_delete_permission(request, obj):
        raise PermissionDenied


def can_view(definition, request, obj=None):
    try:
        return bool(definition.model_admin.has_view_permission(request, obj))
    except Exception:
        return False


def can_change(definition, request, obj=None):
    try:
        return bool(definition.model_admin.has_change_permission(request, obj))
    except Exception:
        return False


def can_delete(definition, request, obj=None):
    try:
        return bool(definition.model_admin.has_delete_permission(request, obj))
    except Exception:
        return False


def safe_model_definition(registry, request, app_label, model_name):
    try:
        return registry.get(app_label, model_name, request=request)
    except PermissionDenied:
        raise
    except (LookupError, Http404) as exc:
        raise Http404("Model not found") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "PermissionDenied":
            raise PermissionDenied from exc
        raise Http404("Model not found") from exc
