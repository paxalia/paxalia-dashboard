from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from paxalia.packages.engine import inspect_package, PackageError


class Command(BaseCommand):
    help = "Validate a Paxalia .paxalia package without modifying the database."

    def add_arguments(self, parser):
        parser.add_argument("package", type=str)
        parser.add_argument("--password", default=None)

    def handle(self, *args, **options):
        path = Path(options["package"]).expanduser()
        if not path.is_file():
            raise CommandError(f"Package not found: {path}")
        try:
            manifest, payload, models = inspect_package(path.read_bytes(), password=options.get("password"))
        except (PackageError, ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Paxalia package is valid."))
        self.stdout.write(f"Package ID: {manifest.get('package_id', '')}")
        self.stdout.write(f"Format: {manifest.get('format')} v{manifest.get('format_version')}")
        self.stdout.write(f"Models: {len(models)}")
        self.stdout.write(f"Records: {len(payload.get('records') or [])}")
