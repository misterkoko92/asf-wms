from datetime import date
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms.carton_handlers import _shipment_is_locked, handle_carton_status_update
from wms.models import (
    Carton,
    CartonItem,
    CartonStatus,
    Destination,
    Location,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentStatus,
    Warehouse,
)


class CartonHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="carton-handler-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="HANDLER-SKU",
            name="Produit Handler",
            default_location=self.location,
            qr_code_image="qr_codes/handler.png",
        )
        self.lot = ProductLot.objects.create(
            product=self.product,
            lot_code="HANDLER-LOT",
            received_on=date(2026, 1, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=10,
            quantity_reserved=0,
            location=self.location,
        )

    def _create_destination(self, code):
        correspondent_org = Contact.objects.create(
            name=f"Correspondent Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name=f"Correspondent {code}",
            contact_type=ContactType.PERSON,
            first_name="Correspondent",
            last_name=code,
            organization=correspondent_org,
            is_active=True,
        )
        return Destination.objects.create(
            city=f"Paris {code}",
            iata_code=code,
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )

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

    def test_bulk_mark_cartons_labeled_updates_only_eligible_rows(self):
        editable_shipment = Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        locked_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        eligible_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-1",
            status=CartonStatus.ASSIGNED,
            shipment=editable_shipment,
        )
        locked_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-2",
            status=CartonStatus.ASSIGNED,
            shipment=locked_shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_mark_cartons_labeled",
                "selected_carton_ids": [str(eligible_carton.id), str(locked_carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        eligible_carton.refresh_from_db()
        locked_carton.refresh_from_db()
        self.assertEqual(eligible_carton.status, CartonStatus.LABELED)
        self.assertEqual(locked_carton.status, CartonStatus.ASSIGNED)

    def test_bulk_action_alias_updates_labeled_status_from_selected_rows(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-BULK-ALIAS",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "bulk_action": "bulk_mark_cartons_labeled",
                "selected_carton_ids": [str(carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.LABELED)

    def test_bulk_mark_cartons_assigned_updates_only_labeled_rows(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        eligible_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-3",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )
        ignored_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-4",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_mark_cartons_assigned",
                "selected_carton_ids": [str(eligible_carton.id), str(ignored_carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        eligible_carton.refresh_from_db()
        ignored_carton.refresh_from_db()
        self.assertEqual(eligible_carton.status, CartonStatus.ASSIGNED)
        self.assertEqual(ignored_carton.status, CartonStatus.ASSIGNED)

    def test_bulk_update_cartons_packed_updates_only_eligible_unassigned_rows(self):
        eligible_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-READY",
            status=CartonStatus.PICKING,
        )
        ignored_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-READY-LOCKED",
            status=CartonStatus.ASSIGNED,
            shipment=Shipment.objects.create(
                status=ShipmentStatus.PICKING,
                is_disputed=False,
                shipper_name="Sender",
                recipient_name="Recipient",
                destination_address="1 rue test",
                destination_country="France",
            ),
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_update_cartons_packed",
                "selected_carton_ids": [str(eligible_carton.id), str(ignored_carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        eligible_carton.refresh_from_db()
        ignored_carton.refresh_from_db()
        self.assertEqual(eligible_carton.status, CartonStatus.PACKED)
        self.assertEqual(ignored_carton.status, CartonStatus.ASSIGNED)

    def test_bulk_update_cartons_packed_ignores_unconfirmed_skipped_transition(self):
        carton = Carton.objects.create(
            code="CT-HANDLER-BULK-SKIP-PACKED",
            status=CartonStatus.DRAFT,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_update_cartons_packed",
                "selected_carton_ids": [str(carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.DRAFT)

    def test_bulk_update_cartons_picking_updates_only_eligible_unassigned_rows(self):
        eligible_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-PICKING",
            status=CartonStatus.PACKED,
        )
        ignored_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-PICKING-SHIPPED",
            status=CartonStatus.SHIPPED,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_update_cartons_picking",
                "selected_carton_ids": [str(eligible_carton.id), str(ignored_carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        eligible_carton.refresh_from_db()
        ignored_carton.refresh_from_db()
        self.assertEqual(eligible_carton.status, CartonStatus.PICKING)
        self.assertEqual(ignored_carton.status, CartonStatus.SHIPPED)

    def test_bulk_assign_cartons_shipment_ignores_unconfirmed_skipped_transition(self):
        destination = self._create_destination("NKC")
        target_shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination=destination,
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-BULK-SKIP-ASSIGN",
            status=CartonStatus.DRAFT,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_assign_cartons_shipment",
                "bulk_shipment_id": str(target_shipment.id),
                "selected_carton_ids": [str(carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertIsNone(carton.shipment_id)
        self.assertEqual(carton.status, CartonStatus.DRAFT)

    def test_bulk_assign_cartons_shipment_updates_only_eligible_unassigned_rows(self):
        destination = self._create_destination("BAS")
        target_shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination=destination,
            destination_address="1 rue test",
            destination_country="France",
        )
        eligible_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-ASSIGN",
            status=CartonStatus.PACKED,
        )
        ignored_carton = Carton.objects.create(
            code="CT-HANDLER-BULK-ASSIGN-LOCKED",
            status=CartonStatus.SHIPPED,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_assign_cartons_shipment",
                "bulk_shipment_id": str(target_shipment.id),
                "selected_carton_ids": [str(eligible_carton.id), str(ignored_carton.id)],
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        eligible_carton.refresh_from_db()
        ignored_carton.refresh_from_db()
        self.assertEqual(eligible_carton.shipment_id, target_shipment.id)
        self.assertEqual(eligible_carton.status, CartonStatus.ASSIGNED)
        self.assertIsNone(ignored_carton.shipment_id)
        self.assertEqual(ignored_carton.status, CartonStatus.SHIPPED)

    def test_bulk_assign_cartons_shipment_applies_confirmed_skipped_transition(self):
        destination = self._create_destination("NKC")
        target_shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination=destination,
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-BULK-CONFIRM-ASSIGN",
            status=CartonStatus.DRAFT,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_assign_cartons_shipment",
                "bulk_shipment_id": str(target_shipment.id),
                "selected_carton_ids": [str(carton.id)],
                "confirm_skipped_statuses": "1",
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.shipment_id, target_shipment.id)
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)

    def test_bulk_mark_cartons_labeled_applies_confirmed_skipped_transition_with_assignment(self):
        destination = self._create_destination("NKC")
        target_shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Expéditeur",
            recipient_name="Recipient",
            destination=destination,
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-BULK-CONFIRM-LABELED",
            status=CartonStatus.PACKED,
        )
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "bulk_mark_cartons_labeled",
                "selected_carton_ids": [str(carton.id)],
                "bulk_shipment_id": str(target_shipment.id),
                "confirm_skipped_statuses": "1",
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        carton.refresh_from_db()
        self.assertEqual(carton.shipment_id, target_shipment.id)
        self.assertEqual(carton.status, CartonStatus.LABELED)

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

    def test_delete_carton_ignores_planned_shipment_carton(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            is_disputed=False,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 rue test",
            destination_country="France",
        )
        carton = Carton.objects.create(
            code="CT-HANDLER-DELETE",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        self.lot.quantity_on_hand = 8
        self.lot.save(update_fields=["quantity_on_hand"])
        CartonItem.objects.create(carton=carton, product_lot=self.lot, quantity=2)
        request = self.factory.post(
            "/scan/cartons-ready",
            {
                "action": "delete_carton",
                "carton_id": str(carton.id),
            },
        )
        request.user = self.user

        response = handle_carton_status_update(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Carton.objects.filter(pk=carton.id).exists())
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantity_on_hand, 8)
