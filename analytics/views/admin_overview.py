from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from django.apps import apps

@staff_member_required
def admin_overview(request):
    User = get_user_model()
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)

    # User stats
    total_users = User.objects.count()
    new_users_today = User.objects.filter(date_joined__date=today).count()
    new_users_week = User.objects.filter(date_joined__date__gte=last_7_days).count()
    active_users = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=7)).count()

    # Registrations per day (last 30 days)
    registrations = (
        User.objects
        .filter(date_joined__date__gte=last_30_days)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    reg_dict = {entry['day']: entry['count'] for entry in registrations}

    # Content stats (adjust CONTENT_MODELS to match your project)
    CONTENT_MODELS = ['content.Article', 'content.Page']
    content_total = 0
    content_dict = {}
    for model_str in CONTENT_MODELS:
        try:
            app_label, model_name = model_str.split('.')
            model = apps.get_model(app_label, model_name)
            content_total += model.objects.count()
            if hasattr(model, 'created_at'):
                qs = model.objects.filter(created_at__date__gte=last_30_days)
                daily = (
                    qs.annotate(day=TruncDate('created_at'))
                    .values('day')
                    .annotate(count=Count('id'))
                    .order_by('day')
                )
                for entry in daily:
                    content_dict[entry['day']] = content_dict.get(entry['day'], 0) + entry['count']
        except (LookupError, AttributeError):
            continue

    # Login activity (last 30 days)
    logins = (
        User.objects
        .filter(last_login__date__gte=last_30_days)
        .annotate(day=TruncDate('last_login'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    login_dict = {entry['day']: entry['count'] for entry in logins}

    # Build date range (last 30 days, inclusive)
    date_list = [today - timedelta(days=i) for i in range(29, -1, -1)]
    date_range = [d.isoformat() for d in date_list]  # strings like "2025-03-20"

    reg_counts = [reg_dict.get(d, 0) for d in date_list]
    content_counts = [content_dict.get(d, 0) for d in date_list]
    login_counts = [login_dict.get(d, 0) for d in date_list]

    context = {
        'active_page': 'admin_overview',
        'page_title': 'Admin Overview',
        'page_subtitle': 'Site and user activity at a glance',
        'total_users': total_users,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'active_users': active_users,
        'content_total': content_total,
        'chart_data': {
            'labels': date_range,
            'registrations': reg_counts,
            'content': content_counts,
            'logins': login_counts,
        },
    }
    return render(request, 'analytics/admin_overview.html', context)