from django import template
from django.utils.html import format_html
import json

from ..settings import get_config

register = template.Library()

@register.simple_tag
def get_analytics_config():
    return get_config()


@register.simple_tag
def analytics_consent_config():
    """Render consent configuration as a CSP-safe metadata element.

    The browser analytics script reads the JSON from this element before it
    starts tracking. Keeping configuration in markup rather than an inline
    script avoids requiring ``unsafe-inline`` or a per-request nonce on host
    pages that use a strict Content-Security-Policy.
    """
    config = get_config()
    payload = {
        'enabled': bool(config['CONSENT_MODE_ENABLED']),
        'cookieName': config['CONSENT_COOKIE_NAME'],
        'grantedValue': config['CONSENT_COOKIE_GRANTED_VALUE'],
        'browserLogEnabled': bool(config.get('LOGGING_ENABLED', True)),
        'browserLogUrl': '/api/paxalia/browser-log/',
        'captureConsole': bool(config.get('LOG_BROWSER_CAPTURE_CONSOLE', False)),
        'captureResourceErrors': bool(config.get('LOG_BROWSER_CAPTURE_RESOURCE_ERRORS', True)),
        'maxBrowserEvents': int(config.get('LOG_BROWSER_MAX_EVENTS_PER_PAGE', 50)),
    }
    safe_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    # The attribute value is escaped by the template system. The JavaScript
    # consumer parses it as JSON; no executable inline script is emitted.
    return format_html('<meta name="paxalia-consent-config" content="{}">', safe_json)
