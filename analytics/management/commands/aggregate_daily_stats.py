from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from analytics.models import PageView, DailySiteStats

class Command(BaseCommand):
    help = 'Aggregate daily stats including session metrics'

    def handle(self, *args, **options):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # "Page view" metrics below deliberately exclude API calls (is_api=True)
        # so Overview/Pages/Traffic/Geography numbers reflect human page
        # traffic, not API requests. API volume is aggregated separately
        # into api_calls.
        pageviews = PageView.objects.filter(created_at__date=yesterday, is_bot=False, is_api=False)
        api_calls_qs = PageView.objects.filter(created_at__date=yesterday, is_bot=False, is_api=True)

        total_views = pageviews.count()
        unique_ips = pageviews.values('ip_hash').distinct().count()
        unique_users = pageviews.exclude(user=None).values('user').distinct().count()
        api_calls = api_calls_qs.count()

        # Session stats
        sessions = pageviews.exclude(session_id='', is_bot=False).values('session_id')
        total_sessions = sessions.distinct().count()

        # Bounces: sessions with only 1 page view
        bounce_ids = (
            sessions
            .annotate(cnt=Count('id'))
            .filter(cnt=1)
            .values_list('session_id', flat=True)
        )
        bounces = bounce_ids.count()

        # Top pages
        top = (
            pageviews
            .filter(is_bot=False)
            .values('path')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        top_pages = {item['path']: item['count'] for item in top}

        stats, _ = DailySiteStats.objects.update_or_create(
            date=yesterday,
            defaults={
                'total_views': total_views,
                'unique_ips': unique_ips,
                'unique_users': unique_users,
                'api_calls': api_calls,
                'top_pages': top_pages,
                'total_sessions': total_sessions,
                'bounces': bounces,
            }
        )
        self.stdout.write(f'Aggregated stats for {yesterday}')