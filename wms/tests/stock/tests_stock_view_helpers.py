from django.test import RequestFactory, TestCase

from wms.models import (
    Location,
    MovementType,
    Product,
    ProductCategory,
    ProductLot,
    StockMovement,
    Warehouse,
)
from wms.stock_view_helpers import build_stock_context


class StockViewHelpersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.warehouse_a = Warehouse.objects.create(name="Alpha", code="A")
        self.warehouse_b = Warehouse.objects.create(name="Bravo", code="B")
        self.location_a = Location.objects.create(
            warehouse=self.warehouse_a,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.location_b = Location.objects.create(
            warehouse=self.warehouse_b,
            zone="B",
            aisle="01",
            shelf="001",
        )
        self.category_med = ProductCategory.objects.create(name="Medical")
        self.category_food = ProductCategory.objects.create(name="Food")

    def _create_product(self, sku, name, *, category):
        return Product.objects.create(
            sku=sku,
            name=name,
            category=category,
            qr_code_image="qr_codes/test.png",
            is_active=True,
        )

    def test_build_stock_context_applies_query_category_warehouse_and_sort(self):
        product_a = self._create_product("ABC-001", "Mask", category=self.category_med)
        product_b = self._create_product("DEF-001", "Rice", category=self.category_food)
        product_c = self._create_product("ABC-EMPTY", "Mask Empty", category=self.category_med)

        lot_a = ProductLot.objects.create(
            product=product_a,
            location=self.location_a,
            quantity_on_hand=10,
            quantity_reserved=3,
        )
        ProductLot.objects.create(
            product=product_b,
            location=self.location_b,
            quantity_on_hand=8,
            quantity_reserved=0,
        )
        ProductLot.objects.create(
            product=product_c,
            location=self.location_a,
            quantity_on_hand=0,
            quantity_reserved=0,
        )

        StockMovement.objects.create(
            movement_type=MovementType.IN,
            product=product_a,
            product_lot=lot_a,
            quantity=10,
            to_location=self.location_a,
        )

        request = self.factory.get(
            "/scan/stock/",
            {
                "q": "ABC",
                "category": str(self.category_med.id),
                "warehouse": str(self.warehouse_a.id),
                "sort": "qty_desc",
            },
        )
        context = build_stock_context(request)

        products = list(context["products"])
        self.assertEqual([item.id for item in products], [product_a.id])
        self.assertEqual(products[0].stock_total, 7)
        self.assertEqual(context["query"], "ABC")
        self.assertEqual(context["category_id"], str(self.category_med.id))
        self.assertEqual(context["warehouse_id"], str(self.warehouse_a.id))
        self.assertEqual(context["sort"], "qty_desc")
        self.assertFalse(context["include_zero"])
        self.assertEqual(
            [category.name for category in context["categories"]],
            ["FOOD", "MEDICAL"],
        )
        self.assertEqual(
            [warehouse.name for warehouse in context["warehouses"]],
            ["Alpha", "Bravo"],
        )

    def test_build_stock_context_uses_name_sort_when_sort_is_unknown(self):
        product_b = self._create_product("SKU-B", "Zulu", category=self.category_med)
        product_a = self._create_product("SKU-A", "Alpha", category=self.category_med)

        ProductLot.objects.create(
            product=product_a,
            location=self.location_a,
            quantity_on_hand=5,
            quantity_reserved=0,
        )
        ProductLot.objects.create(
            product=product_b,
            location=self.location_a,
            quantity_on_hand=5,
            quantity_reserved=0,
        )

        request = self.factory.get("/scan/stock/", {"sort": "unknown"})
        context = build_stock_context(request)

        products = list(context["products"])
        self.assertEqual([item.name for item in products], ["Alpha", "Zulu"])
        self.assertEqual(context["sort"], "unknown")
        self.assertFalse(context["include_zero"])

    def test_build_stock_context_include_zero_includes_out_of_stock_products(self):
        product_in_stock = self._create_product(
            "SKU-IN",
            "Alpha In Stock",
            category=self.category_med,
        )
        product_out_stock = self._create_product(
            "SKU-OUT",
            "Zulu Out Stock",
            category=self.category_med,
        )
        ProductLot.objects.create(
            product=product_in_stock,
            location=self.location_a,
            quantity_on_hand=4,
            quantity_reserved=1,
        )

        request_default = self.factory.get("/scan/stock/", {"sort": "name"})
        context_default = build_stock_context(request_default)
        self.assertEqual(
            [item.id for item in context_default["products"]],
            [product_in_stock.id],
        )
        self.assertFalse(context_default["include_zero"])

        request_include_zero = self.factory.get(
            "/scan/stock/",
            {"sort": "name", "include_zero": "1"},
        )
        context_include_zero = build_stock_context(request_include_zero)
        products = list(context_include_zero["products"])
        self.assertEqual(
            [item.id for item in products],
            [product_in_stock.id, product_out_stock.id],
        )
        self.assertEqual([item.stock_total for item in products], [3, 0])
        self.assertTrue(context_include_zero["include_zero"])
