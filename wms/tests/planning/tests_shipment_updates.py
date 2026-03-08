from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
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
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)
from wms.planning.shipment_updates import apply_version_updates


class PlanningShipmentUpdateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=self.user,
        )
        self.volunteer_snapshot = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        self.flight_snapshot = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF123",
            departure_date="2026-03-10",
            destination_iata="CDG",
        )

    def make_published_version_for_shipment(self, shipment):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )
        shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment=shipment,
            shipment_reference=shipment.reference,
            carton_count=3,
            equivalent_units=3,
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_snapshot,
            volunteer_snapshot=self.volunteer_snapshot,
            flight_snapshot=self.flight_snapshot,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        return version

    def make_shipment(self, *, status):
        return Shipment.objects.create(
            status=status,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_apply_version_updates_marks_shipments_planned(self):
        shipment = self.make_shipment(status=ShipmentStatus.PACKED)
        version = self.make_published_version_for_shipment(shipment)

        summary = apply_version_updates(version, actor_name="planner")

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PLANNED)
        self.assertEqual(
            ShipmentTrackingEvent.objects.filter(
                shipment=shipment,
                status=ShipmentTrackingStatus.PLANNED,
            ).count(),
            1,
        )
        self.assertEqual(
            summary,
            {
                "considered": 1,
                "updated": 1,
                "tracking_events_created": 1,
                "skipped_missing": 0,
                "skipped_locked": 0,
            },
        )

    def test_apply_version_updates_does_not_rewind_shipped_shipments(self):
        shipment = self.make_shipment(status=ShipmentStatus.SHIPPED)
        version = self.make_published_version_for_shipment(shipment)

        summary = apply_version_updates(version, actor_name="planner")

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.SHIPPED)
        self.assertFalse(
            ShipmentTrackingEvent.objects.filter(
                shipment=shipment,
                status=ShipmentTrackingStatus.PLANNED,
            ).exists()
        )
        self.assertEqual(summary["updated"], 0)
        self.assertEqual(summary["skipped_locked"], 1)
