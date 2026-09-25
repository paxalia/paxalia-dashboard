"""Paxalia Logs dashboard and safe log export endpoints."""
import csv
import json
import re
from datetime import datetime, timezone as dt_timezone

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _

from ..logging.application import queryset_for, resolve_application_sources, serialize_row, source_summary
from ..logging.handler import get_live_log_buffer
from ..logging.redaction import redact, strip_ansi
from ..models import PaxaliaLogEvent, PaxaliaLogGroup
from ..permissions import require_section_permission
from ..settings import get_config
from .utils import detect_active_preset, get_current_site, get_date_range, section_enabled


def _csv_safe(value):
    """Neutralize spreadsheet formula prefixes before values enter CSV."""
    if value is None:
        return ""
    value = str(value)
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value



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



def _ai_safe_location(event):
    """Return a repository/package-relative location without server filesystem paths."""
    raw = str(getattr(event, 'file_name', '') or '').replace('\\', '/')
    if '/site-packages/' in raw:
        raw = raw.split('/site-packages/', 1)[1]
    else:
        match = re.search(r'(^|/)(paxalia/.*)$', raw)
        if match:
            raw = match.group(2)
        elif raw.startswith('/'):
            raw = raw.rsplit('/', 1)[-1]
    line = getattr(event, 'line_number', None)
    function = str(getattr(event, 'function_name', '') or '').strip()
    location = raw or '—'
    if line:
        location += f':{line}'
    if function:
        location += f' · {function}'
    return location


def _ai_safe_stack(stack_trace):
    """Keep traceback evidence while removing server-specific path prefixes."""
    text = strip_ansi(stack_trace or "").replace("\\", "/")
    # Normalize Paxalia package paths first so they remain recognizable.
    text = re.sub(r'(?i)(?:[A-Za-z]:)?/[^"\n]*?/site-packages/(paxalia/)', r'\1', text)
    text = re.sub(r'(?i)(?:[A-Za-z]:)?/[^"\n]*/(paxalia/[A-Za-z0-9_./-]+)', r'\1', text)
    text = re.sub(
        r'''File (["'])(?:[A-Za-z]:)?/[^"']*/(paxalia/[A-Za-z0-9_./-]+)(["'])''',
        r'File \1\2\3',
        text,
    )
    # Remaining absolute Python file paths are reduced to a stable placeholder
    # plus basename, preserving file identity without exposing server layout.
    text = re.sub(
        r'''File (["'])(?:[A-Za-z]:)?/[^"']*/([^/\\"']+)(["'])''',
        r'File \1<absolute-path>/\2\3',
        text,
    )
    return redact(text, extra_keys=())

def _ai_incident_context(event):
    """Build a minimal, allowlisted incident payload for external AI tools."""
    message = redact(event.message or '', extra_keys=())
    stack = _ai_safe_stack(event.stack_trace or '')
    lines = [
        'PAXALIA INCIDENT',
        '=================',
        f"Severity: {event.severity or '—'}",
        f"Source: {event.source or '—'}",
        f"Category: {event.category or '—'}",
        f"Action: {event.action or '—'}",
        f"Logger: {event.logger_name or '—'}",
        f"Release: {event.release or '—'}",
        f"Request Method: {event.request_method or '—'}",
        f"Response Status: {event.response_status or '—'}",
        f"Duration: {event.duration_ms} ms" if event.duration_ms else 'Duration: —',
        '',
        'MESSAGE',
        '-------',
        message or '—',
        '',
        'EXCEPTION',
        '---------',
        f"Type: {event.exception_type or '—'}",
        f"Location: {_ai_safe_location(event)}",
        '',
        'STACK TRACE',
        '-----------',
        stack or '—',
    ]
    return '\n'.join(lines)

def _serialize_event(event):
    return {
        'id': str(event.id),
        'timestamp': event.timestamp.isoformat(),
        'severity': event.severity,
        'source': event.source,
        'category': event.category,
        'action': event.action,
        'message': strip_ansi(event.message),
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
    for event in page_obj.object_list:
        event.message = strip_ansi(event.message)
    for group in groups:
        group.normalized_message = strip_ansi(group.normalized_message)
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
def live_log_feed(request):
    """Return a cross-worker live log view from the local buffer + persisted events."""
    if not section_enabled('logs'):
        raise Http404
    raw_since = request.GET.get('since')
    try:
        limit = max(1, min(2000, int(request.GET.get('limit', '2000') or 2000)))
    except (TypeError, ValueError):
        limit = 2000

    local_payload = get_live_log_buffer().snapshot(since=raw_since, limit=limit)
    entries = list(local_payload.get('entries') or [])

    try:
        since_value = int(raw_since) if raw_since not in (None, '') else None
    except (TypeError, ValueError):
        since_value = None

    persistent = PaxaliaLogEvent.objects.order_by('-timestamp')
    if since_value is not None:
        since_dt = datetime.fromtimestamp(since_value / 1_000_000, tz=dt_timezone.utc)
        persistent = persistent.filter(timestamp__gte=since_dt)
    persistent = list(persistent[:limit])
    for event in reversed(persistent):
        timestamp = event.timestamp.timestamp()
        sequence = int(timestamp * 1_000_000)
        message = strip_ansi(event.message or '')[:4000]
        stack_trace = strip_ansi(event.stack_trace or '')[:12000]
        text = f"{event.severity or 'INFO'} {message}"
        if stack_trace:
            text += f"\n{stack_trace}"
        entries.append({
            'id': str(event.id),
            'sequence': sequence,
            'timestamp': timestamp,
            'level': str(event.severity or 'INFO').upper(),
            'logger': str(event.logger_name or ''),
            'message': message,
            'stack_trace': stack_trace,
            'text': text,
        })

    entries.sort(key=lambda item: (int(item.get('sequence') or 0), str(item.get('id') or '')))
    deduped = []
    seen = set()
    for entry in entries:
        key = str(entry.get('id') or entry.get('sequence'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    deduped = deduped[-limit:]

    persistent_latest = max((int(item.get('sequence') or 0) for item in deduped), default=0)
    payload = {
        'entries': deduped,
        'latest_sequence': max(int(local_payload.get('latest_sequence') or 0), persistent_latest),
        'oldest_sequence': min((int(item.get('sequence') or 0) for item in deduped), default=0),
        'reset': bool(local_payload.get('reset')),
        'limit': limit,
    }
    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


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
    event.message = strip_ansi(event.message)
    event.stack_trace = strip_ansi(event.stack_trace)
    for row in related:
        row.message = strip_ansi(row.message)
        row.stack_trace = strip_ansi(row.stack_trace)
    metadata = redact(event.metadata or {}, extra_keys=())
    return render(request, 'paxalia/log_detail.html', {
        'active_page': 'logs', 'page_title': _('Log Detail'),
        'page_subtitle': _('Detailed event, request, correlation, and sanitized metadata'),
        'event': event, 'related': related,
        'metadata_json': json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
        'ai_incident_context': _ai_incident_context(event),
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
            row['stack_trace'] = strip_ansi(event.stack_trace)
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
                _csv_safe(value)
                for value in (
                    event.timestamp.isoformat(), event.severity, event.source, event.category,
                    event.logger_name, strip_ansi(event.message), event.request_method, event.request_path,
                    event.response_status or '', event.traffic_type, event.request_id,
                    event.correlation_id, event.exception_type, event.file_name, event.line_number or '',
                    event.fingerprint, event.group.suppressed_count if event.group else 0,
                )
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

