from collections import defaultdict

from django.db import migrations, models
from django.db.models import Q


LEGACY_INDEX_NAMES = (
    "paxalia_dailysitestats_site_id_date_a6d83392_uniq",
    "analytics_dailysitestats_site_id_date_3e8f8f14_uniq",
    "unique_dailysitestats_site_date",
    "unique_dailysitestats_date_when_site_null",
)


def merge_duplicate_daily_stats(apps, schema_editor):
    """
    Repair duplicate DailySiteStats rows before the final uniqueness rules
    are installed.

    The old unique_together=('site', 'date') does not protect the NULL site
    bucket on PostgreSQL because NULL values are not equal for normal unique
    indexes. This migration collapses duplicate (site_id, date) groups into
    one survivor, summing counters and merging top_pages.
    """
    DailySiteStats = apps.get_model("paxalia", "DailySiteStats")

    groups = defaultdict(list)
    for row in DailySiteStats.objects.all().order_by("id"):
        groups[(row.site_id, row.date)].append(row)

    for (_site_id, _date), rows in groups.items():
        if len(rows) <= 1:
            continue

        primary, *duplicates = rows
        merged_top_pages = dict(primary.top_pages or {})

        for duplicate in duplicates:
            primary.total_views += duplicate.total_views
            primary.unique_ips += duplicate.unique_ips
            primary.unique_users += duplicate.unique_users
            primary.api_calls += duplicate.api_calls
            primary.total_sessions += duplicate.total_sessions
            primary.bounces += duplicate.bounces
            primary.bot_views += duplicate.bot_views

            for path, count in (duplicate.top_pages or {}).items():
                merged_top_pages[path] = merged_top_pages.get(path, 0) + count

        primary.top_pages = merged_top_pages
        primary.save()
        DailySiteStats.objects.filter(
            pk__in=[duplicate.pk for duplicate in duplicates]
        ).delete()


def drop_legacy_indexes(apps, schema_editor):
    """
    Remove the legacy Django-generated unique index if it exists.

    Django's AlterUniqueTogether clears the migration state, but an already
    existing database can still physically contain the old unique index.
    PostgreSQL reports that index by the generated name from the migration
    that originally created it. The target partial-index names are also
    removed defensively so an interrupted/manual 0018 attempt can be rerun.
    """
    connection = schema_editor.connection
    table = schema_editor.quote_name("paxalia_dailysitestats")

    # DROP INDEX IF EXISTS is supported by PostgreSQL and SQLite, which are
    # the supported development/production backends for this package. For
    # other backends, fall back to Django's introspection/schema editor.
    vendor = connection.vendor

    if vendor in {"postgresql", "sqlite"}:
        for index_name in LEGACY_INDEX_NAMES:
            schema_editor.execute(
                f"DROP INDEX IF EXISTS {schema_editor.quote_name(index_name)}"
            )
        return

    constraints = connection.introspection.get_constraints(
        connection.cursor(), table_name="paxalia_dailysitestats"
    )
    for index_name in LEGACY_INDEX_NAMES:
        info = constraints.get(index_name)
        if not info:
            continue
        # Let the backend's schema editor generate the proper DROP syntax.
        # Unique indexes are represented as constraints by introspection on
        # some backends, so use the operation only when a real constraint is
        # exposed.
        if info.get("columns"):
            try:
                schema_editor.execute(
                    schema_editor._delete_constraint_sql(schema_editor.quote_name(index_name))
                )
            except Exception:
                # A backend that cannot expose/drop this object safely leaves
                # it untouched; AddConstraint below may then raise, making the
                # migration failure explicit instead of silently corrupting
                # state.
                raise


def noop_reverse(apps, schema_editor):
    # The merge is intentionally irreversible: the original duplicate
    # grouping cannot be reconstructed from the surviving row.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("paxalia", "0017_data_import"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_daily_stats, noop_reverse),

        migrations.AlterUniqueTogether(
            name="dailysitestats",
            unique_together=set(),
        ),

        migrations.RunPython(drop_legacy_indexes, migrations.RunPython.noop),

        migrations.AddConstraint(
            model_name="dailysitestats",
            constraint=models.UniqueConstraint(
                fields=["site", "date"],
                condition=Q(site__isnull=False),
                name="unique_dailysitestats_site_date",
            ),
        ),
        migrations.AddConstraint(
            model_name="dailysitestats",
            constraint=models.UniqueConstraint(
                fields=["date"],
                condition=Q(site__isnull=True),
                name="unique_dailysitestats_date_when_site_null",
            ),
        ),
    ]
