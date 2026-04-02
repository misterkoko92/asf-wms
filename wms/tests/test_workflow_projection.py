from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact
from wms.models import (
    Destination,
    Location,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    ShipmentWorkflowProjection,
    Warehouse,
)
from wms.workflow_projection import (
    CURRENT_SEGMENT_CLOSED,
    CURRENT_SEGMENT_DELIVERY_TO_CLOSE,
    CURRENT_SEGMENT_PLANNED_TO_BOARDING,
    build_destination_week_workflow_projection_rows,
    build_shipment_workflow_projection_payload,
)


class ShipmentWorkflowProjectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="workflow-projection-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.warehouse = Warehouse.objects.create(name="Projection WH", code="PROJ")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.correspondent = Contact.objects.create(name="Projection Correspondent", is_active=True)
        self.destination = Destination.objects.create(
            city="DAKAR",
            iata_code="DKR",
            country="SENEGAL",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

    def _create_shipment(self, *, reference, status):
        return Shipment.objects.create(
            reference=reference,
            status=status,
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
        )

    def _create_tracking_event(self, *, shipment, status, hours_ago):
        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=status,
            actor_name="Actor",
            actor_structure="ASF",
            created_by=self.user,
        )
        ShipmentTrackingEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )

    def test_build_projection_payload_for_open_planned_shipment(self):
        shipment = self._create_shipment(
            reference="EXP-PROJ-OPEN",
            status=ShipmentStatus.PLANNED,
        )
        Shipment.objects.filter(pk=shipment.pk).update(
            created_at=timezone.now() - timedelta(hours=120)
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=96,
        )
        shipment.refresh_from_db()

        payload = build_shipment_workflow_projection_payload(
            shipment=shipment,
            tracking_alert_hours=72,
            workflow_blockage_hours=72,
        )

        self.assertEqual(payload["reference"], shipment.reference)
        self.assertEqual(payload["current_segment"], CURRENT_SEGMENT_PLANNED_TO_BOARDING)
        self.assertFalse(payload["is_closed"])
        self.assertEqual(payload["delay_state"], "new")
        self.assertGreaterEqual(payload["current_delay_hours"], 24)
        self.assertEqual(payload["active_blockage_category"], "suivi")
        self.assertIsNone(payload["lead_hours_planned_to_boarding"])
        self.assertEqual(payload["destination_label"], str(self.destination))

    def test_build_projection_payload_for_resolved_dispute_and_closed_case(self):
        shipment = self._create_shipment(
            reference="EXP-PROJ-CLOSED",
            status=ShipmentStatus.DELIVERED,
        )
        created_at = timezone.now() - timedelta(hours=300)
        Shipment.objects.filter(pk=shipment.pk).update(
            created_at=created_at,
            is_disputed=False,
            dispute_reason="docs_missing",
            dispute_owner="qualite",
            dispute_opened_at=timezone.now() - timedelta(hours=80),
            dispute_resolved_at=timezone.now() - timedelta(hours=20),
            closed_at=timezone.now() - timedelta(hours=4),
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=220,
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            hours_ago=180,
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            hours_ago=120,
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            hours_ago=40,
        )
        shipment.refresh_from_db()

        payload = build_shipment_workflow_projection_payload(
            shipment=shipment,
            tracking_alert_hours=72,
            workflow_blockage_hours=72,
        )

        self.assertEqual(payload["current_segment"], CURRENT_SEGMENT_CLOSED)
        self.assertTrue(payload["is_closed"])
        self.assertEqual(payload["delay_state"], "on_time")
        self.assertEqual(payload["active_blockage_category"], "")
        self.assertFalse(payload["has_open_dispute"])
        self.assertEqual(payload["dispute_reason"], "docs_missing")
        self.assertEqual(payload["dispute_owner"], "qualite")
        self.assertGreater(payload["dispute_resolution_hours"], 0)
        self.assertGreater(payload["lead_hours_total_to_delivery"], 0)
        self.assertGreater(payload["lead_hours_delivery_to_close"], 0)

    def test_build_projection_payload_for_delivered_not_closed_case(self):
        shipment = self._create_shipment(
            reference="EXP-PROJ-CLOSURE",
            status=ShipmentStatus.DELIVERED,
        )
        Shipment.objects.filter(pk=shipment.pk).update(
            created_at=timezone.now() - timedelta(hours=220)
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=180,
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            hours_ago=150,
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            hours_ago=100,
        )
        self._create_tracking_event(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            hours_ago=90,
        )
        shipment.refresh_from_db()

        payload = build_shipment_workflow_projection_payload(
            shipment=shipment,
            tracking_alert_hours=72,
            workflow_blockage_hours=72,
        )

        self.assertEqual(payload["current_segment"], CURRENT_SEGMENT_DELIVERY_TO_CLOSE)
        self.assertEqual(payload["delay_state"], "new")
        self.assertEqual(payload["active_blockage_category"], "cloture")

    def test_shipment_save_schedules_projection_refresh(self):
        with mock.patch(
            "wms.events.handlers_projections.handle_workflow_projection_refresh_requested_event"
        ) as handler_mock:
            shipment = self._create_shipment(
                reference="EXP-PROJ-SIGNAL-001",
                status=ShipmentStatus.DRAFT,
            )

        handler_mock.assert_called_once()

    def test_tracking_event_create_schedules_projection_refresh(self):
        shipment = self._create_shipment(
            reference="EXP-PROJ-SIGNAL-002",
            status=ShipmentStatus.PLANNED,
        )

        with mock.patch(
            "wms.events.handlers_projections.handle_workflow_projection_refresh_requested_event"
        ) as handler_mock:
            ShipmentTrackingEvent.objects.create(
                shipment=shipment,
                status=ShipmentTrackingStatus.PLANNED,
                actor_name="Ops",
                actor_structure="ASF",
                created_by=self.user,
            )

        handler_mock.assert_called_once()

    def test_build_destination_week_projection_rows_groups_by_planned_iso_week(self):
        first_shipment = self._create_shipment(
            reference="EXP-PROJ-WEEK-001",
            status=ShipmentStatus.PLANNED,
        )
        second_shipment = self._create_shipment(
            reference="EXP-PROJ-WEEK-002",
            status=ShipmentStatus.DRAFT,
        )
        ignored_shipment = self._create_shipment(
            reference="EXP-PROJ-WEEK-003",
            status=ShipmentStatus.DRAFT,
        )
        planned_at = timezone.make_aware(datetime(2026, 3, 31, 10, 0))

        ShipmentWorkflowProjection.objects.create(
            shipment=first_shipment,
            destination=self.destination,
            reference=first_shipment.reference,
            destination_label=str(self.destination),
            shipment_status=first_shipment.status,
            planned_at=planned_at,
            current_segment="planned_to_boarding",
            segment_started_at=planned_at,
            segment_age_hours=72.0,
            is_closed=False,
            has_open_dispute=True,
            delay_state="critical",
            active_blockage_category="suivi",
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=second_shipment,
            destination=self.destination,
            reference=second_shipment.reference,
            destination_label=str(self.destination),
            shipment_status=second_shipment.status,
            planned_at=planned_at + timedelta(hours=4),
            current_segment="creation_expedition",
            segment_started_at=planned_at,
            segment_age_hours=36.0,
            is_closed=False,
            has_open_dispute=False,
            delay_state="new",
            active_blockage_category="creation_expedition",
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=ignored_shipment,
            destination=self.destination,
            reference=ignored_shipment.reference,
            destination_label=str(self.destination),
            shipment_status=ignored_shipment.status,
            current_segment="creation_expedition",
            segment_started_at=planned_at,
            segment_age_hours=24.0,
            is_closed=False,
            has_open_dispute=False,
            delay_state="new",
            active_blockage_category="creation_expedition",
        )

        rows = build_destination_week_workflow_projection_rows(
            ShipmentWorkflowProjection.objects.all()
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bucket_label"], "2026-W14")
        self.assertEqual(rows[0]["shipment_count"], 2)
        self.assertEqual(rows[0]["open_dispute_count"], 1)
        self.assertEqual(rows[0]["critical_shipment_count"], 1)
        self.assertEqual(rows[0]["top_blockage_category"], "suivi")
