from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from wms.models import Carton, CartonStatus, Shipment, ShipmentStatus
from wms.shipment_status import compute_shipment_progress, sync_shipment_ready_state


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
