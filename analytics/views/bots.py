from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from ..models import PageView, DailySiteStats

@staff_member_required
def bots_overview(request):
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)

    total_bot_views = PageView.objects.filter(is_bot=True).count()
    bot_views_today = PageView.objects.filter(is_bot=True, created_at__date=today).count()
    unique_bot_ips = PageView.objects.filter(is_bot=True).values('ip_hash').distinct().count()

    # Daily bot views (last 30 days)
    stats = DailySiteStats.objects.filter(date__gte=last_30_days).order_by('date')
    dates = [s.date.isoformat() for s in stats]
    bot_counts = [s.bot_views for s in stats]

    # Top bot paths (last 30 days)
    top_paths_qs = (
        PageView.objects
        .filter(is_bot=True, created_at__date__gte=last_30_days)
        .values('path')
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    top_paths = [item['path'] for item in top_paths_qs]
    top_counts = [item['count'] for item in top_paths_qs]

    # Bot requests by country (last 30 days)
    country_qs = (
        PageView.objects
        .filter(is_bot=True, created_at__date__gte=last_30_days)
        .values('country_code')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    country_codes = [c['country_code'] or 'Unknown' for c in country_qs]
    country_counts = [c['count'] for c in country_qs]

    bot_data = {
        'dates': dates,
        'bot_counts': bot_counts,
        'top_paths': top_paths,
        'top_counts': top_counts,
        'country_codes': country_codes,
        'country_counts': country_counts,
    }

    context = {
        'active_page': 'bots',
        'page_title': 'Bot Traffic',
        'page_subtitle': 'Analysis of scanner and bot requests',
        'total_bot_views': total_bot_views,
        'bot_views_today': bot_views_today,
        'unique_bot_ips': unique_bot_ips,
        'bot_data': bot_data,
    }
    return render(request, 'analytics/bots.html', context)