from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from contacts.models import Contact
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
    StockMovement,
    Warehouse,
)


class ApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-user", password="pass1234"
        )
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
        self.assertEqual(response.status_code, 200)
        data = response.json()
        item = next(row for row in data if row["id"] == self.product.id)
        self.assertEqual(item["available_stock"], 8)

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
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test",
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
