# paxalia/rum.py
"""
Real User Monitoring — Core Web Vitals aggregation and JS error
grouping, computed from data collected client-side by
paxalia-events.js (Web Vitals ride on the existing AnalyticsEvent
model, category='web_vitals'; JS errors get their own JSError model —
see models.py for why).

CORE WEB VITALS CAVEATS (read before trusting these numbers blindly):

- The industry-standard aggregation is the 75th percentile of field
  data, not the average — a single slow device/connection shouldn't
  be allowed to average out into an invisible blip, but it also
  shouldn't be the number everyone chases either. That's what
  _percentile() below computes; there is no "average" reported here
  on purpose.
- LCP and INP are measured natively via PerformanceObserver in the
  browser — see paxalia-events.js — and match the metrics'
  standard definitions closely.
- CLS uses a simplified session-window algorithm: shifts are grouped
  into a session (gap < 1s between shifts, session capped at 5s
  total) and the max session total is reported, which matches the
  current official CLS definition.
- INP here is the single largest interaction duration observed on the
  page, not the full "high-percentile of all interactions" algorithm
  the very latest spec uses for pages with dozens of interactions —
  documented as a simplification in paxalia-events.js. For a typical
  page with a handful of interactions this converges to the same
  number; it will run slightly pessimistic on highly-interactive pages
  (a single-page app with continuous interaction).

Rating thresholds below are Google's published "good / needs
improvement / poor" boundaries as of this package's last update — they
occasionally change; check web.dev/vitals if a rating looks off.
"""
from django.db.models import Count, Max, Min

from .models import AnalyticsEvent, JSError

# (good_max, needs_improvement_max) — anything above the second value
# is 'poor'. LCP/INP in milliseconds, CLS unitless.
RATING_THRESHOLDS = {
    'LCP': (2500, 4000),
    'CLS': (0.1, 0.25),
    'INP': (200, 500),
}

METRIC_LABELS = {
    'LCP': 'Largest Contentful Paint',
    'CLS': 'Cumulative Layout Shift',
    'INP': 'Interaction to Next Paint',
}


def rate_metric(metric, value):
    """Return 'good' / 'needs-improvement' / 'poor', or None if unrated."""
    thresholds = RATING_THRESHOLDS.get(metric)
    if thresholds is None or value is None:
        return None
    good_max, ni_max = thresholds
    if value <= good_max:
        return 'good'
    if value <= ni_max:
        return 'needs-improvement'
    return 'poor'


def _percentile(sorted_values, pct):
    """Linear-interpolation percentile of an already-sorted list."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def compute_web_vitals_summary(start_dt, end_dt, site=None):
    """
    Return {metric: {'p75', 'rating', 'sample_count', 'good_pct',
    'needs_improvement_pct', 'poor_pct'}} for LCP/CLS/INP. A metric
    with no samples in range gets sample_count=0 and everything else
    None — the template shows an empty state rather than a fake zero.
    """
    qs = AnalyticsEvent.objects.filter(
        category='web_vitals', created_at__range=(start_dt, end_dt)
    )
    if site is not None:
        qs = qs.filter(site=site)

    summary = {}
    for metric in RATING_THRESHOLDS:
        values = sorted(
            v for v in qs.filter(action=metric).values_list('value', flat=True) if v is not None
        )
        if not values:
            summary[metric] = {
                'label': METRIC_LABELS[metric], 'sample_count': 0, 'p75': None,
                'rating': None, 'good_pct': None, 'needs_improvement_pct': None, 'poor_pct': None,
            }
            continue

        p75 = _percentile(values, 75)
        ratings = [rate_metric(metric, v) for v in values]
        total = len(ratings)
        summary[metric] = {
            'label': METRIC_LABELS[metric],
            'sample_count': total,
            'p75': round(p75, 3 if metric == 'CLS' else 0),
            'rating': rate_metric(metric, p75),
            'good_pct': round(100 * ratings.count('good') / total, 1),
            'needs_improvement_pct': round(100 * ratings.count('needs-improvement') / total, 1),
            'poor_pct': round(100 * ratings.count('poor') / total, 1),
        }
    return summary


def compute_top_js_errors(start_dt, end_dt, site=None, limit=20):
    """
    JS errors grouped by message (the vast majority of dedup value is
    in the message text alone — grouping in filename/lineno too would
    split the same error across minified-build hashes that change
    every deploy). Returns a list of {message, count, first_seen,
    last_seen, sample_path} ordered by count desc.
    """
    qs = JSError.objects.filter(created_at__range=(start_dt, end_dt))
    if site is not None:
        qs = qs.filter(site=site)

    grouped = (
        qs.values('message')
        .annotate(count=Count('id'), first_seen=Min('created_at'), last_seen=Max('created_at'))
        .order_by('-count')[:limit]
    )
    results = []
    for row in grouped:
        sample = qs.filter(message=row['message']).order_by('-created_at').values('path', 'filename', 'lineno').first()
        results.append({
            'message': row['message'],
            'count': row['count'],
            'first_seen': row['first_seen'],
            'last_seen': row['last_seen'],
            'sample_path': sample['path'] if sample else '',
            'sample_location': f"{sample['filename']}:{sample['lineno']}" if sample and sample['filename'] else '',
        })
    return results
