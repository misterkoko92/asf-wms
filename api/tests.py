from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from wms.models import (
    Location,
    Product,
    ProductLot,
    ProductLotStatus,
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

    def test_products_list_includes_available_stock(self):
        ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-API",
            expires_on=date(2026, 1, 1),
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=10,
            quantity_reserved=2,
            location=self.location,
        )
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
