from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.pallet_listing import (
    apply_listing_mapping,
    build_listing_columns,
    build_listing_extract_options,
    build_listing_mapping_defaults,
    build_listing_review_rows,
    load_listing_table,
    pending_listing_extract_options,
)


class PalletListingTests(SimpleTestCase):
    def test_build_listing_mapping_defaults_and_apply_mapping_skip_empty_rows(self):
        headers = ["Nom", "QTY", "Colonne libre"]
        mapping = build_listing_mapping_defaults(headers)
        self.assertEqual(mapping[0], "name")
        self.assertEqual(mapping[1], "quantity")

        rows = [
            ["", "", ""],
            ["Masque", "4", "x"],
            ["Gants", "2", "y"],
        ]
        mapped_rows = apply_listing_mapping(rows, {0: "name", 1: "quantity"})
        self.assertEqual(
            mapped_rows,
            [
                {"name": "Masque", "quantity": "4"},
                {"name": "Gants", "quantity": "2"},
            ],
        )

    def test_build_listing_extract_options_and_pending_options(self):
        excel_options = build_listing_extract_options(".xlsx", "Feuil1", 3, "all", None, None)
        self.assertEqual(excel_options, {"sheet_name": "Feuil1", "header_row": 3})

        pdf_options = build_listing_extract_options(".pdf", "", 1, "custom", 2, 5)
        self.assertEqual(pdf_options, {"pdf_pages": (2, 5)})

        pending = {
            "extension": ".pdf",
            "sheet_name": "",
            "header_row": 1,
            "pdf_pages": {"mode": "custom", "start": 4, "end": 7},
        }
        self.assertEqual(
            pending_listing_extract_options(pending),
            {"pdf_pages": (4, 7)},
        )

    def test_build_listing_review_rows_builds_existing_match_and_fallback_locations(self):
        mapping = {0: "name", 1: "brand", 2: "quantity"}
        rows = [["Masque", "ASF", "3"]]
        product = SimpleNamespace(id=42, sku="SKU-42", name="Masque", brand="ASF")
        existing_display = {
            "warehouse": "WH1",
            "zone": "R1",
            "aisle": "E1",
            "shelf": "B1",
            "name": "Masque",
            "brand": "ASF",
        }

        with mock.patch(
            "wms.pallet_listing.extract_product_identity",
            return_value=(None, "Masque", "ASF"),
        ):
            with mock.patch(
                "wms.pallet_listing.find_product_matches",
                return_value=([product], "name_brand"),
            ):
                with mock.patch(
                    "wms.pallet_listing.build_product_display",
                    return_value=existing_display,
                ):
                    review_rows = build_listing_review_rows(rows, mapping, start_index=5)

        self.assertEqual(len(review_rows), 1)
        row = review_rows[0]
        self.assertEqual(row["index"], 5)
        self.assertEqual(row["match_type"], "Nom + Marque")
        self.assertEqual(row["default_match"], "product:42")
        self.assertEqual(row["values"]["name"], "Masque")
        self.assertEqual(row["values"]["quantity"], "3")
        self.assertEqual(row["values"]["warehouse"], "WH1")
        self.assertEqual(row["values"]["zone"], "R1")
        self.assertEqual(row["values"]["aisle"], "E1")
        self.assertEqual(row["values"]["shelf"], "B1")
        self.assertEqual(row["match_options"][0]["value"], "product:42")

    def test_build_listing_columns_uses_first_non_empty_sample(self):
        headers = ["Nom", "Quantite"]
        rows = [["", ""], ["Masque", "5"], ["Gants", "2"]]
        columns = build_listing_columns(headers, rows, {0: "name"})
        self.assertEqual(
            columns,
            [
                {"index": 0, "name": "Nom", "sample": "Masque", "mapped": "name"},
                {"index": 1, "name": "Quantite", "sample": "5", "mapped": ""},
            ],
        )

    def test_load_listing_table_reads_file_and_passes_extract_options(self):
        pending = {
            "file_path": "/tmp/listing.csv",
            "extension": ".csv",
            "sheet_name": "",
            "header_row": 1,
            "pdf_pages": {"mode": "all", "start": None, "end": None},
        }
        with mock.patch(
            "wms.pallet_listing.Path.read_bytes",
            return_value=b"header1,header2\nv1,v2\n",
        ) as read_mock:
            with mock.patch(
                "wms.pallet_listing.extract_tabular_data",
                return_value=(["header1", "header2"], [["v1", "v2"]]),
            ) as extract_mock:
                headers, rows = load_listing_table(pending)

        read_mock.assert_called_once()
        extract_mock.assert_called_once_with(
            b"header1,header2\nv1,v2\n",
            ".csv",
        )
        self.assertEqual(headers, ["header1", "header2"])
        self.assertEqual(rows, [["v1", "v2"]])
