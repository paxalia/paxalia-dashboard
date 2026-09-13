from datetime import timedelta
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.conf_uploads import get_uploads_incoming_root
from analytics.models import FileUpload
from analytics.settings import get_config


class Command(BaseCommand):
    help = 'Remove abandoned chunked-upload sessions and their temporary files.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=None)

    def handle(self, *args, **options):
        hours = options.get('hours')
        if hours is None:
            hours = int(get_config().get('UPLOAD_SESSION_TTL_HOURS', 24))
        hours = max(1, hours)
        cutoff = timezone.now() - timedelta(hours=hours)

        qs = FileUpload.objects.filter(
            status__in=['pending', 'uploading', 'failed'],
            updated_at__lt=cutoff,
        )
        removed = 0
        for upload in qs.iterator():
            temp_path = os.path.join(get_uploads_incoming_root(), '.tmp', str(upload.id))
            if upload.storage_path:
                for path in (upload.storage_path, temp_path):
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except OSError:
                        pass
            else:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass
            upload.delete()
            removed += 1

        self.stdout.write(self.style.SUCCESS(f'Removed {removed} abandoned upload session(s).'))
