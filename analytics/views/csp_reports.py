# analytics/views/csp_reports.py
import json
import logging

from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from honeypot.decorators import honeypot_exempt

from ..middleware import AnalyticsMiddleware
from ..models import CSPViolation

logger = logging.getLogger('analytics.security')

# Same reasoning as the public event API: this is an unauthenticated,
# browser-initiated endpoint, so it needs its own modest rate limit to
# avoid being used to flood the database.
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 30


def _rate_limited(request):
    ip = AnalyticsMiddleware._get_ip(request) or 'unknown'
    cache_key = f'analytics:csp_rl:{ip}'
    count = cache.get(cache_key, 0)
    if count >= _RATE_LIMIT_MAX_REQUESTS:
        return True
    cache.add(cache_key, 0, timeout=_RATE_LIMIT_WINDOW_SECONDS)
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=_RATE_LIMIT_WINDOW_SECONDS)
    return False


@csrf_exempt
@honeypot_exempt
@require_POST
def csp_report(request):
    """
    Collection endpoint for browser CSP violation reports. This package
    doesn't set the CSP header itself — point your own CSP's
    report-uri (legacy) or report-to (Reporting API) at this URL to
    start receiving reports here.

    Handles both the legacy `{"csp-report": {...}}` body (sent as
    application/csp-report, but browsers vary) and the newer Reporting
    API array-of-reports body (application/reports+json).
    """
    if _rate_limited(request):
        return HttpResponse(status=429)

    try:
        raw = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponse(status=400)

    reports = []
    if isinstance(raw, dict) and 'csp-report' in raw:
        reports = [raw['csp-report']]
    elif isinstance(raw, list):
        # Reporting API: [{"type": "csp-violation", "body": {...}}, ...]
        for item in raw:
            body = item.get('body', item) if isinstance(item, dict) else {}
            reports.append(body)
    elif isinstance(raw, dict):
        reports = [raw]

    for r in reports[:20]:  # hard cap per request, defense in depth
        try:
            CSPViolation.objects.create(
                blocked_uri=str(r.get('blockedURL') or r.get('blocked-uri', ''))[:2048],
                violated_directive=str(r.get('effectiveDirective') or r.get('violated-directive', ''))[:255],
                document_uri=str(r.get('documentURL') or r.get('document-uri', ''))[:2048],
                source_file=str(r.get('sourceFile', ''))[:2048],
                line_number=r.get('lineNumber') or None,
                raw_report=r if isinstance(r, dict) else {},
            )
        except Exception:
            logger.exception('Failed to store CSP violation report')

    # Browsers ignore the response body/status beyond 2xx; 204 is conventional.
    return HttpResponse(status=204)
