from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonFormat,
    Destination,
    IntegrationEvent,
    Location,
    Order,
    OrderLine,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentValidationStatus,
    StockMovement,
    Warehouse,
)


class ApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api-user", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.warehouse = Warehouse.objects.create(name="API WH", code="API")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="A", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            sku="API-001",
            name="API Product",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.correspondent_contact = self._create_contact(
            "API Correspondent",
            contact_type=ContactType.PERSON,
        )
        self.destination = Destination.objects.create(
            city="Saint-Denis",
            iata_code="RUN",
            country="France",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.shipper_contact = self._create_contact("API Shipper")
        self.recipient_contact = self._create_contact("API Recipient")
        self._ensure_shipment_shipper(self.shipper_contact)
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

    def _bind_recipient(self, shipper_contact, recipient_contact, destination):
        shipper = self._ensure_shipment_shipper(shipper_contact)
        recipient_referent = (
            Contact.objects.filter(
                organization=recipient_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            )
            .order_by("id")
            .first()
        )
        if recipient_referent is None:
            recipient_referent = self._create_person_contact(
                f"Default {recipient_contact.name}",
                organization=recipient_contact,
            )
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
        shipment_recipient_contact, _created = ShipmentRecipientContact.objects.update_or_create(
            recipient_organization=recipient_organization,
            contact=recipient_referent,
            defaults={"is_active": True},
        )
        link, _created = ShipmentShipperRecipientLink.objects.get_or_create(
            shipper=shipper,
            recipient_organization=recipient_organization,
            defaults={"is_active": True},
        )
        ShipmentAuthorizedRecipientContact.objects.update_or_create(
            link=link,
            recipient_contact=shipment_recipient_contact,
            defaults={"is_default": True, "is_active": True},
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

    def _create_lot(self, quantity):
        return ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-API",
            expires_on=date(2026, 1, 1),
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity,
            location=self.location,
        )

    def test_products_list_includes_available_stock(self):
        lot = self._create_lot(quantity=10)
        lot.quantity_reserved = 2
        lot.save(update_fields=["quantity_reserved"])
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        item = next(row for row in data if row["id"] == self.product.id)
        self.assertEqual(item["available_stock"], 8)

    def test_products_default_filters_active_only(self):
        inactive = Product.objects.create(
            sku="API-002",
            name="Inactive Product",
            is_active=False,
        )
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        ids = {row["id"] for row in data}
        self.assertIn(self.product.id, ids)
        self.assertNotIn(inactive.id, ids)

        response = self.client.get("/api/v1/products/?is_active=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = {row["id"] for row in data}
        self.assertIn(inactive.id, ids)
        self.assertNotIn(self.product.id, ids)

    def test_receive_stock_creates_lot(self):
        payload = {
            "product_id": self.product.id,
            "quantity": 5,
            "location_id": self.location.id,
            "lot_code": "LOT-NEW",
        }
        response = self.client.post("/api/v1/stock/receive/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ProductLot.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_pack_carton_creates_carton(self):
        self._create_lot(quantity=5)
        payload = {
            "product_id": self.product.id,
            "quantity": 2,
        }
        response = self.client.post("/api/v1/pack/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Carton.objects.count(), 1)

    def test_order_reserve_and_prepare(self):
        self._create_lot(quantity=10)
        CartonFormat.objects.create(
            name="API format",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=self.shipper_contact.name,
            shipper_contact=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact=self.correspondent_contact,
            destination_address="10 Rue Test",
            destination_city=self.destination.city,
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=4)
        response = self.client.post(f"/api/v1/orders/{order.id}/reserve/")
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.RESERVED)
        response = self.client.post(f"/api/v1/orders/{order.id}/prepare/")
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertIn(order.status, {OrderStatus.READY, OrderStatus.PREPARING})
        line = order.lines.first()
        self.assertEqual(line.prepared_quantity, 4)

    @override_settings(INTEGRATION_API_KEY="test-key")
    def test_integration_shipments_with_api_key(self):
        contact = Contact.objects.create(name="Dest Contact")
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=contact,
        )
        Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination=destination,
            destination_address="10 Rue Test",
            destination_country="France",
        )
        client = APIClient()
        response = client.get("/api/v1/integrations/shipments/")
        self.assertEqual(response.status_code, 403)
        response = client.get(
            "/api/v1/integrations/shipments/",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)

    @override_settings(INTEGRATION_API_KEY="test-key")
    def test_integration_shipments_filters(self):
        contact = Contact.objects.create(name="Filter Contact")
        destination_paris = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=contact,
        )
        destination_lyon = Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=contact,
        )
        shipment_paris = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination=destination_paris,
            destination_address="10 Rue Test",
            destination_country="France",
            status=ShipmentStatus.PACKED,
        )
        Shipment.objects.create(
            shipper_name="Sender 2",
            recipient_name="Recipient 2",
            destination=destination_lyon,
            destination_address="20 Rue Test",
            destination_country="France",
            status=ShipmentStatus.SHIPPED,
        )
        client = APIClient()
        response = client.get(
            "/api/v1/integrations/shipments/?status=packed",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], shipment_paris.id)

        response = client.get(
            "/api/v1/integrations/shipments/?destination=PAR",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], shipment_paris.id)

    @override_settings(INTEGRATION_API_KEY="test-key")
    def test_integration_event_create(self):
        client = APIClient()
        payload = {
            "source": "asf-scheduler",
            "event_type": "planning.assignment",
            "payload": {"foo": "bar"},
        }
        response = client.post(
            "/api/v1/integrations/events/",
            payload,
            format="json",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(IntegrationEvent.objects.count(), 1)
