# analytics/views/events.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count
from django.http import JsonResponse, Http404
from django.db.models.functions import TruncDate
from django.views.decorators.csrf import csrf_exempt

from honeypot.decorators import honeypot_exempt

from analytics.models import AnalyticsEvent

from .utils import get_date_range, detect_active_preset, section_enabled

from datetime import timedelta
import json


# Create your views here.


@csrf_exempt
@honeypot_exempt
def analytics_event_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        body = json.loads(request.body.decode('utf-8'))
        category = body.get('category', '').strip()
        action = body.get('action', '').strip()
        if not category or not action:
            return JsonResponse({'error': 'category and action are required'}, status=400)

        AnalyticsEvent.objects.create(
            category=category,
            action=action,
            label=body.get('label', ''),
            value=body.get('value'),
            path=body.get('path', ''),
            session_id=getattr(request, 'analytics_session_id', ''),
            ip_hash='',
            country_code='',
            country_name='',
            city='',
        )
        return JsonResponse({'status': 'ok'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def analytics_events(request):
    if not section_enabled('events'):
        raise Http404
    start_dt, end_dt = get_date_range(request)
    events_qs = AnalyticsEvent.objects.filter(created_at__range=(start_dt, end_dt))

    # Stat cards
    today = timezone.now().date()
    today_events = events_qs.filter(created_at__date=today).count()
    yesterday_events = events_qs.filter(created_at__date=today - timedelta(days=1)).count()

    # Daily chart
    daily = (
        events_qs
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    chart_labels = [d['day'].strftime('%b %d') for d in daily]
    chart_data = [d['count'] for d in daily]

    # Top categories / actions
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

    # NEW: Top labels, events by page, recent events
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
    recent_events = events_qs.select_related().order_by('-created_at')[:50]

    # Compare to previous period
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
    return render(request, 'analytics/events.html', context)
