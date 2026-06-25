import os
import tarfile
from datetime import datetime
from django.core.management.base import BaseCommand
from analytics.models import BackupConfiguration, BackupArchive

class Command(BaseCommand):
    help = 'Create a new backup archive based on the current configuration'

    def add_arguments(self, parser):
        parser.add_argument('--archive-id', type=str, help='UUID of the BackupArchive record to update')

    def handle(self, *args, **options):
        archive_id = options.get('archive_id')
        config = BackupConfiguration.objects.first()
        if not config or not config.enabled:
            self.stdout.write(self.style.WARNING('Backup is disabled or not configured.'))
            return

        if not config.storage_path:
            self.stdout.write(self.style.ERROR('Backup storage path is not set.'))
            return

        os.makedirs(config.storage_path, exist_ok=True)

        paths = config.get_backup_paths_list()
        if not paths:
            self.stdout.write(self.style.ERROR('No backup paths defined.'))
            return

        archive = None
        if archive_id:
            try:
                archive = BackupArchive.objects.get(id=archive_id)
                archive.status = 'creating'
                archive.save()
            except BackupArchive.DoesNotExist:
                pass

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup_{timestamp}.tar.gz'
        temp_archive = os.path.join(config.storage_path, filename)

        try:
            with tarfile.open(temp_archive, 'w:gz') as tar:
                for path in paths:
                    if os.path.exists(path):
                        arcname = os.path.basename(path)
                        tar.add(path, arcname=arcname)
                    else:
                        self.stdout.write(self.style.WARNING(f'Path does not exist: {path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create backup: {e}'))
            if archive:
                archive.status = 'failed'
                archive.error_message = str(e)[:500]
                archive.save()
            return

        size = os.path.getsize(temp_archive)

        if archive:
            archive.filename = filename
            archive.size = size
            archive.storage_path = temp_archive
            archive.status = 'completed'
            archive.completed_at = datetime.now()
            archive.save()
        else:
            archive = BackupArchive.objects.create(
                filename=filename,
                size=size,
                storage_path=temp_archive,
                status='completed',
                completed_at=datetime.now()
            )

        self.stdout.write(self.style.SUCCESS(f'Backup created: {filename} ({size} bytes)'))

        retention = config.retention_count
        if retention > 0:
            old_backups = BackupArchive.objects.exclude(pk=archive.pk).order_by('-created_at')
            to_delete = old_backups[retention - 1:]
            for old in to_delete:
                if os.path.exists(old.storage_path):
                    os.remove(old.storage_path)
                old.delete()
                self.stdout.write(f'Deleted old backup: {old.filename}')