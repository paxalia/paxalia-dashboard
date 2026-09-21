from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.conf import settings
from django.utils import timezone

from paxalia.models import CSPViolation, JSError, LoginEvent, PaxaliaLogEvent, PaxaliaLogGroup, SecurityAuditLog
from paxalia.settings import get_config


class Command(BaseCommand):
    help = 'Prune Paxalia observability records according to LOG_RETENTION_DAYS.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report counts without deleting records.')

    def handle(self, *args, **options):
        cfg = get_config()
        policy = cfg.get('LOG_RETENTION_DAYS') or {}
        now = timezone.now()
        user_cfg = getattr(settings, 'PAXALIA_DASHBOARD', {}) or {}
        legacy_security_default = int(get_config().get('SECURITY_LOG_RETENTION_DAYS', 180))
        explicit_policy = 'LOG_RETENTION_DAYS' in user_cfg
        security_policy = policy if explicit_policy else {}
        buckets = {
            'system': int(policy.get('system', 30)),
            'request': int(policy.get('request', policy.get('system', 30))),
            'browser': int(policy.get('browser', policy.get('system', 30))),
            'application': int(policy.get('application', policy.get('system', 30))),
            'login': int(security_policy.get('login', legacy_security_default)),
            'security': int(security_policy.get('security', legacy_security_default)),
        }

        queryset = PaxaliaLogEvent.objects.all()
        groups = [
            ('request', Q(category='request'), buckets['request']),
            ('browser', Q(source__in=['JavaScript', 'Browser', 'CSP']), buckets['browser']),
            ('application', Q(category__startswith='application'), buckets['application']),
            ('security', Q(source='Authentication'), buckets['security']),
        ]
        handled = Q(pk__in=[])
        for _name, condition, days in groups:
            cutoff = now - timedelta(days=max(0, days))
            bucket_q = condition & Q(timestamp__lt=cutoff)
            handled |= condition
            if options['dry_run']:
                self.stdout.write(f'{_name}: {queryset.filter(bucket_q).count()} records eligible for deletion')
            else:
                deleted = queryset.filter(bucket_q).delete()[0]
                self.stdout.write(f'{_name}: deleted {deleted} records')

        system_cutoff = now - timedelta(days=max(0, buckets['system']))
        system_q = ~handled & Q(timestamp__lt=system_cutoff)
        if options['dry_run']:
            self.stdout.write(f'system: {queryset.filter(system_q).count()} records eligible for deletion')
        else:
            deleted = queryset.filter(system_q).delete()[0]
            self.stdout.write(f'system: deleted {deleted} records')

        # The legacy authentication/security models remain the source of truth
        # for existing historical records. Their retention falls back to the
        # established SECURITY_LOG_RETENTION_DAYS unless LOG_RETENTION_DAYS was
        # explicitly configured for a more granular policy.
        legacy_targets = [
            ('login', LoginEvent, 'created_at', buckets['login']),
            ('security_audit', SecurityAuditLog, 'created_at', buckets['security']),
        ]
        for name, model, field_name, days in legacy_targets:
            cutoff = now - timedelta(days=max(0, days))
            legacy_q = model.objects.filter(**{f'{field_name}__lt': cutoff})
            if options['dry_run']:
                self.stdout.write(f'{name}: {legacy_q.count()} records eligible for deletion')
            else:
                deleted = legacy_q.delete()[0]
                self.stdout.write(f'{name}: deleted {deleted} records')

        group_days = max(0, int(policy.get('group', 90)))
        group_cutoff = now - timedelta(days=group_days)
        group_q = PaxaliaLogGroup.objects.filter(last_seen__lt=group_cutoff)
        if options['dry_run']:
            self.stdout.write(f'groups: {group_q.count()} records eligible for deletion')
        else:
            deleted = group_q.delete()[0]
            self.stdout.write(f'groups: deleted {deleted} records')
