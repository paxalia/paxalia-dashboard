from django.core.management.base import BaseCommand
from django.utils import timezone

from paxalia.models import ChartAnnotation, Deployment, Site


class Command(BaseCommand):
    help = (
        "Records a deployment and auto-creates a matching ChartAnnotation "
        "so it shows up on the Overview traffic chart with zero extra "
        "configuration. Meant to be called from CI/CD right after a "
        "successful deploy, e.g.:\n\n"
        "  python manage.py record_deployment "
        "--version $(git rev-parse --short HEAD) "
        "--notes \"Deploy from main\""
    )

    def add_arguments(self, parser):
        parser.add_argument('--version', default='', help='Git SHA, tag, or version string.')
        parser.add_argument('--notes', default='', help='Free-text deploy notes.')
        parser.add_argument(
            '--site', default=None,
            help='Site domain to attach the annotation to (default: unassigned, shows on every site\'s chart).',
        )

    def handle(self, *args, **options):
        site = None
        if options['site']:
            site = Site.objects.filter(domain=options['site']).first()
            if site is None:
                self.stderr.write(self.style.WARNING(
                    f"No Site with domain \"{options['site']}\" — recording as unassigned instead."
                ))

        now = timezone.now()
        label = f"Deploy {options['version']}".strip() if options['version'] else 'Deploy'

        annotation = ChartAnnotation.objects.create(site=site, date=now.date(), label=label)
        deployment = Deployment.objects.create(
            version=options['version'], notes=options['notes'], site=site,
            deployed_at=now, annotation=annotation,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Recorded deployment {deployment.version or deployment.pk} and created a matching chart annotation."
        ))
