import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from paxalia.packages.engine import inspect_package, PackageError


class Command(BaseCommand):
    help = "Inspect a Paxalia .paxalia package manifest and safe structural summary."

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
        summary = {
            "manifest": {
                "format": manifest.get("format"),
                "format_version": manifest.get("format_version"),
                "package_id": manifest.get("package_id"),
                "created_at": manifest.get("created_at"),
                "paxalia_version": manifest.get("paxalia_version"),
                "django_version": manifest.get("django_version"),
                "encrypted": bool(manifest.get("encrypted")),
                "models": manifest.get("models", []),
            },
            "records": len(payload.get("records") or []),
            "relationships": int(payload.get("relationship_count", 0) or 0),
            "translations": int(payload.get("translation_count", 0) or 0),
            "available_models": sorted(models),
        }
        self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
