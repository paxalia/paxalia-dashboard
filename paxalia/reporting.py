# paxalia/reporting.py
"""
compute_overview_snapshot() is the one place that computes a
traffic summary — used by both the scheduled email/PDF report
(management/commands/send_scheduled_reports.py) and the public
read-only shared link view (views/share_links.py::shared_dashboard_view).
Deliberately a smaller, simpler snapshot than the full authenticated
Overview page (no period-comparison toggle, no annotations, no segment
filter) — good enough for "here's how the site did," not a
replacement for the dashboard itself.
"""
from django.db.models import Count
from django.db.models.functions import TruncDate

from paxalia.models import PageView


def compute_overview_snapshot(start_dt, end_dt, site):
    qs = PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False, is_api=False)
    if site is not None:
        qs = qs.filter(site=site)

    total_views = qs.count()
    unique_visitors = qs.exclude(session_id='').exclude(session_id__isnull=True) \
        .values('session_id').distinct().count()

    daily = list(
        qs.annotate(day=TruncDate('created_at'))
          .values('day').annotate(count=Count('id')).order_by('day')
    )
    top_pages = list(
        qs.values('path').annotate(count=Count('id')).order_by('-count')[:10]
    )
    top_referrers = list(
        qs.exclude(referrer='').values('referrer').annotate(count=Count('id')).order_by('-count')[:5]
    )

    return {
        'site': site,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'total_views': total_views,
        'unique_visitors': unique_visitors,
        'daily': daily,
        'top_pages': top_pages,
        'top_referrers': top_referrers,
    }
