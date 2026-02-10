from django.test import TestCase

from wms.models import Product
from wms.scan_pack_helpers import build_pack_line_values, build_packing_bins


class ScanPackHelpersTests(TestCase):
    def setUp(self):
        self.carton_size = {
            "length_cm": 40,
            "width_cm": 30,
            "height_cm": 30,
            "max_weight_g": 8000,
        }

    def test_build_packing_bins_requires_dimensions_when_no_defaults(self):
        product = Product.objects.create(name="No Data", sku="NO-DATA")
        bins, errors, warnings = build_packing_bins(
            [{"product": product, "quantity": 1}],
            self.carton_size,
            apply_defaults=False,
        )
        self.assertIsNone(bins)
        self.assertTrue(errors)
        self.assertEqual(warnings, [])

    def test_build_packing_bins_applies_defaults(self):
        product = Product.objects.create(name="No Data", sku="NO-DATA")
        bins, errors, warnings = build_packing_bins(
            [{"product": product, "quantity": 2}],
            self.carton_size,
            apply_defaults=True,
        )
        self.assertIsNotNone(bins)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_build_packing_bins_detects_overweight(self):
        product = Product.objects.create(
            name="Heavy",
            sku="HEAVY",
            weight_g=9000,
            length_cm=10,
            width_cm=10,
            height_cm=10,
        )
        bins, errors, warnings = build_packing_bins(
            [{"product": product, "quantity": 1}],
            self.carton_size,
            apply_defaults=True,
        )
        self.assertIsNone(bins)
        self.assertTrue(errors)
        self.assertEqual(warnings, [])

    def test_build_pack_line_values_defaults(self):
        lines = build_pack_line_values(2)
        self.assertEqual(
            lines,
            [
                {"product_code": "", "quantity": ""},
                {"product_code": "", "quantity": ""},
            ],
        )

    def test_build_pack_line_values_reads_payload(self):
        data = {"line_1_product_code": "SKU-1", "line_1_quantity": "3"}
        lines = build_pack_line_values(1, data)
        self.assertEqual(lines[0]["product_code"], "SKU-1")
        self.assertEqual(lines[0]["quantity"], "3")
