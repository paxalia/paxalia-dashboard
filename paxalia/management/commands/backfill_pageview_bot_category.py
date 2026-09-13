from django.core.management.base import BaseCommand

from paxalia.models import AnalyticsSettings, PageView
from paxalia.bot_classification import classify_bot


class Command(BaseCommand):
    help = (
        "Backfills PageView.bot_category (and re-derives is_bot from it) "
        "for rows created before this phase, using the current "
        "AnalyticsSettings.bot_paths and the bot_classification.py pattern "
        "list. Safe to re-run any time bot_paths changes or the pattern "
        "list is extended — it always recomputes from scratch rather than "
        "only filling in unset rows.\n\n"
        "Unlike backfill_pageview_is_api, this can't be done as a handful "
        "of queryset .update() calls — classification depends on each "
        "row's own user_agent, not a single shared condition — so it "
        "iterates in batches. On a large PageView table this can take a "
        "while; a --batch-size flag is provided for tuning."
    )

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=5000)
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report how many rows would change per category without saving.',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']

        # Mirrors get_analytics_settings() in middleware.py: bot_paths
        # only exists on a saved AnalyticsSettings row; with none saved
        # yet there simply are no configured scanner paths to match
        # against, and only UA-based classification applies.
        settings_obj = AnalyticsSettings.objects.first()
        bot_paths = (
            [p.strip() for p in settings_obj.bot_paths.split('\n') if p.strip()]
            if settings_obj else []
        )

        changed_counts = {}
        total_checked = 0
        to_update = []

        qs = PageView.objects.only('id', 'path', 'user_agent', 'is_bot', 'bot_category').iterator(chunk_size=batch_size)
        for pv in qs:
            total_checked += 1
            is_malicious_path = any(pv.path.startswith(bp) for bp in bot_paths)
            new_category = classify_bot(is_malicious_path, pv.user_agent)
            new_is_bot = bool(new_category)

            if new_category != pv.bot_category or new_is_bot != pv.is_bot:
                changed_counts[new_category or '(not a bot)'] = changed_counts.get(new_category or '(not a bot)', 0) + 1
                if not dry_run:
                    pv.bot_category = new_category
                    pv.is_bot = new_is_bot
                    to_update.append(pv)

            if len(to_update) >= batch_size:
                PageView.objects.bulk_update(to_update, ['bot_category', 'is_bot'], batch_size=batch_size)
                to_update = []

        if to_update:
            PageView.objects.bulk_update(to_update, ['bot_category', 'is_bot'], batch_size=batch_size)

        verb = 'Would change' if dry_run else 'Changed'
        self.stdout.write(self.style.SUCCESS(f"Checked {total_checked} row(s)."))
        if changed_counts:
            for category, count in sorted(changed_counts.items(), key=lambda kv: -kv[1]):
                self.stdout.write(f"  {verb} {count} row(s) -> {category}")
        else:
            self.stdout.write("  No rows needed reclassification.")
