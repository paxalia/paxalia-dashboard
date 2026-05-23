# analytics/views/export.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import Http404
from django.http import HttpResponse

from .utils import get_date_range, parse_user_agent, get_billing_models

from analytics.settings import get_config
from analytics.models import PageView, AnalyticsEvent

import json
import csv


# Create your views here.


@staff_member_required
def analytics_export(request, export_type):
    """
    Export analytics data as CSV or JSON, respecting the current date filter
    and path search (for Pages).  Accepts ?format=csv (default) or ?format=json.
    """
    start_dt, end_dt = get_date_range(request)
    fmt = request.GET.get('format', 'csv').lower()
    if fmt not in ('csv', 'json'):
        raise Http404("Invalid format")

    # Helper: return the correct HttpResponse for the chosen format
    def build_response(filename_base, headers, rows):
        if fmt == 'json':
            payload = [dict(zip(headers, row)) for row in rows]
            response = HttpResponse(
                json.dumps(payload, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.json"'
            return response
        else:  # csv
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
            return response

    # ── 1. Overview – Top Pages table ──
    if export_type == 'overview_top_pages':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        top_pages = (
            base_qs.values('path')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        rows = [[item['path'], item['count']] for item in top_pages]
        return build_response(
            f'top_pages_{start_dt.date()}_{end_dt.date()}',
            ['Page', 'Views'],
            rows,
        )

    # ── 2. Pages list ──
    elif export_type == 'pages':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        path_query = request.GET.get('path', '').strip()
        if path_query:
            base_qs = base_qs.filter(path__icontains=path_query)
        pages = (
            base_qs.values('path')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        rows = [[item['path'], item['count']] for item in pages]
        return build_response(
            f'pages_{start_dt.date()}_{end_dt.date()}',
            ['Page', 'Views'],
            rows,
        )

    # ── 3. API – Top Endpoints table ──
    elif export_type == 'api_endpoints':
        api_prefix = get_config()['API_PATH_PREFIX']
        api_qs = PageView.objects.filter(
            created_at__range=(start_dt, end_dt),
            path__startswith=api_prefix,
        )
        top_eps = (
            api_qs.values('path')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        rows = [[ep['path'], ep['count']] for ep in top_eps]
        return build_response(
            f'api_endpoints_{start_dt.date()}_{end_dt.date()}',
            ['Endpoint', 'Calls'],
            rows,
        )

    # ── 4. API – Status Codes table ──
    elif export_type == 'api_status':
        api_prefix = get_config()['API_PATH_PREFIX']
        api_qs = PageView.objects.filter(
            created_at__range=(start_dt, end_dt),
            path__startswith=api_prefix,
        )
        status = (
            api_qs.values('status_code')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        rows = [[s['status_code'], s['count']] for s in status]
        return build_response(
            f'api_status_{start_dt.date()}_{end_dt.date()}',
            ['Status Code', 'Count'],
            rows,
        )

    # ── 5. Traffic – Referrers table ──
    elif export_type == 'traffic_referrers':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        referrers = (
            base_qs.exclude(referrer='')
            .values('referrer')
            .annotate(count=Count('id'))
            .order_by('-count')[:15]
        )
        rows = [[r['referrer'], r['count']] for r in referrers]
        return build_response(
            f'referrers_{start_dt.date()}_{end_dt.date()}',
            ['Referrer', 'Visits'],
            rows,
        )

    # ── 6. Traffic – Browser Distribution table ──
    elif export_type == 'traffic_browsers':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        raw = base_qs.values('user_agent').annotate(count=Count('id'))
        counts = {}
        for item in raw:
            ua = item.get('user_agent', '').lower()
            if 'firefox' in ua:
                name = 'Firefox'
            elif 'edg' in ua:
                name = 'Edge'
            elif 'chrome' in ua and 'safari' in ua:
                name = 'Chrome'
            elif 'safari' in ua:
                name = 'Safari'
            elif 'opera' in ua or 'opr' in ua:
                name = 'Opera'
            else:
                name = 'Other'
            counts[name] = counts.get(name, 0) + item['count']
        rows = sorted([[k, v] for k, v in counts.items()], key=lambda x: x[1], reverse=True)
        return build_response(
            f'browsers_{start_dt.date()}_{end_dt.date()}',
            ['Browser', 'Visits'],
            rows,
        )

    # ── 7. Traffic – Operating Systems ──
    elif export_type == 'traffic_os':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        raw = base_qs.values('user_agent').annotate(count=Count('id'))
        counts = {}
        for item in raw:
            ua_string = item.get('user_agent', '')
            parsed = parse_user_agent(ua_string)
            os_name = parsed['os']
            cnt = item['count']
            counts[os_name] = counts.get(os_name, 0) + cnt
        rows = sorted([[k, v] for k, v in counts.items()], key=lambda x: x[1], reverse=True)
        return build_response(
            f'os_{start_dt.date()}_{end_dt.date()}',
            ['Operating System', 'Views'],
            rows,
        )

    # ── 8. Traffic – Device Types ──
    elif export_type == 'traffic_devices':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        raw = base_qs.values('user_agent').annotate(count=Count('id'))
        counts = {}
        for item in raw:
            ua_string = item.get('user_agent', '')
            parsed = parse_user_agent(ua_string)
            device = parsed['device']
            cnt = item['count']
            counts[device] = counts.get(device, 0) + cnt
        rows = sorted([[k, v] for k, v in counts.items()], key=lambda x: x[1], reverse=True)
        return build_response(
            f'devices_{start_dt.date()}_{end_dt.date()}',
            ['Device', 'Views'],
            rows,
        )

    # ── 9. Geography ──
    elif export_type == 'geography_countries':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        countries = (
            base_qs
            .exclude(country_code='')
            .values('country_code', 'country_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        rows = [[c['country_name'], c['country_code'], c['count']] for c in countries]
        return build_response(
            f'countries_{start_dt.date()}_{end_dt.date()}',
            ['Country', 'Code', 'Visitors'],
            rows,
        )

    elif export_type == 'geography_cities':
        base_qs = PageView.objects.filter(created_at__range=(start_dt, end_dt))
        cities = (
            base_qs.exclude(city='')
            .values('city', 'country_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:20]
        )
        rows = [[c['city'], c['country_name'], c['count']] for c in cities]
        return build_response(
            f'cities_{start_dt.date()}_{end_dt.date()}',
            ['City', 'Country', 'Visitors'],
            rows,
        )

    # ── 10. Events ──
    elif export_type == 'events_labels':
        qs = AnalyticsEvent.objects.filter(created_at__range=(start_dt, end_dt))
        lbls = qs.exclude(label='').values('label').annotate(count=Count('id')).order_by('-count')
        rows = [[l['label'], l['count']] for l in lbls]
        return build_response(f'events_labels_{start_dt.date()}_{end_dt.date()}', ['Label', 'Events'], rows)

    elif export_type == 'events_pages':
        qs = AnalyticsEvent.objects.filter(created_at__range=(start_dt, end_dt))
        pgs = qs.values('path').annotate(count=Count('id')).order_by('-count')
        rows = [[p['path'], p['count']] for p in pgs]
        return build_response(f'events_pages_{start_dt.date()}_{end_dt.date()}', ['Page', 'Events'], rows)

    elif export_type == 'events_recent':
        events_qs = AnalyticsEvent.objects.filter(created_at__range=(start_dt, end_dt))
        recent = events_qs.order_by('-created_at')[:50]
        rows = [
            [e.created_at.strftime('%Y-%m-%d %H:%M:%S'), e.category, e.action, e.label or '', e.path]
            for e in recent
        ]
        return build_response(
            f'events_recent_{start_dt.date()}_{end_dt.date()}',
            ['Time', 'Category', 'Action', 'Label', 'Page'],
            rows,
        )

    # ── 11. Billing ──
    elif export_type == 'billing_plans':
        _, UserPlan, _ = get_billing_models()
        if not UserPlan:
            raise Http404
        plans = UserPlan.objects.exclude(current_plan__isnull=True).values('current_plan__slug').annotate(count=Count('id'))
        rows = [[p['current_plan__slug'], p['count']] for p in plans]
        return build_response(f'billing_plans_{start_dt.date()}_{end_dt.date()}', ['Plan', 'Users'], rows)

    elif export_type == 'billing_invoices':
        Invoice, _, _ = get_billing_models()
        if not Invoice:
            raise Http404
        invoices = Invoice.objects.filter(date__range=(start_dt.date(), end_dt.date()), status='paid')
        rows = [[i.invoice_number, i.user.username, str(i.amount), str(i.date)] for i in invoices]
        return build_response(f'invoices_{start_dt.date()}_{end_dt.date()}', ['Invoice', 'User', 'Amount', 'Date'], rows)

    # Fallback
    raise Http404("Invalid export type")
