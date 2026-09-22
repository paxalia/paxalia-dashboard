from dataclasses import dataclass


@dataclass(frozen=True)
class PaxaliaModelAdapter:
    """Thin reusable adapter around a registered Django ModelAdmin."""

    definition: object

    @property
    def model(self):
        return self.definition.model

    @property
    def model_admin(self):
        return self.definition.model_admin

    def queryset(self, request):
        return self.model_admin.get_queryset(request)

    def form_class(self, request, obj=None):
        return self.model_admin.get_form(request, obj=obj, change=obj is not None)

    def inline_instances(self, request, obj=None):
        return self.model_admin.get_inline_instances(request, obj)

    def actions(self, request):
        return self.model_admin.get_actions(request) or {}

    def changelist_formset(self, request, **kwargs):
        getter = getattr(self.model_admin, "get_changelist_formset", None)
        if getter is None:
            return None
        return getter(request, **kwargs)

    def deleted_objects(self, request, objects):
        getter = getattr(self.model_admin, "get_deleted_objects", None)
        if getter is None:
            return None
        return getter(objects, request)

    def construct_change_message(self, request, form, formsets=None, change=False):
        getter = getattr(self.model_admin, "construct_change_message", None)
        if getter is None:
            return ""
        return getter(request, form, formsets or [], change)

    def permissions(self, request, obj=None):
        return self.definition.permission_map(request, obj=obj)

    def metadata(self, request, obj=None):
        return self.definition.metadata(request, obj=obj)
