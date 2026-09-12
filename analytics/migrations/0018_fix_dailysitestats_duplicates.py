from collections import defaultdict

from django.db import migrations, models
from django.db.models import Q


def merge_duplicate_daily_stats(apps, schema_editor):
    """
    Fixes the root cause of the reported "DailySiteStats.MultipleObjectsReturned"
    production error: unique_together=[('site','date')] never actually
    protected the site=NULL case, since SQL treats every NULL as
    distinct from every other NULL for uniqueness purposes. Concurrent
    requests to AnalyticsMiddleware's get_or_create(site_id=None,
    date=today) could each create their own row instead of finding the
    existing one.

    This merges every duplicate group into one row (summing the
    numeric counters, merging top_pages by summing per-path counts,
    keeping the lowest id/earliest row as the survivor) before the
    schema change below adds a constraint that actually works for the
    NULL case.
    """
    DailySiteStats = apps.get_model('analytics', 'DailySiteStats')

    groups = defaultdict(list)
    for row in DailySiteStats.objects.all().order_by('id'):
        groups[(row.site_id, row.date)].append(row)

    for (site_id, date), rows in groups.items():
        if len(rows) <= 1:
            continue

        primary, *duplicates = rows  # lowest id (created_at) survives
        merged_top_pages = dict(primary.top_pages or {})

        for dup in duplicates:
            primary.total_views += dup.total_views
            primary.unique_ips += dup.unique_ips
            primary.unique_users += dup.unique_users
            primary.api_calls += dup.api_calls
            primary.total_sessions += dup.total_sessions
            primary.bounces += dup.bounces
            primary.bot_views += dup.bot_views
            for path, count in (dup.top_pages or {}).items():
                merged_top_pages[path] = merged_top_pages.get(path, 0) + count

        primary.top_pages = merged_top_pages
        primary.save()
        DailySiteStats.objects.filter(id__in=[d.id for d in duplicates]).delete()


def noop_reverse(apps, schema_editor):
    # Merging is inherently one-directional — once 3 rows become 1,
    # there's no record of which counts came from which original row.
    # Reversing this migration just leaves the deduplicated state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0017_data_import'),
    ]

    operations = [
        # 1. Merge existing duplicates FIRST — a partial unique index
        # would refuse to install (Postgres) or simply not fix
        # anything (SQLite) if duplicate rows still exist.
        migrations.RunPython(merge_duplicate_daily_stats, noop_reverse),

        # 2. Drop the constraint that never worked for site=NULL.
        migrations.AlterUniqueTogether(
            name='dailysitestats',
            unique_together=set(),
        ),

        # 3. Two partial unique indexes replicate the intended "one row
        # per (site, date)" rule correctly for BOTH cases: a real site,
        # and the NULL/unassigned bucket. This is the actual fix.
        migrations.AddConstraint(
            model_name='dailysitestats',
            constraint=models.UniqueConstraint(
                fields=['site', 'date'],
                condition=Q(site__isnull=False),
                name='unique_dailysitestats_site_date',
            ),
        ),
        migrations.AddConstraint(
            model_name='dailysitestats',
            constraint=models.UniqueConstraint(
                fields=['date'],
                condition=Q(site__isnull=True),
                name='unique_dailysitestats_date_when_site_null',
            ),
        ),
    ]
