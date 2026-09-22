from django.urls import path

from . import views
from . import package_views

urlpatterns = [
    path("admin/packages/", package_views.package_center, name="admin_packages"),
    path("admin/packages/export/", package_views.package_export_center, name="admin_package_export"),
    path("admin/packages/import/", package_views.package_import_center, name="admin_package_import"),
    path("admin/packages/history/", package_views.package_history, name="admin_package_history"),
    path("admin/packages/failures/", package_views.package_failure_report, name="admin_package_failure_report"),
    path("admin/packages/retry/<str:retry_id>/", package_views.package_retry, name="admin_package_retry"),
    path("admin/<str:app_label>/<str:model_name>/export/", package_views.model_export, name="admin_model_export"),
    path("admin/<str:app_label>/<str:model_name>/import/", package_views.model_import, name="admin_model_import"),
    path("admin/<str:app_label>/<str:model_name>/localization/", package_views.model_localization, name="admin_model_localization"),
    path("admin/", views.admin_home, name="admin_home"),
    path("admin/models/", views.admin_models, name="admin_models"),
    path("admin/audit/", views.admin_audit, name="admin_audit"),
    path("admin/<str:app_label>/<str:model_name>/", views.model_overview, name="admin_model_overview"),
    path("admin/<str:app_label>/<str:model_name>/records/", views.model_changelist, name="admin_model_list"),
    path("admin/<str:app_label>/<str:model_name>/add/", views.model_add, name="admin_model_add"),
    path("admin/<str:app_label>/<str:model_name>/actions/", views.model_action, name="admin_model_action"),
    path("admin/<str:app_label>/<str:model_name>/bulk-delete/", views.model_bulk_delete, name="admin_bulk_delete"),
    path("admin/<str:app_label>/<str:model_name>/stats/", views.model_stats, name="admin_model_stats"),
    path("admin/<str:app_label>/<str:model_name>/<path:object_id>/history/", views.model_history, name="admin_object_history"),
    path("admin/<str:app_label>/<str:model_name>/<path:object_id>/change/", views.model_change, name="admin_object_change"),
    path("admin/<str:app_label>/<str:model_name>/<path:object_id>/delete/", views.model_delete, name="admin_object_delete"),
    path("admin/<str:app_label>/<str:model_name>/<path:object_id>/", views.model_detail, name="admin_object_detail"),
]
