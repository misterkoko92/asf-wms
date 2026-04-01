from datetime import date
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from contacts.models import Contact
from wms.document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE
from wms.models import (
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    OpsPilotageSnapshot,
    PlanningArtifact,
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
    Shipment,
    ShipmentStatus,
    ShipmentWorkflowProjection,
)


class CaptureOpsPilotageSnapshotCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ops-pilotage-command-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.correspondent = Contact.objects.create(
            name="Ops Pilotage Command Contact",
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        shipment = Shipment.objects.create(
            reference="EXP-OPS-CMD-001",
            status=ShipmentStatus.PLANNED,
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=shipment,
            destination=self.destination,
            reference=shipment.reference,
            destination_label=str(self.destination),
            shipment_status=shipment.status,
            current_segment="planned_to_boarding",
            segment_age_hours=160.0,
            is_closed=False,
            has_open_dispute=False,
            delay_state="persistent",
            current_delay_hours=88.0,
            active_blockage_category="suivi",
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-30",
            week_end="2026-04-05",
            created_by=self.user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )
        shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="PLAN-CMD-001",
            shipper_name="Association B",
            destination_iata="ABJ",
            carton_count=6,
            equivalent_units=6,
        )
        volunteer_snapshot = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Bob",
        )
        flight_snapshot = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF901",
            departure_date="2026-04-02",
            destination_iata="ABJ",
            capacity_units=8,
            payload={"departure_time": "11:30"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_snapshot,
            volunteer_snapshot=volunteer_snapshot,
            flight_snapshot=flight_snapshot,
            assigned_carton_count=6,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        PlanningArtifact.objects.create(
            version=version,
            artifact_type="planning_pdf",
            label="Planning PDF",
            file_path="/tmp/planning-cmd.pdf",
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source=DOCUMENT_SCAN_QUEUE_SOURCE,
            target="antivirus",
            event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            payload={"model": "wms.AccountDocument", "pk": 2},
            status=IntegrationStatus.PENDING,
        )

    def test_capture_ops_pilotage_snapshot_writes_rows(self):
        out = StringIO()

        call_command("capture_ops_pilotage_snapshot", snapshot_date="2026-04-01", stdout=out)

        self.assertTrue(OpsPilotageSnapshot.objects.filter(snapshot_date=date(2026, 4, 1)).exists())
        self.assertIn("Captured", out.getvalue())

    def test_capture_ops_pilotage_snapshot_rejects_invalid_snapshot_date(self):
        with self.assertRaises(CommandError) as error:
            call_command("capture_ops_pilotage_snapshot", snapshot_date="2026-99-99")

        self.assertIn("snapshot-date", str(error.exception))

    @mock.patch(
        "wms.management.commands.capture_ops_pilotage_snapshot.capture_ops_pilotage_snapshots"
    )
    @mock.patch("wms.management.commands.capture_ops_pilotage_snapshot.timezone.localdate")
    def test_capture_ops_pilotage_snapshot_uses_localdate_when_snapshot_date_is_missing(
        self,
        localdate_mock,
        capture_mock,
    ):
        out = StringIO()
        localdate_mock.return_value = date(2026, 4, 2)
        capture_mock.return_value = 7

        call_command("capture_ops_pilotage_snapshot", stdout=out)

        capture_mock.assert_called_once_with(snapshot_date=date(2026, 4, 2))
        self.assertIn("2026-04-02", out.getvalue())
