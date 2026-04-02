from django.core.management.base import BaseCommand

from wms.jobs.workflow_projection import run_rebuild_workflow_projection_job


class Command(BaseCommand):
    help = "Rebuild the shipment workflow projection read model."

    def handle(self, *args, **options):
        projected_count = run_rebuild_workflow_projection_job()
        self.stdout.write(f"Projected {projected_count} shipment workflow rows.")
