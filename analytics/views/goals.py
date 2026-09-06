# analytics/views/goals.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.conversions import goal_conversion, funnel_dropoff
from analytics.models import Goal, Funnel, FunnelStep, PageView

from .utils import get_date_range, section_enabled, get_current_site, site_scoped


@staff_member_required
def goals_management(request):
    if not section_enabled('goals'):
        raise Http404

    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)

    if request.method == 'POST' and 'save_goal' in request.POST:
        name = request.POST.get('name', '').strip()
        goal_type = request.POST.get('goal_type')
        match_value = request.POST.get('match_value', '').strip()
        if not name or goal_type not in ('page', 'event') or not match_value:
            messages.error(request, _('Name, type, and match value are all required.'))
        else:
            Goal.objects.create(
                site=current_site, name=name, goal_type=goal_type, match_value=match_value,
            )
            messages.success(request, _('Goal created.'))
        return redirect('analytics:goals')

    goals = Goal.objects.filter(is_active=True)
    if current_site is not None:
        goals = goals.filter(site=current_site)

    total_sessions = site_scoped(
        PageView.objects.filter(created_at__range=(start_dt, end_dt), is_bot=False, is_api=False),
        current_site,
    ).exclude(session_id='').exclude(session_id__isnull=True).values('session_id').distinct().count()

    goal_rows = []
    for goal in goals:
        completed, rate = goal_conversion(goal, start_dt, end_dt, current_site, total_sessions)
        goal_rows.append({'goal': goal, 'completed': completed, 'rate': rate})

    context = {
        'active_page': 'goals',
        'page_title': _('Goals'),
        'page_subtitle': _('Conversion rate for each goal in the selected date range'),
        'goal_rows': goal_rows,
        'total_sessions': total_sessions,
        'show_search': False,
    }
    return render(request, 'analytics/goals.html', context)


@staff_member_required
@require_POST
def goal_delete(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id)
    goal.delete()
    messages.success(request, _('Goal deleted.'))
    return redirect('analytics:goals')


@staff_member_required
def funnels_management(request):
    if not section_enabled('funnels'):
        raise Http404

    current_site = get_current_site(request)
    start_dt, end_dt = get_date_range(request)

    if request.method == 'POST' and 'save_funnel' in request.POST:
        name = request.POST.get('name', '').strip()
        step_names = request.POST.getlist('step_name')
        step_types = request.POST.getlist('step_type')
        step_values = request.POST.getlist('step_value')

        if not name or not step_names or any(not v.strip() for v in step_values):
            messages.error(request, _('Funnel name and every step value are required.'))
        else:
            funnel = Funnel.objects.create(site=current_site, name=name)
            for i, (s_name, s_type, s_value) in enumerate(zip(step_names, step_types, step_values), start=1):
                if not s_value.strip():
                    continue
                FunnelStep.objects.create(
                    funnel=funnel, order=i,
                    name=s_name.strip() or f'Step {i}',
                    step_type=s_type, match_value=s_value.strip(),
                )
            messages.success(request, _('Funnel created.'))
        return redirect('analytics:funnels')

    funnels = Funnel.objects.prefetch_related('steps')
    if current_site is not None:
        funnels = funnels.filter(site=current_site)

    funnel_reports = [
        {'funnel': funnel, 'dropoff': funnel_dropoff(funnel, start_dt, end_dt, current_site)}
        for funnel in funnels
    ]

    context = {
        'active_page': 'funnels',
        'page_title': _('Funnels'),
        'page_subtitle': _('Step-by-step drop-off for the selected date range'),
        'funnel_reports': funnel_reports,
        'show_search': False,
    }
    return render(request, 'analytics/funnels.html', context)


@staff_member_required
@require_POST
def funnel_delete(request, funnel_id):
    funnel = get_object_or_404(Funnel, id=funnel_id)
    funnel.delete()
    messages.success(request, _('Funnel deleted.'))
    return redirect('analytics:funnels')
