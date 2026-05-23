import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count
from analytics.models import PageView, DailySiteStats, AnalyticsEvent
from analytics.settings import get_config
from django.contrib.auth.models import User

PAGES = [
    '/', '/blog/', '/blog/test-article/',
    '/journey/', '/challenges/', '/careers/',
    '/pricing/', '/faq/', '/contact/', '/press-media/',
    '/download/', '/download/linux/', '/download/windows/',
    '/api/timer/start/', '/api/timer/stop/',
]

COUNTRY_POOL = [
    ('US', 'United States', ['New York', 'Los Angeles', 'Chicago', 'Houston']),
    ('DE', 'Germany', ['Berlin', 'Munich', 'Hamburg', 'Frankfurt']),
    ('IN', 'India', ['Mumbai', 'Delhi', 'Bangalore', 'Chennai']),
    ('BR', 'Brazil', ['São Paulo', 'Rio de Janeiro', 'Brasília']),
    ('GB', 'United Kingdom', ['London', 'Manchester', 'Birmingham']),
    ('JP', 'Japan', ['Tokyo', 'Osaka', 'Kyoto']),
    ('FR', 'France', ['Paris', 'Lyon', 'Marseille']),
    ('CA', 'Canada', ['Toronto', 'Vancouver', 'Montreal']),
    ('AU', 'Australia', ['Sydney', 'Melbourne', 'Brisbane']),
    ('NG', 'Nigeria', ['Lagos', 'Abuja', 'Kano']),
]

COUNTRY_WEIGHTS = [25, 20, 18, 8, 7, 6, 5, 5, 4, 2]   # sum = 100

class Command(BaseCommand):
    help = 'Generate 30 days of fake analytics, events, and optional billing data'

    def handle(self, *args, **options):
        today = timezone.now().date()
        start = today - timedelta(days=30)

        # ── Optional billing setup ──
        try:
            from billing.models import BillingInvoice, UserBilling, PricingTier

            plans = list(PricingTier.objects.filter(is_active=True))
            if not plans:
                plan = PricingTier.objects.create(
                    slug='free',
                    price_amount=0,
                    price_currency='USD',
                )
                plan.set_current_language('en')
                plan.name = 'Free'
                plan.save()
                plans = [plan]

            # demo user for invoices
            billing_user, _ = User.objects.get_or_create(
                username='analytics-demo',
                defaults={'email': 'demo@example.com'}
            )

            billing_available = True
        except ImportError:
            plans = []
            billing_user = None
            billing_available = False

        # ── Generate daily data ──
        for day_offset in range(30):
            date = start + timedelta(days=day_offset)
            num_views = random.randint(50, 250)
            num_sessions = random.randint(10, 40)
            session_ids = [uuid.uuid4().hex for _ in range(num_sessions)]

            # Page views
            for _ in range(num_views):
                path = random.choice(PAGES)
                session_id = random.choice(session_ids)
                country = random.choices(COUNTRY_POOL, weights=COUNTRY_WEIGHTS, k=1)[0]
                city = random.choice(country[2])
                created = timezone.make_aware(
                    timezone.datetime(
                        date.year, date.month, date.day,
                        random.randint(0, 23), random.randint(0, 59)
                    )
                )
                PageView.objects.create(
                    path=path,
                    method='GET',
                    status_code=200,
                    ip_hash=uuid.uuid4().hex,
                    user_agent='Mozilla/5.0 (Test)',
                    referrer='https://google.com/' if random.random() < 0.3 else '',
                    created_at=created,
                    session_id=session_id,
                    country_code=country[0],
                    country_name=country[1],
                    city=city,
                )

            # Events
            num_events = random.randint(5, 30)
            for _ in range(num_events):
                cat = random.choice(['button', 'download', 'form', 'video'])
                if cat == 'download':
                    act = 'click'
                    lbl = random.choice(['linux', 'windows', 'macos'])
                elif cat == 'button':
                    act = 'click'
                    lbl = random.choice(['signup-hero', 'pricing-cta', 'nav-download', 'nav-pricing'])
                elif cat == 'form':
                    act = 'submit'
                    lbl = random.choice(['contact', 'newsletter', 'application'])
                elif cat == 'video':
                    act = 'play'
                    lbl = random.choice(['intro', 'tutorial', 'webinar'])
                else:
                    act = 'click'
                    lbl = ''
                AnalyticsEvent.objects.create(
                    category=cat,
                    action=act,
                    label=lbl,
                    value=None,
                    path=random.choice(PAGES),
                    session_id=random.choice(session_ids) if session_ids else '',
                    ip_hash='',
                    country_code=random.choice([c[0] for c in COUNTRY_POOL]),
                    country_name='',
                    city='',
                    created_at=created,
                )

            # Billing invoices (only if billing is available)
            if billing_available:
                num_invoices = random.randint(3, 8)
                for inv_num in range(num_invoices):
                    BillingInvoice.objects.create(
                        user=billing_user,
                        invoice_number=f'INV-{date.strftime("%Y%m%d")}-{inv_num+1:03d}',
                        date=date,
                        amount=round(random.uniform(5, 200), 2),
                        status=random.choice(['paid', 'paid', 'paid', 'pending']),
                    )

            self.stdout.write(
                f'  Day {date}: {num_views} views, {num_sessions} sessions, '
                f'{num_events} events'
                f'{f", {num_invoices} invoices" if billing_available else ""}'
            )

        # ── Create UserBilling subscriptions (only if billing available) ──
        if billing_available and plans:
            for plan in plans[:3]:
                username = f'demo-{plan.slug}'
                if not User.objects.filter(username=username).exists():
                    u = User.objects.create_user(username=username, email=f'{plan.slug}@example.com')
                    UserBilling.objects.create(user=u, current_plan=plan)

        # ── Aggregate daily stats ──
        self.stdout.write('Aggregating daily stats...')
        for day_offset in range(1, 31):
            date = today - timedelta(days=day_offset)
            views = PageView.objects.filter(created_at__date=date)
            if not views.exists():
                continue

            total = views.count()
            unique_ips = views.values('ip_hash').distinct().count()
            api_prefix = get_config()['API_PATH_PREFIX']
            api_calls = views.filter(path__startswith=api_prefix).count()

            sessions_qs = views.exclude(session_id='')
            total_sessions = sessions_qs.values('session_id').distinct().count()
            bounce_sessions = (
                sessions_qs.values('session_id')
                .annotate(cnt=Count('id'))
                .filter(cnt=1)
                .count()
            )

            top = (
                views.values('path')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            )
            top_dict = {item['path']: item['count'] for item in top}

            DailySiteStats.objects.update_or_create(
                date=date,
                defaults={
                    'total_views': total,
                    'unique_ips': unique_ips,
                    'api_calls': api_calls,
                    'top_pages': top_dict,
                    'total_sessions': total_sessions,
                    'bounces': bounce_sessions,
                }
            )

        self.stdout.write(self.style.SUCCESS('Seeded 30 days of analytics data'))