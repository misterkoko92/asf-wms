from django.test import TestCase

from wms.models import Location, Product, ProductKitItem, ProductLot, Warehouse
from wms.scan_product_helpers import (
    build_product_options,
    build_product_group_key,
    build_product_label,
    build_product_selection_data,
    get_product_volume_cm3,
    get_product_weight_g,
    resolve_product,
)


class ScanProductHelpersTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Main")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="A", aisle="01", shelf="001"
        )

    def test_resolve_product_prefers_barcode(self):
        product_barcode = Product.objects.create(
            name="Barcode Product",
            sku="SKU-B",
            barcode="MATCH",
        )
        Product.objects.create(name="Ean Product", sku="SKU-E", ean="MATCH")
        Product.objects.create(name="Sku Product", sku="MATCH")
        Product.objects.create(name="MATCH")

        resolved = resolve_product("MATCH")
        self.assertEqual(resolved.id, product_barcode.id)

    def test_resolve_product_prefix_unique(self):
        Product.objects.create(name="Compresses", sku="CMP-1")
        Product.objects.create(name="Bandages", sku="BND-1")
        resolved = resolve_product("Comp")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, "Compresses")

    def test_resolve_product_prefix_ambiguous_returns_none(self):
        Product.objects.create(name="Compresses", sku="CMP-1")
        Product.objects.create(name="Composite", sku="CMP-2")
        resolved = resolve_product("Comp")
        self.assertIsNone(resolved)

    def test_get_product_weight_g_for_kit(self):
        component_a = Product.objects.create(name="Comp A", sku="C-A", weight_g=100)
        component_b = Product.objects.create(name="Comp B", sku="C-B", weight_g=50)
        kit = Product.objects.create(name="Kit", sku="KIT-1")
        ProductKitItem.objects.create(kit=kit, component=component_a, quantity=2)
        ProductKitItem.objects.create(kit=kit, component=component_b, quantity=1)

        self.assertEqual(get_product_weight_g(kit), 250)

    def test_get_product_weight_g_missing_component_weight(self):
        component_a = Product.objects.create(name="Comp A", sku="C-A", weight_g=100)
        component_b = Product.objects.create(name="Comp B", sku="C-B")
        kit = Product.objects.create(name="Kit", sku="KIT-2")
        ProductKitItem.objects.create(kit=kit, component=component_a, quantity=1)
        ProductKitItem.objects.create(kit=kit, component=component_b, quantity=1)

        self.assertIsNone(get_product_weight_g(kit))

    def test_get_product_volume_cm3_for_kit(self):
        component = Product.objects.create(
            name="Comp V", sku="C-V", length_cm=2, width_cm=3, height_cm=4
        )
        kit = Product.objects.create(name="Kit V", sku="KIT-V")
        ProductKitItem.objects.create(kit=kit, component=component, quantity=2)

        self.assertEqual(get_product_volume_cm3(kit), 48)

    def test_build_product_options_includes_kits(self):
        component = Product.objects.create(
            name="Comp", sku="COMP-1", weight_g=100, length_cm=1, width_cm=1, height_cm=1
        )
        ProductLot.objects.create(
            product=component,
            quantity_on_hand=10,
            quantity_reserved=0,
            location=self.location,
        )
        kit = Product.objects.create(name="Kit", sku="KIT-1")
        ProductKitItem.objects.create(kit=kit, component=component, quantity=2)

        options = build_product_options(include_kits=True)
        kit_option = next(item for item in options if item["id"] == kit.id)
        self.assertEqual(kit_option["available_stock"], 5)

    def test_build_product_group_key_prefers_lot(self):
        product = Product.objects.create(name="Lot Product", sku="SKU-LOT", brand="Brand")
        key = build_product_group_key(product, "lot-1")
        self.assertEqual(key, ("SKU-LOT", "LOT-1"))

    def test_build_product_group_key_uses_brand_fallback(self):
        product = Product.objects.create(name="Brand Product", sku="SKU-B", brand="Acme")
        key = build_product_group_key(product, "")
        self.assertEqual(key, ("SKU-B", "ACME"))

    def test_build_product_label_includes_brand_and_lot(self):
        product = Product.objects.create(name="Compresses", sku="SKU-C", brand="ACME")
        label = build_product_label(product, "LOT-9")
        self.assertEqual(label, "Compresses (ACME) - Lot LOT-9")

    def test_build_product_selection_data_returns_lookup(self):
        product = Product.objects.create(name="Item", sku="SKU-1")
        options, products_by_id, available_by_id = build_product_selection_data()
        option_ids = {item["id"] for item in options}
        self.assertIn(product.id, option_ids)
        self.assertIn(product.id, products_by_id)
        self.assertIn(product.id, available_by_id)
