# paxalia/management/commands/import_bot_paths.py
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from paxalia.models import AnalyticsSettings

class Command(BaseCommand):
    help = 'Import bot paths from a text file into AnalyticsSettings.bot_paths'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to the text file (one path per line). If not provided, looks for bots_paths.txt in the paxalia app directory or project root.'
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Replace existing bot_paths instead of appending'
        )

    def handle(self, *args, **options):
        file_path = options.get('file')
        # If no file provided, search in common locations
        if not file_path:
            cwd = os.getcwd()
            candidates = [
                os.path.join(cwd, 'paxalia', 'bots_paths.txt'),
                os.path.join(cwd, 'bots_paths.txt'),
                os.path.join(settings.BASE_DIR, 'paxalia', 'bots_paths.txt'),
                os.path.join(settings.BASE_DIR, 'bots_paths.txt'),
                # Also check the installed Paxalia app directory.
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bots_paths.txt'),
            ]
            # Remove duplicates
            candidates = list(dict.fromkeys(candidates))

            for cand in candidates:
                if os.path.exists(cand):
                    file_path = cand
                    break

            if not file_path:
                self.stderr.write(self.style.ERROR(
                    "No bot-path source file was found. Place bots_paths.txt in the Paxalia app/project root or specify --file."
                ))
                return
        else:
            if not os.path.exists(file_path):
                self.stderr.write(self.style.ERROR("The specified bot-path source file could not be found."))
                return

        self.stdout.write("Reading bot-path rules from the selected source file.")

        try:
            with open(file_path, 'r') as f:
                raw_lines = f.readlines()
        except Exception:
            self.stderr.write(self.style.ERROR("The bot-path source file could not be read."))
            return

        paths = []
        for raw in raw_lines:
            line = raw.strip()
            if not line:
                continue
            if '|' in line:
                line = line.split('|')[-1].strip()
            if line:
                paths.append(line)

        if not paths:
            self.stderr.write(self.style.WARNING("No paths found in file."))
            return

        settings_obj, created = AnalyticsSettings.objects.get_or_create(pk=1)

        if options['replace']:
            settings_obj.bot_paths = '\n'.join(paths)
            self.stdout.write(self.style.SUCCESS(f"Replaced bot_paths with {len(paths)} entries."))
        else:
            existing = set(settings_obj.bot_paths.splitlines())
            new_paths = [p for p in paths if p not in existing]
            if new_paths:
                settings_obj.bot_paths = '\n'.join(list(existing) + new_paths)
                self.stdout.write(self.style.SUCCESS(f"Added {len(new_paths)} new bot paths."))
            else:
                self.stdout.write("No new paths to add.")

        settings_obj.save()