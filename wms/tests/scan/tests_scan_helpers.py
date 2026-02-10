from django.test import TestCase
from django.urls import reverse

from wms.scan_helpers import build_packing_result
from wms.models import Carton, CartonItem, Location, Product, ProductLot, Warehouse


class PackingResultTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Main")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="A", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            sku="SKU-1", name="Compresses", brand="ACME"
        )

    def test_build_packing_result_groups_by_lot(self):
        carton = Carton.objects.create(code="C-LOT")
        lot1 = ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-1",
            quantity_on_hand=10,
            location=self.location,
        )
        lot2 = ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-2",
            quantity_on_hand=10,
            location=self.location,
        )
        CartonItem.objects.create(carton=carton, product_lot=lot1, quantity=2)
        CartonItem.objects.create(carton=carton, product_lot=lot2, quantity=3)

        result = build_packing_result([carton.id])
        items = result["cartons"][0]["items"]
        labels = {item["label"] for item in items}
        self.assertEqual(len(items), 2)
        self.assertTrue(any(label.endswith("Lot LOT-1") for label in labels))
        self.assertTrue(any(label.endswith("Lot LOT-2") for label in labels))
        self.assertEqual(
            result["cartons"][0]["packing_list_url"],
            reverse("scan:scan_carton_document", args=[carton.id]),
        )
        self.assertEqual(
            result["cartons"][0]["picking_url"],
            reverse("scan:scan_carton_picking", args=[carton.id]),
        )

    def test_build_packing_result_merges_without_lot(self):
        carton = Carton.objects.create(code="C-NOLOT")
        lot1 = ProductLot.objects.create(
            product=self.product,
            lot_code="",
            quantity_on_hand=10,
            location=self.location,
        )
        lot2 = ProductLot.objects.create(
            product=self.product,
            lot_code="",
            quantity_on_hand=10,
            location=self.location,
        )
        CartonItem.objects.create(carton=carton, product_lot=lot1, quantity=1)
        CartonItem.objects.create(carton=carton, product_lot=lot2, quantity=4)

        result = build_packing_result([carton.id])
        items = result["cartons"][0]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 5)
