import os
import tarfile
import tempfile

from django.core.management.base import BaseCommand
from django.utils import timezone

from paxalia.models import BackupArchive, BackupConfiguration


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

        overlap_warning = config.get_path_overlap_warning()
        if overlap_warning:
            self.stdout.write(self.style.ERROR(overlap_warning))
            return

        archive = None
        if archive_id:
            try:
                archive = BackupArchive.objects.get(id=archive_id)
                archive.status = 'creating'
                archive.error_message = ''
                archive.save(update_fields=['status', 'error_message'])
            except BackupArchive.DoesNotExist:
                pass

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f'backup_{timestamp}.tar.gz'
        final_archive = os.path.join(config.storage_path, filename)
        fd, temp_archive = tempfile.mkstemp(
            prefix='.paxalia-backup-', suffix='.partial', dir=config.storage_path
        )
        os.close(fd)

        try:
            with tarfile.open(temp_archive, 'w:gz') as tar:
                for path in paths:
                    if os.path.exists(path):
                        arcname = os.path.basename(os.path.abspath(path))
                        tar.add(path, arcname=arcname)
                    else:
                        self.stdout.write(self.style.WARNING(f'Path does not exist: {path}'))

            # Make the completed archive visible atomically. Readers never see
            # a partially written .tar.gz at the final path.
            os.replace(temp_archive, final_archive)
            temp_archive = None
            size = os.path.getsize(final_archive)
        except Exception as exc:
            if temp_archive:
                try:
                    os.remove(temp_archive)
                except OSError:
                    pass
            self.stdout.write(self.style.ERROR(f'Failed to create backup: {exc}'))
            if archive:
                archive.status = 'failed'
                archive.error_message = str(exc)[:500]
                archive.save(update_fields=['status', 'error_message'])
            return

        completed_at = timezone.now()
        if archive:
            archive.filename = filename
            archive.size = size
            archive.storage_path = final_archive
            archive.status = 'completed'
            archive.completed_at = completed_at
            archive.save(update_fields=[
                'filename', 'size', 'storage_path', 'status', 'completed_at'
            ])
        else:
            archive = BackupArchive.objects.create(
                filename=filename,
                size=size,
                storage_path=final_archive,
                status='completed',
                completed_at=completed_at,
            )

        self.stdout.write(self.style.SUCCESS(f'Backup created: {filename} ({size} bytes)'))

        retention = config.retention_count
        if retention > 0:
            old_backups = BackupArchive.objects.exclude(pk=archive.pk).order_by('-created_at')
            to_delete = old_backups[max(retention - 1, 0):]
            for old in to_delete:
                if os.path.exists(old.storage_path):
                    try:
                        os.remove(old.storage_path)
                    except OSError:
                        pass
                old.delete()
                self.stdout.write(f'Deleted old backup: {old.filename}')
