from decimal import Decimal

from django.test import TestCase

from wms.models import Location, Product, ProductCategory, Warehouse


class ListingSuggestionEngineTests(TestCase):
    def test_build_listing_assisted_suggestions_auto_matches_unique_ean(self):
        from wms.incomplete_product_suggestions import build_listing_assisted_suggestions

        product = Product.objects.create(
            name="Thermometre Braun",
            brand="BRAUN",
            ean="1234567890123",
        )

        result = build_listing_assisted_suggestions(
            rows=[
                {
                    "index": 2,
                    "name": "BRAUN THERMOMETRE FRONTAL",
                    "ean": "1234567890123",
                }
            ]
        )

        self.assertEqual(result["auto_matches"]["row-2"]["product_id"], product.id)
        self.assertEqual(result["auto_matches"]["row-2"]["match_type"], "ean")

    def test_build_listing_assisted_suggestions_ignores_duplicate_ean_matches(self):
        from wms.incomplete_product_suggestions import build_listing_assisted_suggestions

        Product.objects.create(name="Produit A", brand="BRAUN", ean="1234567890123")
        Product.objects.create(name="Produit B", brand="BRAUN", ean="1234567890123")

        result = build_listing_assisted_suggestions(
            rows=[
                {
                    "index": 2,
                    "name": "BRAUN THERMOMETRE FRONTAL",
                    "ean": "1234567890123",
                }
            ]
        )

        self.assertEqual(result["auto_matches"], {})

    def test_build_listing_assisted_suggestions_emits_brand_group_from_batch_prefix(self):
        from wms.incomplete_product_suggestions import build_listing_assisted_suggestions

        root_category = ProductCategory.objects.create(name="DIAGNOSTIC")
        child_category = ProductCategory.objects.create(name="THERMOMETRES", parent=root_category)
        warehouse = Warehouse.objects.create(name="Main")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        Product.objects.create(
            name="Thermometre Auriculaire",
            brand="BRAUN",
            category=child_category,
            tva=Decimal("0.0550"),
            default_location=location,
        )
        Product.objects.create(
            name="Thermometre Frontal",
            brand="BRAUN",
            category=child_category,
            tva=Decimal("0.0550"),
            default_location=location,
        )

        result = build_listing_assisted_suggestions(
            rows=[
                {"index": 2, "name": "BRAUN THERMOMETRE FRONTAL", "brand": ""},
                {"index": 3, "name": "BRAUN THERMOMETRE AURICULAIRE", "brand": ""},
                {"index": 4, "name": "BRAUN THERMOMETRE SANS CONTACT", "brand": ""},
            ]
        )

        self.assertEqual(len(result["group_suggestions"]), 4)
        self.assertEqual(result["group_suggestions"][0]["field_name"], "brand")
        self.assertEqual(result["group_suggestions"][0]["proposed_value"], "BRAUN")
        self.assertEqual(result["group_suggestions"][0]["confidence"], "Forte")
        self.assertEqual(result["group_suggestions"][0]["source"], "Base + Batch")
        self.assertEqual(result["group_suggestions"][0]["row_keys"], ["row-2", "row-3", "row-4"])
