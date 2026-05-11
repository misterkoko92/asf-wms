from types import SimpleNamespace
from unittest import mock

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

    def test_import_product_row_auto_generates_sku_when_blank(self):
        product, created, warnings = import_product_row({"name": "Produit Sans SKU"})

        self.assertTrue(created)
        self.assertTrue(product.sku.startswith("ASF-"))
        self.assertRegex(product.sku, r"^ASF-[A-F0-9]{8}$")
        self.assertEqual(warnings, [])

    def test_import_product_row_auto_generates_sku_with_installation_prefix(self):
        installation = SimpleNamespace(identity=SimpleNamespace(sku_prefix="ORG"))

        with mock.patch(
            "wms.models_domain.catalog.get_installation_config",
            return_value=installation,
        ):
            product, created, warnings = import_product_row({"name": "Produit Sans SKU"})

        self.assertTrue(created)
        self.assertTrue(product.sku.startswith("ORG-"))
        self.assertRegex(product.sku, r"^ORG-[A-F0-9]{8}$")
        self.assertEqual(warnings, [])

    def test_import_product_row_rejects_duplicate_rack_color_in_same_warehouse(self):
        existing, _, _ = import_product_row(
            {
                "name": "Produit Existant",
                "warehouse": "Main",
                "zone": "A",
                "aisle": "01",
                "shelf": "001",
                "rack_color": "#FF0000",
            }
        )

        with self.assertRaisesMessage(ValueError, "Couleur rack déjà utilisée dans cet entrepôt."):
            import_product_row(
                {
                    "name": "Produit Nouveau",
                    "warehouse": "Main",
                    "zone": "B",
                    "aisle": "01",
                    "shelf": "001",
                    "rack_color": "#FF0000",
                }
            )

        self.assertEqual(existing.default_location.zone, "A")

    def test_import_product_row_allows_same_rack_color_in_other_warehouse(self):
        import_product_row(
            {
                "name": "Produit Main",
                "warehouse": "Main",
                "zone": "A",
                "aisle": "01",
                "shelf": "001",
                "rack_color": "#FF0000",
            }
        )

        product, created, warnings = import_product_row(
            {
                "name": "Produit Secondary",
                "warehouse": "Secondary",
                "zone": "A",
                "aisle": "01",
                "shelf": "001",
                "rack_color": "#FF0000",
            }
        )

        self.assertTrue(created)
        self.assertEqual(product.default_location.warehouse.name, "Secondary")
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

    def test_find_product_matches_prefers_barcode_then_ean_before_name_brand(self):
        barcode_product = Product.objects.create(
            name="Item",
            sku="SKU-BAR",
            brand="ACME",
            barcode="BAR-001",
        )
        ean_product = Product.objects.create(
            name="Item",
            sku="SKU-EAN",
            brand="ACME",
            ean="EAN-001",
        )

        matches, mode = find_product_matches(
            sku="",
            name="Item",
            brand="ACME",
            barcode="BAR-001",
            ean="EAN-001",
        )
        self.assertEqual(mode, "barcode")
        self.assertEqual([match.id for match in matches], [barcode_product.id])

        matches, mode = find_product_matches(
            sku="",
            name="Item",
            brand="ACME",
            barcode="",
            ean="EAN-001",
        )
        self.assertEqual(mode, "ean")
        self.assertEqual([match.id for match in matches], [ean_product.id])

    def test_find_product_matches_barcode_ignores_case_and_special_chars(self):
        product = Product.objects.create(
            name="Item",
            sku="SKU-BAR-NORM",
            brand="ACME",
            barcode="BAR CODE-001",
        )

        matches, mode = find_product_matches(
            sku="",
            name="Other",
            brand="ACME",
            barcode="barcode 001",
            ean="",
        )

        self.assertEqual(mode, "barcode")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_ean_ignores_case_and_special_chars(self):
        product = Product.objects.create(
            name="Item",
            sku="SKU-EAN-NORM",
            brand="ACME",
            ean="EAN 001-XYZ",
        )

        matches, mode = find_product_matches(
            sku="",
            name="Other",
            brand="ACME",
            barcode="",
            ean="ean001xyz",
        )

        self.assertEqual(mode, "ean")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_name_brand_fallback(self):
        product = Product.objects.create(name="Item", sku="SKU-1", brand="ACME")
        matches, mode = find_product_matches(sku="", name="Item", brand="ACME")
        self.assertEqual(mode, "name_brand")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_sku_ignores_case_and_special_chars(self):
        product = Product.objects.create(name="Item", sku="SKU-ABC_123", brand="ACME")
        matches, mode = find_product_matches(
            sku="sku abc-123",
            name="Other",
            brand="ACME",
        )
        self.assertEqual(mode, "sku")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_name_brand_ignores_case_accents_and_special_chars(self):
        product = Product.objects.create(
            name="Pansement-Gel",
            sku="SKU-NORM-1",
            brand="Médical Plus",
        )
        matches, mode = find_product_matches(
            sku="",
            name="pansement gel",
            brand="medical plus",
        )
        self.assertEqual(mode, "name_brand")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_name_only_fallback(self):
        product = Product.objects.create(
            name="Masque FFP2",
            sku="SKU-NAME-1",
            brand="",
        )
        matches, mode = find_product_matches(
            sku="",
            name="Masque FFP2",
            brand="",
        )
        self.assertEqual(mode, "name")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_name_only_ignores_case_accents_and_special_chars(self):
        product = Product.objects.create(
            name="Masque FFP2+",
            sku="SKU-NAME-NORM",
            brand="",
        )

        matches, mode = find_product_matches(
            sku="",
            name="masqué ffp2",
            brand="",
        )

        self.assertEqual(mode, "name")
        self.assertEqual([match.id for match in matches], [product.id])

    def test_find_product_matches_returns_empty_for_values_that_normalize_to_blank(self):
        matches, mode = find_product_matches(
            sku="***",
            name="???",
            brand="---",
            barcode="!!!",
            ean="###",
        )

        self.assertEqual(matches, [])
        self.assertIsNone(mode)
