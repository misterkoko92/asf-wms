from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact
from wms.models import Destination, Shipment, ShipmentStatus, ShipmentWorkflowProjection


class RebuildWorkflowProjectionsCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="workflow-projection-command-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.correspondent = Contact.objects.create(name="Workflow Projection Command Contact")
        self.destination = Destination.objects.create(
            city="BAMAKO",
            iata_code="BKO",
            country="MALI",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

    def test_rebuild_workflow_projections_creates_rows_for_existing_shipments(self):
        shipment = Shipment.objects.create(
            reference="EXP-CMD-PROJ-001",
            status=ShipmentStatus.DRAFT,
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
        )

        out = StringIO()
        call_command("rebuild_workflow_projections", stdout=out)

        projection = ShipmentWorkflowProjection.objects.get(shipment=shipment)
        self.assertEqual(projection.reference, shipment.reference)
        self.assertIn("Projected 1 shipment workflow rows.", out.getvalue())

    @mock.patch(
        "wms.management.commands.rebuild_workflow_projections.run_rebuild_workflow_projection_job",
        return_value=4,
    )
    def test_rebuild_workflow_projections_delegates_to_job_layer(self, rebuild_job_mock):
        out = StringIO()

        call_command("rebuild_workflow_projections", stdout=out)

        rebuild_job_mock.assert_called_once_with()
        self.assertIn("Projected 4 shipment workflow rows.", out.getvalue())
