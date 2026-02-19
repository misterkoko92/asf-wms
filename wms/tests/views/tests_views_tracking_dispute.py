from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from wms.models import (
    Carton,
    CartonStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ShipmentTrackingDisputeFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tracking-dispute-user",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.user)

    def _create_shipment(self, *, status=ShipmentStatus.PACKED, is_disputed=False):
        return Shipment.objects.create(
            status=status,
            is_disputed=is_disputed,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_boarding_step_marks_shipment_and_cartons_shipped(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        carton_a = Carton.objects.create(
            code="CT-DSP-001",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )
        carton_b = Carton.objects.create(
            code="CT-DSP-002",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "status": ShipmentTrackingStatus.BOARDING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "embarque",
            },
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        carton_a.refresh_from_db()
        carton_b.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.SHIPPED)
        self.assertEqual(carton_a.status, CartonStatus.SHIPPED)
        self.assertEqual(carton_b.status, CartonStatus.SHIPPED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 1)

    def test_planning_step_rejects_unlabeled_cartons(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            code="CT-DSP-004",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "status": ShipmentTrackingStatus.PLANNING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planning",
            },
        )

        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0)

    def test_planned_step_requires_previous_planning_ok_step(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            code="CT-DSP-005",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "status": ShipmentTrackingStatus.PLANNED,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planned",
            },
        )

        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0)

    def test_planning_then_planned_updates_shipment_sequence(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            code="CT-DSP-006",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )
        url = reverse("scan:scan_shipment_track", args=[shipment.tracking_token])

        first = self.client.post(
            url,
            {
                "status": ShipmentTrackingStatus.PLANNING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planning ok",
            },
        )
        self.assertEqual(first.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 1)

        second = self.client.post(
            url,
            {
                "status": ShipmentTrackingStatus.PLANNED,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planned",
            },
        )
        self.assertEqual(second.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PLANNED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 2)

    def test_set_disputed_blocks_tracking_progression(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        url = reverse("scan:scan_shipment_track", args=[shipment.tracking_token])

        response_dispute = self.client.post(url, {"action": "set_disputed"})
        self.assertEqual(response_dispute.status_code, 302)
        shipment.refresh_from_db()
        self.assertTrue(shipment.is_disputed)
        self.assertIsNotNone(shipment.disputed_at)

        response_progress = self.client.post(
            url,
            {
                "status": ShipmentTrackingStatus.BOARDING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "ignore",
            },
        )
        self.assertEqual(response_progress.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PLANNED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0)

    def test_resolve_dispute_resets_status_to_ready(self):
        shipment = self._create_shipment(
            status=ShipmentStatus.SHIPPED,
            is_disputed=True,
        )
        carton = Carton.objects.create(
            code="CT-DSP-003",
            status=CartonStatus.SHIPPED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {"action": "resolve_dispute"},
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        carton.refresh_from_db()
        self.assertFalse(shipment.is_disputed)
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(carton.status, CartonStatus.LABELED)
