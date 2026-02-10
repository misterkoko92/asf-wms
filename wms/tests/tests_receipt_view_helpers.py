from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.receipt_view_helpers import build_receipts_view_rows


class ReceiptViewHelpersTests(SimpleTestCase):
    def test_build_receipts_view_rows_formats_quantity_and_hors_format_variants(self):
        receipt_with_pallets = SimpleNamespace(
            received_on="2026-01-01",
            source_contact=SimpleNamespace(name="Donor A"),
            pallet_count=3,
            carton_count=None,
            hors_format_count=2,
            hors_format_items=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(description=" Tube medical "),
                    SimpleNamespace(description=""),
                ]
            ),
            carrier_contact=SimpleNamespace(name="Carrier A"),
        )
        receipt_with_cartons = SimpleNamespace(
            received_on="2026-01-02",
            source_contact=SimpleNamespace(name="Donor B"),
            pallet_count=None,
            carton_count=5,
            hors_format_count=1,
            hors_format_items=SimpleNamespace(all=lambda: []),
            carrier_contact=None,
        )
        receipt_with_desc_only = SimpleNamespace(
            received_on="2026-01-03",
            source_contact=None,
            pallet_count=None,
            carton_count=None,
            hors_format_count=0,
            hors_format_items=SimpleNamespace(
                all=lambda: [SimpleNamespace(description="Materiel divers")]
            ),
            carrier_contact=None,
        )
        receipt_without_hors_format = SimpleNamespace(
            received_on="2026-01-04",
            source_contact=None,
            pallet_count=None,
            carton_count=None,
            hors_format_count=None,
            hors_format_items=SimpleNamespace(all=lambda: []),
            carrier_contact=None,
        )

        rows = build_receipts_view_rows(
            [
                receipt_with_pallets,
                receipt_with_cartons,
                receipt_with_desc_only,
                receipt_without_hors_format,
            ]
        )

        self.assertEqual(rows[0]["name"], "Donor A")
        self.assertEqual(rows[0]["quantity"], "3 palettes")
        self.assertEqual(rows[0]["hors_format"], "2 : Tube medical")
        self.assertEqual(rows[0]["carrier"], "Carrier A")

        self.assertEqual(rows[1]["name"], "Donor B")
        self.assertEqual(rows[1]["quantity"], "5 colis")
        self.assertEqual(rows[1]["hors_format"], "1")
        self.assertEqual(rows[1]["carrier"], "-")

        self.assertEqual(rows[2]["name"], "-")
        self.assertEqual(rows[2]["quantity"], "-")
        self.assertEqual(rows[2]["hors_format"], "Materiel divers")
        self.assertEqual(rows[2]["carrier"], "-")

        self.assertEqual(rows[3]["name"], "-")
        self.assertEqual(rows[3]["quantity"], "-")
        self.assertEqual(rows[3]["hors_format"], "-")
        self.assertEqual(rows[3]["carrier"], "-")
