from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.pallet_listing import (
    _completed_field_labels,
    _enrich_group_suggestions,
    _format_category_value,
    _format_location_value,
    _group_suggestion_current_value,
    _group_suggestion_linked_product,
    apply_listing_group_suggestion_to_overrides,
    apply_listing_mapping,
    build_listing_columns,
    build_listing_extract_options,
    build_listing_mapping_defaults,
    build_listing_review_rows,
    build_listing_review_state,
    build_listing_visible_columns,
    capture_listing_review_overrides_from_post,
    load_listing_table,
    normalize_listing_mapping,
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

    def test_normalize_listing_mapping_ignores_invalid_indexes_and_blank_fields(self):
        mapping = normalize_listing_mapping(
            {
                "0": "name",
                "1": "quantity",
                "oops": "brand",
                "5": "",
                None: "ean",
            }
        )

        self.assertEqual(mapping, {0: "name", 1: "quantity"})

    def test_apply_listing_mapping_skips_non_product_rows_from_classifier(self):
        rows = [
            ["TOTAL", "12"],
            ["Masque", "4"],
            ["", ""],
        ]

        with mock.patch(
            "wms.pallet_listing.is_non_product_listing_row",
            side_effect=[True, False],
        ):
            mapped_rows = apply_listing_mapping(
                rows,
                {"0": "name", "1": "quantity", "oops": "brand"},
            )

        self.assertEqual(mapped_rows, [{"name": "Masque", "quantity": "4"}])

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

    def test_capture_listing_review_overrides_defaults_selection_and_tracks_completed_labels(self):
        overrides = capture_listing_review_overrides_from_post(
            {
                "row_2_name": " Produit modifie ",
                "row_2_brand": " BRAUN ",
                "row_2_match": "",
            },
            [["Produit source", "3"]],
            {0: "name", 1: "quantity"},
        )

        self.assertEqual(overrides["row-2"]["selection"], "new")
        self.assertEqual(overrides["row-2"]["values"]["name"], "Produit modifie")
        self.assertEqual(overrides["row-2"]["values"]["brand"], "BRAUN")
        self.assertEqual(overrides["row-2"]["values"]["quantity"], "3")
        self.assertEqual(
            _completed_field_labels(
                {"name": "Produit source", "brand": ""},
                overrides["row-2"]["values"],
            ),
            ["Nom", "Marque"],
        )

    def test_group_suggestion_helpers_format_values_and_linked_product(self):
        row = {
            "values": {
                "brand": "BRAUN",
                "category_l1": "Sante",
                "category_l2": "Diagnostic",
                "category_l3": "Thermometres",
                "category_l4": "",
                "tva": "5.5",
                "warehouse": "WH1",
                "zone": "R2",
                "aisle": "A3",
                "shelf": "B4",
            },
            "default_match": "product:42",
            "existing": {"sku": "SKU-42", "name": "Thermometre"},
        }

        self.assertEqual(_format_category_value(row["values"]), "Sante > Diagnostic > Thermometres")
        self.assertEqual(_format_location_value(row["values"]), "WH1 / R2 / A3 / B4")
        self.assertEqual(_group_suggestion_current_value(row, "brand"), "BRAUN")
        self.assertEqual(
            _group_suggestion_current_value(row, "category"),
            "Sante > Diagnostic > Thermometres",
        )
        self.assertEqual(_group_suggestion_current_value(row, "tva"), "5.5")
        self.assertEqual(_group_suggestion_current_value(row, "location"), "WH1 / R2 / A3 / B4")
        self.assertEqual(_group_suggestion_linked_product(row), "SKU-42 - Thermometre")

    def test_enrich_group_suggestions_skips_unknown_rows_and_handles_new_products(self):
        enriched = _enrich_group_suggestions(
            [
                {
                    "id": "location:main",
                    "field_name": "location",
                    "proposed_value": "WH1 / R2 / A3 / B4",
                    "row_keys": ["row-2", "row-999"],
                }
            ],
            [
                {
                    "index": 2,
                    "values": {
                        "ean": "123456789",
                        "name": "Thermometre",
                        "warehouse": "WH1",
                        "zone": "R2",
                        "aisle": "A3",
                        "shelf": "B4",
                    },
                    "default_match": "new",
                    "existing": {},
                }
            ],
        )

        self.assertEqual(enriched[0]["field_label"], "Emplacement")
        self.assertEqual(
            enriched[0]["preview_rows"],
            [
                {
                    "row_key": "row-2",
                    "index": 2,
                    "ean": "123456789",
                    "name": "Thermometre",
                    "current_value": "WH1 / R2 / A3 / B4",
                    "proposed_value": "WH1 / R2 / A3 / B4",
                    "linked_product": "",
                }
            ],
        )

    def test_build_listing_visible_columns_only_keeps_columns_with_values(self):
        listing_rows = [
            {
                "fields": [
                    {"name": "name", "value": "Thermometre frontal", "existing": ""},
                    {"name": "brand", "value": "BRAUN", "existing": ""},
                    {"name": "ean", "value": "", "existing": "1234567890123"},
                    {"name": "category_l1", "value": "", "existing": ""},
                ],
                "locations": [
                    {"name": "warehouse", "value": "MAIN", "existing": ""},
                    {"name": "zone", "value": "", "existing": ""},
                ],
                "values": {"rack_color": "Bleu"},
            },
            {
                "fields": [
                    {"name": "name", "value": "Masque", "existing": ""},
                    {"name": "brand", "value": "", "existing": ""},
                    {"name": "ean", "value": "", "existing": ""},
                    {"name": "category_l1", "value": "", "existing": ""},
                ],
                "locations": [
                    {"name": "warehouse", "value": "", "existing": ""},
                    {"name": "zone", "value": "", "existing": ""},
                ],
                "values": {"rack_color": ""},
            },
        ]

        visible_columns = build_listing_visible_columns(listing_rows)

        self.assertEqual(
            visible_columns["review_fields"],
            [("name", "Nom"), ("brand", "Marque"), ("ean", "EAN")],
        )
        self.assertEqual(visible_columns["location_fields"], [("warehouse", "Entrepôt")])
        self.assertTrue(visible_columns["show_rack_color_column"])

    def test_build_listing_review_state_filters_dismissed_suggestions_and_exposes_completion_summary(
        self,
    ):
        mapping = {0: "name", 1: "ean", 2: "quantity"}
        rows = [["Braun Thermometre Frontal", "1234567890123", "3"]]

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
                "group_suggestions": [
                    {
                        "id": "brand:braun",
                        "field_name": "brand",
                        "proposed_value": "BRAUN",
                        "confidence": "Forte",
                        "source": "Base + Batch",
                        "row_keys": ["row-2"],
                        "per_row_updates": {"row-2": {"brand": "BRAUN"}},
                    },
                    {
                        "id": "category:braun",
                        "field_name": "category",
                        "proposed_value": "Thermomètres",
                        "confidence": "Forte",
                        "source": "Base + Batch",
                        "row_keys": ["row-2"],
                        "per_row_updates": {"row-2": {"category_l1": "Thermomètres"}},
                    },
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
                    review_state = build_listing_review_state(
                        rows,
                        mapping,
                        review_overrides={
                            "row-2": {
                                "selection": "new",
                                "values": {
                                    "brand": "BRAUN",
                                    "category_l1": "Thermomètres",
                                },
                            }
                        },
                        dismissed_suggestion_ids=["category:braun"],
                    )

        self.assertEqual(
            [suggestion["id"] for suggestion in review_state["group_suggestions"]],
            ["brand:braun"],
        )
        row = review_state["rows"][0]
        self.assertEqual(row["status_label"], "Nouveau produit")
        self.assertEqual(row["completion_labels"], ["Marque", "Cat L1"])
        self.assertEqual(row["completion_summary"], "Marque, Cat L1")

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
