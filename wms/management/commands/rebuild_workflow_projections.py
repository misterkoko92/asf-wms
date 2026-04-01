from django.core.management.base import BaseCommand

from wms.workflow_projection import rebuild_shipment_workflow_projections


class Command(BaseCommand):
    help = "Rebuild the shipment workflow projection read model."

    def handle(self, *args, **options):
        projected_count = rebuild_shipment_workflow_projections()
        self.stdout.write(f"Projected {projected_count} shipment workflow rows.")
