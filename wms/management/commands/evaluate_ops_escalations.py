from django.core.management.base import BaseCommand

from wms.jobs.pilotage import run_evaluate_ops_escalations_job


class Command(BaseCommand):
    help = "Évalue et persiste les escalades locales de pilotage."

    def handle(self, *args, **options):
        summary = run_evaluate_ops_escalations_job()
        self.stdout.write(
            self.style.SUCCESS(
                "Evaluated ops escalations: "
                f"open={summary['open_count']}, resolved={summary['resolved_count']}."
            )
        )
