from dataclasses import dataclass

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.urls import NoReverseMatch, reverse
from django.utils.text import capfirst

from ..settings import get_config

DEFAULT_SENSITIVE_FIELDS = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "client_secret", "signing_secret", "api_key", "apikey",
    "private_key", "session_key", "csrf_token", "authorization", "cookie",
    "credential", "credentials", "secret_key", "encryption_key",
}


def _model_label(model):
    return f"{model._meta.app_label}.{model._meta.model_name}"


def _configured_models(key):
    values = get_config().get(key) or []
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _model_config(model):
    all_config = get_config().get("ADMIN_MODELS") or {}
    if not isinstance(all_config, dict):
        return {}
    label = _model_label(model).lower()
    for configured_label, value in all_config.items():
        if str(configured_label).lower() == label:
            return value if isinstance(value, dict) else {}
    return {}


def _option_list(model, key):
    value = _model_config(model).get(key) or ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(dict.fromkeys(str(item) for item in value if str(item)))


def is_model_hidden(model):
    label = _model_label(model).lower()
    if label in _configured_models("ADMIN_MODEL_DENYLIST"):
        return True
    return bool(_model_config(model).get("hidden", False))


def is_model_allowed(model):
    allowlist = _configured_models("ADMIN_MODEL_ALLOWLIST")
    return not allowlist or _model_label(model).lower() in allowlist


def sensitive_field_names(model):
    config = get_config()
    names = set(DEFAULT_SENSITIVE_FIELDS)
    configured = config.get("ADMIN_SENSITIVE_FIELDS") or []
    if isinstance(configured, str):
        configured = [configured]
    names.update(str(x).lower() for x in configured if str(x))
    names.update(str(x).lower() for x in _option_list(model, "sensitive_fields"))
    return names


def is_sensitive_field(field, model):
    name = str(getattr(field, "name", "")).lower()
    normalized = name.replace("_", "")
    names = sensitive_field_names(model)
    normalized_names = {x.replace("_", "") for x in names}
    return name in names or normalized in normalized_names


def configured_model_options(model):
    return _model_config(model)


def hidden_field_names(model):
    return set(_option_list(model, "hidden_fields"))


def display_field_names(model):
    values = _option_list(model, "display_fields")
    return set(values) if values else None


def has_localization_capability(model):
    """Detect common translation integrations without requiring one package."""
    if hasattr(model, "_parler_meta"):
        return True
    for field in model._meta.get_fields():
        if getattr(field, "name", "") == "translations":
            return True
    return False


@dataclass(frozen=True)
class PaxaliaModelCapabilities:
    view: bool
    add: bool
    change: bool
    delete: bool
    search: bool
    filters: bool
    actions: bool
    relationships: bool
    inlines: bool
    fieldsets: bool
    readonly_fields: bool
    ordering: bool
    list_editable: bool
    history: bool
    localization: bool
    import_export: bool
    protected: bool

    def as_dict(self):
        return {
            "view": self.view,
            "add": self.add,
            "change": self.change,
            "delete": self.delete,
            "search": self.search,
            "filters": self.filters,
            "actions": self.actions,
            "relationships": self.relationships,
            "inlines": self.inlines,
            "fieldsets": self.fieldsets,
            "readonly_fields": self.readonly_fields,
            "ordering": self.ordering,
            "list_editable": self.list_editable,
            "history": self.history,
            "localization": self.localization,
            "import_export": self.import_export,
            "protected": self.protected,
        }


@dataclass(frozen=True)
class PaxaliaModelDefinition:
    """Reusable description of one Django Admin-registered model."""

    model: object
    model_admin: object

    @property
    def app_label(self):
        return self.model._meta.app_label

    @property
    def model_name(self):
        return self.model._meta.model_name

    @property
    def label(self):
        return _model_label(self.model)

    @property
    def verbose_name(self):
        return capfirst(str(self.model._meta.verbose_name))

    @property
    def verbose_name_plural(self):
        return capfirst(str(self.model._meta.verbose_name_plural))

    @property
    def app_verbose_name(self):
        return capfirst(str(self.model._meta.app_config.verbose_name))

    @property
    def options(self):
        return configured_model_options(self.model)

    @property
    def localization_supported(self):
        return has_localization_capability(self.model)

    @property
    def sensitive_fields(self):
        return sensitive_field_names(self.model)

    @property
    def hidden_fields(self):
        return hidden_field_names(self.model)

    @property
    def display_fields(self):
        return display_field_names(self.model)

    @property
    def identity_fields(self):
        configured = _option_list(self.model, "identity_fields")
        if configured:
            return configured
        result = [self.model._meta.pk.name]
        for field in self.model._meta.fields:
            if field.name != self.model._meta.pk.name and getattr(field, "unique", False):
                result.append(field.name)
        return tuple(dict.fromkeys(result))

    @property
    def import_export_supported(self):
        # Every registered model has the generic Paxalia package surface.
        # Model-specific sensitivity/identity rules are still enforced by
        # the package engine and Django ModelAdmin permissions at execution.
        return True

    @property
    def protected(self):
        return bool(self.options.get("protected", False))

    @property
    def max_relation_items(self):
        default = get_config().get("ADMIN_MAX_RELATION_ITEMS", 10) or 10
        value = self.options.get("max_relation_items", default)
        try:
            return max(1, min(int(value), 100))
        except (TypeError, ValueError):
            return max(1, min(int(default), 100))

    def list_display(self, request):
        return tuple(self.model_admin.get_list_display(request) or ())

    def list_display_links(self, request):
        values = self.model_admin.get_list_display_links(request, list(self.list_display(request)))
        return tuple(values or ())

    def list_editable(self, request):
        """Return Django's changelist-editable fields.

        ``ModelAdmin.list_editable`` is a declarative attribute in supported
        Django releases; it is not a standard ``get_list_editable()`` hook.
        A third-party ModelAdmin may define such a method, so honor that
        extension when it exists, otherwise use the native attribute.
        """
        getter = getattr(self.model_admin, "get_list_editable", None)
        if callable(getter):
            return tuple(getter(request) or ())
        return tuple(getattr(self.model_admin, "list_editable", ()) or ())

    def list_filter(self, request):
        return tuple(self.model_admin.get_list_filter(request) or ())

    def search_fields(self, request):
        return tuple(self.model_admin.get_search_fields(request) or ())

    def ordering(self, request):
        return tuple(self.model_admin.get_ordering(request) or ())

    def date_hierarchy(self, request):
        return getattr(self.model_admin, "date_hierarchy", None)

    def fieldsets(self, request, obj=None):
        return tuple(self.model_admin.get_fieldsets(request, obj) or ())

    def readonly_fields_for(self, request, obj=None):
        configured = _option_list(self.model, "readonly_fields")
        try:
            registered = tuple(self.model_admin.get_readonly_fields(request, obj) or ())
        except Exception:
            registered = ()
        return tuple(dict.fromkeys((*registered, *configured)))

    def actions(self, request):
        return self.model_admin.get_actions(request) or {}

    def inline_instances(self, request, obj=None):
        return tuple(self.model_admin.get_inline_instances(request, obj) or ())

    def metadata(self, request, obj=None):
        """Return Django-native registry metadata for extension surfaces."""
        return {
            "model": self.model,
            "model_admin": self.model_admin,
            "app_label": self.app_label,
            "model_name": self.model_name,
            "label": self.label,
            "verbose_name": self.verbose_name,
            "verbose_name_plural": self.verbose_name_plural,
            "list_display": self.list_display(request),
            "list_display_links": self.list_display_links(request),
            "list_editable": self.list_editable(request),
            "list_filter": self.list_filter(request),
            "search_fields": self.search_fields(request),
            "ordering": self.ordering(request),
            "date_hierarchy": self.date_hierarchy(request),
            "fieldsets": self.fieldsets(request, obj),
            "readonly_fields": self.readonly_fields_for(request, obj),
            "actions": self.actions(request),
            "inlines": self.inline_instances(request, obj),
            "identity_fields": self.identity_fields,
            "hidden_fields": tuple(sorted(self.hidden_fields)),
            "display_fields": tuple(sorted(self.display_fields)) if self.display_fields else None,
            "sensitive_fields": tuple(sorted(self.sensitive_fields)),
            "protected": self.protected,
            "max_relation_items": self.max_relation_items,
            "options": self.options,
        }

    def url(self, name, **kwargs):
        return reverse(
            f"paxalia:{name}",
            kwargs={
                "app_label": self.app_label,
                "model_name": self.model_name,
                **kwargs,
            },
        )

    def permission_map(self, request, obj=None):
        return {
            "view": bool(self.model_admin.has_view_permission(request, obj)),
            "add": bool(self.model_admin.has_add_permission(request)),
            "change": bool(self.model_admin.has_change_permission(request, obj)),
            "delete": bool(self.model_admin.has_delete_permission(request, obj)),
        }

    def capabilities(self, request):
        perms = self.permission_map(request)
        try:
            list_filter = self.list_filter(request)
        except Exception:
            list_filter = ()
        try:
            search_fields = self.search_fields(request)
        except Exception:
            search_fields = ()
        try:
            actions = self.actions(request)
        except Exception:
            actions = {}
        relations = [field for field in self.model._meta.get_fields() if field.is_relation]
        try:
            inlines = self.inline_instances(request, None)
        except Exception:
            inlines = ()
        readonly_fields = self.readonly_fields_for(request, None)
        try:
            ordering = self.ordering(request)
        except Exception:
            ordering = ()
        try:
            fieldsets = self.fieldsets(request, None)
        except Exception:
            fieldsets = ()
        try:
            list_editable = self.list_editable(request)
        except Exception:
            list_editable = ()
        return PaxaliaModelCapabilities(
            view=perms["view"],
            add=perms["add"],
            change=perms["change"],
            delete=perms["delete"],
            search=bool(search_fields),
            filters=bool(list_filter),
            actions=bool(actions),
            relationships=bool(relations),
            inlines=bool(inlines),
            fieldsets=bool(fieldsets),
            readonly_fields=bool(readonly_fields),
            ordering=bool(ordering),
            list_editable=bool(list_editable) and bool(perms["change"]),
            history=True,
            localization=self.localization_supported,
            import_export=self.import_export_supported,
            protected=self.protected,
        )


class PaxaliaAdminRegistry:
    """Safe abstraction over Django's registered ModelAdmin registry."""

    def __init__(self, admin_site=None):
        self.admin_site = admin_site or admin.site

    def definitions(self, request=None):
        values = []
        for model, model_admin in self.admin_site._registry.items():
            if is_model_hidden(model) or not is_model_allowed(model):
                continue
            try:
                if request is not None and not model_admin.has_module_permission(request):
                    continue
            except Exception:
                continue
            values.append(PaxaliaModelDefinition(model, model_admin))
        values.sort(
            key=lambda item: (
                item.app_verbose_name.lower(),
                item.verbose_name_plural.lower(),
                item.model_name,
            )
        )
        return values

    def get(self, app_label, model_name, request=None):
        app_label = str(app_label).lower()
        model_name = str(model_name).lower()
        for definition in self.definitions(request=request):
            if definition.app_label == app_label and definition.model_name == model_name:
                return definition
        raise PermissionDenied("Paxalia Admin model is unavailable.")

    def app_groups(self, request=None):
        groups = {}
        for definition in self.definitions(request=request):
            groups.setdefault(definition.app_label, []).append(definition)
        return groups

    def app_group_cards(self, request=None):
        cards = []
        for app_label, definitions in self.app_groups(request=request).items():
            cards.append({
                "app_label": app_label,
                "app_verbose_name": definitions[0].app_verbose_name if definitions else app_label,
                "definitions": [
                    {
                        "definition": definition,
                        "capabilities": definition.capabilities(request),
                    }
                    for definition in definitions
                ],
            })
        return cards

    def is_registered(self, model):
        return model in self.admin_site._registry

    def validate_configuration(self):
        """Return non-fatal configuration diagnostics for the Admin registry."""
        issues = []
        config = get_config()

        for key in ("ADMIN_MODEL_ALLOWLIST", "ADMIN_MODEL_DENYLIST"):
            values = config.get(key) or []
            if not isinstance(values, (list, tuple, set)):
                issues.append({
                    "level": "error", "code": "invalid_config", "setting": key,
                    "message": f"{key} must be a list-like value.",
                })
                continue
            for value in values:
                label = str(value).lower()
                if "." not in label:
                    issues.append({
                        "level": "warning", "code": "invalid_model_label", "setting": key,
                        "message": f"Model label '{value}' should use app_label.model_name.",
                    })

        try:
            list_per_page = int(config.get("ADMIN_LIST_PER_PAGE", 50) or 50)
            if not 1 <= list_per_page <= 1000:
                raise ValueError
        except (TypeError, ValueError):
            issues.append({
                "level": "error", "code": "invalid_option", "setting": "ADMIN_LIST_PER_PAGE",
                "message": "ADMIN_LIST_PER_PAGE must be an integer between 1 and 1000.",
            })

        try:
            max_bulk = int(config.get("ADMIN_MAX_BULK_OPERATIONS", 500) or 500)
            if not 1 <= max_bulk <= 5000:
                raise ValueError
        except (TypeError, ValueError):
            issues.append({
                "level": "error", "code": "invalid_option", "setting": "ADMIN_MAX_BULK_OPERATIONS",
                "message": "ADMIN_MAX_BULK_OPERATIONS must be an integer between 1 and 5000.",
            })

        model_configs = config.get("ADMIN_MODELS") or {}
        if not isinstance(model_configs, dict):
            issues.append({
                "level": "error", "code": "invalid_config", "setting": "ADMIN_MODELS",
                "message": "ADMIN_MODELS must be a mapping keyed by app_label.model_name.",
            })
            return issues

        registered = {
            definition.label.lower(): definition.model
            for definition in self.definitions()
        }
        allowed_sequence = (
            "identity_fields", "sensitive_fields", "readonly_fields", "hidden_fields", "display_fields"
        )
        for label, options in model_configs.items():
            if not isinstance(options, dict):
                issues.append({
                    "level": "error", "code": "invalid_model_config", "setting": "ADMIN_MODELS",
                    "message": f"Configuration for '{label}' must be a mapping.",
                })
                continue
            normalized = str(label).lower()
            if normalized not in registered:
                issues.append({
                    "level": "warning", "code": "missing_model", "setting": "ADMIN_MODELS",
                    "message": f"Configured model '{label}' is not registered with Django Admin.",
                })
                continue
            model = registered[normalized]
            valid_names = {
                field.name
                for field in model._meta.get_fields()
                if getattr(field, "concrete", False) or getattr(field, "many_to_many", False)
            }
            for option_name in allowed_sequence:
                values = options.get(option_name) or []
                if isinstance(values, str):
                    values = [values]
                if not isinstance(values, (list, tuple, set)):
                    issues.append({
                        "level": "error", "code": "invalid_option",
                        "setting": f"ADMIN_MODELS.{label}.{option_name}",
                        "message": f"{option_name} must be a list-like value.",
                    })
                    continue
                for field_name in values:
                    if str(field_name) not in valid_names:
                        issues.append({
                            "level": "warning", "code": "missing_field",
                            "setting": f"ADMIN_MODELS.{label}.{option_name}",
                            "message": f"Field '{field_name}' does not exist on {label}.",
                        })
            identity = set(str(value) for value in (options.get("identity_fields") or []))
            sensitive = set(str(value) for value in (options.get("sensitive_fields") or []))
            if identity & sensitive:
                issues.append({
                    "level": "warning", "code": "sensitive_identity",
                    "setting": f"ADMIN_MODELS.{label}",
                    "message": f"Identity fields {sorted(identity & sensitive)!r} are also marked sensitive; values will stay masked.",
                })
            if "list_per_page" in options:
                try:
                    page_size = int(options["list_per_page"])
                    if not 1 <= page_size <= 1000:
                        raise ValueError
                except (TypeError, ValueError):
                    issues.append({
                        "level": "error", "code": "invalid_option",
                        "setting": f"ADMIN_MODELS.{label}.list_per_page",
                        "message": "list_per_page must be an integer between 1 and 1000.",
                    })
            if "max_relation_items" in options:
                try:
                    max_items = int(options["max_relation_items"])
                    if not 1 <= max_items <= 100:
                        raise ValueError
                except (TypeError, ValueError):
                    issues.append({
                        "level": "error", "code": "invalid_option",
                        "setting": f"ADMIN_MODELS.{label}.max_relation_items",
                        "message": "max_relation_items must be an integer between 1 and 100.",
                    })
            for boolean_key in ("hidden", "protected", "allow_duplicate"):
                if boolean_key in options and not isinstance(options[boolean_key], bool):
                    issues.append({
                        "level": "warning", "code": "invalid_option",
                        "setting": f"ADMIN_MODELS.{label}.{boolean_key}",
                        "message": f"{boolean_key} should be a boolean value.",
                    })

        return issues

    def django_admin_url(self):
        try:
            return reverse("admin:index")
        except NoReverseMatch:
            return None


registry = PaxaliaAdminRegistry()
