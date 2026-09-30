"""Bounded Paxalia Transfer Center maintenance and verification."""
from django.core.management.base import BaseCommand

from paxalia.transfer_center.service import maintenance


class Command(BaseCommand):
    help = "Process bounded Paxalia Transfer Center verification, expiry, and recovery work."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--batch-size', type=int, default=None)

    def handle(self, *args, **options):
        result = maintenance(batch_size=options.get('batch_size'), dry_run=bool(options['dry_run']))
        prefix = 'Dry-run transfers (bounded)' if options['dry_run'] else 'Transfers'
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}: processed={result.get('processed', 0)}, "
            f"completed={result.get('completed', 0)}, "
            f"expired={result.get('expired', 0)}, failed={result.get('failed', 0)}, "
            f"eligible={result.get('eligible', result.get('processed', 0))}"
        ))
