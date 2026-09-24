from django.urls import path, include
from .views import (
    analytics_dashboard, analytics_pages, analytics_page_detail, analytics_api,
    analytics_traffic, analytics_realtime, analytics_realtime_data, analytics_settings,
    analytics_export, analytics_geography, analytics_event_api, analytics_events,
    analytics_billing, uploads, releases_page, admin_overview, bots_overview, about
)
from .views.events import analytics_js_error_api, analytics_browser_log_api
from .views.chat_ops import slack_command, discord_interaction
from .views import rum as rum_views
from .views import uptime as uptime_views
from .views import compliance as compliance_views
from .views import data_import as data_import_views
from .views import server as server_views
from .views import backup as backup_views
from .views import security as security_views
from .views import csp_reports as csp_report_views
from .views import sites as sites_views
from .views import broken_links as broken_links_views
from .views import goals as goals_views
from .views import segments as segments_views
from .views import campaigns as campaigns_views
from .views import annotations as annotations_views
from .views import cohorts as cohorts_views
from .views import mfa as mfa_views
from .views import auth as auth_views
from .views import admin_security as admin_security_views
from .views import api_keys as api_keys_views
from .views import paxalia_api
from .views import api_docs as api_docs_views
from .views import reports as reports_views
from .views import share_links as share_links_views
from .views import notifications as notifications_views
from .views import logs as logs_views
from .views import login_activity as login_activity_views
from .views.dependencies import dependencies, dependency_status
from .admin_center import urls as admin_center_urls

app_name = 'paxalia'

# ─── Public API endpoints (no hardcoded path prefix) ──────────────
api_urlpatterns = [
    path('event/', analytics_event_api, name='event_api'),
    path('js-error/', analytics_js_error_api, name='js_error_api'),
    path('browser-log/', analytics_browser_log_api, name='browser_log_api'),
    path('slack/command/', slack_command, name='slack_command'),
    path('discord/interactions/', discord_interaction, name='discord_interactions'),
    path('realtime/data/', analytics_realtime_data, name='realtime_data'),
    path('server/metrics/', server_views.api_server_metrics, name='api_server_metrics'),
    path('server/history/', server_views.api_server_history, name='api_server_history'),
    path('uploads/init/', uploads.upload_init, name='upload_init'),
    path('uploads/chunk/<uuid:upload_id>/', uploads.upload_chunk, name='upload_chunk'),
    path('uploads/complete/<uuid:upload_id>/', uploads.upload_complete, name='upload_complete'),
    path('uploads/delete/<uuid:upload_id>/', uploads.upload_delete, name='upload_delete'),
    path('uploads/list/', uploads.upload_list, name='upload_list'),
]

# ─── Paxalia API (versioned, key-authenticated, documented) ───────
paxalia_api_urlpatterns = [
    path('ingest/', paxalia_api.paxalia_api_ingest, name='paxalia_api_ingest'),
    path('stats/summary/', paxalia_api.paxalia_api_stats_summary, name='paxalia_api_stats_summary'),
    path('pageviews/', paxalia_api.paxalia_api_pageviews, name='paxalia_api_pageviews'),
    path('events/', paxalia_api.paxalia_api_events, name='paxalia_api_events'),
]

# ─── Dashboard pages ──────────────────────────────────────────────
dashboard_urlpatterns = [
    # Paxalia authentication is available inside the package but does not
    # replace a host project's public authentication routes. The administrator
    # flow enforces all three Paxalia layers before privileged access.
    path('auth/login/', auth_views.paxalia_login, name='auth_login'),
    path('auth/logout/', auth_views.paxalia_logout, name='auth_logout'),
    path('auth/signup/', auth_views.paxalia_signup, name='auth_signup'),
    path('auth/password-reset/', auth_views.PaxaliaPasswordResetView.as_view(), name='auth_password_reset'),
    path('auth/password-reset/done/', auth_views.password_reset_done, name='auth_password_reset_done'),
    path('auth/password-reset/<uidb64>/<token>/', auth_views.PaxaliaPasswordResetConfirmView.as_view(), name='auth_password_reset_confirm'),
    path('auth/password-reset/complete/', auth_views.password_reset_complete, name='auth_password_reset_complete'),
    path('auth/password-change/', auth_views.password_change, name='auth_password_change'),
    path('auth/password-change/done/', auth_views.password_change_done, name='auth_password_change_done'),
    path('auth/2fa/setup/', auth_views.paxalia_2fa_setup, name='auth_2fa_setup'),
    path('auth/2fa/verify/', auth_views.paxalia_2fa_verify, name='auth_2fa_verify'),
    path('auth/2fa/reset/', auth_views.paxalia_2fa_reset, name='auth_2fa_reset'),
    path('auth/recovery/regenerate/', auth_views.paxalia_recovery_regenerate, name='auth_recovery_regenerate'),
    path('auth/device/', auth_views.paxalia_device_login, name='auth_device_login'),
    path('auth/device/options/', auth_views.paxalia_device_login_options, name='auth_device_login_options'),
    path('auth/device/verify/', auth_views.paxalia_device_login_verify, name='auth_device_login_verify'),
    path('auth/device/register/', auth_views.paxalia_device_register, name='auth_device_register'),
    path('auth/device/register/verify/', auth_views.paxalia_device_register_verify, name='auth_device_register_verify'),
    path('auth/session-expired/', auth_views.paxalia_session_expired, name='auth_session_expired'),
    path('auth/access-denied/', auth_views.paxalia_access_denied, name='auth_access_denied'),
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
    path('logs/', logs_views.logs_overview, name='logs'),
    path('logs/feed/', logs_views.log_feed, name='log_feed'),
    path('logs/live/', logs_views.live_log_feed, name='live_log_feed'),
    path('logs/<uuid:event_id>/', logs_views.log_detail, name='log_detail'),
    path('logs/export/', logs_views.logs_export, name='logs_export'),
    path('application-logs/', logs_views.application_logs, name='application_logs'),
    path('rum/', rum_views.rum_overview, name='rum'),
    path('uptime/', uptime_views.uptime_overview, name='uptime'),
    path('uptime/<int:monitor_id>/toggle/', uptime_views.uptime_monitor_toggle, name='uptime_monitor_toggle'),
    path('uptime/<int:monitor_id>/delete/', uptime_views.uptime_monitor_delete, name='uptime_monitor_delete'),
    path('compliance/', compliance_views.compliance_overview, name='compliance'),
    path('import/', data_import_views.data_import_page, name='data_import'),
    path('billing/', analytics_billing, name='billing'),
    path('bots/', bots_overview, name='bots'),

    path('server/overview/', server_views.server_overview, name='server_overview'),
    path('server/cpu/', server_views.server_cpu, name='server_cpu'),
    path('server/memory/', server_views.server_memory, name='server_memory'),
    path('server/disk/', server_views.server_disk, name='server_disk'),
    path('server/network/', server_views.server_network, name='server_network'),
    path('server/services/', server_views.server_services, name='server_services'),
    path('server/processes/', server_views.server_processes, name='server_processes'),
    path('server/slow-queries/', server_views.server_slow_queries, name='server_slow_queries'),
    path('server/queues/', server_views.server_queues, name='server_queues'),
    path('server/deployments/', server_views.server_deployments, name='server_deployments'),

    # Paxalia Admin — Django Admin-compatible administrative surface.
    path('', include(admin_center_urls)),

    # Backward-compatible admin overview URL.
    path('admin-overview/', admin_overview, name='admin_overview'),

    path('security/', security_views.security_center, name='security'),
    path('security/overview/', admin_security_views.security_overview, name='security_overview'),
    path('security/authentication/', admin_security_views.security_authentication, name='security_authentication'),
    path('security/admins/', admin_security_views.security_admins, name='security_admins'),
    path('security/devices/', admin_security_views.admin_devices, name='admin_devices'),
    path('security/devices/<uuid:device_id>/rename/', admin_security_views.admin_device_rename, name='admin_device_rename'),
    path('security/devices/<uuid:device_id>/revoke/', admin_security_views.admin_device_revoke, name='admin_device_revoke'),
    path('security/sessions/', admin_security_views.admin_sessions, name='admin_sessions'),
    path('security/sessions/<uuid:login_event_id>/revoke/', admin_security_views.admin_session_revoke, name='admin_session_revoke'),
    path('security/sessions/revoke-others/', admin_security_views.admin_sessions_revoke_others, name='admin_sessions_revoke_others'),
    path('security/sessions/revoke-all/', admin_security_views.admin_sessions_revoke_all, name='admin_sessions_revoke_all'),
    path('security/logins/users/', login_activity_views.login_activity, {'mode': 'user'}, name='user_login_activity'),
    path('security/logins/admins/', login_activity_views.login_activity, {'mode': 'admin'}, name='admin_login_activity'),
    path('security/logins/failed/', login_activity_views.login_activity, {'mode': 'failed'}, name='failed_login_activity'),
    path('security/dependencies/', dependencies, name='dependencies'),
    path('security/dependencies/status/<path:package_name>/', dependency_status, name='dependency_status'),
    path('security/ip/block/', security_views.security_block_ip, name='security_block_ip'),
    path('security/ip/<int:block_id>/unblock/', security_views.security_unblock_ip, name='security_unblock_ip'),
    path('csp-report/', csp_report_views.csp_report, name='csp_report'),

    path('sites/', sites_views.sites_management, name='sites'),
    path('sites/<uuid:site_id>/toggle/', sites_views.site_toggle_active, name='site_toggle_active'),
    path('sites/<uuid:site_id>/delete/', sites_views.site_delete, name='site_delete'),
    path('broken-links/', broken_links_views.broken_links, name='broken_links'),

    path('goals/', goals_views.goals_management, name='goals'),
    path('goals/<uuid:goal_id>/delete/', goals_views.goal_delete, name='goal_delete'),
    path('funnels/', goals_views.funnels_management, name='funnels'),
    path('funnels/<uuid:funnel_id>/delete/', goals_views.funnel_delete, name='funnel_delete'),
    path('segments/', segments_views.segments_management, name='segments'),
    path('segments/<uuid:segment_id>/delete/', segments_views.segment_delete, name='segment_delete'),
    path('campaigns/', campaigns_views.campaigns_dashboard, name='campaigns'),
    path('annotations/', annotations_views.annotations_management, name='annotations'),
    path('annotations/<uuid:annotation_id>/delete/', annotations_views.annotation_delete, name='annotation_delete'),
    path('cohorts/', cohorts_views.cohorts_retention, name='cohorts'),
    path('mfa/enroll/', mfa_views.mfa_enroll, name='mfa_enroll'),
    path('mfa/disable/', mfa_views.mfa_disable, name='mfa_disable'),

    path('api-keys/', api_keys_views.api_keys_management, name='api_keys'),
    path('api-keys/<uuid:key_id>/revoke/', api_keys_views.api_key_revoke, name='api_key_revoke'),
    path('api-keys/<uuid:key_id>/delete/', api_keys_views.api_key_delete, name='api_key_delete'),
    path('api-docs/', api_docs_views.api_docs, name='api_docs'),

    path('reports/', reports_views.reports_management, name='reports'),
    path('reports/<uuid:report_id>/toggle/', reports_views.report_toggle_active, name='report_toggle_active'),
    path('reports/<uuid:report_id>/delete/', reports_views.report_delete, name='report_delete'),

    path('share-links/', share_links_views.share_links_management, name='share_links'),
    path('share-links/<uuid:link_id>/revoke/', share_links_views.share_link_revoke, name='share_link_revoke'),
    path('share-links/<uuid:link_id>/delete/', share_links_views.share_link_delete, name='share_link_delete'),
    # Public — deliberately outside staff auth, gated by token (+ optional password) only.
    path('shared/<uuid:token>/', share_links_views.shared_dashboard_view, name='shared_dashboard'),

    path('notifications/', notifications_views.notifications_list, name='notifications'),
    path('notifications/<uuid:notification_id>/read/', notifications_views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', notifications_views.notifications_mark_all_read, name='notifications_mark_all_read'),

    path('backups/', backup_views.backup_management, name='backups'),
    path('backups/reauth/', backup_views.backup_reauth, name='backup_reauth'),
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
    path('paxalia-api/v1/', include(paxalia_api_urlpatterns)),
]


