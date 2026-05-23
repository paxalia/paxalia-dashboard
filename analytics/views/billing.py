# analytics/views/billing.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count
from django.http import Http404
from django.db.models import Sum

from .utils import get_date_range, detect_active_preset, get_billing_models, section_enabled

from datetime import timedelta


# Create your views here.

@staff_member_required
def analytics_billing(request):
    if not section_enabled('billing'):
        raise Http404("Billing section is disabled")
    Invoice, UserPlan, Donation = get_billing_models()
    if not Invoice:
        raise Http404("Billing models not available")

    start_dt, end_dt = get_date_range(request)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Base queryset for invoices in the selected range
    invoice_qs = Invoice.objects.filter(
        date__range=(start_dt.date(), end_dt.date()),
        status='paid'
    )

    # Total revenue (all-time)
    total_revenue = Invoice.objects.filter(status='paid').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Today & yesterday revenue
    today_revenue = Invoice.objects.filter(
        date=today, status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0
    yesterday_revenue = Invoice.objects.filter(
        date=yesterday, status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # This month revenue
    first_of_month = today.replace(day=1)
    month_revenue = Invoice.objects.filter(
        date__gte=first_of_month, status='paid'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Daily income chart for the selected range
    daily_income = (
        invoice_qs
        .values('date')
        .annotate(income=Sum('amount'))
        .order_by('date')
    )
    chart_labels = [d['date'].strftime('%b %d') for d in daily_income]
    chart_income = [float(d['income']) for d in daily_income]

    # Top plans – count users per current_plan
    top_plans = (
        UserPlan.objects
        .exclude(current_plan__isnull=True)
        .values('current_plan__slug')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Recent invoices
    recent_invoices = (
        invoice_qs
        .select_related('user')
        .order_by('-date', '-id')[:20]
    )

    # Active subscriptions count
    active_subscriptions = UserPlan.objects.exclude(current_plan__isnull=True).count()

    # Total donations (all-time)
    total_donations = Donation.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Compare to previous period
    compare_active = request.GET.get('compare') == '1'
    previous_labels = []
    previous_income = []
    if compare_active:
        period_delta = (end_dt.date() - start_dt.date()).days
        prev_end = start_dt.date() - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_delta)
        prev_qs = Invoice.objects.filter(
            date__range=(prev_start, prev_end), status='paid'
        )
        prev_daily = (
            prev_qs
            .values('date')
            .annotate(income=Sum('amount'))
            .order_by('date')
        )
        previous_labels = [d['date'].strftime('%b %d') for d in prev_daily]
        previous_income = [float(d['income']) for d in prev_daily]

    active_preset = detect_active_preset(start_dt.date(), end_dt.date())
    date_range_label = f"{start_dt.date()} – {end_dt.date()}"

    context = {
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'yesterday_revenue': yesterday_revenue,
        'month_revenue': month_revenue,
        'active_subscriptions': active_subscriptions,
        'total_donations': total_donations,
        'chart_labels': chart_labels,
        'chart_income': chart_income,
        'top_plans': top_plans,
        'recent_invoices': recent_invoices,
        'compare_active': compare_active,
        'previous_labels': previous_labels,
        'previous_income': previous_income,
        'start_date': start_dt.date(),
        'end_date': end_dt.date(),
        'active_preset': active_preset,
        'date_range_label': date_range_label,
        'show_search': False,
        'active_page': 'billing',
    }
    return render(request, 'analytics/billing.html', context)
