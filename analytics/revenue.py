# analytics/revenue.py
"""
Revenue analytics built strictly on the documented billing contract
(see README's "Billing Integration" table) — Invoice.{date, amount,
status, user}, UserPlan.{user, current_plan.slug}. Nothing here reads
a field beyond that contract, since this package doesn't own billing
data and can't assume a consuming project's Invoice/UserPlan model has
anything more than what's documented.

That constraint shapes every metric below:

MRR / ARR: there is no documented subscription-price field (a Plan's
`slug` is guaranteed, its price is not), so "MRR" here is an
invoice-based proxy — the sum of 'paid' invoices in a calendar month —
not the textbook "sum of active subscription values" definition. Track
it as a revenue-collected trend, not a promise of future recurring
revenue. ARR is presented as a run-rate (current month's proxy-MRR ×
12), not trailing-twelve-months actual revenue — both are labeled as
such in the UI, not just here.

Churn: there is no subscription start/cancel timestamp either, only
`current_plan` as a point-in-time snapshot (see UserPlan.current_plan
usage in views/billing.py — NULL means "no active plan right now", but
there's no record of *when* it went NULL). So churn here is computed
purely from invoice history: a user counts as churned for month M if
they had a 'paid' invoice in month M-1 but none in month M. This is a
standard "billing-history churn" proxy and needs nothing beyond the
documented Invoice fields, but it will miss a customer who churns and
re-subscribes within the same lookback, and it can't distinguish
"canceled" from "payment coincidentally didn't fall in this window"
for irregular (non-monthly) billing cycles.

Dunning: 'paid' is the only invoice status this package's contract
defines. Anything else (whatever a project's Invoice.status vocabulary
actually contains — 'pending', 'failed', 'overdue', 'refunded', ...)
is grouped generically as "not paid" rather than matched against a
hardcoded set of expected status strings.
"""
from datetime import date, timedelta

from django.db.models import Count, Sum


def _month_bounds(year, month):
    """Return (first_day, last_day) date objects for a calendar month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _shift_month(year, month, delta):
    """Return (year, month) for `delta` months before/after (year, month)."""
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, idx % 12 + 1


def compute_monthly_revenue_trend(Invoice, today=None, num_months=12):
    """
    Trailing `num_months` calendar months of 'paid' invoice totals,
    oldest first, including the current (partial) month. Returns
    {'labels': [...], 'values': [...], 'current_month_revenue': float,
    'projected_arr': float}.
    """
    today = today or date.today()
    labels, values = [], []

    for i in range(num_months - 1, -1, -1):
        y, m = _shift_month(today.year, today.month, -i)
        start, end = _month_bounds(y, m)
        end = min(end, today)  # cap the current, still-in-progress month
        total = Invoice.objects.filter(
            date__range=(start, end), status='paid'
        ).aggregate(t=Sum('amount'))['t'] or 0
        labels.append(start.strftime('%b %Y'))
        values.append(float(total))

    current_month_revenue = values[-1] if values else 0.0
    return {
        'labels': labels,
        'values': values,
        'current_month_revenue': current_month_revenue,
        'projected_arr': current_month_revenue * 12,
    }


def compute_churn(Invoice, today=None):
    """
    Customer + revenue churn between the last two FULLY completed
    calendar months (the current, still-in-progress month is skipped
    entirely to avoid comparing a partial month against a full one).

    Returns None if there isn't enough invoice history yet (no paying
    customers in the baseline month), otherwise:
        {'baseline_label', 'following_label',
         'baseline_customers', 'churned_customers', 'customer_churn_pct',
         'baseline_revenue', 'churned_revenue', 'revenue_churn_pct'}
    """
    today = today or date.today()
    base_y, base_m = _shift_month(today.year, today.month, -2)
    foll_y, foll_m = _shift_month(today.year, today.month, -1)
    base_start, base_end = _month_bounds(base_y, base_m)
    foll_start, foll_end = _month_bounds(foll_y, foll_m)

    baseline_invoices = Invoice.objects.filter(
        date__range=(base_start, base_end), status='paid'
    )
    baseline_by_user = (
        baseline_invoices.values('user_id').annotate(total=Sum('amount'))
    )
    baseline_user_totals = {row['user_id']: row['total'] for row in baseline_by_user}
    if not baseline_user_totals:
        return None

    following_payers = set(
        Invoice.objects.filter(
            date__range=(foll_start, foll_end), status='paid'
        ).values_list('user_id', flat=True)
    )

    churned_user_ids = set(baseline_user_totals) - following_payers
    baseline_revenue = sum(baseline_user_totals.values())
    churned_revenue = sum(baseline_user_totals[uid] for uid in churned_user_ids)

    return {
        'baseline_label': base_start.strftime('%b %Y'),
        'following_label': foll_start.strftime('%b %Y'),
        'baseline_customers': len(baseline_user_totals),
        'churned_customers': len(churned_user_ids),
        'customer_churn_pct': round(len(churned_user_ids) / len(baseline_user_totals) * 100, 1),
        'baseline_revenue': float(baseline_revenue),
        'churned_revenue': float(churned_revenue),
        'revenue_churn_pct': round(float(churned_revenue) / float(baseline_revenue) * 100, 1) if baseline_revenue else 0.0,
    }


def compute_dunning(Invoice, lookback_days=90, limit=50):
    """
    Every non-'paid' invoice in the lookback window, generic to
    whatever status vocabulary the project's Invoice model actually
    uses. Returns {'summary': [{'status', 'count', 'total'}, ...],
    'recent': <queryset, select_related('user'), most recent first>}.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    qs = Invoice.objects.exclude(status='paid').filter(date__gte=cutoff)

    summary = list(
        qs.values('status').annotate(count=Count('id'), total=Sum('amount')).order_by('-count')
    )
    for row in summary:
        row['total'] = float(row['total'] or 0)

    recent = qs.select_related('user').order_by('-date')[:limit]
    return {'summary': summary, 'recent': recent}
