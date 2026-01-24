from django.test import TestCase

from wms.import_services_products import (
    extract_product_identity,
    find_product_matches,
    import_product_row,
)
from wms.models import Product, ProductCategory, ProductLot, RackColor


class ImportProductsExtraTests(TestCase):
    def test_import_product_row_normalizes_and_creates_stock(self):
        row = {
            "name": "compresses steriles",
            "brand": "acme",
            "warehouse": "Main",
            "zone": "a",
            "aisle": "b",
            "shelf": "c",
            "rack_color": "#FF0000",
            "length_cm": "2",
            "width_cm": "3",
            "height_cm": "4",
            "quantity": "5",
            "category_l1": "medical",
            "category_l2": "epi",
        }
        product, created, warnings = import_product_row(row)
        self.assertTrue(created)
        self.assertEqual(product.name, "Compresses Steriles")
        self.assertEqual(product.brand, "ACME")
        self.assertEqual(product.volume_cm3, 24)
        self.assertIsNotNone(product.default_location_id)
        location = product.default_location
        self.assertEqual((location.zone, location.aisle, location.shelf), ("A", "B", "C"))
        rack_color = RackColor.objects.get(
            warehouse=location.warehouse,
            zone="A",
        )
        self.assertEqual(rack_color.color, "#FF0000")
        self.assertEqual(ProductLot.objects.count(), 1)
        lot = ProductLot.objects.get()
        self.assertEqual(lot.quantity_on_hand, 5)
        category = ProductCategory.objects.get(id=product.category_id)
        self.assertEqual(category.name, "EPI")
        self.assertEqual(category.parent.name, "MEDICAL")
        self.assertEqual(warnings, [])

    def test_extract_product_identity_normalizes(self):
        sku, name, brand = extract_product_identity(
            {"sku": "SKU-1", "name": "compresses steriles", "brand": "acme"}
        )
        self.assertEqual(sku, "SKU-1")
        self.assertEqual(name, "Compresses Steriles")
        self.assertEqual(brand, "ACME")

    def test_find_product_matches_prefers_sku(self):
        product = Product.objects.create(name="Item", sku="SKU-1", brand="ACME")
        Product.objects.create(name="Item", sku="SKU-2", brand="ACME")
        matches, mode = find_product_matches(sku="SKU-1", name="Item", brand="ACME")
        self.assertEqual(mode, "sku")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_name_brand_fallback(self):
        product = Product.objects.create(name="Item", sku="SKU-1", brand="ACME")
        matches, mode = find_product_matches(sku="", name="Item", brand="ACME")
        self.assertEqual(mode, "name_brand")
        self.assertEqual([match.id for match in matches], [product.id])
