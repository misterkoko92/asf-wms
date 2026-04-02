from django.core.management.base import BaseCommand, CommandError

from wms.jobs.runtime_checks import (
    build_planning_pdf_runtime_unavailable_message,
    get_planning_pdf_runtime_status,
)


class Command(BaseCommand):
    help = "Vérifie la readiness runtime pour la génération du planning PDF."

    def handle(self, *args, **options):
        runtime_status = get_planning_pdf_runtime_status()
        if not runtime_status["available"]:
            raise CommandError(build_planning_pdf_runtime_unavailable_message(runtime_status))
        self.stdout.write(
            self.style.SUCCESS(
                "Planning PDF runtime ready: "
                f"backend={runtime_status['backend']}, status={runtime_status['status']}."
            )
        )
