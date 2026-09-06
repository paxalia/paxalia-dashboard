# analytics/conversions.py
"""
Goal and funnel completion logic. Both are computed on the fly against
PageView/AnalyticsEvent — there's no separate "completion" log table,
since the underlying visit/event data already exists.

FUNNEL LIMITATION (documented, not silently approximated): true funnel
semantics require strict ordering — a session should only count as
having reached step 2 if step 1 happened first, in the same session.
Computing that exactly means walking each session's events in
timestamp order in Python, which doesn't scale well against a large
date range purely in SQL. What's implemented here is the common,
cheaper approximation many lightweight analytics tools use: a session
"reached" step N if it matches all of steps 1..N at any point in the
date range, regardless of order. This means the reported drop-off is a
lower bound on the true drop-off (some sessions counted as "reaching"
step 3 might have actually hit it before step 1). Good enough for a
directional view of where people fall off; not a substitute for a
strictly-ordered funnel tool.
"""
from analytics.models import PageView, AnalyticsEvent


def _matching_session_ids(match_type, match_value, start_dt, end_dt, site):
    """Return a set of distinct session_ids matching a Goal/FunnelStep's
    (type, value) within the date range and site."""
    if match_type == 'page':
        qs = PageView.objects.filter(
            path=match_value, created_at__range=(start_dt, end_dt), is_bot=False,
        )
        if site is not None:
            qs = qs.filter(site=site)
        return set(qs.exclude(session_id='').exclude(session_id__isnull=True)
                     .values_list('session_id', flat=True).distinct())

    if match_type == 'event':
        if ':' not in match_value:
            return set()
        category, _, action = match_value.partition(':')
        qs = AnalyticsEvent.objects.filter(
            category=category, action=action, created_at__range=(start_dt, end_dt),
        )
        if site is not None:
            qs = qs.filter(site=site)
        return set(qs.exclude(session_id='').exclude(session_id__isnull=True)
                     .values_list('session_id', flat=True).distinct())

    return set()


def goal_conversion(goal, start_dt, end_dt, site, total_sessions):
    """Return (completed_session_count, conversion_rate_percent) for a Goal."""
    sessions = _matching_session_ids(goal.goal_type, goal.match_value, start_dt, end_dt, site)
    completed = len(sessions)
    rate = round((completed / total_sessions) * 100, 1) if total_sessions else 0
    return completed, rate


def funnel_dropoff(funnel, start_dt, end_dt, site):
    """
    Return a list of dicts, one per step, in order:
        [{'step': FunnelStep, 'sessions': int, 'pct_of_step_1': float,
          'pct_of_previous': float}, ...]

    See the module docstring for the ordering caveat.
    """
    steps = list(funnel.steps.order_by('order'))
    results = []
    running_intersection = None
    step_1_count = None

    for step in steps:
        step_sessions = _matching_session_ids(step.step_type, step.match_value, start_dt, end_dt, site)
        running_intersection = step_sessions if running_intersection is None else (running_intersection & step_sessions)
        count = len(running_intersection)
        if step_1_count is None:
            step_1_count = count or 1  # avoid division by zero if step 1 itself is empty

        prev_count = results[-1]['sessions'] if results else count
        results.append({
            'step': step,
            'sessions': count,
            'pct_of_step_1': round((count / step_1_count) * 100, 1),
            'pct_of_previous': round((count / prev_count) * 100, 1) if prev_count else 0,
        })

    return results
