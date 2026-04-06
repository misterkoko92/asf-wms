from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from wms.domain.stock import StockError
from wms.models import Carton, CartonStatus, Shipment, ShipmentStatus
from wms.shipment_status import (
    compute_shipment_progress,
    confirm_shipment_ready,
    shipment_can_be_confirmed_ready,
    sync_shipment_ready_state,
)


class ShipmentStatusTests(TestCase):
    def _create_shipment(self, *, status=ShipmentStatus.DRAFT):
        return Shipment.objects.create(
            status=status,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def test_compute_shipment_progress_returns_partial_when_not_all_cartons_ready(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        Carton.objects.create(code="CT-SS-1", shipment=shipment, status=CartonStatus.LABELED)
        Carton.objects.create(code="CT-SS-2", shipment=shipment, status=CartonStatus.ASSIGNED)

        total, ready, status, label = compute_shipment_progress(shipment)

        self.assertEqual((total, ready), (2, 1))
        self.assertEqual(status, ShipmentStatus.PICKING)
        self.assertEqual(label, "EN COURS (1/2)")

    def test_sync_shipment_ready_state_short_circuits_for_shipped(self):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)

        with mock.patch.object(shipment, "save") as save_mock:
            sync_shipment_ready_state(shipment)

        save_mock.assert_not_called()

    def test_sync_shipment_ready_state_clears_ready_at_when_no_longer_packed(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        shipment.ready_at = timezone.now() - timedelta(hours=1)
        shipment.save(update_fields=["ready_at"])
        Carton.objects.create(code="CT-SS-3", shipment=shipment, status=CartonStatus.DRAFT)

        sync_shipment_ready_state(shipment)
        shipment.refresh_from_db()

        self.assertEqual(shipment.status, ShipmentStatus.PICKING)
        self.assertIsNone(shipment.ready_at)

    def test_confirm_shipment_ready_marks_assigned_cartons_labeled_and_sets_shipment_packed(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        carton = Carton.objects.create(
            code="CT-SS-4", shipment=shipment, status=CartonStatus.ASSIGNED
        )

        self.assertTrue(shipment_can_be_confirmed_ready(shipment))

        confirm_shipment_ready(shipment=shipment, user=None)
        shipment.refresh_from_db()
        carton.refresh_from_db()

        self.assertEqual(carton.status, CartonStatus.LABELED)
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertIsNotNone(shipment.ready_at)

    def test_confirm_shipment_ready_rejects_when_any_carton_is_not_ready(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        Carton.objects.create(code="CT-SS-5", shipment=shipment, status=CartonStatus.PICKING)

        self.assertFalse(shipment_can_be_confirmed_ready(shipment))

        with self.assertRaises(StockError):
            confirm_shipment_ready(shipment=shipment, user=None)
