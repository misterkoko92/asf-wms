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
            status_events=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        previous_status=CartonStatus.DRAFT,
                        new_status=CartonStatus.ASSIGNED,
                    )
                ]
            ),
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
            status_events=SimpleNamespace(all=lambda: []),
            cartonitem_set=SimpleNamespace(all=lambda: [item_missing_both]),
        )
        carton_unknown_status = SimpleNamespace(
            id=12,
            code="C-012",
            created_at=datetime(2026, 1, 12, 12, 0, 0),
            status="unknown-status",
            shipment_id=None,
            shipment=None,
            preassigned_destination=None,
            current_location="A3",
            status_events=SimpleNamespace(all=lambda: []),
            cartonitem_set=SimpleNamespace(all=lambda: [item_missing_volume]),
        )
        carton_preassigned = SimpleNamespace(
            id=13,
            code="MM-00013",
            created_at=datetime(2026, 1, 13, 12, 0, 0),
            status=CartonStatus.PACKED,
            shipment_id=None,
            shipment=None,
            preassigned_destination=SimpleNamespace(iata_code="NKC"),
            current_location="A4",
            status_events=SimpleNamespace(all=lambda: []),
            cartonitem_set=SimpleNamespace(all=lambda: [item_draft]),
        )
        carton_planned = SimpleNamespace(
            id=14,
            code="C-PLANNED",
            created_at=datetime(2026, 1, 14, 12, 0, 0),
            status=CartonStatus.ASSIGNED,
            shipment_id=88,
            shipment=SimpleNamespace(reference="S-088", status="planned", is_disputed=False),
            preassigned_destination=None,
            current_location="A5",
            status_events=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        previous_status=CartonStatus.PACKED,
                        new_status=CartonStatus.ASSIGNED,
                    )
                ]
            ),
            cartonitem_set=SimpleNamespace(all=lambda: [item_assigned]),
        )

        rows = build_cartons_ready_rows(
            [
                carton_assigned,
                carton_draft,
                carton_unknown_status,
                carton_preassigned,
                carton_planned,
            ],
            carton_capacity_cm3=5000,
        )

        self.assertEqual([row["id"] for row in rows], [10, 11, 12, 13, 14])

        assigned_row = rows[0]
        self.assertEqual(assigned_row["status_label"], "Affecté")
        self.assertEqual(assigned_row["status_tone"], "progress")
        self.assertEqual(
            assigned_row["status_badges"],
            [
                {"label": "Créé", "variant": "prep-draft"},
                {"label": "Affecté", "variant": "assignment-assigned"},
            ],
        )
        self.assertFalse(assigned_row["can_toggle"])
        self.assertTrue(assigned_row["can_edit"])
        self.assertTrue(assigned_row["can_delete"])
        self.assertEqual(assigned_row["shipment_reference"], "S-077")
        self.assertEqual(
            assigned_row["packing_list_url"],
            f'{reverse("scan:scan_shipment_carton_document", args=[77, 10])}?delivery=html',
        )
        self.assertTrue(
            assigned_row["packing_list_url"].endswith(
                "/scan/shipment/77/carton/10/doc/?delivery=html"
            )
        )
        self.assertEqual(
            assigned_row["picking_url"],
            reverse("scan:scan_carton_picking", args=[10]),
        )
        self.assertTrue(assigned_row["picking_url"].endswith("/scan/carton/10/picking/"))
        self.assertEqual(
            assigned_row["detail_url"],
            reverse("scan:scan_carton_edit", args=[10]),
        )
        self.assertEqual(assigned_row["summary_line_count"], 1)
        self.assertEqual(assigned_row["summary_total_quantity"], 2)
        self.assertEqual(
            assigned_row["product_rows"],
            [{"label": "Mask", "quantity": 2, "display": "Mask x 2"}],
        )
        self.assertTrue(assigned_row["has_packing_list"])
        self.assertTrue(assigned_row["has_picking"])
        self.assertTrue(assigned_row["can_bulk_mark_labeled"])
        self.assertFalse(assigned_row["can_bulk_mark_assigned"])
        self.assertEqual(assigned_row["weight_kg"], 1.0)
        self.assertEqual(assigned_row["volume_percent"], 40)

        draft_row = rows[1]
        self.assertEqual(draft_row["status_label"], "Créé")
        self.assertEqual(draft_row["status_tone"], "progress")
        self.assertEqual(
            draft_row["status_badges"],
            [
                {"label": "Créé", "variant": "prep-draft"},
                {"label": "Libre", "variant": "assignment-free"},
            ],
        )
        self.assertTrue(draft_row["can_toggle"])
        self.assertTrue(draft_row["can_edit"])
        self.assertTrue(draft_row["can_delete"])
        self.assertEqual(draft_row["shipment_reference"], "")
        self.assertEqual(
            draft_row["packing_list_url"],
            f'{reverse("scan:scan_carton_document", args=[11])}?delivery=html',
        )
        self.assertTrue(
            draft_row["packing_list_url"].endswith("/scan/carton/11/doc/?delivery=html")
        )
        self.assertIsNone(draft_row["weight_kg"])
        self.assertIsNone(draft_row["volume_percent"])

        unknown_row = rows[2]
        self.assertEqual(unknown_row["status_label"], "unknown-status")
        self.assertEqual(unknown_row["status_tone"], "progress")
        self.assertEqual(
            unknown_row["status_badges"],
            [
                {"label": "Prépa inconnue", "variant": "prep-unknown"},
                {"label": "Libre", "variant": "assignment-free"},
            ],
        )
        self.assertIsNone(unknown_row["volume_percent"])
        self.assertEqual(unknown_row["packing_list"][0]["quantity"], 1)
        self.assertEqual(
            unknown_row["product_rows"],
            [{"label": "Kit", "quantity": 1, "display": "Kit x 1"}],
        )

        preassigned_row = rows[3]
        self.assertEqual(preassigned_row["shipment_reference"], "(NKC)")
        self.assertEqual(
            preassigned_row["status_badges"],
            [
                {"label": "Disponible", "variant": "prep-packed"},
                {"label": "Libre", "variant": "assignment-free"},
            ],
        )
        self.assertTrue(preassigned_row["can_edit"])
        self.assertTrue(preassigned_row["can_delete"])

        planned_row = rows[4]
        self.assertEqual(planned_row["shipment_reference"], "S-088")
        self.assertEqual(
            planned_row["status_badges"],
            [
                {"label": "Disponible", "variant": "prep-packed"},
                {"label": "Affecté", "variant": "assignment-assigned"},
            ],
        )
        self.assertFalse(planned_row["can_edit"])
        self.assertFalse(planned_row["can_delete"])
        self.assertFalse(planned_row["can_bulk_mark_labeled"])
        self.assertFalse(planned_row["can_bulk_mark_assigned"])
