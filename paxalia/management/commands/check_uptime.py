from django.core.management.base import BaseCommand

from paxalia.uptime import monitors_due_for_check, perform_check, record_check


class Command(BaseCommand):
    help = (
        "Runs an HTTP check for every active UptimeMonitor whose "
        "check_interval_minutes has elapsed since its last check. "
        "Intended to run frequently via cron/Celery beat — every "
        "minute is typical — same scheduling assumption this package "
        "already makes for aggregate_daily_stats, "
        "send_scheduled_reports, and detect_anomalies. Running this "
        "every minute does not mean every monitor is pinged every "
        "minute — only the ones actually due are checked each run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report which monitors are due and the check result without saving anything.',
        )

    def handle(self, *args, **options):
        due = monitors_due_for_check()
        if not due:
            self.stdout.write('No monitors due for a check.')
            return

        up_count = 0
        down_count = 0
        for monitor in due:
            result = perform_check(monitor)
            if options['dry_run']:
                self.stdout.write(
                    f"{monitor.name}: {result['status']} "
                    f"(status_code={result['status_code']}, {result['response_time_ms']}ms) "
                    f"{result['error_message']}"
                )
            else:
                record_check(monitor, result)

            if result['status'] == 'up':
                up_count += 1
            else:
                down_count += 1

        verb = 'Would check' if options['dry_run'] else 'Checked'
        self.stdout.write(self.style.SUCCESS(f"{verb} {len(due)} monitor(s): {up_count} up, {down_count} down."))
