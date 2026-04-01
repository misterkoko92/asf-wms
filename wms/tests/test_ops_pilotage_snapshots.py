from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

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
from wms.ops_pilotage_snapshots import build_ops_pilotage_snapshots


class OpsPilotageSnapshotTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ops-pilotage-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.correspondent = Contact.objects.create(name="Ops Pilotage Contact", is_active=True)
        self.destination = Destination.objects.create(
            city="DAKAR",
            iata_code="DKR",
            country="SENEGAL",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.shipment = Shipment.objects.create(
            reference="EXP-OPS-001",
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
            shipment=self.shipment,
            destination=self.destination,
            reference=self.shipment.reference,
            destination_label=str(self.destination),
            shipment_status=self.shipment.status,
            current_segment="planned_to_boarding",
            segment_age_hours=190.0,
            is_closed=False,
            has_open_dispute=True,
            dispute_reason="docs_missing",
            dispute_owner="qualite",
            delay_state="critical",
            current_delay_hours=118.0,
            active_blockage_category="suivi",
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-30",
            week_end="2026-04-05",
            created_by=self.user,
        )
        self.version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )
        self.shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="PLAN-OPS-001",
            shipper_name="Association A",
            destination_iata="DKR",
            carton_count=12,
            equivalent_units=12,
        )
        self.volunteer_snapshot = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        self.flight_snapshot = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF900",
            departure_date="2026-04-01",
            destination_iata="DKR",
            capacity_units=10,
            payload={"departure_time": "10:00"},
        )
        PlanningAssignment.objects.create(
            version=self.version,
            shipment_snapshot=self.shipment_snapshot,
            volunteer_snapshot=self.volunteer_snapshot,
            flight_snapshot=self.flight_snapshot,
            assigned_carton_count=12,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        PlanningArtifact.objects.create(
            version=self.version,
            artifact_type="planning_pdf",
            label="Planning PDF",
            file_path="/tmp/planning-ops.pdf",
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source=DOCUMENT_SCAN_QUEUE_SOURCE,
            target="antivirus",
            event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            payload={"model": "wms.AccountDocument", "pk": 1},
            status=IntegrationStatus.FAILED,
        )

    def test_build_ops_pilotage_snapshots_captures_global_destination_and_flight_metrics(self):
        rows = build_ops_pilotage_snapshots(snapshot_date=date(2026, 4, 1))

        metrics = {(row["scope_type"], row["metric_key"]) for row in rows}

        self.assertIn(("global", "sla_new_count"), metrics)
        self.assertIn(("global", "sla_critical_count"), metrics)
        self.assertIn(("destination", "critical_shipment_count"), metrics)
        self.assertIn(("flight", "capacity_overload_count"), metrics)

    def test_build_ops_pilotage_snapshots_captures_planning_pdf_and_queue_health(self):
        rows = build_ops_pilotage_snapshots(snapshot_date=date(2026, 4, 1))

        metrics = {(row["scope_type"], row["metric_key"]) for row in rows}
        row_map = {(row["scope_type"], row["scope_key"], row["metric_key"]): row for row in rows}

        self.assertIn(("planning_export", "planning_pdf_ok"), metrics)
        self.assertIn(("queue", "document_scan_failed_count"), metrics)
        self.assertEqual(
            row_map[("planning_export", str(self.version.pk), "planning_pdf_ok")]["metric_value"],
            1,
        )
        self.assertEqual(
            row_map[("queue", DOCUMENT_SCAN_QUEUE_SOURCE, "document_scan_failed_count")][
                "metric_value"
            ],
            1,
        )

    def test_capture_rows_can_be_persisted_with_unique_scope_metric_keys(self):
        rows = build_ops_pilotage_snapshots(snapshot_date=date(2026, 4, 1))

        OpsPilotageSnapshot.objects.bulk_create(OpsPilotageSnapshot(**row) for row in rows)

        self.assertEqual(
            OpsPilotageSnapshot.objects.filter(snapshot_date=date(2026, 4, 1)).count(),
            len(rows),
        )

    @override_settings(DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS="invalid")
    def test_build_ops_pilotage_snapshots_falls_back_when_document_scan_timeout_is_invalid(self):
        rows = build_ops_pilotage_snapshots(snapshot_date=date(2026, 4, 1))

        queue_metrics = {
            row["metric_key"]: row["metric_value"] for row in rows if row["scope_type"] == "queue"
        }

        self.assertIn("document_scan_failed_count", queue_metrics)
