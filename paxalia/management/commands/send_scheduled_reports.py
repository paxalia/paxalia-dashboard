from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone

from paxalia.models import ScheduledReport
from paxalia.reporting import compute_overview_snapshot
from paxalia.report_delivery import send_report_email

# Approximate, not calendar-aligned: "monthly" means "~30 days since
# last send," not "the 1st of the month." Documented here rather than
# pretending this is calendar-exact.
FREQUENCY_DAYS = {'weekly': 7, 'monthly': 30}


class Command(BaseCommand):
    help = (
        "Sends any ScheduledReport that's due (weekly ~7 days, monthly "
        "~30 days since it was last sent, or never sent). Intended to "
        "run daily via cron/Celery beat — running it more or less "
        "often just changes how close to on-time reports go out, "
        "since due-ness is checked against last_sent_at each run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="List which reports would be sent, without sending them.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        due_reports = [r for r in ScheduledReport.objects.filter(is_active=True) if self._is_due(r, now)]

        if options['dry_run']:
            for report in due_reports:
                self.stdout.write(f"Would send: {report.name} ({report.frequency})")
            self.stdout.write(self.style.SUCCESS(f"{len(due_reports)} report(s) due."))
            return

        sent_count = 0
        for report in due_reports:
            # Prevent two cron/Celery workers from sending the same due report
            # concurrently. Redis/memcached-backed Django caches provide an
            # atomic add; local-memory cache still protects the common
            # single-process case without changing report semantics.
            lock_key = f'paxalia:scheduled-report:{report.pk}'
            try:
                claimed = cache.add(lock_key, str(now.timestamp()), timeout=300)
            except Exception:
                claimed = True
            if not claimed:
                continue

            try:
                # Re-read after claiming so another worker that completed the
                # report just before our claim cannot make this run duplicate.
                report.refresh_from_db(fields=['last_sent_at', 'is_active', 'frequency'])
                if not report.is_active or not self._is_due(report, now):
                    continue
                period_days = FREQUENCY_DAYS[report.frequency]
                start_dt = now - timedelta(days=period_days)
                snapshot = compute_overview_snapshot(start_dt, now, report.site)

                if send_report_email(report, snapshot):
                    report.last_sent_at = now
                    report.save(update_fields=['last_sent_at'])
                    sent_count += 1
                else:
                    self.stderr.write(f"Failed to send: {report.name} (see logs for details)")
            finally:
                try:
                    cache.delete(lock_key)
                except Exception:
                    pass

        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count}/{len(due_reports)} due report(s)."))

    @staticmethod
    def _is_due(report, now):
        if report.last_sent_at is None:
            return True
        days_since = (now - report.last_sent_at).total_seconds() / 86400
        return days_since >= FREQUENCY_DAYS[report.frequency]
