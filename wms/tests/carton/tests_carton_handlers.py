from types import SimpleNamespace

from django.test import RequestFactory, TestCase

from wms.carton_handlers import _shipment_is_locked, handle_carton_status_update
from wms.models import Carton, CartonStatus, Shipment, ShipmentStatus


class CartonHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_handle_carton_status_update_returns_none_for_non_post_or_other_action(self):
        get_request = self.factory.get("/scan/cartons-ready")
        post_request = self.factory.post(
            "/scan/cartons-ready",
            {"action": "other_action"},
        )

        self.assertIsNone(handle_carton_status_update(get_request))
        self.assertIsNone(handle_carton_status_update(post_request))

    def test_handle_carton_status_update_updates_allowed_unassigned_carton(self):
        carton = Carton.objects.create(code="CT-HANDLER-1", status=CartonStatus.PICKING)
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "update_carton_status",
                "carton_id": str(carton.id),
                "status": CartonStatus.PACKED,
            },
        )

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PACKED)

    def test_mark_carton_labeled_ignored_when_shipment_disputed(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            is_disputed=True,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-2",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "mark_carton_labeled",
                "carton_id": str(carton.id),
            },
        )

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)

    def test_shipment_is_locked_handles_missing_and_locked_status(self):
        self.assertFalse(_shipment_is_locked(SimpleNamespace(shipment=None)))

        locked_carton = SimpleNamespace(
            shipment=SimpleNamespace(status=ShipmentStatus.PLANNED, is_disputed=False)
        )
        self.assertTrue(_shipment_is_locked(locked_carton))

    def test_mark_carton_labeled_updates_when_shipment_is_editable(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-3",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "mark_carton_labeled",
                "carton_id": str(carton.id),
            },
        )

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.LABELED)

    def test_mark_carton_assigned_updates_from_labeled(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-4",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "mark_carton_assigned",
                "carton_id": str(carton.id),
            },
        )

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)

    def test_mark_carton_labeled_ignored_when_shipment_status_is_locked(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-5",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "mark_carton_labeled",
                "carton_id": str(carton.id),
            },
        )

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)
