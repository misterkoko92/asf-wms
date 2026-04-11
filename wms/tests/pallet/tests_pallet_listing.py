from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.pallet_listing import (
    apply_listing_group_suggestion_to_overrides,
    apply_listing_mapping,
    build_listing_columns,
    build_listing_extract_options,
    build_listing_mapping_defaults,
    build_listing_review_rows,
    build_listing_review_state,
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

    def test_build_listing_mapping_defaults_supports_common_pdf_headers(self):
        headers = ["EAN", "DESIGNATION", "PRIX HT", "QTE", "TOTAL HT"]

        mapping = build_listing_mapping_defaults(headers)

        self.assertEqual(
            mapping,
            {
                0: "ean",
                1: "name",
                2: "pu_ht",
                3: "quantity",
            },
        )

    def test_apply_listing_mapping_skips_detected_summary_rows(self):
        rows = [
            ["3400930210598", "BOCEAL MAUX GORGE FL PULV+EMB 20ML", "3,94 €", "4", "15,76 €"],
            ["", "VALORISATION DU DON", "", "181", "1873,07 €"],
        ]

        mapped_rows = apply_listing_mapping(
            rows,
            {0: "ean", 1: "name", 2: "pu_ht", 3: "quantity"},
        )

        self.assertEqual(
            mapped_rows,
            [
                {
                    "ean": "3400930210598",
                    "name": "BOCEAL MAUX GORGE FL PULV+EMB 20ML",
                    "pu_ht": "3,94 €",
                    "quantity": "4",
                }
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
                "wms.pallet_listing.build_listing_assisted_suggestions",
                return_value={"auto_matches": {}, "line_suggestions": {}, "group_suggestions": []},
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
        self.assertEqual(row["default_match"], "new")
        self.assertEqual(row["values"]["name"], "Masque")
        self.assertEqual(row["values"]["quantity"], "3")
        self.assertEqual(row["values"]["warehouse"], "WH1")
        self.assertEqual(row["values"]["zone"], "R1")
        self.assertEqual(row["values"]["aisle"], "E1")
        self.assertEqual(row["values"]["shelf"], "B1")
        self.assertEqual(row["match_options"][0]["value"], "product:42")
        self.assertEqual(row["match_badge"], "")
        self.assertEqual(row["line_suggestions"], [])

    def test_build_listing_review_rows_surfaces_barcode_match_type(self):
        mapping = {0: "name", 1: "barcode", 2: "quantity"}
        rows = [["Masque", "BAR-42", "3"]]
        product = SimpleNamespace(id=42, sku="SKU-42", name="Masque", brand="")

        with mock.patch(
            "wms.pallet_listing.extract_product_identity",
            return_value=("", "Masque", ""),
        ):
            with mock.patch(
                "wms.pallet_listing.build_listing_assisted_suggestions",
                return_value={"auto_matches": {}, "line_suggestions": {}, "group_suggestions": []},
            ):
                with mock.patch(
                    "wms.pallet_listing.find_product_matches",
                    return_value=([product], "barcode"),
                ):
                    with mock.patch(
                        "wms.pallet_listing.build_product_display",
                        return_value={"warehouse": "", "zone": "", "aisle": "", "shelf": ""},
                    ):
                        review_rows = build_listing_review_rows(rows, mapping)

        self.assertEqual(review_rows[0]["match_type"], "Barcode")
        self.assertEqual(review_rows[0]["default_match"], "new")

    def test_build_listing_review_state_marks_exact_ean_match_as_auto(self):
        mapping = {0: "name", 1: "ean", 2: "quantity"}
        rows = [["Braun Thermometre Frontal", "1234567890123", "3"]]
        product = SimpleNamespace(id=42, sku="SKU-42", name="Thermometre Braun", brand="BRAUN")

        with mock.patch(
            "wms.pallet_listing.build_listing_assisted_suggestions",
            return_value={
                "auto_matches": {
                    "row-2": {
                        "product_id": 42,
                        "match_type": "ean",
                    }
                },
                "line_suggestions": {},
                "group_suggestions": [],
            },
        ):
            with mock.patch(
                "wms.pallet_listing.extract_product_identity",
                return_value=("", "Braun Thermometre Frontal", ""),
            ):
                with mock.patch(
                    "wms.pallet_listing.find_product_matches",
                    return_value=([product], "ean"),
                ):
                    with mock.patch(
                        "wms.pallet_listing.build_product_display",
                        return_value={"warehouse": "", "zone": "", "aisle": "", "shelf": ""},
                    ):
                        review_state = build_listing_review_state(rows, mapping)

        self.assertEqual(review_state["group_suggestions"], [])
        self.assertEqual(len(review_state["rows"]), 1)
        row = review_state["rows"][0]
        self.assertEqual(row["default_match"], "product:42")
        self.assertEqual(row["match_badge"], "Match auto EAN")

    def test_build_listing_review_state_enriches_group_suggestion_preview_rows(self):
        mapping = {0: "name", 1: "ean", 2: "quantity"}
        rows = [["Braun Thermometre Frontal", "1234567890123", "3"]]

        with mock.patch(
            "wms.pallet_listing.build_listing_assisted_suggestions",
            return_value={
                "auto_matches": {},
                "line_suggestions": {},
                "group_suggestions": [
                    {
                        "id": "brand:braun",
                        "field_name": "brand",
                        "proposed_value": "BRAUN",
                        "confidence": "Forte",
                        "source": "Base + Batch",
                        "row_keys": ["row-2"],
                        "per_row_updates": {
                            "row-2": {"brand": "BRAUN", "name": "Thermometre Frontal"}
                        },
                    }
                ],
            },
        ):
            with mock.patch(
                "wms.pallet_listing.extract_product_identity",
                return_value=("", "Braun Thermometre Frontal", ""),
            ):
                with mock.patch(
                    "wms.pallet_listing.find_product_matches",
                    return_value=([], None),
                ):
                    review_state = build_listing_review_state(rows, mapping)

        self.assertEqual(len(review_state["group_suggestions"]), 1)
        suggestion = review_state["group_suggestions"][0]
        self.assertEqual(suggestion["field_label"], "Marque")
        self.assertEqual(
            suggestion["preview_rows"],
            [
                {
                    "row_key": "row-2",
                    "index": 2,
                    "ean": "1234567890123",
                    "name": "Braun Thermometre Frontal",
                    "current_value": "-",
                    "proposed_value": "BRAUN",
                    "linked_product": "",
                }
            ],
        )

    def test_apply_listing_group_suggestion_to_overrides_only_updates_new_rows_and_empty_fields(
        self,
    ):
        review_overrides = {
            "row-2": {
                "selection": "new",
                "values": {
                    "name": "BRAUN Thermometre frontal",
                    "brand": "",
                    "warehouse": "WH1",
                    "zone": "",
                },
            },
            "row-3": {
                "selection": "product:42",
                "values": {
                    "name": "BRAUN Thermometre auriculaire",
                    "brand": "",
                    "warehouse": "",
                    "zone": "",
                },
            },
        }

        apply_listing_group_suggestion_to_overrides(
            review_overrides,
            {
                "field_name": "brand",
                "per_row_updates": {
                    "row-2": {
                        "brand": "BRAUN",
                        "name": "Thermometre frontal",
                        "warehouse": "WH2",
                        "zone": "A1",
                    },
                    "row-3": {
                        "brand": "BRAUN",
                        "name": "Thermometre auriculaire",
                    },
                },
            },
        )

        self.assertEqual(review_overrides["row-2"]["values"]["brand"], "BRAUN")
        self.assertEqual(review_overrides["row-2"]["values"]["name"], "Thermometre frontal")
        self.assertEqual(review_overrides["row-2"]["values"]["warehouse"], "WH1")
        self.assertEqual(review_overrides["row-2"]["values"]["zone"], "A1")
        self.assertEqual(review_overrides["row-3"]["values"]["brand"], "")
        self.assertEqual(
            review_overrides["row-3"]["values"]["name"],
            "BRAUN Thermometre auriculaire",
        )

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

    def test_listing_helpers_accept_session_serialized_mapping_keys(self):
        headers = ["Nom", "Quantite"]
        rows = [["Masque", "5"]]
        session_mapping = {"0": "name", "1": "quantity"}

        mapped_rows = apply_listing_mapping(rows, session_mapping)
        columns = build_listing_columns(headers, rows, session_mapping)

        self.assertEqual(mapped_rows, [{"name": "Masque", "quantity": "5"}])
        self.assertEqual(columns[0]["mapped"], "name")
        self.assertEqual(columns[1]["mapped"], "quantity")

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
