"""Paxalia Logs dashboard and safe log export endpoints."""
import csv
import json

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _

from ..logging.application import queryset_for, resolve_application_sources, serialize_row, source_summary
from ..logging.redaction import redact
from ..models import PaxaliaLogEvent, PaxaliaLogGroup
from ..permissions import require_section_permission
from ..settings import get_config
from .utils import detect_active_preset, get_current_site, get_date_range, section_enabled


def _apply_filters(request, qs):
    params = request.GET
    start_dt, end_dt = get_date_range(request)
    qs = qs.filter(timestamp__range=(start_dt, end_dt))
    site = get_current_site(request)
    if site is not None:
        qs = qs.filter(site=site)
    for field in ('severity', 'source', 'category', 'logger_name', 'traffic_type', 'request_method', 'exception_type', 'fingerprint', 'release'):
        value = params.get(field)
        if value:
            qs = qs.filter(**{field: value[:255]})
    if params.get('status'):
        try:
            qs = qs.filter(response_status=int(params['status']))
        except (TypeError, ValueError):
            pass
    if params.get('path'):
        qs = qs.filter(request_path__icontains=params['path'][:200])
    if params.get('q'):
        needle = params['q'][:200]
        qs = qs.filter(Q(message__icontains=needle) | Q(logger_name__icontains=needle) | Q(exception_type__icontains=needle) | Q(request_path__icontains=needle))
    return qs, start_dt, end_dt, site


def _serialize_event(event):
    return {
        'id': str(event.id),
        'timestamp': event.timestamp.isoformat(),
        'severity': event.severity,
        'source': event.source,
        'category': event.category,
        'action': event.action,
        'message': event.message,
        'logger_name': event.logger_name,
        'request_path': event.request_path,
        'request_method': event.request_method,
        'response_status': event.response_status,
        'traffic_type': event.traffic_type,
        'request_id': event.request_id,
        'correlation_id': event.correlation_id,
        'fingerprint': event.fingerprint,
        'suppressed_count': event.group.suppressed_count if event.group else 0,
    }


@require_section_permission('logs')
def logs_overview(request):
    if not section_enabled('logs'):
        raise Http404
    qs, start_dt, end_dt, site = _apply_filters(request, PaxaliaLogEvent.objects.select_related('site', 'user', 'group'))
    stats = {key: qs.filter(severity=key).count() for key in ('CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG')}
    stats['total'] = sum(stats.values())
    group_qs = PaxaliaLogGroup.objects.filter(last_seen__range=(start_dt, end_dt))
    if site is not None:
        group_qs = group_qs.filter(events__site=site).distinct()
    stats['open_problems'] = group_qs.filter(severity__in=['ERROR', 'CRITICAL']).count()
    stats['repeated_problems'] = group_qs.filter(occurrence_count__gt=1).count()
    stats['suppressed'] = group_qs.aggregate(total=Sum('suppressed_count'))['total'] or 0
    new_group_qs = PaxaliaLogGroup.objects.filter(first_seen__date=timezone.now().date())
    if site is not None:
        new_group_qs = new_group_qs.filter(events__site=site).distinct()
    stats['new_problems_today'] = new_group_qs.count()
    traffic = {kind: qs.filter(traffic_type=kind).count() for kind in ('WEB', 'API', 'BOT', 'INTERNAL')}
    daily = (
        qs.annotate(day=TruncDate('timestamp'))
        .values('day')
        .annotate(
            count=Count('id'),
            critical=Count('id', filter=Q(severity='CRITICAL')),
            errors=Count('id', filter=Q(severity='ERROR')),
            warnings=Count('id', filter=Q(severity='WARNING')),
            info=Count('id', filter=Q(severity='INFO')),
            debug=Count('id', filter=Q(severity='DEBUG')),
            browser_errors=Count('id', filter=Q(source__in=['JavaScript', 'Browser']) & Q(severity__in=['ERROR', 'CRITICAL'])),
            login_failures=Count('id', filter=Q(source='Authentication') & Q(action='login_failed')),
            application_errors=Count('id', filter=Q(source='Application') & Q(severity__in=['ERROR', 'CRITICAL'])),
            api_failures=Count('id', filter=Q(traffic_type='API') & Q(severity__in=['ERROR', 'CRITICAL'])),
            bot_failures=Count('id', filter=Q(traffic_type='BOT') & Q(severity__in=['ERROR', 'CRITICAL'])),
        )
        .order_by('day')
    )
    groups = group_qs.select_related().order_by('-last_seen')[:25]
    paginator = Paginator(qs.order_by('-timestamp'), 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    pagination_query = request.GET.copy()
    pagination_query.pop('page', None)
    return render(request, 'paxalia/logs.html', {
        'active_page': 'logs',
        'page_title': _('Paxalia Logs'),
        'page_subtitle': _('Application, HTTP, browser, and runtime observability'),
        'events': page_obj.object_list,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'stats': stats,
        'traffic': traffic,
        'daily': list(daily),
        'new_problems_today': stats['new_problems_today'],
        'groups': groups,
        'start_dt': start_dt,
        'end_dt': end_dt,
        'active_preset': detect_active_preset(start_dt.date(), end_dt.date()),
        'site': site,
        'filters': request.GET,
        'severity_choices': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
        'log_refresh_seconds': max(5, int(get_config().get('DEFAULT_REALTIME_REFRESH', 30))),
    })


@require_section_permission('logs')
def log_detail(request, event_id):
    if not section_enabled('logs'):
        raise Http404
    event = get_object_or_404(PaxaliaLogEvent.objects.select_related('group', 'site', 'user'), id=event_id)
    relation_q = Q()
    has_relation = False
    if event.group_id:
        relation_q |= Q(group_id=event.group_id)
        has_relation = True
    if event.request_id:
        relation_q |= Q(request_id=event.request_id)
        has_relation = True
    if event.correlation_id:
        relation_q |= Q(correlation_id=event.correlation_id)
        has_relation = True
    related = PaxaliaLogEvent.objects.none() if not has_relation else PaxaliaLogEvent.objects.filter(relation_q).exclude(id=event.id).distinct().order_by('-timestamp')[:50]
    metadata = redact(event.metadata or {}, extra_keys=())
    return render(request, 'paxalia/log_detail.html', {
        'active_page': 'logs', 'page_title': _('Log Detail'),
        'page_subtitle': _('Detailed event, request, correlation, and sanitized metadata'),
        'event': event, 'related': related,
        'metadata_json': json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
    })


@require_section_permission('logs')
def log_feed(request):
    if not section_enabled('logs'):
        raise Http404
    qs, _start, _end, _site = _apply_filters(request, PaxaliaLogEvent.objects.select_related('group'))
    qs = qs.order_by('-timestamp')[:50]
    return JsonResponse({'events': [_serialize_event(event) for event in qs]})


@require_section_permission('logs')
def logs_export(request):
    if not section_enabled('logs'):
        raise Http404
    qs, _start, _end, _site = _apply_filters(request, PaxaliaLogEvent.objects.select_related('group'))
    
    try:
        limit = max(1, min(10000, int(request.GET.get('limit', '10000') or 10000)))
    except (TypeError, ValueError):
        limit = 10000
    rows = qs.order_by('-timestamp')[:limit]
    fmt = request.GET.get('format', 'csv').lower()
    if fmt == 'json':
        payload = []
        for event in rows:
            row = _serialize_event(event)
            row['metadata'] = redact(event.metadata or {})
            row['stack_trace'] = event.stack_trace
            row['exception_type'] = event.exception_type
            row['file_name'] = event.file_name
            row['line_number'] = event.line_number
            row['function_name'] = event.function_name
            row['suppressed_count'] = event.group.suppressed_count if event.group else 0
            payload.append(row)
        response = HttpResponse(json.dumps(payload, ensure_ascii=False, default=str), content_type='application/json')
    else:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="paxalia-logs.csv"'
        writer = csv.writer(response)
        writer.writerow(['timestamp', 'severity', 'source', 'category', 'logger', 'message', 'method', 'path', 'status', 'traffic', 'request_id', 'correlation_id', 'exception_type', 'file', 'line', 'fingerprint', 'suppressed_count'])
        for event in rows:
            writer.writerow([
                event.timestamp.isoformat(), event.severity, event.source, event.category,
                event.logger_name, event.message, event.request_method, event.request_path,
                event.response_status or '', event.traffic_type, event.request_id,
                event.correlation_id, event.exception_type, event.file_name, event.line_number or '',
                event.fingerprint, event.group.suppressed_count if event.group else 0,
            ])
    response['Cache-Control'] = 'no-store'
    return response


@require_section_permission('logs')
def application_logs(request):
    if not section_enabled('logs'):
        raise Http404
    sources = resolve_application_sources(request.user)
    selected = request.GET.get('source') or (sources[0].name if sources else '')
    source = next((s for s in sources if s.name == selected), None)
    rows = []
    summary = None
    source_stats = None
    page_obj = None
    start_dt, end_dt = get_date_range(request)
    pagination_query = request.GET.copy()
    pagination_query.pop('page', None)
    if source is not None:
        qs = queryset_for(source)
        timestamp = source.fields.get('timestamp')
        if timestamp:
            # Timestamp field is explicitly declared by the host application.
            qs = qs.filter(**{f'{timestamp}__range': (start_dt, end_dt)})
        exact_filters = {
            'action': source.fields.get('action'),
            'feature': source.fields.get('feature'),
            'category': source.fields.get('category'),
            'screen': source.fields.get('screen'),
            'workspace': source.fields.get('workspace'),
            'status': source.fields.get('status'),
        }
        for concept, field_name in exact_filters.items():
            value = request.GET.get(concept)
            if not value or not field_name:
                continue
            if concept == 'status':
                try:
                    qs = qs.filter(**{field_name: int(value)})
                except (TypeError, ValueError):
                    pass
            else:
                qs = qs.filter(**{field_name: value[:255]})
        search = request.GET.get('q')
        search_fields = [source.fields.get(key) for key in ('action', 'feature', 'category', 'screen', 'workspace')]
        search_q = Q()
        for field_name in search_fields:
            if field_name:
                search_q |= Q(**{f'{field_name}__icontains': search[:200]})
        if search and search_q:
            qs = qs.filter(search_q)
        source_stats = source_summary(source)
        paginator = Paginator(qs, 50)
        page_obj = paginator.get_page(request.GET.get('page'))
        summary = {
            'total': qs.count(),
            'rows': [serialize_row(source, item) for item in page_obj.object_list],
        }
    return render(request, 'paxalia/application_logs.html', {
        'active_page': 'application_logs', 'page_title': _('Application Logs'),
        'page_subtitle': _('Read-only views of existing host application log models'),
        'sources': sources, 'selected_source': source, 'model_verbose_name': (source.model._meta.verbose_name_plural if source else ''), 'summary': summary, 'source_stats': source_stats,
        'page_obj': page_obj, 'pagination_query': pagination_query, 'filters': request.GET,
        'start_dt': start_dt, 'end_dt': end_dt,
        'active_preset': detect_active_preset(start_dt.date(), end_dt.date()),
    })
