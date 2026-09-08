# analytics/views/paxalia_api.py
"""
The Paxalia API: server-to-server event ingestion and read access to
analytics data, both authenticated with a PaxaliaAPIKey (see
analytics/api_keys.py). Plain JSON over HTTP, no framework dependency
(no Django REST Framework) — pagination is a simple limit/offset.

Distinct from analytics_event_api (views/events.py), which stays
anonymous/unauthenticated on purpose for browser-side use.
"""
import json
import logging
from datetime import datetime

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from analytics.api_keys import authenticate_request
from analytics.models import AnalyticsEvent, PageView

logger = logging.getLogger('analytics.paxalia_api')

MAX_LIMIT = 500
DEFAULT_LIMIT = 100

# Same reasoning as the browser event API's rate limiter: a valid key
# doesn't mean unlimited trust, especially since a leaked key would
# otherwise have no ceiling on ingestion volume.
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 300


def _rate_limited(api_key):
    cache_key = f'analytics:paxalia_api_rl:{api_key.id}'
    count = cache.get(cache_key, 0)
    if count >= RATE_LIMIT_MAX_REQUESTS:
        return True
    cache.add(cache_key, 0, timeout=RATE_LIMIT_WINDOW_SECONDS)
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=RATE_LIMIT_WINDOW_SECONDS)
    return False


def _require_key(request, scope):
    api_key = authenticate_request(request, scope)
    if api_key is None:
        return None, JsonResponse(
            {'error': 'Missing or invalid API key. Send it as: Authorization: Bearer pxa_...'},
            status=401,
        )
    if _rate_limited(api_key):
        return None, JsonResponse({'error': 'Too many requests'}, status=429)
    return api_key, None


def _parse_date_range(request):
    end_str = request.GET.get('end_date')
    start_str = request.GET.get('start_date')
    end_date = timezone.now()
    if end_str:
        try:
            end_date = timezone.make_aware(datetime.strptime(end_str, '%Y-%m-%d'))
        except ValueError:
            pass
    start_date = end_date - timezone.timedelta(days=30)
    if start_str:
        try:
            start_date = timezone.make_aware(datetime.strptime(start_str, '%Y-%m-%d'))
        except ValueError:
            pass
    return start_date, end_date


def _paginate(request):
    try:
        limit = min(int(request.GET.get('limit', DEFAULT_LIMIT)), MAX_LIMIT)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    try:
        offset = max(int(request.GET.get('offset', 0)), 0)
    except (TypeError, ValueError):
        offset = 0
    return max(limit, 1), offset


# ─── Ingestion ──────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def paxalia_api_ingest(request):
    """POST /paxalia-api/v1/ingest/ — server-to-server event ingestion.
    Same payload shape as the public browser event API."""
    api_key, error_response = _require_key(request, 'ingest')
    if error_response:
        return error_response

    try:
        body = json.loads(request.body.decode('utf-8'))
        if not isinstance(body, dict):
            raise ValueError('Payload must be a JSON object')
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    category = str(body.get('category', ''))[:255].strip()
    action = str(body.get('action', ''))[:255].strip()
    if not category or not action:
        return JsonResponse({'error': 'category and action are required'}, status=400)

    try:
        AnalyticsEvent.objects.create(
            site=api_key.site,
            category=category,
            action=action,
            label=str(body.get('label', ''))[:255],
            path=str(body.get('path', ''))[:255],
            session_id=str(body.get('session_id', ''))[:64],
        )
        return JsonResponse({'status': 'ok'}, status=201)
    except Exception:
        logger.exception('Paxalia API: failed to ingest event')
        return JsonResponse({'error': 'Failed to save event'}, status=500)


# ─── Read API ───────────────────────────────────────────────────────

@require_http_methods(["GET"])
def paxalia_api_stats_summary(request):
    """GET /paxalia-api/v1/stats/summary/"""
    api_key, error_response = _require_key(request, 'read')
    if error_response:
        return error_response

    start_dt, end_dt = _parse_date_range(request)
    qs = PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False, is_api=False)
    if api_key.site is not None:
        qs = qs.filter(site=api_key.site)

    return JsonResponse({
        'start_date': start_dt.date().isoformat(),
        'end_date': end_dt.date().isoformat(),
        'total_views': qs.count(),
        'unique_visitors': qs.exclude(session_id='').values('session_id').distinct().count(),
    })


@require_http_methods(["GET"])
def paxalia_api_pageviews(request):
    """GET /paxalia-api/v1/pageviews/ — paginated, ?limit=&offset=&start_date=&end_date="""
    api_key, error_response = _require_key(request, 'read')
    if error_response:
        return error_response

    start_dt, end_dt = _parse_date_range(request)
    limit, offset = _paginate(request)

    qs = PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False, is_api=False)
    if api_key.site is not None:
        qs = qs.filter(site=api_key.site)
    qs = qs.order_by('-created_at')

    total = qs.count()
    page = qs[offset:offset + limit]

    return JsonResponse({
        'total': total,
        'limit': limit,
        'offset': offset,
        'results': [
            {
                'path': pv.path,
                'method': pv.method,
                'status_code': pv.status_code,
                'referrer': pv.referrer,
                'country_code': pv.country_code,
                'utm_source': pv.utm_source,
                'utm_medium': pv.utm_medium,
                'utm_campaign': pv.utm_campaign,
                'created_at': pv.created_at.isoformat(),
            }
            for pv in page
        ],
    })


@require_http_methods(["GET"])
def paxalia_api_events(request):
    """GET /paxalia-api/v1/events/ — paginated, ?limit=&offset=&start_date=&end_date=&category="""
    api_key, error_response = _require_key(request, 'read')
    if error_response:
        return error_response

    start_dt, end_dt = _parse_date_range(request)
    limit, offset = _paginate(request)

    qs = AnalyticsEvent.objects.filter(created_at__range=(start_dt, end_dt))
    if api_key.site is not None:
        qs = qs.filter(site=api_key.site)
    category_filter = request.GET.get('category')
    if category_filter:
        qs = qs.filter(category=category_filter)
    qs = qs.order_by('-created_at')

    total = qs.count()
    page = qs[offset:offset + limit]

    return JsonResponse({
        'total': total,
        'limit': limit,
        'offset': offset,
        'results': [
            {
                'category': e.category,
                'action': e.action,
                'label': e.label,
                'value': e.value,
                'path': e.path,
                'created_at': e.created_at.isoformat(),
            }
            for e in page
        ],
    })
