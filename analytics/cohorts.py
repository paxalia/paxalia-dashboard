# analytics/cohorts.py
"""
Retention analysis: groups visitors into cohorts by the period (week or
month) they were first seen in, then measures what fraction of each
cohort returns in later periods.

VISITOR IDENTITY CAVEAT (documented, not silently glossed over):
There's no persistent cross-session visitor identifier in this package.
What's used here is PageView.session_id, set from the `_analytics_sid`
cookie in middleware.py — a real improvement over using ip_hash (no
shared-IP/dynamic-IP false merging), but that cookie is set once with a
30-day max_age and is never refreshed. A visitor who returns after
their cookie has expired gets a new session_id and shows up as a brand
new visitor in a new cohort, rather than as a returning member of their
original cohort. Practically: weekly cohorts over a 4-5 week lookback
are reasonably meaningful; monthly cohorts beyond ~1 month will
increasingly undercount genuine return visits as more visitors' cookies
expire between the cohort period and the period being measured.
"""
from collections import defaultdict

from django.db.models.functions import TruncWeek, TruncMonth

from analytics.models import PageView

MAX_PERIODS = 12  # hard cap, regardless of what's requested — keeps the
                   # O(cohorts x members) retention loop below bounded


def compute_retention(unit, num_periods, site):
    """
    Returns a list of cohort rows, most recent cohort last is NOT
    guaranteed — sorted oldest-to-newest cohort period, each with:
        {'period': date, 'size': int,
         'offsets': [{'offset': int, 'retained': int, 'pct': float}, ...]}
    """
    num_periods = min(num_periods, MAX_PERIODS)
    trunc_fn = TruncWeek if unit == 'week' else TruncMonth

    qs = PageView.objects.filter(is_bot=False, is_api=False) \
        .exclude(session_id='').exclude(session_id__isnull=True)
    if site is not None:
        qs = qs.filter(site=site)

    # Distinct (session, period) pairs only — this is the expensive part
    # to get wrong: pulling every raw PageView row here instead would
    # scale with total traffic rather than with (visitors x periods
    # visited), which is what actually matters for this computation.
    rows = (
        qs.annotate(period=trunc_fn('created_at'))
          .values('session_id', 'period')
          .distinct()
    )

    visits_by_session = defaultdict(set)
    for row in rows:
        visits_by_session[row['session_id']].add(row['period'])

    if not visits_by_session:
        return []

    first_period_by_session = {
        sid: min(periods) for sid, periods in visits_by_session.items()
    }

    cohort_sessions = defaultdict(set)
    for sid, first in first_period_by_session.items():
        cohort_sessions[first].add(sid)

    all_periods = sorted({p for periods in visits_by_session.values() for p in periods})
    period_index = {p: i for i, p in enumerate(all_periods)}

    cohort_periods = sorted(cohort_sessions.keys())[-num_periods:]

    results = []
    for cohort_period in cohort_periods:
        members = cohort_sessions[cohort_period]
        cohort_idx = period_index[cohort_period]
        max_offset = min(len(all_periods) - 1 - cohort_idx, num_periods - 1)

        offsets = []
        for offset in range(0, max_offset + 1):
            target_period = all_periods[cohort_idx + offset]
            retained = sum(1 for sid in members if target_period in visits_by_session[sid])
            pct = round((retained / len(members)) * 100, 1) if members else 0
            offsets.append({'offset': offset, 'retained': retained, 'pct': pct})

        results.append({'period': cohort_period, 'size': len(members), 'offsets': offsets})

    return results
