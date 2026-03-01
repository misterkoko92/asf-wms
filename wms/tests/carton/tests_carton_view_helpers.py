from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse

from wms.carton_view_helpers import build_cartons_ready_rows, get_carton_capacity_cm3
from wms.models import CartonFormat, CartonStatus


class CartonViewHelpersTests(TestCase):
    def test_get_carton_capacity_cm3_uses_default_then_fallback(self):
        self.assertIsNone(get_carton_capacity_cm3())

        fallback = CartonFormat.objects.create(
            name="Fallback",
            length_cm=Decimal("40"),
            width_cm=Decimal("30"),
            height_cm=Decimal("20"),
            max_weight_g=8000,
            is_default=False,
        )
        self.assertEqual(get_carton_capacity_cm3(), Decimal("24000"))

        CartonFormat.objects.create(
            name="Default",
            length_cm=Decimal("50"),
            width_cm=Decimal("40"),
            height_cm=Decimal("30"),
            max_weight_g=9000,
            is_default=True,
        )
        self.assertEqual(get_carton_capacity_cm3(), Decimal("60000"))
        self.assertEqual(fallback.is_default, False)

    def test_build_cartons_ready_rows_builds_status_urls_weights_and_volume(self):
        product_with_metrics = SimpleNamespace(
            id=1,
            sku="SKU-1",
            name="Mask",
            brand="BrandX",
            weight_g=500,
            volume_cm3=1000,
        )
        product_missing_weight = SimpleNamespace(
            id=2,
            sku="SKU-2",
            name="Gloves",
            brand="",
            weight_g=None,
            volume_cm3=400,
        )
        product_missing_volume = SimpleNamespace(
            id=3,
            sku="SKU-3",
            name="Kit",
            brand="",
            weight_g=200,
            volume_cm3=None,
        )
        product_missing_both = SimpleNamespace(
            id=4,
            sku="SKU-4",
            name="Unknown",
            brand="",
            weight_g=None,
            volume_cm3=None,
        )

        item_assigned = SimpleNamespace(
            product_lot=SimpleNamespace(product=product_with_metrics, lot_code="L1"),
            quantity=2,
        )
        item_draft = SimpleNamespace(
            product_lot=SimpleNamespace(product=product_with_metrics, lot_code=""),
            quantity=1,
        )
        item_missing_weight = SimpleNamespace(
            product_lot=SimpleNamespace(product=product_missing_weight, lot_code=""),
            quantity=1,
        )
        item_missing_volume = SimpleNamespace(
            product_lot=SimpleNamespace(product=product_missing_volume, lot_code=""),
            quantity=1,
        )
        item_missing_both = SimpleNamespace(
            product_lot=SimpleNamespace(product=product_missing_both, lot_code=""),
            quantity=1,
        )

        carton_assigned = SimpleNamespace(
            id=10,
            code="C-010",
            created_at=datetime(2026, 1, 10, 12, 0, 0),
            status=CartonStatus.ASSIGNED,
            shipment_id=77,
            shipment=SimpleNamespace(reference="S-077", status="draft"),
            current_location="A1",
            cartonitem_set=SimpleNamespace(all=lambda: [item_assigned]),
        )
        carton_draft = SimpleNamespace(
            id=11,
            code="C-011",
            created_at=datetime(2026, 1, 11, 12, 0, 0),
            status=CartonStatus.DRAFT,
            shipment_id=None,
            shipment=None,
            current_location="A2",
            cartonitem_set=SimpleNamespace(all=lambda: [item_missing_both]),
        )
        carton_unknown_status = SimpleNamespace(
            id=12,
            code="C-012",
            created_at=datetime(2026, 1, 12, 12, 0, 0),
            status="unknown-status",
            shipment_id=None,
            shipment=None,
            current_location="A3",
            cartonitem_set=SimpleNamespace(all=lambda: [item_missing_volume]),
        )

        rows = build_cartons_ready_rows(
            [carton_assigned, carton_draft, carton_unknown_status],
            carton_capacity_cm3=5000,
        )

        self.assertEqual([row["id"] for row in rows], [10, 11, 12])

        assigned_row = rows[0]
        self.assertEqual(assigned_row["status_label"], "Affecté")
        self.assertFalse(assigned_row["can_toggle"])
        self.assertEqual(assigned_row["shipment_reference"], "S-077")
        self.assertEqual(
            assigned_row["packing_list_url"],
            reverse("scan:scan_shipment_carton_document", args=[77, 10]),
        )
        self.assertTrue(
            assigned_row["packing_list_url"].endswith("/scan/shipment/77/carton/10/doc/")
        )
        self.assertEqual(
            assigned_row["picking_url"],
            reverse("scan:scan_carton_picking", args=[10]),
        )
        self.assertTrue(assigned_row["picking_url"].endswith("/scan/carton/10/picking/"))
        self.assertEqual(assigned_row["weight_kg"], 1.0)
        self.assertEqual(assigned_row["volume_percent"], 40)

        draft_row = rows[1]
        self.assertEqual(draft_row["status_label"], "Créé")
        self.assertTrue(draft_row["can_toggle"])
        self.assertEqual(draft_row["shipment_reference"], "")
        self.assertEqual(
            draft_row["packing_list_url"],
            reverse("scan:scan_carton_document", args=[11]),
        )
        self.assertTrue(draft_row["packing_list_url"].endswith("/scan/carton/11/doc/"))
        self.assertIsNone(draft_row["weight_kg"])
        self.assertIsNone(draft_row["volume_percent"])

        unknown_row = rows[2]
        self.assertEqual(unknown_row["status_label"], "unknown-status")
        self.assertIsNone(unknown_row["volume_percent"])
        self.assertEqual(unknown_row["packing_list"][0]["quantity"], 1)
