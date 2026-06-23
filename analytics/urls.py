from django.urls import path
from .views import (
    analytics_dashboard, analytics_pages, analytics_page_detail, analytics_api,
    analytics_traffic, analytics_realtime, analytics_realtime_data, analytics_settings,
    analytics_export, analytics_geography, analytics_event_api, analytics_events,
    analytics_billing, uploads, releases_page
)

app_name = 'analytics'

urlpatterns = [
    # API endpoints (must come first)
    path('api/event/', analytics_event_api, name='event_api'),
    path('realtime/data/', analytics_realtime_data, name='realtime_data'),

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

    path('releases/', releases_page, name='releases'),
    path('releases/upload/init/', uploads.upload_init, name='upload_init'),
    path('releases/upload/chunk/<uuid:upload_id>/', uploads.upload_chunk, name='upload_chunk'),
    path('releases/upload/complete/<uuid:upload_id>/', uploads.upload_complete, name='upload_complete'),
    path('releases/upload/list/', uploads.upload_list, name='upload_list'),
    path('releases/upload/delete/<uuid:upload_id>/', uploads.upload_delete, name='upload_delete'),
]
