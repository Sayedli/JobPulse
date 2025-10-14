from django.core.management.base import BaseCommand, CommandError

from applications.services import ingestion


class Command(BaseCommand):
    help = "Fetches job postings from the Simplify Jobs New Grad repository."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            dest="url",
            default=ingestion.SIMPLIFY_JOBS_README,
            help="Override the README source URL.",
        )

    def handle(self, *args, **options):
        url = options["url"]
        self.stdout.write(f"Fetching jobs from {url}...")
        try:
            created, updated = ingestion.sync_simplify_jobs(markdown_url=url)
        except Exception as exc:
            raise CommandError(f"Failed to fetch jobs: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Job sync completed. created={created} updated={updated}"))
