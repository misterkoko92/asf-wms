from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.import_services import import_product_row
from wms.models import Carton, CartonFormat, Order, OrderLine, OrderStatus
from wms.services import prepare_order, reserve_stock_for_order


class FlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="flow-user", password="pass1234"
        )

    def test_import_to_order_prepare_flow(self):
        row = {
            "name": "Compresses steriles",
            "sku": "CMP-1",
            "brand": "ACME",
            "warehouse": "Main",
            "zone": "A",
            "aisle": "01",
            "shelf": "001",
            "length_cm": "2",
            "width_cm": "3",
            "height_cm": "4",
            "weight_g": "50",
            "quantity": "10",
        }
        product, created, warnings = import_product_row(row, user=self.user)
        self.assertTrue(created)
        self.assertEqual(warnings, [])

        CartonFormat.objects.create(
            name="Default",
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
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=product, quantity=4)

        reserve_stock_for_order(order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.RESERVED)

        prepare_order(user=self.user, order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.READY)
        self.assertIsNotNone(order.shipment_id)
        self.assertTrue(Carton.objects.filter(shipment=order.shipment).exists())
