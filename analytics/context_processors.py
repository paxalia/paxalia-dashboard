from .settings import get_config

def analytics_config(request):
    config = get_config()
    return {
        'sidebar_sections': config['SIDEBAR_SECTIONS'],
        'billing_available': 'billing' in config['SIDEBAR_SECTIONS'],
    }