# paxalia/views/events.py

import json
import logging
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from honeypot.decorators import honeypot_exempt

from paxalia.middleware import AnalyticsMiddleware
from paxalia.models import AnalyticsEvent, JSError
from paxalia.settings import get_config
from .utils import get_date_range, detect_active_preset, section_enabled

logger = logging.getLogger(__name__)

# SECURITY: this endpoint is intentionally public/anonymous (any visitor's
# browser calls it), which also makes it a prime target for flooding —
# either to bloat the database or to skew paxalia. A simple fixed-window
# limiter keyed by IP + session keeps a single client from hammering it,
# without requiring an extra dependency. This is deliberately conservative
# (not exact/atomic under heavy concurrency) — good enough to blunt casual
# abuse; put a real rate limiter (e.g. at the reverse proxy / WAF layer)
# in front for stronger guarantees.
EVENT_RATE_LIMIT_WINDOW_SECONDS = 60
EVENT_RATE_LIMIT_MAX_REQUESTS = 60
MAX_PUBLIC_JSON_BODY_BYTES = 64 * 1024


def _event_rate_limited(request):
    ip = AnalyticsMiddleware._get_ip(request) or 'unknown'
    session_id = getattr(request, 'analytics_session_id', '') or 'no-session'
    cache_key = f'paxalia:event_rl:{ip}:{session_id}'
    if cache.add(cache_key, 1, timeout=EVENT_RATE_LIMIT_WINDOW_SECONDS):
        return False
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.add(cache_key, 1, timeout=EVENT_RATE_LIMIT_WINDOW_SECONDS)
        count = 1
    return count > EVENT_RATE_LIMIT_MAX_REQUESTS


def _clean_str(value, max_len):
    """Coerce a JSON value to a trimmed string, never raising on bad input."""
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:max_len]


# ─── Public Event API ──────────────────────────────────────────────────

def _consent_denied(request):
    """
    True if consent mode is on and this request's cookie doesn't show
    granted consent — mirrors AnalyticsMiddleware's server-side gate
    and paxalia-events.js's client-side gate (Phase 14). Checked
    here too as defense in depth: the client-side gate stops the
    normal tracker from firing, but nothing stops a request sent
    directly to this endpoint from bypassing it.
    """
    if not get_config()['CONSENT_MODE_ENABLED']:
        return False
    cookie_name = get_config()['CONSENT_COOKIE_NAME']
    granted_value = get_config()['CONSENT_COOKIE_GRANTED_VALUE']
    return request.COOKIES.get(cookie_name) != granted_value


@csrf_exempt
@honeypot_exempt
@require_http_methods(["POST"])
def analytics_event_api(request):
    """
    Public API endpoint to record paxalia events.
    Expects a JSON POST with 'category' and 'action'.
    """
    if _event_rate_limited(request):
        logger.warning('paxalia: event API rate limit exceeded')
        return JsonResponse({'error': 'Too many requests'}, status=429)

    if _consent_denied(request):
        return JsonResponse({'status': 'skipped', 'reason': 'consent not granted'})

    if len(request.body) > MAX_PUBLIC_JSON_BODY_BYTES:
        return JsonResponse({'error': 'Payload too large'}, status=413)

    # 1. Parse JSON body
    try:
        body = json.loads(request.body.decode('utf-8'))
        if not isinstance(body, dict):
            raise ValueError('Payload must be a JSON object')
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
        logger.warning('paxalia: Invalid JSON received: %s', e)
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # 2. Validate required fields (coerced to strings so a non-string
    #    category/action can never throw an uncaught AttributeError)
    category = _clean_str(body.get('category'), 255)
    action = _clean_str(body.get('action'), 255)
    if not category or not action:
        logger.warning('paxalia: Missing category or action in payload')
        return JsonResponse({'error': 'category and action are required'}, status=400)

    # 3. Handle optional fields
    label = _clean_str(body.get('label'), 255)
    path = _clean_str(body.get('path'), 255)

    value_raw = body.get('value')
    if value_raw is not None and value_raw != '':
        try:
            value = float(value_raw)
        except (ValueError, TypeError):
            value = None
    else:
        value = None

    # 4. Store the event
    try:
        AnalyticsEvent.objects.create(
            category=category,
            action=action,
            label=label,
            value=value,
            path=path,
            session_id=getattr(request, 'analytics_session_id', ''),
            ip_hash='',
            country_code='',
            country_name='',
            city='',
        )
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        logger.error('paxalia: Failed to save event: %s', e)
        return JsonResponse({'error': 'Failed to save event'}, status=500)


# ─── Public JS Error API (Phase 11 — Real User Monitoring) ─────────────

MAX_STACK_LENGTH = 4000


def _clean_int(value):
    """Coerce to int, or None on anything that isn't cleanly one — a
    malformed lineno/colno shouldn't fail the whole report."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@csrf_exempt
@honeypot_exempt
@require_http_methods(["POST"])
def analytics_js_error_api(request):
    """Record a bounded client-side JavaScript error report."""
    if _event_rate_limited(request):
        logger.warning('paxalia: JS error API rate limit exceeded')
        return JsonResponse({'error': 'Too many requests'}, status=429)

    if _consent_denied(request):
        return JsonResponse({'status': 'skipped', 'reason': 'consent not granted'})

    if len(request.body) > MAX_PUBLIC_JSON_BODY_BYTES:
        return JsonResponse({'error': 'Payload too large'}, status=413)

    try:
        body = json.loads(request.body.decode('utf-8'))
        if not isinstance(body, dict):
            raise ValueError('Payload must be a JSON object')
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
        logger.warning('paxalia: Invalid JSON received (js-error): %s', e)
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    message = _clean_str(body.get('message'), 500)
    if not message:
        return JsonResponse({'error': 'message is required'}, status=400)

    try:
        JSError.objects.create(
            message=message,
            filename=_clean_str(body.get('filename'), 500),
            lineno=_clean_int(body.get('lineno')),
            colno=_clean_int(body.get('colno')),
            stack=_clean_str(body.get('stack'), MAX_STACK_LENGTH),
            path=_clean_str(body.get('path'), 255),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
            session_id=getattr(request, 'analytics_session_id', ''),
        )
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        logger.error('paxalia: Failed to save JS error: %s', e)
        return JsonResponse({'error': 'Failed to save error report'}, status=500)


# ─── Admin Dashboard View ─────────────────────────────────────────────

@staff_member_required
def analytics_events(request):
    """Dashboard view showing event paxalia."""
    if not section_enabled('events'):
        raise Http404

    start_dt, end_dt = get_date_range(request)
    events_qs = AnalyticsEvent.objects.filter(created_at__range=(start_dt, end_dt))

    # Stats
    today = timezone.now().date()
    today_events = events_qs.filter(created_at__date=today).count()
    yesterday_events = events_qs.filter(created_at__date=today - timedelta(days=1)).count()

    # Chart
    daily = (
        events_qs
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels = [d['day'].strftime('%b %d') for d in daily]
    chart_data = [d['count'] for d in daily]

    # Top lists
    top_categories = (
        events_qs.values('category')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    top_actions = (
        events_qs.values('category', 'action')
        .annotate(count=Count('id'))
        .order_by('-count')[:30]
    )
    top_labels = (
        events_qs.exclude(label='')
        .values('label')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    events_by_page = (
        events_qs.values('path')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    recent_events = events_qs.order_by('-created_at')[:50]

    # Compare period
    compare_active = request.GET.get('compare') == '1'
    previous_labels = []
    previous_data = []
    if compare_active:
        period_delta = (end_dt - start_dt).days
        prev_end = start_dt - timedelta(seconds=1)
        prev_start = prev_end - timedelta(days=period_delta)
        prev_qs = AnalyticsEvent.objects.filter(created_at__range=(prev_start, prev_end))
        prev_daily = (
            prev_qs
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        previous_labels = [d['day'].strftime('%b %d') for d in prev_daily]
        previous_data = [d['count'] for d in prev_daily]

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'today_events': today_events,
        'yesterday_events': yesterday_events,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'top_categories': top_categories,
        'top_actions': top_actions,
        'top_labels': top_labels,
        'events_by_page': events_by_page,
        'recent_events': recent_events,
        'compare_active': compare_active,
        'previous_labels': previous_labels,
        'previous_data': previous_data,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
        'active_page': 'events',
    }
    return render(request, 'paxalia/events.html', context)
