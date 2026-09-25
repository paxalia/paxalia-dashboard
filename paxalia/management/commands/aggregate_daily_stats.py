from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from paxalia.models import PageView, DailySiteStats

class Command(BaseCommand):
    help = 'Aggregate daily stats including session metrics'

    def handle(self, *args, **options):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Build one aggregate row per Site, including the intentional
        # site=None bucket for unmatched hosts. This keeps DailySiteStats
        # semantically aligned with the multi-site PageView model.
        site_ids = list(
            PageView.objects
            .filter(created_at__date=yesterday)
            .values_list('site_id', flat=True)
            .distinct()
        )
        if not site_ids:
            site_ids = [None]

        for site_id in site_ids:
            pageviews = PageView.objects.filter(
                created_at__date=yesterday,
                site_id=site_id,
                is_bot=False,
                is_api=False,
            )
            api_calls_qs = PageView.objects.filter(
                created_at__date=yesterday,
                site_id=site_id,
                is_bot=False,
                is_api=True,
            )

            total_views = pageviews.count()
            unique_ips = pageviews.values('ip_hash').distinct().count()
            unique_users = pageviews.exclude(user=None).values('user').distinct().count()
            api_calls = api_calls_qs.count()

            sessions = pageviews.exclude(session_id='').values('session_id')
            total_sessions = sessions.distinct().count()
            bounce_ids = (
                sessions
                .annotate(cnt=Count('id'))
                .filter(cnt=1)
                .values_list('session_id', flat=True)
            )
            bounces = bounce_ids.count()

            top = (
                pageviews
                .values('path')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )
            top_pages = {item['path']: item['count'] for item in top}

            DailySiteStats.objects.update_or_create(
                site_id=site_id,
                date=yesterday,
                defaults={
                    'total_views': total_views,
                    'unique_ips': unique_ips,
                    'unique_users': unique_users,
                    'api_calls': api_calls,
                    'top_pages': top_pages,
                    'total_sessions': total_sessions,
                    'bounces': bounces,
                    'bot_views': PageView.objects.filter(
                        created_at__date=yesterday,
                        site_id=site_id,
                        is_bot=True,
                    ).count(),
                },
            )

        self.stdout.write(f'Aggregated stats for {yesterday}')

