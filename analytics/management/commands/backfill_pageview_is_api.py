from django.core.management.base import BaseCommand

from analytics.models import PageView
from analytics.settings import get_config


class Command(BaseCommand):
    help = (
        "Backfills PageView.is_api for rows created before this field "
        "existed, based on the current API_PATH_PREFIX setting. Safe to "
        "re-run any time API_PATH_PREFIX changes — it always recomputes "
        "from scratch rather than only filling in unset rows."
    )

    def handle(self, *args, **options):
        api_prefix = get_config()['API_PATH_PREFIX']

        updated_to_true = PageView.objects.filter(
            path__startswith=api_prefix
        ).exclude(is_api=True).update(is_api=True)

        updated_to_false = PageView.objects.exclude(
            path__startswith=api_prefix
        ).exclude(is_api=False).update(is_api=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled is_api using prefix '{api_prefix}': "
                f"{updated_to_true} row(s) set True, {updated_to_false} row(s) set False."
            )
        )
