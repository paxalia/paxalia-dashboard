from django.urls import path, include
from .views import (
    analytics_dashboard, analytics_pages, analytics_page_detail, analytics_api,
    analytics_traffic, analytics_realtime, analytics_realtime_data, analytics_settings,
    analytics_export, analytics_geography, analytics_event_api, analytics_events,
    analytics_billing, uploads, releases_page, admin_overview, bots_overview, about
)
from .views import server as server_views
from .views import backup as backup_views
from .views import security as security_views
from .views import csp_reports as csp_report_views

app_name = 'analytics'

# ─── Public API endpoints (no hardcoded path prefix) ──────────────
api_urlpatterns = [
    path('event/', analytics_event_api, name='event_api'),
    path('realtime/data/', analytics_realtime_data, name='realtime_data'),
    path('server/metrics/', server_views.api_server_metrics, name='api_server_metrics'),
    path('server/history/', server_views.api_server_history, name='api_server_history'),
    path('uploads/init/', uploads.upload_init, name='upload_init'),
    path('uploads/chunk/<uuid:upload_id>/', uploads.upload_chunk, name='upload_chunk'),
    path('uploads/complete/<uuid:upload_id>/', uploads.upload_complete, name='upload_complete'),
    path('uploads/delete/<uuid:upload_id>/', uploads.upload_delete, name='upload_delete'),
    path('uploads/list/', uploads.upload_list, name='upload_list'),
]

# ─── Dashboard pages ──────────────────────────────────────────────
dashboard_urlpatterns = [
    # Dashboard pages
    path('', analytics_dashboard, name='dashboard'),
    path('pages/', analytics_pages, name='pages'),
    path('pages/<path:path>/', analytics_page_detail, name='page_detail'),
    path('api/', analytics_api, name='api'),
    path('traffic/', analytics_traffic, name='traffic'),
    path('realtime/', analytics_realtime, name='realtime'),
    path('settings/', analytics_settings, name='settings'),
    path('export/<str:export_type>/', analytics_export, name='export'),
    path('geography/', analytics_geography, name='geography'),
    path('events/', analytics_events, name='events'),
    path('billing/', analytics_billing, name='billing'),
    path('bots/', bots_overview, name='bots'),

    path('server/overview/', server_views.server_overview, name='server_overview'),
    path('server/cpu/', server_views.server_cpu, name='server_cpu'),
    path('server/memory/', server_views.server_memory, name='server_memory'),
    path('server/disk/', server_views.server_disk, name='server_disk'),
    path('server/network/', server_views.server_network, name='server_network'),
    path('server/services/', server_views.server_services, name='server_services'),
    path('server/processes/', server_views.server_processes, name='server_processes'),

    path('admin-overview/', admin_overview, name='admin_overview'),

    path('security/', security_views.security_center, name='security'),
    path('security/sessions/<uuid:login_event_id>/revoke/', security_views.security_revoke_session, name='security_revoke_session'),
    path('security/ip/block/', security_views.security_block_ip, name='security_block_ip'),
    path('security/ip/<int:block_id>/unblock/', security_views.security_unblock_ip, name='security_unblock_ip'),
    path('csp-report/', csp_report_views.csp_report, name='csp_report'),

    path('backups/', backup_views.backup_management, name='backups'),
    path('backups/trigger/', backup_views.backup_trigger, name='backup_trigger'),
    path('backups/delete/<uuid:backup_id>/', backup_views.backup_delete, name='backup_delete'),
    path('backups/download/<uuid:backup_id>/', backup_views.backup_download_single, name='backup_download_single'),
    path('backups/download/init/<uuid:backup_id>/', backup_views.backup_download_init, name='backup_download_init'),
    path('backups/download/chunk/<uuid:backup_id>/<int:chunk_index>/', backup_views.backup_download_chunk, name='backup_download_chunk'),

    path('releases/', releases_page, name='releases'),

    path('about/', about, name='about'),
]

# ─── Combined for backward compatibility ────────────────────────────
urlpatterns = dashboard_urlpatterns + [
    path('api/', include(api_urlpatterns)),
]