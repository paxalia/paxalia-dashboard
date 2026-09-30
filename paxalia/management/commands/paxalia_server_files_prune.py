"""Prune expired and over-limit Paxalia Server Files operation history."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils import timezone

from paxalia.server_files.models import ServerFileOperation
from paxalia.server_files.policy import (
    cleanup_batch_size,
    maximum_operation_records,
    operation_retention_days,
)


def require_operation_table(db_connection):
    """Fail with an actionable command error if the history table is absent.

    A missing table is a deployment/schema problem, not an empty history.
    Avoid allowing the raw backend exception to escape as a traceback that
    obscures the likely migration/model-registration cause.
    """
    table_name = ServerFileOperation._meta.db_table
    try:
        table_names = db_connection.introspection.table_names()
    except Exception as exc:
        raise CommandError(
            "Unable to inspect the database schema for Paxalia Server Files. "
            "Verify database connectivity and migration state."
        ) from exc

    if table_name not in table_names:
        raise CommandError(
            "Paxalia Server Files operation-history table is missing "
            f"({table_name}). Keep ServerFileOperation registered from "
            "paxalia.models and retain its CreateModel migration. Do not add "
            "a DeleteModel migration for this model. Run `python manage.py "
            "showmigrations paxalia` and reconcile the migration history. "
            "For a disposable development database, remove an uncommitted, "
            "accidental DeleteModel migration and recreate the database before "
            "running `python manage.py migrate paxalia`."
        )


class Command(BaseCommand):
    help = "Incrementally prune Paxalia Server Files operation history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report eligible rows without deleting them.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Maximum rows processed in this invocation.",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias to use (default: default).",
        )

    def handle(self, *args, **options):
        using = options["database"]
        try:
            db_connection = connections[using]
        except Exception as exc:
            raise CommandError(
                f"Unknown or unavailable database alias {using!r}."
            ) from exc

        require_operation_table(db_connection)

        try:
            configured_batch = cleanup_batch_size()
            max_records = maximum_operation_records()
            retention_days = operation_retention_days()
        except Exception as exc:
            raise CommandError(
                "Invalid Paxalia Server Files cleanup configuration."
            ) from exc

        batch_size = (
            configured_batch
            if options["batch_size"] is None
            else options["batch_size"]
        )
        if isinstance(batch_size, bool) or not 1 <= batch_size <= 10000:
            raise CommandError("--batch-size must be between 1 and 10000.")

        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(days=retention_days)
        operations = ServerFileOperation.objects.using(using)

        # One invocation has a global processing budget across all cleanup
        # priorities. Querysets are sliced before evaluation and never loaded
        # without an explicit bound.
        expired_ids = list(
            operations.filter(created_at__lt=cutoff)
            .order_by("created_at", "id")
            .values_list("pk", flat=True)[:batch_size]
        )
        processed = len(expired_ids)
        eligible = list(expired_ids) if dry_run else []
        deleted = 0

        if not dry_run and expired_ids:
            deleted, _ = operations.filter(pk__in=expired_ids).delete()

        budget = max(0, batch_size - processed)
        current_count = operations.count()
        if dry_run:
            # Model the post-expiration count without deleting rows. The
            # excluded IDs also prevent selecting the same rows twice.
            current_count = max(0, current_count - len(expired_ids))

        excess = max(0, current_count - max_records)
        if budget and excess:
            low_value_ids = list(
                operations.filter(operation__in=("list", "history", "preview"))
                .exclude(pk__in=expired_ids)
                .order_by("created_at", "id")
                .values_list("pk", flat=True)[: min(budget, excess)]
            )
            processed += len(low_value_ids)
            if dry_run:
                eligible.extend(low_value_ids)
            elif low_value_ids:
                removed, _ = operations.filter(pk__in=low_value_ids).delete()
                deleted += removed

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: up to {len(eligible)} operation rows would be "
                    "eligible in this bounded pass."
                )
            )
            return

        current_count = operations.count()
        if current_count > max_records:
            self.stdout.write(
                self.style.WARNING(
                    f"History remains above its {max_records} record cap because "
                    "protected records were retained or more cleanup passes are "
                    f"needed ({current_count} rows remain)."
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {deleted} operation rows in this bounded pass; "
                f"{current_count} rows remain."
            )
        )

