from types import SimpleNamespace
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from wms.models import Product
from wms.scan_pack_helpers import build_packing_bins, build_packing_result


class ScanPackHelpersExtraTests(TestCase):
    def setUp(self):
        self.carton_size = {
            "length_cm": 40,
            "width_cm": 30,
            "height_cm": 30,
            "max_weight_g": 8000,
        }

    def test_build_packing_bins_requires_carton_size(self):
        bins, errors, warnings = build_packing_bins([], None)
        self.assertIsNone(bins)
        self.assertEqual(errors, ["Format de carton requis."])
        self.assertEqual(warnings, [])

    def test_build_packing_bins_warns_when_weight_or_volume_missing(self):
        weight_missing = Product.objects.create(
            name="VolumeOnly",
            sku="VOL-ONLY",
            length_cm=10,
            width_cm=10,
            height_cm=10,
        )
        volume_missing = Product.objects.create(
            name="WeightOnly",
            sku="WGT-ONLY",
            weight_g=120,
        )
        bins, errors, warnings = build_packing_bins(
            [
                {"product": weight_missing, "quantity": 1},
                {"product": volume_missing, "quantity": 1},
            ],
            self.carton_size,
            apply_defaults=False,
        )
        self.assertIsNotNone(bins)
        self.assertEqual(errors, [])
        self.assertTrue(any("poids manquant" in warning for warning in warnings))
        self.assertTrue(any("volume manquant" in warning for warning in warnings))

    def test_build_packing_bins_rejects_product_with_excessive_volume(self):
        oversized = Product.objects.create(
            name="Oversized",
            sku="OVERSIZED",
            weight_g=100,
            length_cm=100,
            width_cm=100,
            height_cm=10,
        )
        bins, errors, warnings = build_packing_bins(
            [{"product": oversized, "quantity": 1}],
            self.carton_size,
            apply_defaults=True,
        )
        self.assertIsNone(bins)
        self.assertTrue(any("volume unitaire superieur" in error for error in errors))
        self.assertEqual(warnings, [])

    def test_build_packing_bins_reuses_existing_bin_for_same_product(self):
        product = Product.objects.create(
            name="Reusable",
            sku="REUSE",
            weight_g=1000,
            length_cm=10,
            width_cm=10,
            height_cm=10,
        )
        bins, errors, warnings = build_packing_bins(
            [
                {"product": product, "quantity": 6},
                {"product": product, "quantity": 2},
            ],
            self.carton_size,
            apply_defaults=False,
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(len(bins), 1)
        entry = bins[0]["items"][product.id]
        self.assertEqual(entry["quantity"], 8)

    def test_build_packing_result_groups_items_and_builds_urls(self):
        product = SimpleNamespace(id=11, sku="SKU-11", name="Mask", brand="ASF")
        lot = SimpleNamespace(product=product, lot_code="LOT-01")
        item_a = SimpleNamespace(product_lot=lot, quantity=2)
        item_b = SimpleNamespace(product_lot=lot, quantity=3)
        carton_without_shipment = SimpleNamespace(
            id=1,
            code="C-001",
            shipment_id=None,
            cartonitem_set=SimpleNamespace(all=lambda: [item_a]),
        )
        carton_with_shipment = SimpleNamespace(
            id=2,
            code="C-002",
            shipment_id=99,
            cartonitem_set=SimpleNamespace(all=lambda: [item_b]),
        )
        queryset = mock.MagicMock()
        queryset.select_related.return_value = queryset
        queryset.prefetch_related.return_value = queryset
        queryset.order_by.return_value = [carton_with_shipment, carton_without_shipment]

        with mock.patch("wms.scan_pack_helpers.Carton.objects.filter", return_value=queryset):
            result = build_packing_result([1, 2])

        self.assertEqual([row["code"] for row in result["cartons"]], ["C-001", "C-002"])
        self.assertEqual(
            result["cartons"][0]["packing_list_url"],
            reverse("scan:scan_carton_document", args=[1]),
        )
        self.assertEqual(
            result["cartons"][1]["packing_list_url"],
            reverse("scan:scan_shipment_carton_document", args=[99, 2]),
        )
        self.assertEqual(
            result["cartons"][0]["picking_url"],
            reverse("scan:scan_carton_picking", args=[1]),
        )
        self.assertEqual(
            result["aggregate"],
            [{"label": "Mask (ASF) - Lot LOT-01", "quantity": 5}],
        )

    def test_build_packing_bins_guards_when_floor_division_returns_zero(self):
        product = Product.objects.create(
            name="Guarded",
            sku="GUARDED",
            weight_g=100,
            length_cm=1,
            width_cm=1,
            height_cm=1,
        )

        def _zero_for_float(value):
            return 0 if isinstance(value, float) else int(value)

        with mock.patch("wms.scan_pack_helpers.int", side_effect=_zero_for_float):
            bins, errors, warnings = build_packing_bins(
                [
                    {"product": product, "quantity": 1},
                    {"product": product, "quantity": 1},
                ],
                self.carton_size,
                apply_defaults=False,
            )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(len(bins), 2)
        self.assertEqual(
            sum(bin_data["items"][product.id]["quantity"] for bin_data in bins),
            2,
        )
