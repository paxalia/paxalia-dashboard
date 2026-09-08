from django.core.management.base import BaseCommand

from analytics.alerts import send_alert
from analytics.anomalies import check_all_sites
from analytics.models import Notification
from analytics.settings import get_config


class Command(BaseCommand):
    help = (
        "Compares yesterday's traffic to the same weekday one week "
        "earlier, per site, and alerts on any change beyond "
        "ANOMALY_ALERT_THRESHOLD_PERCENT (default 30%). Intended to "
        "run once daily via cron/Celery beat, after aggregate_daily_stats."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report anomalies found without sending alerts or creating notifications.",
        )

    def handle(self, *args, **options):
        threshold = get_config().get('ANOMALY_ALERT_THRESHOLD_PERCENT', 30)
        anomalies = check_all_sites(threshold)

        if options['dry_run']:
            for a in anomalies:
                self.stdout.write(
                    f"{a['site'] or 'unassigned'} on {a['date']}: {a['direction']} "
                    f"{a['change_percent']}% ({a['views']} vs {a['baseline_views']} baseline)"
                )
            self.stdout.write(self.style.SUCCESS(f"{len(anomalies)} anomaly(ies) found."))
            return

        alerted = 0
        for a in anomalies:
            # Dedup against re-running the same day: skip if we already
            # notified about this exact site+date.
            already_alerted = Notification.objects.filter(
                site=a['site'], category='anomaly', created_at__date__gte=a['date'],
                subject__contains=str(a['date']),
            ).exists()
            if already_alerted:
                continue

            site_label = a['site'].name if a['site'] else 'unassigned traffic'
            direction_word = 'dropped' if a['direction'] == 'drop' else 'spiked'
            send_alert(
                subject=f"Traffic {direction_word} for {site_label} on {a['date']}",
                message=(
                    f"{site_label}: {a['views']} views on {a['date']} vs "
                    f"{a['baseline_views']} on the same weekday the week before "
                    f"({a['change_percent']}% change)."
                ),
                category='anomaly',
                site=a['site'],
            )
            alerted += 1

        self.stdout.write(self.style.SUCCESS(f"Alerted on {alerted}/{len(anomalies)} anomaly(ies) found."))
