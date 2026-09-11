import psutil
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from analytics.models import ServerMetricSnapshot
from analytics.settings import get_config


class Command(BaseCommand):
    help = (
        "Records one snapshot of CPU/memory/disk-IO/network into "
        "ServerMetricSnapshot, for the Server Overview history charts. "
        "Intended to run frequently via cron/Celery beat — every minute "
        "is typical, the same scheduling assumption this package already "
        "makes for aggregate_daily_stats, send_scheduled_reports, "
        "detect_anomalies, and check_uptime. Without this scheduled, "
        "api_server_history has nothing to show and returns an empty "
        "list rather than fabricating data.\n\n"
        "Also prunes snapshots older than SERVER_METRIC_RETENTION_DAYS "
        "(default 7) on every run, since a once-a-minute schedule would "
        "otherwise grow this table without bound — same idea as "
        "prune_security_logs for LoginEvent/SecurityAuditLog, just done "
        "inline here rather than as a second scheduled command, since a "
        "call this cheap doesn't need its own cron entry."
    )

    def handle(self, *args, **options):
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        ServerMetricSnapshot.objects.create(
            cpu_percent=psutil.cpu_percent(interval=0.5),
            memory_percent=psutil.virtual_memory().percent,
            disk_io_read_bytes=disk_io.read_bytes if disk_io else 0,
            disk_io_write_bytes=disk_io.write_bytes if disk_io else 0,
            network_in_bytes=net_io.bytes_recv if net_io else 0,
            network_out_bytes=net_io.bytes_sent if net_io else 0,
        )

        retention_days = get_config().get('SERVER_METRIC_RETENTION_DAYS', 7)
        cutoff = timezone.now() - timedelta(days=retention_days)
        deleted, _ = ServerMetricSnapshot.objects.filter(recorded_at__lt=cutoff).delete()

        self.stdout.write(self.style.SUCCESS(
            f'Recorded server metric snapshot. Pruned {deleted} snapshot(s) older than {retention_days} day(s).'
        ))
