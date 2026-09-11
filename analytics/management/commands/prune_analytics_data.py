from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import AnalyticsEvent, JSError, PageView, SlowQuery, UptimeCheck
from analytics.settings import get_config

# Maps a DATA_RETENTION_DAYS key to (Model, date_field_name, display_name).
_RETENTION_TARGETS = {
    'pageview': (PageView, 'created_at', 'PageView'),
    'analytics_event': (AnalyticsEvent, 'created_at', 'AnalyticsEvent'),
    'js_error': (JSError, 'created_at', 'JSError'),
    'uptime_check': (UptimeCheck, 'checked_at', 'UptimeCheck'),
    'slow_query': (SlowQuery, 'created_at', 'SlowQuery'),
}


class Command(BaseCommand):
    help = (
        "Deletes rows older than their configured per-data-type "
        "retention period (DATA_RETENTION_DAYS in your PAXALIA_DASHBOARD "
        "dict — keys: pageview, analytics_event, js_error, uptime_check, "
        "slow_query). Separate from SECURITY_LOG_RETENTION_DAYS (see "
        "prune_security_logs, which only covers LoginEvent/"
        "SecurityAuditLog) and from SERVER_METRIC_RETENTION_DAYS (pruned "
        "inline by record_server_metrics on every run, not here). "
        "DATA_RETENTION_DAYS is empty by default: nothing is deleted "
        "unless you explicitly opt a data type in — this command is a "
        "no-op out of the box, not a silent data-loss risk on upgrade."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report how many rows would be deleted per data type without deleting them.',
        )

    def handle(self, *args, **options):
        configured = get_config().get('DATA_RETENTION_DAYS') or {}
        if not configured:
            self.stdout.write('No DATA_RETENTION_DAYS configured — nothing to do.')
            return

        for key, days in configured.items():
            if not days:
                continue

            target = _RETENTION_TARGETS.get(key)
            if target is None:
                self.stderr.write(self.style.WARNING(f"Unknown DATA_RETENTION_DAYS key '{key}' — skipping."))
                continue

            Model, date_field, label = target
            cutoff = timezone.now() - timedelta(days=days)
            qs = Model.objects.filter(**{f'{date_field}__lt': cutoff})
            count = qs.count()

            if options['dry_run']:
                self.stdout.write(
                    f"Would delete {count} {label} row(s) older than {cutoff.date()} (retention: {days} day(s))."
                )
            else:
                qs.delete()
                self.stdout.write(self.style.SUCCESS(
                    f"Deleted {count} {label} row(s) older than {cutoff.date()} (retention: {days} day(s))."
                ))
