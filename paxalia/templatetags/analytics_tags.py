from django import template
from django.utils.safestring import mark_safe
import json

from ..settings import get_config

register = template.Library()

@register.simple_tag
def get_analytics_config():
    return get_config()


@register.simple_tag
def analytics_consent_config():
    """
    Renders a small inline <script> exposing consent-mode config to
    paxalia-events.js as window.PAXALIA_CONSENT_CONFIG. Include this
    tag immediately before the paxalia-events.js <script src="...">
    tag on your tracked pages — see the README's "Consent Mode"
    section. If omitted, paxalia-events.js defaults to consent mode
    disabled (tracking behaves exactly as it did before Phase 14).
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
    # Escape '</' so a maliciously-configured cookie name/value (server
    # config, not user input, but cheap insurance) can't break out of
    # the <script> tag early.
    safe_json = json.dumps(payload).replace('</', '<\\/')
    return mark_safe(f'<script>window.PAXALIA_CONSENT_CONFIG = {safe_json};</script>')