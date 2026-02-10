from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.product_import_review import (
    build_match_context,
    format_import_location,
    row_is_empty,
    summarize_import_row,
)


class ProductImportReviewTests(SimpleTestCase):
    def test_row_is_empty(self):
        self.assertTrue(row_is_empty({"a": "", "b": "  ", "c": None}))
        self.assertFalse(row_is_empty({"a": "", "b": "x"}))

    def test_format_import_location(self):
        row = {"warehouse": "WH", "zone": "Z1", "aisle": "A1", "shelf": "S1"}
        self.assertEqual(format_import_location(row), "WH Z1-A1-S1")
        self.assertEqual(format_import_location({"warehouse": "WH"}), "-")

    def test_summarize_import_row(self):
        row = {
            "sku": "SKU-1",
            "nom_produit": "Mask",
            "marque": "BrandX",
            "quantite": "2",
            "entrepot": "WH",
            "rack": "R1",
            "etagere": "A1",
            "bac": "S1",
        }
        self.assertEqual(
            summarize_import_row(row),
            {
                "sku": "SKU-1",
                "name": "Mask",
                "brand": "BrandX",
                "quantity": 2,
                "location": "WH R1-A1-S1",
            },
        )
        self.assertEqual(
            summarize_import_row({}),
            {
                "sku": "",
                "name": "",
                "brand": "",
                "quantity": "-",
                "location": "-",
            },
        )

    def test_build_match_context_handles_none_and_empty_match_ids(self):
        self.assertIsNone(build_match_context(None))

        pending = {
            "token": "tok-1",
            "matches": [{"row_index": 2, "match_type": "unknown", "row_summary": {"sku": "X"}, "match_ids": []}],
            "default_action": "create",
        }
        context = build_match_context(pending)
        self.assertEqual(context["token"], "tok-1")
        self.assertEqual(context["default_action"], "create")
        self.assertEqual(context["matches"][0]["match_type"], "")
        self.assertEqual(context["matches"][0]["products"], [])

    def test_build_match_context_resolves_products_and_labels(self):
        pending = {
            "token": "tok-2",
            "matches": [
                {
                    "row_index": 3,
                    "match_type": "sku",
                    "row_summary": {"sku": "SKU-1"},
                    "match_ids": [10, 99],
                },
                {
                    "row_index": 4,
                    "match_type": "name_brand",
                    "row_summary": {"name": "Mask"},
                    "match_ids": [10],
                },
            ],
        }
        product = SimpleNamespace(
            id=10,
            sku="SKU-10",
            name="Mask",
            brand="BrandX",
            available_stock=7,
            default_location=SimpleNamespace(__str__=lambda self: "WH-Z1-A1-S1"),
        )
        query = mock.MagicMock()
        query.select_related.return_value = query
        query.annotate.return_value = [product]
        with mock.patch("wms.product_import_review.Product.objects.filter", return_value=query):
            context = build_match_context(pending)

        self.assertEqual(context["token"], "tok-2")
        self.assertEqual(context["default_action"], "update")
        self.assertEqual(context["matches"][0]["match_type"], "SKU")
        self.assertEqual(context["matches"][1]["match_type"], "Nom + Marque")
        self.assertEqual(len(context["matches"][0]["products"]), 1)
        self.assertEqual(context["matches"][0]["products"][0]["id"], 10)
        self.assertEqual(context["matches"][0]["products"][0]["available_stock"], 7)
