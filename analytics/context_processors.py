# analytics/context_processors.py

import uuid
from django.urls import reverse
from .settings import get_config

def analytics_config(request):
    config = get_config()

    # ─── Multi-site: current selection + switcher options ──────────
    from .models import Site
    from .views.utils import get_current_site
    current_site = get_current_site(request) if hasattr(request, 'session') else None
    all_sites = list(Site.objects.filter(is_active=True)) if 'sites' in config['SIDEBAR_SECTIONS'] else []

    from .models import Segment
    from .views.utils import get_current_segment
    current_segment = get_current_segment(request) if hasattr(request, 'session') else None
    all_segments = list(Segment.objects.all()) if 'segments' in config['SIDEBAR_SECTIONS'] else []

    # ─── Build upload URLs with a placeholder ──────────────────────
    dummy_id = uuid.uuid4()

    upload_init_url = reverse('analytics:upload_init')
    upload_chunk_url = reverse('analytics:upload_chunk', kwargs={'upload_id': dummy_id}).replace(str(dummy_id), 'PLACEHOLDER')
    upload_complete_url = reverse('analytics:upload_complete', kwargs={'upload_id': dummy_id}).replace(str(dummy_id), 'PLACEHOLDER')
    upload_delete_url = reverse('analytics:upload_delete', kwargs={'upload_id': dummy_id}).replace(str(dummy_id), 'PLACEHOLDER')
    upload_list_url = reverse('analytics:upload_list')

    return {
        'sidebar_sections': config['SIDEBAR_SECTIONS'],
        'billing_available': 'billing' in config['SIDEBAR_SECTIONS'],
        # ─── API endpoints ──────────────────────────────────────────
        'ANALYTICS_REALTIME_DATA_URL': reverse('analytics:realtime_data'),
        'ANALYTICS_SERVER_METRICS_URL': reverse('analytics:api_server_metrics'),
        'ANALYTICS_SERVER_HISTORY_URL': reverse('analytics:api_server_history'),
        'ANALYTICS_UPLOAD_INIT_URL': upload_init_url,
        'ANALYTICS_UPLOAD_CHUNK_URL': upload_chunk_url,
        'ANALYTICS_UPLOAD_COMPLETE_URL': upload_complete_url,
        'ANALYTICS_UPLOAD_DELETE_URL': upload_delete_url,
        'ANALYTICS_UPLOAD_LIST_URL': upload_list_url,
        'ANALYTICS_EVENTS_DATA_URL': reverse('analytics:events'),
        'analytics_current_site': current_site,
        'analytics_all_sites': all_sites,
        'analytics_current_segment': current_segment,
        'analytics_all_segments': all_segments,
    }