# analytics/views/notifications.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from analytics.models import Notification

from .utils import section_enabled, get_current_site


@staff_member_required
def notifications_list(request):
    if not section_enabled('notifications'):
        raise Http404

    current_site = get_current_site(request)

    notifications = Notification.objects.select_related('site')
    if current_site is not None:
        notifications = notifications.filter(site=current_site)

    context = {
        'active_page': 'notifications',
        'page_title': _('Notifications'),
        'page_subtitle': _('Anomalies, security events, and report activity'),
        'notifications': notifications[:200],
        'show_search': False,
    }
    return render(request, 'analytics/notifications.html', context)


@staff_member_required
@require_POST
def notification_mark_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return redirect('analytics:notifications')


@staff_member_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    messages.success(request, _('All notifications marked as read.'))
    return redirect('analytics:notifications')
