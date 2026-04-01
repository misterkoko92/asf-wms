from django.core.management.base import BaseCommand, CommandError

from tools.planning_comm_helper import excel_runtime


class Command(BaseCommand):
    help = "Vérifie la readiness runtime pour la génération du planning PDF."

    def handle(self, *args, **options):
        runtime_status = excel_runtime.get_excel_runtime_status()
        if not runtime_status["available"]:
            raise CommandError(excel_runtime.build_runtime_unavailable_message(runtime_status))
        self.stdout.write(
            self.style.SUCCESS(
                "Planning PDF runtime ready: "
                f"backend={runtime_status['backend']}, status={runtime_status['status']}."
            )
        )
