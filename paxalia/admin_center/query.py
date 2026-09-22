# Django's changelist ordering query parameter is the stable ``o`` key.
# Do not import ORDER_VAR from django.contrib.admin: Django 6.0 no longer
# re-exports that internal constant there.
ORDER_VAR = "o"
from django.contrib.admin.utils import label_for_field, lookup_field
from django.contrib.admin.views.main import ChangeList
from django.utils.html import conditional_escape

from .registry import is_sensitive_field, sensitive_field_names


def build_changelist(definition, request):
    model_admin = definition.model_admin
    ChangeListClass = model_admin.get_changelist(request)
    list_display = list(model_admin.get_list_display(request))
    list_display_links = model_admin.get_list_display_links(request, list_display)
    list_filter = model_admin.get_list_filter(request)
    date_hierarchy = model_admin.date_hierarchy
    search_fields = model_admin.get_search_fields(request)
    list_select_related = model_admin.get_list_select_related(request)
    configured_page_size = (definition.options or {}).get("list_per_page")
    list_per_page = model_admin.list_per_page
    if configured_page_size and model_admin.list_per_page == 100:
        try:
            list_per_page = max(1, min(int(configured_page_size), 1000))
        except (TypeError, ValueError):
            pass
    elif configured_page_size:
        try:
            list_per_page = max(1, min(int(configured_page_size), 1000))
        except (TypeError, ValueError):
            pass
    list_max_show_all = model_admin.list_max_show_all
    list_editable_getter = getattr(model_admin, "get_list_editable", None)
    if callable(list_editable_getter):
        list_editable = tuple(list_editable_getter(request) or ())
    else:
        list_editable = tuple(getattr(model_admin, "list_editable", ()) or ())
    sortable_by = (
        model_admin.get_sortable_by(request)
        if hasattr(model_admin, "get_sortable_by")
        else getattr(model_admin, "sortable_by", None)
    )
    search_help_text = getattr(model_admin, "search_help_text", None)

    args = [
        request,
        definition.model,
        list_display,
        list_display_links,
        list_filter,
        date_hierarchy,
        search_fields,
        list_select_related,
        list_per_page,
        list_max_show_all,
        list_editable,
        model_admin,
    ]
    try:
        return ChangeListClass(
            *args,
            sortable_by=sortable_by,
            search_help_text=search_help_text,
        )
    except TypeError:
        try:
            return ChangeListClass(*args, sortable_by=sortable_by)
        except TypeError:
            return ChangeListClass(*args)


def column_headers(change_list):
    headers = []
    sortable_by = getattr(change_list, "sortable_by", None)
    ordering_columns = {}
    try:
        ordering_columns = change_list.get_ordering_field_columns()
    except Exception:
        pass

    for idx, name in enumerate(change_list.list_display):
        field = None
        attr = getattr(change_list.model, name, None)
        try:
            field = change_list.model._meta.get_field(name)
        except Exception:
            pass
        label = name.replace("_", " ").title()
        try:
            label = label_for_field(name, change_list.model, model_admin=change_list.model_admin)
        except Exception:
            pass
        sortable = True
        if sortable_by is not None:
            sortable = name in sortable_by or getattr(attr, "admin_order_field", None) in sortable_by
        direction = ordering_columns.get(idx + 1)
        sort_value = idx + 1
        if direction == "asc":
            sort_value = -(idx + 1)
        elif direction == "desc":
            sort_value = idx + 1
        sort_url = None
        if sortable:
            try:
                sort_url = change_list.get_query_string({ORDER_VAR: sort_value}, [])
            except Exception:
                pass
        headers.append({
            "name": name,
            "label": label,
            "index": idx + 1,
            "sortable": sortable,
            "ascending": direction == "asc",
            "descending": direction == "desc",
            "sort_url": sort_url,
        })
    return headers


def render_column_value(obj, field_name, model_admin):
    from django.contrib.admin.utils import display_for_value

    try:
        field, attr, value = lookup_field(field_name, obj, model_admin)
        names = sensitive_field_names(obj._meta.model)
        normalized_name = str(field_name).lower().replace("_", "")
        normalized_names = {name.replace("_", "") for name in names}
        if (field is not None and is_sensitive_field(field, obj._meta.model)) or normalized_name in normalized_names:
            return "••••••••"
        if field is not None and getattr(field, "choices", None):
            value = dict(field.flatchoices).get(value, value)
        elif value is None:
            value = display_for_value(value, model_admin.get_empty_value_display())
        elif field is not None and getattr(field, "many_to_many", False):
            value = ", ".join(str(item) for item in list(value.all()[:5]))
        else:
            value = display_for_value(value, model_admin.get_empty_value_display())
        return conditional_escape(value) if isinstance(value, str) else value
    except Exception:
        try:
            return conditional_escape(str(getattr(obj, field_name)))
        except Exception:
            return "—"


def filter_specs(change_list):
    groups = []
    for spec in getattr(change_list, "filter_specs", []) or []:
        choices = []
        try:
            iterator = spec.choices(change_list)
            for choice in iterator:
                choices.append({
                    "display": choice.get("display", ""),
                    "query_string": choice.get("query_string", "?"),
                    "selected": bool(choice.get("selected")),
                })
        except Exception:
            continue
        if choices:
            groups.append({"title": getattr(spec, "title", "Filter"), "choices": choices[:50]})
    return groups


def date_hierarchy_data(change_list, request, max_values=12):
    """Build bounded, shareable date-hierarchy navigation."""
    field_name = getattr(change_list.model_admin, "date_hierarchy", None)
    if not field_name:
        return None
    try:
        field = change_list.model._meta.get_field(field_name)
    except Exception:
        return None
    data = {
        "field": field_name,
        "label": str(field.verbose_name),
        "year_param": f"{field_name}__year",
        "month_param": f"{field_name}__month",
        "day_param": f"{field_name}__day",
        "years": [],
        "months": [],
        "days": [],
    }
    year_value = request.GET.get(data["year_param"])
    month_value = request.GET.get(data["month_param"])
    day_value = request.GET.get(data["day_param"])
    qs = change_list.queryset
    try:
        if not year_value:
            values = qs.dates(field_name, "year", order="DESC")[:max_values]
            for date_value in values:
                query = {data["year_param"]: date_value.year}
                data["years"].append({
                    "label": str(date_value.year),
                    "query_string": change_list.get_query_string(query, []),
                })
        elif not month_value:
            year = int(year_value)
            values = qs.filter(**{f"{field_name}__year": year}).dates(field_name, "month", order="DESC")[:max_values]
            for date_value in values:
                query = {data["year_param"]: year, data["month_param"]: date_value.month}
                data["months"].append({
                    "label": date_value.strftime("%B"),
                    "query_string": change_list.get_query_string(query, []),
                })
        elif not day_value:
            year, month = int(year_value), int(month_value)
            values = qs.filter(
                **{
                    f"{field_name}__year": year,
                    f"{field_name}__month": month,
                }
            ).dates(field_name, "day", order="DESC")[:max_values]
            for date_value in values:
                query = {
                    data["year_param"]: year,
                    data["month_param"]: month,
                    data["day_param"]: date_value.day,
                }
                data["days"].append({
                    "label": date_value.strftime("%b %d"),
                    "query_string": change_list.get_query_string(query, []),
                })
    except Exception:
        return data
    return data
