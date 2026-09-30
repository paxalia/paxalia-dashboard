from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from paxalia.models import LoginEvent, SecurityAuditLog
from paxalia.resource_policies import prune_log_events
from paxalia.settings import get_config


def _delete_ids_in_batches(model, qs, batch_size):
    total = 0
    while total < batch_size:
        ids = list(qs.values_list('pk', flat=True)[: min(100, batch_size - total)])
        if not ids:
            break
        deleted = len(ids)
        model.objects.filter(pk__in=ids).delete()
        total += deleted
        if deleted == 0:
            break
    return total


def _safe_days(value, default):
    try:
        return max(0, min(3650, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


class Command(BaseCommand):
    help = 'Prune Paxalia observability records according to bounded retention and resource policies.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report bounded eligible rows without deleting records.')
        parser.add_argument('--batch-size', type=int, default=None, help='Global maximum records processed by this cleanup invocation.')

    def handle(self, *args, **options):
        cfg = get_config()
        try:
            raw_batch = options.get('batch_size') if options.get('batch_size') is not None else cfg.get('LOG_CLEANUP_BATCH_SIZE', 500)
            batch_size = max(1, min(int(raw_batch), 5000))
        except (TypeError, ValueError, OverflowError):
            batch_size = 500

        dry_run = bool(options['dry_run'])
        remaining = batch_size
        processed_total = 0
        summary = prune_log_events(dry_run=dry_run, batch_size=remaining)
        canonical_processed = min(remaining, sum(max(0, int(summary.get(key, 0) or 0)) for key in ('retention', 'max_records', 'storage', 'groups')))
        remaining -= canonical_processed
        processed_total += canonical_processed
        self.stdout.write(
            f"Paxalia logs: retention={summary['retention']} max_records={summary['max_records']} "
            f"storage={summary['storage']} groups={summary['groups']} budget_used={canonical_processed}/{batch_size}"
        )

        now = timezone.now()
        user_cfg = getattr(settings, 'PAXALIA_DASHBOARD', {}) or {}
        policy = cfg.get('LOG_RETENTION_DAYS') or {}
        try:
            legacy_security_default = max(0, min(3650, int(cfg.get('SECURITY_LOG_RETENTION_DAYS', 180))))
        except (TypeError, ValueError, OverflowError):
            legacy_security_default = 180
        explicit_policy = 'LOG_RETENTION_DAYS' in user_cfg
        security_policy = policy if explicit_policy else {}
        legacy_targets = [
            ('login', LoginEvent, 'created_at', _safe_days(security_policy.get('login', legacy_security_default), legacy_security_default)),
            ('security_audit', SecurityAuditLog, 'created_at', _safe_days(security_policy.get('security', legacy_security_default), legacy_security_default)),
        ]
        for name, model, field_name, days in legacy_targets:
            if remaining <= 0:
                break
            cutoff = now - timedelta(days=max(0, days))
            qs = model.objects.filter(**{f'{field_name}__lt': cutoff}).order_by(field_name)
            if dry_run:
                eligible = min(qs.count(), remaining)
                self.stdout.write(f'{name}: {eligible} records eligible in this bounded pass')
                remaining -= eligible
                processed_total += eligible
            else:
                deleted = _delete_ids_in_batches(model, qs, remaining)
                deleted = min(deleted, remaining)
                self.stdout.write(f'{name}: deleted {deleted} records in this bounded pass')
                remaining -= deleted
                processed_total += deleted
        self.stdout.write(f'Log prune budget: processed={processed_total} remaining={remaining} limit={batch_size}')

