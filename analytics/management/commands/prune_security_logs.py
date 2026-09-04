from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import LoginEvent, SecurityAuditLog
from analytics.settings import get_config


class Command(BaseCommand):
    help = (
        "Deletes LoginEvent and SecurityAuditLog rows older than "
        "SECURITY_LOG_RETENTION_DAYS (default 180). Intended to run "
        "periodically via cron/Celery beat, e.g. nightly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report how many rows would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        retention_days = get_config()['SECURITY_LOG_RETENTION_DAYS']
        cutoff = timezone.now() - timedelta(days=retention_days)

        login_qs = LoginEvent.objects.filter(created_at__lt=cutoff)
        audit_qs = SecurityAuditLog.objects.filter(created_at__lt=cutoff)

        login_count = login_qs.count()
        audit_count = audit_qs.count()

        if options['dry_run']:
            self.stdout.write(
                f"Would delete {login_count} LoginEvent row(s) and "
                f"{audit_count} SecurityAuditLog row(s) older than {cutoff.date()} "
                f"(retention: {retention_days} days)."
            )
            return

        login_qs.delete()
        audit_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {login_count} LoginEvent row(s) and {audit_count} "
                f"SecurityAuditLog row(s) older than {cutoff.date()}."
            )
        )
