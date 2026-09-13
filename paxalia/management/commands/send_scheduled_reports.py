from datetime import timedelta

from django.core.management.base import BaseCommand
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
            period_days = FREQUENCY_DAYS[report.frequency]
            start_dt = now - timedelta(days=period_days)
            snapshot = compute_overview_snapshot(start_dt, now, report.site)

            if send_report_email(report, snapshot):
                report.last_sent_at = now
                report.save(update_fields=['last_sent_at'])
                sent_count += 1
            else:
                self.stderr.write(f"Failed to send: {report.name} (see logs for details)")

        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count}/{len(due_reports)} due report(s)."))

    @staticmethod
    def _is_due(report, now):
        if report.last_sent_at is None:
            return True
        days_since = (now - report.last_sent_at).days
        return days_since >= FREQUENCY_DAYS[report.frequency]
