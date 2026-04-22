from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from wms.models import Location, Product, ProductKitItem, ProductLot, Warehouse
from wms.scan_product_helpers import (
    build_product_group_key,
    build_product_label,
    build_product_options,
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

    def test_resolve_product_falls_back_to_ean_before_sku(self):
        product_ean = Product.objects.create(
            name="Ean Product",
            sku="SKU-EAN",
            ean="MATCH-EAN",
        )
        Product.objects.create(name="Sku Product", sku="MATCH-EAN")

        resolved = resolve_product("MATCH-EAN")

        self.assertEqual(resolved.id, product_ean.id)

    def test_resolve_product_extracts_udi_gtin_for_ean_lookup(self):
        product = Product.objects.create(
            name="UDI EAN Product",
            sku="UDI-EAN",
            ean="1234567890123",
        )

        resolved = resolve_product("(01)01234567890123(17)260501(10)LOT-A")

        self.assertEqual(resolved.id, product.id)

    def test_resolve_product_extracts_plain_gs1_udi_gtin_for_barcode_lookup(self):
        product = Product.objects.create(
            name="UDI Barcode Product",
            sku="UDI-BARCODE",
            barcode="01234567890123",
        )

        resolved = resolve_product("01012345678901231726050110LOT-A")

        self.assertEqual(resolved.id, product.id)

    def test_resolve_product_returns_none_for_empty_code(self):
        self.assertIsNone(resolve_product(""))
        self.assertIsNone(resolve_product("   "))

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

    def test_build_product_options_includes_nested_kits(self):
        component_a = Product.objects.create(name="Comp A2", sku="COMP-A2")
        component_b = Product.objects.create(name="Comp B2", sku="COMP-B2")
        ProductLot.objects.create(
            product=component_a,
            quantity_on_hand=10,
            quantity_reserved=0,
            location=self.location,
        )
        ProductLot.objects.create(
            product=component_b,
            quantity_on_hand=5,
            quantity_reserved=0,
            location=self.location,
        )
        child_kit = Product.objects.create(name="Child Kit", sku="KIT-CHILD")
        ProductKitItem.objects.create(kit=child_kit, component=component_a, quantity=2)
        parent_kit = Product.objects.create(name="Parent Kit", sku="KIT-PARENT")
        ProductKitItem.objects.create(kit=parent_kit, component=child_kit, quantity=1)
        ProductKitItem.objects.create(kit=parent_kit, component=component_b, quantity=1)

        options = build_product_options(include_kits=True)
        parent_option = next(item for item in options if item["id"] == parent_kit.id)
        self.assertEqual(parent_option["available_stock"], 5)

    def test_build_product_options_skips_empty_kits_and_non_positive_quantities(self):
        component = Product.objects.create(
            name="Comp 2",
            sku="COMP-2",
            weight_g=100,
            length_cm=1,
            width_cm=1,
            height_cm=1,
        )
        ProductLot.objects.create(
            product=component,
            quantity_on_hand=4,
            quantity_reserved=0,
            location=self.location,
        )
        zero_qty_kit = Product.objects.create(name="Zero Kit", sku="KIT-ZERO")
        ProductKitItem.objects.create(kit=zero_qty_kit, component=component, quantity=0)

        options = build_product_options(include_kits=True)
        zero_kit_option = next(item for item in options if item["id"] == zero_qty_kit.id)
        self.assertEqual(zero_kit_option["available_stock"], 0)

    def test_build_product_options_sets_unknown_kit_metrics_to_none(self):
        component = Product.objects.create(name="Comp No Metrics", sku="COMP-NO-METRICS")
        ProductLot.objects.create(
            product=component,
            quantity_on_hand=4,
            quantity_reserved=0,
            location=self.location,
        )
        kit = Product.objects.create(name="Kit No Metrics", sku="KIT-NO-METRICS")
        ProductKitItem.objects.create(kit=kit, component=component, quantity=2)

        options = build_product_options(include_kits=True)
        kit_option = next(item for item in options if item["id"] == kit.id)

        self.assertEqual(kit_option["available_stock"], 2)
        self.assertIsNone(kit_option["weight_g"])
        self.assertIsNone(kit_option["volume_cm3"])

    def test_build_product_options_skips_defensive_empty_prefetched_kit(self):
        base_qs = mock.MagicMock()
        base_qs.annotate.return_value = base_qs
        base_qs.order_by.return_value = base_qs
        base_qs.values.return_value = []
        base_qs.values_list.return_value = []

        fake_kit = SimpleNamespace(kit_items=SimpleNamespace(all=lambda: []))
        kit_qs = mock.MagicMock()
        kit_qs.prefetch_related.return_value = kit_qs
        kit_qs.order_by.return_value = [fake_kit]

        def filter_side_effect(*args, **kwargs):
            if kwargs.get("kit_items__isnull") is True:
                return base_qs
            if kwargs.get("kit_items__isnull") is False:
                return kit_qs
            return Product.objects.none()

        with mock.patch(
            "wms.scan_product_helpers.Product.objects.filter",
            side_effect=filter_side_effect,
        ):
            options = build_product_options(include_kits=True)

        self.assertEqual(options, [])

    def test_build_product_options_limits_queries_when_including_multiple_kits(self):
        components = []
        for index in range(12):
            product = Product.objects.create(
                name=f"Component {index}",
                sku=f"COMP-{index}",
                weight_g=100 + index,
                length_cm=1,
                width_cm=2,
                height_cm=3,
            )
            ProductLot.objects.create(
                product=product,
                quantity_on_hand=20,
                quantity_reserved=0,
                location=self.location,
            )
            components.append(product)

        for index in range(3):
            child_kit = Product.objects.create(name=f"Child Kit {index}", sku=f"CHILD-{index}")
            ProductKitItem.objects.create(
                kit=child_kit,
                component=components[index * 4],
                quantity=1,
            )
            ProductKitItem.objects.create(
                kit=child_kit,
                component=components[index * 4 + 1],
                quantity=1,
            )
            parent_kit = Product.objects.create(name=f"Parent Kit {index}", sku=f"PARENT-{index}")
            ProductKitItem.objects.create(kit=parent_kit, component=child_kit, quantity=1)
            ProductKitItem.objects.create(
                kit=parent_kit,
                component=components[index * 4 + 2],
                quantity=1,
            )
            ProductKitItem.objects.create(
                kit=parent_kit,
                component=components[index * 4 + 3],
                quantity=1,
            )

        previous_debug_cursor = connection.force_debug_cursor
        connection.force_debug_cursor = True
        try:
            with CaptureQueriesContext(connection) as ctx:
                options = build_product_options(include_kits=True)
        finally:
            connection.force_debug_cursor = previous_debug_cursor

        self.assertLessEqual(len(ctx), 8)
        option_by_sku = {item["sku"]: item for item in options}
        self.assertEqual(option_by_sku["PARENT-0"]["available_stock"], 20)
        self.assertEqual(option_by_sku["PARENT-0"]["weight_g"], 406)

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

    def test_get_product_volume_cm3_returns_none_when_kit_component_volume_missing(self):
        component = Product.objects.create(name="No Volume", sku="NO-VOLUME")
        kit = Product.objects.create(name="Kit No Volume", sku="KIT-NV")
        ProductKitItem.objects.create(kit=kit, component=component, quantity=1)

        self.assertIsNone(get_product_volume_cm3(kit))

    def test_get_product_weight_g_for_non_kit_uses_direct_weight(self):
        product = Product.objects.create(name="Simple Product", sku="SIMPLE-1", weight_g=250)

        self.assertEqual(get_product_weight_g(product), 250)

    def test_get_product_weight_g_for_nested_kit(self):
        component_a = Product.objects.create(name="Comp Weight A", sku="W-A", weight_g=100)
        component_b = Product.objects.create(name="Comp Weight B", sku="W-B", weight_g=200)
        child_kit = Product.objects.create(name="Child Weight Kit", sku="W-CHILD")
        ProductKitItem.objects.create(kit=child_kit, component=component_a, quantity=2)
        parent_kit = Product.objects.create(name="Parent Weight Kit", sku="W-PARENT")
        ProductKitItem.objects.create(kit=parent_kit, component=child_kit, quantity=3)
        ProductKitItem.objects.create(kit=parent_kit, component=component_b, quantity=1)

        self.assertEqual(get_product_weight_g(parent_kit), 800)

    def test_get_product_volume_cm3_for_non_kit_uses_volume_field(self):
        product = Product.objects.create(name="Simple Volume", sku="SIMPLE-V", volume_cm3=321)

        self.assertEqual(get_product_volume_cm3(product), 321)
