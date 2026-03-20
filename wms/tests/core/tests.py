from datetime import date
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.admin import PublicAccountRequestAdmin
from wms.models import (
    AssociationProfile,
    Carton,
    CartonFormat,
    CartonStatus,
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    MovementType,
    Order,
    OrderLine,
    OrderStatus,
    OrganizationRole,
    OrganizationRoleAssignment,
    Product,
    ProductKitItem,
    ProductLot,
    ProductLotStatus,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    Receipt,
    ReceiptLine,
    ReceiptStatus,
    RecipientBinding,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentValidationStatus,
    ShipperScope,
    StockMovement,
    Warehouse,
)
from wms.services import (
    StockError,
    consume_stock,
    pack_carton,
    prepare_order,
    receive_receipt_line,
    reserve_stock_for_order,
)


class StockFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="pass1234")
        self.warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="A", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            name="Test product",
            brand="Test",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.correspondent_contact = self._create_contact(
            "StockFlow Correspondent",
            contact_type=ContactType.PERSON,
        )
        self.destination = Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.shipper_contact = self._create_contact("StockFlow Shipper")
        self.recipient_contact = self._create_contact("StockFlow Recipient")
        self._grant_shipper_scope(self.shipper_contact, self.destination)
        self._bind_recipient(self.shipper_contact, self.recipient_contact, self.destination)

    def _create_lot(self, *, quantity, expires_on):
        return ProductLot.objects.create(
            product=self.product,
            lot_code="LOT",
            expires_on=expires_on,
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity,
            location=self.location,
            storage_conditions="dry",
        )

    def _create_contact(self, name, *, contact_type=ContactType.ORGANIZATION):
        return Contact.objects.create(
            name=name,
            contact_type=contact_type,
            is_active=True,
        )

    def _create_person_contact(self, name, *, organization=None):
        first_name, last_name = name.split(" ", 1)
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=True,
        )

    def _assign_role(self, contact, role):
        assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
            organization=contact,
            role=role,
            defaults={"is_active": True},
        )
        if not assignment.is_active:
            assignment.is_active = True
            assignment.save(update_fields=["is_active", "updated_at"])
        return assignment

    def _grant_shipper_scope(self, shipper_contact, destination):
        assignment = self._assign_role(shipper_contact, OrganizationRole.SHIPPER)
        ShipperScope.objects.get_or_create(
            role_assignment=assignment,
            destination=destination,
            defaults={"is_active": True},
        )
        self._ensure_shipment_shipper(shipper_contact)

    def _bind_recipient(self, shipper_contact, recipient_contact, destination):
        self._assign_role(shipper_contact, OrganizationRole.SHIPPER)
        self._assign_role(recipient_contact, OrganizationRole.RECIPIENT)
        RecipientBinding.objects.get_or_create(
            shipper_org=shipper_contact,
            recipient_org=recipient_contact,
            destination=destination,
            defaults={"is_active": True},
        )
        shipper = self._ensure_shipment_shipper(shipper_contact)
        recipient_organization, _created = ShipmentRecipientOrganization.objects.get_or_create(
            organization=recipient_contact,
            defaults={
                "destination": destination,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        updates = []
        if recipient_organization.destination_id != destination.id:
            recipient_organization.destination = destination
            updates.append("destination")
        if recipient_organization.validation_status != ShipmentValidationStatus.VALIDATED:
            recipient_organization.validation_status = ShipmentValidationStatus.VALIDATED
            updates.append("validation_status")
        if not recipient_organization.is_active:
            recipient_organization.is_active = True
            updates.append("is_active")
        if updates:
            recipient_organization.save(update_fields=updates)
        ShipmentShipperRecipientLink.objects.get_or_create(
            shipper=shipper,
            recipient_organization=recipient_organization,
            defaults={"is_active": True},
        )

    def _ensure_shipment_shipper(self, shipper_contact):
        default_contact = (
            Contact.objects.filter(
                organization=shipper_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            )
            .order_by("id")
            .first()
        )
        if default_contact is None:
            default_contact = self._create_person_contact(
                f"Default {shipper_contact.name}",
                organization=shipper_contact,
            )
        shipper, _created = ShipmentShipper.objects.get_or_create(
            organization=shipper_contact,
            defaults={
                "default_contact": default_contact,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        updates = []
        if shipper.default_contact_id != default_contact.id:
            shipper.default_contact = default_contact
            updates.append("default_contact")
        if shipper.validation_status != ShipmentValidationStatus.VALIDATED:
            shipper.validation_status = ShipmentValidationStatus.VALIDATED
            updates.append("validation_status")
        if not shipper.is_active:
            shipper.is_active = True
            updates.append("is_active")
        if updates:
            shipper.save(update_fields=updates)
        return shipper

    def test_consume_stock_follows_fefo(self):
        lot_early = self._create_lot(quantity=5, expires_on=date(2026, 1, 10))
        lot_late = self._create_lot(quantity=10, expires_on=date(2026, 2, 10))

        consume_stock(
            user=self.user,
            product=self.product,
            quantity=7,
            movement_type=MovementType.OUT,
        )

        lot_early.refresh_from_db()
        lot_late.refresh_from_db()
        self.assertEqual(lot_early.quantity_on_hand, 0)
        self.assertEqual(lot_late.quantity_on_hand, 8)

    def test_pack_carton_precondition(self):
        self._create_lot(quantity=20, expires_on=date(2026, 1, 10))
        carton = pack_carton(
            user=self.user,
            product=self.product,
            quantity=5,
            carton=None,
            carton_code=None,
            shipment=None,
            current_location=self.location,
        )
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PICKING)
        movement_types = set(
            StockMovement.objects.filter(related_carton=carton).values_list(
                "movement_type", flat=True
            )
        )
        self.assertEqual(movement_types, {MovementType.PRECONDITION})

    def test_pack_carton_for_shipment(self):
        self._create_lot(quantity=20, expires_on=date(2026, 1, 10))
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=self.user,
        )
        carton = pack_carton(
            user=self.user,
            product=self.product,
            quantity=4,
            carton=None,
            carton_code=None,
            shipment=shipment,
            current_location=self.location,
        )
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)
        self.assertEqual(carton.shipment_id, shipment.id)
        movement_types = set(
            StockMovement.objects.filter(related_carton=carton).values_list(
                "movement_type", flat=True
            )
        )
        self.assertEqual(movement_types, {MovementType.OUT})

    def test_pack_carton_rolls_back_on_insufficient_stock(self):
        with self.assertRaises(StockError):
            pack_carton(
                user=self.user,
                product=self.product,
                quantity=1,
                carton=None,
                carton_code=None,
                shipment=None,
                current_location=self.location,
            )
        self.assertEqual(Carton.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)


class KitPackingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="kit-user", password="pass1234")
        self.warehouse = Warehouse.objects.create(name="Kit WH", code="KWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="K", aisle="01", shelf="001"
        )
        self.component_a = Product.objects.create(
            name="Component A",
            brand="Kit",
            weight_g=100,
            volume_cm3=120,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.component_b = Product.objects.create(
            name="Component B",
            brand="Kit",
            weight_g=200,
            volume_cm3=200,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.kit = Product.objects.create(
            name="Kit Enfant",
            brand="Kit",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        ProductKitItem.objects.create(kit=self.kit, component=self.component_a, quantity=2)
        ProductKitItem.objects.create(kit=self.kit, component=self.component_b, quantity=3)

    def _create_lot(self, product, quantity):
        return ProductLot.objects.create(
            product=product,
            lot_code="LOT",
            expires_on=date(2026, 1, 10),
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity,
            location=self.location,
            storage_conditions="dry",
        )

    def test_pack_carton_with_kit_consumes_components(self):
        lot_a = self._create_lot(self.component_a, 10)
        lot_b = self._create_lot(self.component_b, 10)

        carton = pack_carton(
            user=self.user,
            product=self.kit,
            quantity=2,
            carton=None,
            carton_code=None,
            shipment=None,
            current_location=self.location,
        )

        lot_a.refresh_from_db()
        lot_b.refresh_from_db()
        self.assertEqual(lot_a.quantity_on_hand, 6)
        self.assertEqual(lot_b.quantity_on_hand, 4)
        items = list(carton.cartonitem_set.select_related("product_lot__product"))
        self.assertEqual(len(items), 2)
        item_products = {item.product_lot.product for item in items}
        self.assertEqual(item_products, {self.component_a, self.component_b})

    def test_pack_carton_kit_blocks_when_insufficient_components(self):
        self._create_lot(self.component_a, 1)
        self._create_lot(self.component_b, 10)

        with self.assertRaises(StockError):
            pack_carton(
                user=self.user,
                product=self.kit,
                quantity=1,
                carton=None,
                carton_code=None,
                shipment=None,
                current_location=self.location,
            )
        self.assertEqual(Carton.objects.count(), 0)

    def test_pack_carton_with_nested_kit_consumes_base_components(self):
        parent_kit = Product.objects.create(
            name="Kit Parent",
            brand="Kit",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        ProductKitItem.objects.create(kit=parent_kit, component=self.kit, quantity=2)
        lot_a = self._create_lot(self.component_a, 20)
        lot_b = self._create_lot(self.component_b, 20)

        carton = pack_carton(
            user=self.user,
            product=parent_kit,
            quantity=1,
            carton=None,
            carton_code=None,
            shipment=None,
            current_location=self.location,
        )

        lot_a.refresh_from_db()
        lot_b.refresh_from_db()
        self.assertEqual(lot_a.quantity_on_hand, 16)
        self.assertEqual(lot_b.quantity_on_hand, 14)
        quantities_by_product = {
            item.product_lot.product_id: item.quantity
            for item in carton.cartonitem_set.select_related("product_lot__product")
        }
        self.assertEqual(quantities_by_product[self.component_a.id], 4)
        self.assertEqual(quantities_by_product[self.component_b.id], 6)


class ShipmentReferenceTests(TestCase):
    def _create_shipment(self, user):
        return Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=user,
        )

    def test_shipment_reference_sequence_increments(self):
        user = get_user_model().objects.create_user(username="sequser", password="pass1234")
        with mock.patch("wms.models.timezone.localdate", return_value=date(2026, 1, 2)):
            shipment_1 = self._create_shipment(user)
            shipment_2 = self._create_shipment(user)
        self.assertEqual(shipment_1.reference, "260001")
        self.assertEqual(shipment_2.reference, "260002")

    def test_shipment_reference_resets_each_year(self):
        user = get_user_model().objects.create_user(username="sequser2", password="pass1234")
        with mock.patch("wms.models.timezone.localdate", return_value=date(2027, 1, 2)):
            shipment = self._create_shipment(user)
        self.assertEqual(shipment.reference, "270001")

    def test_tracking_path_uses_tracking_token(self):
        user = get_user_model().objects.create_user(username="sequser3", password="pass1234")
        shipment = self._create_shipment(user)
        self.assertEqual(
            shipment.get_tracking_path(),
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
        )
        self.assertNotIn(shipment.reference, shipment.get_tracking_path())


class ModelValidationTests(TestCase):
    def test_product_validators_reject_negative_values(self):
        product = Product(
            sku="TEST-NEG",
            name="Bad product",
            weight_g=-1,
            volume_cm3=-10,
            length_cm=-1,
            width_cm=-1,
            height_cm=-1,
            qr_code_image="qr_codes/test.png",
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_carton_format_validators_reject_negative_values(self):
        carton_format = CartonFormat(
            name="Bad format",
            length_cm=-1,
            width_cm=-1,
            height_cm=-1,
            max_weight_g=-5,
        )
        with self.assertRaises(ValidationError):
            carton_format.full_clean()


class ReceiptTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="receipt-user", password="pass1234"
        )
        self.warehouse = Warehouse.objects.create(name="Reception", code="REC")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="R", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            name="Receipt product",
            brand="Brand",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.receipt = Receipt.objects.create(
            receipt_type="donation",
            status=ReceiptStatus.DRAFT,
            received_on=date(2025, 12, 20),
            warehouse=self.warehouse,
            created_by=self.user,
        )

    def test_receive_receipt_line_creates_lot(self):
        line = ReceiptLine.objects.create(
            receipt=self.receipt,
            product=self.product,
            quantity=12,
            lot_code="LOT-R1",
            expires_on=date(2026, 5, 1),
            location=self.location,
        )
        lot = receive_receipt_line(user=self.user, line=line)
        line.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertEqual(line.received_lot_id, lot.id)
        self.assertEqual(line.received_by_id, self.user.id)
        self.assertEqual(self.receipt.status, ReceiptStatus.RECEIVED)


class OrderReservationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="order-user", password="pass1234")
        self.warehouse = Warehouse.objects.create(name="Stock", code="STK")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="S", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            name="Order product",
            brand="Brand",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.lot = ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-ORD",
            expires_on=date(2026, 2, 1),
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=self.location,
        )
        CartonFormat.objects.create(
            name="Carton standard",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )
        self.correspondent_contact = self._create_contact(
            "OrderFlow Correspondent",
            contact_type=ContactType.PERSON,
        )
        self.destination = Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.shipper_contact = self._create_contact("OrderFlow Shipper")
        self.recipient_contact = self._create_contact("OrderFlow Recipient")
        self._grant_shipper_scope(self.shipper_contact, self.destination)
        self._bind_recipient(self.shipper_contact, self.recipient_contact, self.destination)

    def _create_contact(self, name, *, contact_type=ContactType.ORGANIZATION):
        return Contact.objects.create(
            name=name,
            contact_type=contact_type,
            is_active=True,
        )

    def _create_person_contact(self, name, *, organization=None):
        first_name, last_name = name.split(" ", 1)
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=True,
        )

    def _assign_role(self, contact, role):
        assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
            organization=contact,
            role=role,
            defaults={"is_active": True},
        )
        if not assignment.is_active:
            assignment.is_active = True
            assignment.save(update_fields=["is_active", "updated_at"])
        return assignment

    def _grant_shipper_scope(self, shipper_contact, destination):
        assignment = self._assign_role(shipper_contact, OrganizationRole.SHIPPER)
        ShipperScope.objects.get_or_create(
            role_assignment=assignment,
            destination=destination,
            defaults={"is_active": True},
        )
        self._ensure_shipment_shipper(shipper_contact)

    def _bind_recipient(self, shipper_contact, recipient_contact, destination):
        self._assign_role(shipper_contact, OrganizationRole.SHIPPER)
        self._assign_role(recipient_contact, OrganizationRole.RECIPIENT)
        RecipientBinding.objects.get_or_create(
            shipper_org=shipper_contact,
            recipient_org=recipient_contact,
            destination=destination,
            defaults={"is_active": True},
        )
        shipper = self._ensure_shipment_shipper(shipper_contact)
        recipient_organization, _created = ShipmentRecipientOrganization.objects.get_or_create(
            organization=recipient_contact,
            defaults={
                "destination": destination,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        updates = []
        if recipient_organization.destination_id != destination.id:
            recipient_organization.destination = destination
            updates.append("destination")
        if recipient_organization.validation_status != ShipmentValidationStatus.VALIDATED:
            recipient_organization.validation_status = ShipmentValidationStatus.VALIDATED
            updates.append("validation_status")
        if not recipient_organization.is_active:
            recipient_organization.is_active = True
            updates.append("is_active")
        if updates:
            recipient_organization.save(update_fields=updates)
        ShipmentShipperRecipientLink.objects.get_or_create(
            shipper=shipper,
            recipient_organization=recipient_organization,
            defaults={"is_active": True},
        )

    def _ensure_shipment_shipper(self, shipper_contact):
        default_contact = (
            Contact.objects.filter(
                organization=shipper_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            )
            .order_by("id")
            .first()
        )
        if default_contact is None:
            default_contact = self._create_person_contact(
                f"Default {shipper_contact.name}",
                organization=shipper_contact,
            )
        shipper, _created = ShipmentShipper.objects.get_or_create(
            organization=shipper_contact,
            defaults={
                "default_contact": default_contact,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        updates = []
        if shipper.default_contact_id != default_contact.id:
            shipper.default_contact = default_contact
            updates.append("default_contact")
        if shipper.validation_status != ShipmentValidationStatus.VALIDATED:
            shipper.validation_status = ShipmentValidationStatus.VALIDATED
            updates.append("validation_status")
        if not shipper.is_active:
            shipper.is_active = True
            updates.append("is_active")
        if updates:
            shipper.save(update_fields=updates)
        return shipper

    def test_reserve_stock_for_order(self):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=self.shipper_contact.name,
            shipper_contact=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact=self.correspondent_contact,
            destination_address="10 Rue Test, Paris",
            destination_city=self.destination.city,
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=8)
        reserve_stock_for_order(order=order)
        self.lot.refresh_from_db()
        order.refresh_from_db()
        line = order.lines.first()
        self.assertEqual(order.status, OrderStatus.RESERVED)
        self.assertEqual(line.reserved_quantity, 8)
        self.assertEqual(self.lot.quantity_reserved, 8)

    def test_prepare_order_consumes_reserved(self):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=self.shipper_contact.name,
            shipper_contact=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact=self.correspondent_contact,
            destination_address="10 Rue Test, Paris",
            destination_city=self.destination.city,
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=6)
        reserve_stock_for_order(order=order)
        prepare_order(user=self.user, order=order)
        self.lot.refresh_from_db()
        line = order.lines.first()
        self.assertEqual(line.prepared_quantity, 6)
        self.assertEqual(line.reserved_quantity, 0)
        self.assertEqual(self.lot.quantity_reserved, 0)


class PublicAccountApprovalTests(TestCase):
    def setUp(self):
        self.reviewer = get_user_model().objects.create_superuser(
            username="admin-approve",
            email="admin-approve@example.com",
            password="pass1234",
        )
        self.account_request = PublicAccountRequest.objects.create(
            association_name="Association Test",
            email="association@example.com",
            phone="+33123456789",
            address_line1="10 Rue Test",
            address_line2="",
            postal_code="75000",
            city="Paris",
            country="France",
            status=PublicAccountRequestStatus.PENDING,
        )

    def test_approve_request_creates_user_without_temp_password(self):
        request = RequestFactory().get("/admin/wms/publicaccountrequest/")
        request.user = self.reviewer

        admin = PublicAccountRequestAdmin(PublicAccountRequest, AdminSite())
        ok, reason = admin._approve_request(request, self.account_request)

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        user = get_user_model().objects.get(email__iexact=self.account_request.email)
        self.assertFalse(user.has_usable_password())

        profile = AssociationProfile.objects.get(user=user)
        self.assertTrue(profile.must_change_password)
        events = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        )
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.payload.get("subject"), "ASF WMS - Compte valide")
        self.assertEqual(event.payload.get("recipient"), [self.account_request.email])
