"""Dedicated historical authentication activity views."""

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from ..models import LoginEvent
from ..settings import get_config
from ..permissions import require_section_permission
from .utils import detect_active_preset, get_date_range, section_enabled


def _login_queryset(request, mode):
    start_dt, end_dt = get_date_range(request)
    qs = LoginEvent.objects.select_related('user').filter(
        created_at__range=(start_dt, end_dt), event_type='login'
    )
    if mode == 'admin':
        qs = qs.filter(is_admin=True)
    elif mode == 'user':
        qs = qs.filter(is_admin=False)
    elif mode == 'failed':
        qs = qs.filter(result='failed')
    if request.GET.get('result') in {'success', 'failed'}:
        qs = qs.filter(result=request.GET['result'])
    if request.GET.get('failure_category'):
        qs = qs.filter(failure_category=request.GET['failure_category'][:100])
    if request.GET.get('traffic_type'):
        qs = qs.filter(traffic_type=request.GET['traffic_type'][:12])
    if request.GET.get('ip'):
        qs = qs.filter(ip_address=request.GET['ip'][:255])
    if request.GET.get('q'):
        q = request.GET['q'][:200]
        raw_search = request.GET.get('raw', '') == '1'
        search_filter = Q(identifier_hash__startswith=q)
        # Staff-only pages may search by account name when the deployment
        # explicitly permits storing failed usernames. For successful rows,
        # searching the linked user's username is always safe and useful.
        user_model = get_user_model()
        username_field = getattr(user_model, 'USERNAME_FIELD', 'username')
        search_filter |= Q(**{f'user__{username_field}__icontains': q})
        if raw_search or get_config().get('SECURITY_STORE_FAILED_USERNAME', False):
            search_filter |= Q(username_attempted__icontains=q)
        qs = qs.filter(search_filter)
    return qs, start_dt, end_dt


@require_section_permission('security')
def login_activity(request, mode='user'):
    if 'security' not in get_config()['SIDEBAR_SECTIONS']:
        raise Http404
    if mode not in {'user', 'admin', 'failed'}:
        raise Http404
    qs, start_dt, end_dt = _login_queryset(request, mode)
    page_obj = Paginator(qs.order_by('-created_at'), 50).get_page(request.GET.get('page'))
    pagination_query = request.GET.copy()
    pagination_query.pop('page', None)
    counts = qs.aggregate(
        total=Count('id'),
        success=Count('id', filter=Q(result='success')),
        failures=Count('id', filter=Q(result='failed')),
    )
    total = counts['total'] or 0
    success = counts['success'] or 0
    failures = counts['failures'] or 0
    categories = list(
        qs.filter(result='failed')
        .exclude(failure_category='')
        .values('failure_category')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    titles = {
        'user': _('User Login Activity'),
        'admin': _('Admin Login Activity'),
        'failed': _('Failed Login Activity'),
    }
    subtitles = {
        'user': _('Historical sign-ins for non-admin accounts, with privacy-safe failure identifiers'),
        'admin': _('Historical sign-ins for staff and administrator accounts'),
        'failed': _('Authentication attempts rejected by the application'),
    }
    title = titles[mode]
    return render(request, 'paxalia/login_activity.html', {
        'active_page': {'user': 'user_login_activity', 'admin': 'admin_login_activity', 'failed': 'failed_login_activity'}[mode],
        'page_title': title,
        'page_subtitle': subtitles[mode],
        'mode': mode, 'page_obj': page_obj, 'pagination_query': pagination_query, 'total': total, 'success': success,
        'failures': failures, 'categories': categories, 'start_dt': start_dt, 'end_dt': end_dt,
        'active_preset': detect_active_preset(start_dt.date(), end_dt.date()),
        'filters': request.GET,
    })

