# paxalia/anomalies.py
"""
Anomaly detection: compares one day's traffic to the same weekday one
week earlier (not the day immediately before), specifically to avoid
flagging ordinary weekday/weekend seasonality as an "anomaly" — a
Monday should be compared to the previous Monday, not to Sunday.

This is intentionally simple (a single week-over-week, same-weekday
comparison) rather than a statistical model (rolling average + std
dev, seasonal decomposition, etc.). Good enough to catch "something
broke" or "something spiked" without pretending to be a real
forecasting system.
"""
from datetime import timedelta

from django.utils import timezone

from paxalia.models import DailySiteStats, Site


def _stats_for(site, date):
    return DailySiteStats.objects.filter(site=site, date=date).first()


def check_anomaly(site, threshold_percent, check_date=None):
    """
    Returns a dict describing the anomaly if one is found, else None:
        {'site': site, 'date': check_date, 'views': int,
         'baseline_views': int, 'change_percent': float, 'direction': 'drop'|'spike'}

    check_date defaults to yesterday (today's data is still partial).
    """
    check_date = check_date or (timezone.now().date() - timedelta(days=1))
    baseline_date = check_date - timedelta(days=7)

    today_stats = _stats_for(site, check_date)
    baseline_stats = _stats_for(site, baseline_date)

    if today_stats is None or baseline_stats is None or baseline_stats.total_views == 0:
        return None  # not enough history yet to compare

    change_percent = round(
        ((today_stats.total_views - baseline_stats.total_views) / baseline_stats.total_views) * 100, 1
    )

    if abs(change_percent) < threshold_percent:
        return None

    return {
        'site': site,
        'date': check_date,
        'views': today_stats.total_views,
        'baseline_views': baseline_stats.total_views,
        'change_percent': change_percent,
        'direction': 'drop' if change_percent < 0 else 'spike',
    }


def check_all_sites(threshold_percent, check_date=None):
    """Runs check_anomaly() for every registered Site plus the
    site=None (unassigned-traffic) bucket. Returns a list of results."""
    sites = list(Site.objects.filter(is_active=True)) + [None]
    results = []
    for site in sites:
        result = check_anomaly(site, threshold_percent, check_date)
        if result:
            results.append(result)
    return results
