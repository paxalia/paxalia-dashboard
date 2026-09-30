from django.core.management.base import BaseCommand

from paxalia.uptime import acquire_monitor_check_lease, monitors_due_for_check, perform_check, record_check


class Command(BaseCommand):
    help = (
        "Runs an HTTP check for every active Paxalia Availability monitor whose "
        "configured interval in seconds has elapsed since its last check. "
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
        unknown_count = 0
        checked_count = 0
        skipped_count = 0
        for monitor in due:
            if not options['dry_run'] and not acquire_monitor_check_lease(monitor):
                skipped_count += 1
                continue
            result = perform_check(monitor)
            checked_count += 1
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
            elif result['status'] == 'down':
                down_count += 1
            else:
                unknown_count += 1

        verb = 'Would check' if options['dry_run'] else 'Checked'
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {checked_count} monitor(s): {up_count} up, {down_count} down, {unknown_count} unknown"
            + (f", {skipped_count} lease-skipped." if skipped_count else ".")
        ))
