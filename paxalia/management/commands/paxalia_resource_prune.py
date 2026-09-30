"""Run bounded Paxalia resource and retention maintenance."""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from paxalia.models import FileUpload, ServerMetricSnapshot, UptimeCheck, UptimeIncident
from paxalia.resource_policies import prune_log_events, notify_log_storage_warning, log_storage_status
from paxalia.transfer_center.service import maintenance as transfer_maintenance
from paxalia.transfer_center.policy import safe_staging_path, send_upload_temp_path, staging_roots
from paxalia.settings import get_config
from paxalia.models import PaxaliaTransfer


def _delete_queryset_in_batches(qs, batch_size, label, stdout):
    total = 0
    while total < batch_size:
        ids = list(qs.values_list('pk', flat=True)[: min(100, batch_size - total)])
        if not ids:
            break
        deleted = len(ids)
        qs.model.objects.filter(pk__in=ids).delete()
        total += deleted
        stdout.write(f"{label}: deleted {deleted}")
        if deleted == 0:
            break
    return total


def _safe_int(value, default, minimum=0, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    parsed = max(minimum, parsed)
    return min(maximum, parsed) if maximum is not None else parsed


def _staging_scan_limit(cfg):
    return _safe_int(cfg.get('TRANSFER_STAGING_SCAN_LIMIT', 5000), 5000, 1, 100000)


def _find_stale_staging_candidates(roots, *, cutoff, candidate_limit, scan_limit, is_referenced):
    """Find stale unreferenced staging files without scanning an unbounded tree."""
    candidates = []
    scanned = 0
    for root in roots:
        if len(candidates) >= candidate_limit or scanned >= scan_limit:
            break
        try:
            iterator = root.iterdir()
            for path in iterator:
                if scanned >= scan_limit:
                    break
                scanned += 1
                if len(candidates) >= candidate_limit:
                    break
                try:
                    if not path.is_file():
                        continue
                    if is_referenced(path):
                        continue
                    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=dt_timezone.utc)
                except (OSError, ValueError, OverflowError):
                    continue
                if mtime < cutoff:
                    candidates.append(path)
        except (OSError, ValueError, RuntimeError):
            continue
    return candidates, scanned


class Command(BaseCommand):
    help = "Apply bounded Paxalia logs, transfers, availability, and resource retention policies."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--batch-size', type=int, default=None)

    def handle(self, *args, **options):
        cfg = get_config()
        default_batch = _safe_int(
            options['batch_size'] if options['batch_size'] is not None
            else cfg.get('LOG_CLEANUP_BATCH_SIZE', 500),
            500, 1, 5000,
        )
        dry_run = bool(options['dry_run'])
        remaining = default_batch
        processed_total = 0

        def budget_limit(configured, maximum):
            return max(1, min(_safe_int(configured, default_batch, 1, maximum), remaining))

        def consume(amount):
            nonlocal remaining, processed_total
            amount = max(0, min(int(amount or 0), remaining))
            remaining -= amount
            processed_total += amount
            return amount

        if dry_run:
            self.stdout.write('Dry run: Paxalia resource maintenance would apply bounded retention policies.')

        if remaining:
            log_result = prune_log_events(dry_run=dry_run, batch_size=remaining)
            log_processed = sum(
                _safe_int(log_result.get(key, 0), 0, 0, remaining)
                for key in ('retention', 'max_records', 'storage', 'groups')
            )
            consume(log_processed)
            self.stdout.write(
                f"{'Logs (dry-run)' if dry_run else 'Logs'}: retention={log_result.get('retention', 0)} "
                f"max_records={log_result.get('max_records', 0)} "
                f"storage={log_result.get('storage', 0)} groups={log_result.get('groups', 0)}"
            )
        else:
            log_result = {'retention': 0, 'max_records': 0, 'storage': 0, 'groups': 0}

        if remaining:
            transfer_batch = budget_limit(cfg.get('TRANSFER_CLEANUP_BATCH_SIZE', 100), 1000)
            transfer_result = transfer_maintenance(batch_size=transfer_batch, dry_run=dry_run)
            consume(transfer_result.get('processed', 0))
            self.stdout.write(
                f"Transfers{' (dry-run)' if dry_run else ''}: "
                f"{'eligible=' + str(transfer_result.get('eligible', 0)) + ' ' if dry_run else ''}"
                f"processed={transfer_result.get('processed', 0)} "
                f"completed={transfer_result.get('completed', 0)} expired={transfer_result.get('expired', 0)}"
            )

        if not dry_run:
            try:
                notify_log_storage_warning(log_storage_status())
            except Exception:
                pass

        now = timezone.now()
        policies = cfg.get('RESOURCE_POLICIES', {}) or {}
        check_policy = policies.get('uptime_check', {}) or {}
        incident_policy = policies.get('uptime_incident', {}) or {}
        metric_policy = policies.get('server_metric', {}) or {}
        transfer_policy = policies.get('transfer', {}) or {}

        check_cutoff = now - timedelta(days=_safe_int(
            check_policy.get('retention_days', cfg.get('AVAILABILITY_HISTORY_RETENTION_DAYS', 90)),
            90, 0, 3650,
        ))
        incident_cutoff = now - timedelta(days=_safe_int(incident_policy.get('retention_days', 365), 365, 0, 3650))
        metric_cutoff = now - timedelta(days=_safe_int(metric_policy.get('retention_days', 7), 7, 0, 3650))
        transfer_cutoff = now - timedelta(days=_safe_int(transfer_policy.get('retention_days', 90), 90, 0, 3650))

        check_qs = UptimeCheck.objects.filter(checked_at__lt=check_cutoff).order_by('checked_at')
        incident_qs = UptimeIncident.objects.filter(
            started_at__lt=incident_cutoff,
        ).exclude(state__in=['open', 'acknowledged']).order_by('started_at')
        metric_qs = ServerMetricSnapshot.objects.filter(recorded_at__lt=metric_cutoff).order_by('recorded_at')
        terminal = ['completed', 'failed', 'cancelled', 'expired']
        transfer_qs = PaxaliaTransfer.objects.filter(status__in=terminal, updated_at__lt=transfer_cutoff).order_by('updated_at')
        old_transfer_ids = transfer_qs.values('pk')
        transfer_upload_qs = FileUpload.objects.filter(
            purpose='transfer_send',
            created_at__lt=transfer_cutoff,
            transfer_id__in=old_transfer_ids,
        ).order_by('created_at')

        # A transfer row can be removed by an earlier retention/count-cap pass,
        # leaving only its FileUpload metadata behind. Keep an explicit orphan
        # cleanup path so those records do not become permanent retention leaks.
        transfer_exists = PaxaliaTransfer.objects.filter(pk=OuterRef('transfer_id'))
        active_transfer_ids = PaxaliaTransfer.objects.filter(
            status__in=(
                'queued', 'preparing', 'transferring',
                'paused', 'interrupted', 'verifying',
            )
        ).values('pk')
        orphan_transfer_upload_qs = (
            FileUpload.objects.filter(
                purpose='transfer_send',
                created_at__lt=transfer_cutoff,
            )
            .exclude(transfer_id__in=active_transfer_ids)
            .annotate(_transfer_exists=Exists(transfer_exists))
            .filter(Q(transfer_id__isnull=True) | Q(_transfer_exists=False))
            .order_by('created_at')
        )

        if dry_run:
            check_count = min(check_qs.count(), remaining)
            consume(check_count)
            incident_count = min(incident_qs.count(), remaining)
            consume(incident_count)
            metric_count = min(metric_qs.count(), remaining)
            consume(metric_count)
            transfer_count = min(transfer_qs.count(), remaining)
            consume(transfer_count)
            upload_count = min(transfer_upload_qs.count(), remaining)
            consume(upload_count)
            orphan_upload_count = min(orphan_transfer_upload_qs.count(), remaining)
            consume(orphan_upload_count)
            self.stdout.write(f"Availability (dry-run): checks={check_count} incidents={incident_count}")
            self.stdout.write(f"Server metrics (dry-run): {metric_count}")
            self.stdout.write(f"Transfer history (dry-run): {transfer_count}")
            self.stdout.write(f"Transfer upload metadata (dry-run): {upload_count}")
            self.stdout.write(f"Orphan transfer upload metadata (dry-run): {orphan_upload_count}")
        else:
            for qs, label in (
                (check_qs, 'Availability checks'),
                (incident_qs, 'Availability incidents'),
                (metric_qs, 'Server metrics'),
                (transfer_qs, 'Transfer history'),
                (transfer_upload_qs, 'Transfer upload metadata'),
                (orphan_transfer_upload_qs, 'Orphan transfer upload metadata'),
            ):
                if not remaining:
                    break
                deleted = _delete_queryset_in_batches(qs, remaining, label, self.stdout)
                consume(deleted)

        if remaining:
            staging_cutoff = now - timedelta(hours=_safe_int(cfg.get('TRANSFER_STAGING_TTL_HOURS', 24), 24, 1, 8760))
            staging_scan_limit = min(_staging_scan_limit(cfg), remaining)

            def _is_staging_referenced(path):
                try:
                    if PaxaliaTransfer.objects.filter(staging_path=str(path)).exists():
                        return True
                    # Resumable send chunks live at .upload-<uuid>, while the
                    # transfer row's public staging_path points at the final
                    # staged filename. Do not delete an active upload's private
                    # temp file merely because it is not referenced by staging_path.
                    if path.parent.name == "send" and path.name.startswith(".upload-"):
                        raw_id = path.name[len(".upload-"):]
                        import uuid
                        try:
                            upload_id = uuid.UUID(raw_id)
                        except (ValueError, AttributeError):
                            return False
                        return FileUpload.objects.filter(
                            pk=upload_id, purpose="transfer_send"
                        ).exists()
                    return False
                except Exception:
                    # A failed reference check is fail-closed: never delete a
                    # staging artifact when its database reference cannot be verified.
                    return True

            try:
                roots = staging_roots()
            except Exception:
                # Never abort database retention because filesystem staging
                # validation is temporarily unavailable. In this state the
                # safe behavior is to skip filesystem deletion altogether.
                self.stdout.write(self.style.WARNING(
                    'Transfer staging cleanup skipped: configuration could not be validated; no staging artifacts were removed.'
                ))
                roots = ()
            candidates, scanned = _find_stale_staging_candidates(
                roots,
                cutoff=staging_cutoff,
                candidate_limit=remaining,
                scan_limit=max(1, staging_scan_limit),
                is_referenced=_is_staging_referenced,
            )

            def _safe_mtime(path):
                try:
                    return path.stat().st_mtime
                except (OSError, ValueError, OverflowError):
                    return float('inf')

            candidates.sort(key=_safe_mtime)
            if dry_run:
                staging_count = min(len(candidates), remaining)
                consume(staging_count)
                self.stdout.write(f"Transfer staging (dry-run): candidates={staging_count} scanned={scanned}")
            else:
                deleted = 0
                for path in candidates[:remaining]:
                    try:
                        path.unlink()
                        deleted += 1
                    except OSError:
                        continue
                consume(deleted)

        # Count caps are also part of the same invocation budget.
        count_specs = [
            ('Availability checks', UptimeCheck.objects.all(), _safe_int(check_policy.get('max_records', cfg.get('AVAILABILITY_MAX_CHECK_RECORDS', 500000)), 500000, 0, 100000000), 'checked_at'),
            ('Availability incidents', UptimeIncident.objects.filter(state='recovered'), _safe_int(incident_policy.get('max_records', 10000), 10000, 0, 100000000), 'started_at'),
            ('Server metrics', ServerMetricSnapshot.objects.all(), _safe_int(metric_policy.get('max_records', 100000), 100000, 0, 100000000), 'recorded_at'),
            ('Transfer history', PaxaliaTransfer.objects.filter(status__in=terminal), _safe_int(transfer_policy.get('max_records', 100000), 100000, 0, 100000000), 'updated_at'),
        ]
        for label, qs, max_records, timestamp_field in count_specs:
            if not remaining:
                break
            excess = max(0, qs.count() - max_records)
            if not excess:
                continue
            if dry_run:
                would_delete = min(excess, remaining)
                consume(would_delete)
                self.stdout.write(f"{label} count cap (dry-run): would delete {would_delete}")
                continue
            ids = list(qs.order_by(timestamp_field).values_list('pk', flat=True)[:remaining])
            deleted = len(ids)
            if ids:
                if qs.model is PaxaliaTransfer:
                    # Count-cap retirement must not strand transfer-owned upload
                    # metadata or staged bytes after the transfer row is removed.
                    transfer_rows = list(
                        PaxaliaTransfer.objects.filter(pk__in=ids).values_list('staging_path', flat=True)
                    )
                    transfer_upload_ids = list(
                        FileUpload.objects.filter(
                            purpose='transfer_send', transfer_id__in=ids
                        ).values_list('id', flat=True)
                    )
                    if transfer_upload_ids:
                        FileUpload.objects.filter(
                            pk__in=transfer_upload_ids, purpose='transfer_send'
                        ).delete()
                    qs.model.objects.filter(pk__in=ids).delete()
                    for staging_path in transfer_rows:
                        if staging_path:
                            try:
                                safe_staging_path(staging_path).unlink(missing_ok=True)
                            except (OSError, ValueError):
                                pass
                    for upload_id in transfer_upload_ids:
                        try:
                            send_upload_temp_path(upload_id).unlink(missing_ok=True)
                        except (OSError, ValueError):
                            pass
                else:
                    qs.model.objects.filter(pk__in=ids).delete()
            consume(deleted)
            self.stdout.write(f"{label} count cap: deleted {deleted}")

        if dry_run:
            self.stdout.write(
                f"Resource maintenance budget: processed={processed_total} remaining={remaining} limit={default_batch}"
            )
            status = log_storage_status()
            self.stdout.write(
                f"Log storage: {status.get('percent') if status.get('percent') is not None else 'n/a'}% of configured capacity"
            )
            self.stdout.write('Paxalia resource maintenance dry-run complete.')
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Paxalia resource maintenance complete. processed={processed_total} budget={default_batch}'
            )
        )

