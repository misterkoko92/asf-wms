from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms.pallet_listing_handlers import (
    clear_pending_listing,
    handle_pallet_listing_action,
    hydrate_listing_state_from_pending,
    init_listing_state,
)


class _FakeForm:
    def __init__(self, *, valid, cleaned_data=None):
        self._valid = valid
        self.cleaned_data = cleaned_data or {}

    def is_valid(self):
        return self._valid


class _FakeTempFile:
    def __init__(self, name):
        self.name = name
        self.written = b""

    def write(self, data):
        self.written += data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class PalletListingHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=12, username="listing-user")

    def _request(self, data=None):
        request = self.factory.post("/scan/receive-pallet/", data or {})
        request.user = self.user
        request.session = {}
        return request

    def _listing_form(self, *, valid=True):
        return _FakeForm(
            valid=valid,
            cleaned_data={
                "received_on": date(2026, 1, 10),
                "pallet_count": 3,
                "source_contact": SimpleNamespace(id=101),
                "carrier_contact": SimpleNamespace(id=202),
                "transport_request_date": date(2026, 1, 8),
            },
        )

    def test_init_listing_state_defaults(self):
        state = init_listing_state()
        self.assertEqual(state["listing_stage"], None)
        self.assertEqual(state["listing_columns"], [])
        self.assertEqual(state["listing_rows"], [])
        self.assertEqual(state["listing_errors"], [])
        self.assertEqual(state["listing_sheet_names"], [])
        self.assertEqual(state["listing_sheet_name"], "")
        self.assertEqual(state["listing_header_row"], 1)
        self.assertEqual(state["listing_pdf_pages_mode"], "all")
        self.assertEqual(state["listing_pdf_page_start"], "")
        self.assertEqual(state["listing_pdf_page_end"], "")
        self.assertEqual(state["listing_pdf_total_pages"], "")
        self.assertEqual(state["listing_file_type"], "")

    def test_clear_pending_listing_unlinks_file_and_ignorés_oserror(self):
        request = self._request()
        request.session["pallet_listing_pending"] = {"file_path": "/tmp/pending-listing.csv"}
        with mock.patch("wms.pallet_listing_handlers.Path.unlink") as unlink_mock:
            clear_pending_listing(request)
        self.assertNotIn("pallet_listing_pending", request.session)
        unlink_mock.assert_called_once_with(missing_ok=True)

        request = self._request()
        request.session["pallet_listing_pending"] = {"file_path": "/tmp/pending-listing.csv"}
        with mock.patch(
            "wms.pallet_listing_handlers.Path.unlink",
            side_effect=OSError("boom"),
        ):
            clear_pending_listing(request)
        self.assertNotIn("pallet_listing_pending", request.session)

    def test_hydrate_listing_state_from_pending_returns_none_without_pending(self):
        state = init_listing_state()
        self.assertIsNone(hydrate_listing_state_from_pending(state, None))

    def test_hydrate_listing_state_from_pending_handles_excel_meta(self):
        state = init_listing_state()
        pending = {
            "extension": ".xlsx",
            "sheet_names": ["Sheet1", "Sheet2"],
            "sheet_name": "Sheet2",
            "header_row": 3,
            "file_type": "excel",
            "receipt_meta": {
                "received_on": "2026-01-10",
                "pallet_count": 4,
                "source_contact_id": 101,
                "carrier_contact_id": 202,
                "transport_request_date": "2026-01-08",
            },
        }
        source_qs = SimpleNamespace(first=lambda: SimpleNamespace(name="Donateur A"))
        carrier_qs = SimpleNamespace(first=lambda: SimpleNamespace(name="Transporteur B"))
        with mock.patch(
            "wms.pallet_listing_handlers.Contact.objects.filter",
            side_effect=[source_qs, carrier_qs],
        ):
            listing_meta = hydrate_listing_state_from_pending(state, pending)

        self.assertEqual(listing_meta["received_on"], "2026-01-10")
        self.assertEqual(listing_meta["pallet_count"], 4)
        self.assertEqual(listing_meta["source_contact"], "Donateur A")
        self.assertEqual(listing_meta["carrier_contact"], "Transporteur B")
        self.assertEqual(listing_meta["sheet_name"], "Sheet2")
        self.assertEqual(listing_meta["header_row"], 3)
        self.assertEqual(listing_meta["sheet_names"], "Sheet1, Sheet2")
        self.assertEqual(state["listing_sheet_names"], ["Sheet1", "Sheet2"])
        self.assertEqual(state["listing_sheet_name"], "Sheet2")
        self.assertEqual(state["listing_header_row"], 3)
        self.assertEqual(state["listing_file_type"], "excel")

    def test_hydrate_listing_state_from_pending_handles_pdf_custom_pages(self):
        state = init_listing_state()
        pending = {
            "extension": ".pdf",
            "pdf_pages": {"mode": "custom", "start": 2, "end": 5, "total": 9},
            "file_type": "pdf",
            "receipt_meta": {},
        }
        no_contact = SimpleNamespace(first=lambda: None)
        with mock.patch(
            "wms.pallet_listing_handlers.Contact.objects.filter",
            side_effect=[no_contact, no_contact],
        ):
            listing_meta = hydrate_listing_state_from_pending(state, pending)

        self.assertEqual(listing_meta["pdf_pages"], "2 - 5")
        self.assertEqual(listing_meta["pdf_total_pages"], 9)
        self.assertEqual(state["listing_pdf_pages_mode"], "custom")
        self.assertEqual(state["listing_pdf_page_start"], "2")
        self.assertEqual(state["listing_pdf_page_end"], "5")
        self.assertEqual(state["listing_pdf_total_pages"], "9")
        self.assertEqual(state["listing_file_type"], "pdf")

    def test_hydrate_listing_state_from_pending_handles_pdf_all_pages_label(self):
        state = init_listing_state()
        pending = {
            "extension": ".pdf",
            "pdf_pages": {"mode": "all", "total": 4},
            "receipt_meta": {},
        }
        no_contact = SimpleNamespace(first=lambda: None)
        with mock.patch(
            "wms.pallet_listing_handlers.Contact.objects.filter",
            side_effect=[no_contact, no_contact],
        ):
            listing_meta = hydrate_listing_state_from_pending(state, pending)
        self.assertEqual(listing_meta["pdf_pages"], "Toutes les pages")

    def test_handle_listing_cancel_clears_pending_and_redirects(self):
        request = self._request()
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.clear_pending_listing") as clear_mock:
            response = handle_pallet_listing_action(
                request,
                action="listing_cancel",
                listing_form=self._listing_form(),
                state=state,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        clear_mock.assert_called_once_with(request)

    def test_handle_listing_upload_requires_valid_form_and_file(self):
        request = self._request()
        state = init_listing_state()
        response = handle_pallet_listing_action(
            request,
            action="listing_upload",
            listing_form=self._listing_form(valid=False),
            state=state,
        )
        self.assertIsNone(response)
        self.assertEqual(
            state["listing_errors"],
            [
                "Renseignez les informations de réception.",
                "Fichier requis pour importer le listing.",
            ],
        )

    def test_handle_listing_upload_rejects_unsupported_file_format(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.txt", b"abc"),
            }
        )
        state = init_listing_state()
        response = handle_pallet_listing_action(
            request,
            action="listing_upload",
            listing_form=self._listing_form(valid=True),
            state=state,
        )
        self.assertIsNone(response)
        self.assertIn("Format de fichier non supporté.", state["listing_errors"])

    def test_handle_listing_upload_skips_processing_when_file_too_big(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.csv", b"abc"),
            }
        )
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.LISTING_MAX_FILE_SIZE_MB", 0):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("Fichier trop volumineux (> 0 MB).", state["listing_errors"])
        self.assertEqual(state["listing_file_type"], "csv")

    def test_handle_listing_upload_excel_success_builds_pending_and_mapping_columns(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.xlsx", b"excel-bytes"),
                "listing_sheet_name": "",
                "listing_header_row": "2",
            }
        )
        state = init_listing_state()
        temp_file = _FakeTempFile("/tmp/fake-listing.xlsx")
        with mock.patch(
            "wms.pallet_listing_handlers.list_excel_sheets",
            return_value=["Sheet1", "Sheet2"],
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.extract_tabular_data",
                return_value=(["Nom", "Quantite"], [["Masque", "2"]]),
            ):
                with mock.patch(
                    "wms.pallet_listing_handlers.build_listing_mapping_defaults",
                    return_value={0: "name", 1: "quantity"},
                ):
                    with mock.patch(
                        "wms.pallet_listing_handlers.build_listing_columns",
                        return_value=[{"index": 0, "mapped": "name"}],
                    ):
                        with mock.patch(
                            "wms.pallet_listing_handlers.tempfile.NamedTemporaryFile",
                            return_value=temp_file,
                        ):
                            with mock.patch(
                                "wms.pallet_listing_handlers.uuid.uuid4",
                                return_value=SimpleNamespace(hex="tok-123"),
                            ):
                                response = handle_pallet_listing_action(
                                    request,
                                    action="listing_upload",
                                    listing_form=self._listing_form(valid=True),
                                    state=state,
                                )

        self.assertIsNone(response)
        self.assertEqual(state["listing_stage"], "mapping")
        self.assertEqual(state["listing_columns"], [{"index": 0, "mapped": "name"}])
        self.assertEqual(state["listing_file_type"], "excel")
        self.assertEqual(state["listing_sheet_name"], "Sheet1")
        self.assertEqual(state["listing_header_row"], 2)
        pending = request.session["pallet_listing_pending"]
        self.assertEqual(pending["token"], "tok-123")
        self.assertEqual(pending["file_path"], "/tmp/fake-listing.xlsx")
        self.assertEqual(pending["extension"], ".xlsx")
        self.assertEqual(pending["headers"], ["Nom", "Quantite"])
        self.assertEqual(pending["mapping"], {0: "name", 1: "quantity"})
        self.assertEqual(pending["sheet_name"], "Sheet1")
        self.assertEqual(
            pending["receipt_meta"],
            {
                "received_on": "2026-01-10",
                "pallet_count": 3,
                "source_contact_id": 101,
                "carrier_contact_id": 202,
                "transport_request_date": "2026-01-08",
            },
        )

    def test_handle_listing_upload_excel_invalid_header_row_and_unknown_sheet(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.xlsx", b"excel-bytes"),
                "listing_sheet_name": "UnknownSheet",
                "listing_header_row": "-2",
            }
        )
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.list_excel_sheets",
            return_value=["Main"],
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.extract_tabular_data"
            ) as extract_mock:
                response = handle_pallet_listing_action(
                    request,
                    action="listing_upload",
                    listing_form=self._listing_form(valid=True),
                    state=state,
                )
        self.assertIsNone(response)
        self.assertIn("Ligne des titres invalide (>= 1).", state["listing_errors"])
        self.assertIn("Feuille inconnue: UnknownSheet.", state["listing_errors"])
        self.assertEqual(state["listing_sheet_names"], ["Main"])
        self.assertEqual(state["listing_header_row"], 1)
        extract_mock.assert_not_called()

    def test_handle_listing_upload_excel_header_parse_error(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.xlsx", b"excel-bytes"),
                "listing_header_row": "not-a-number",
            }
        )
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.list_excel_sheets",
            return_value=["Main"],
        ):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("Ligne des titres invalide.", state["listing_errors"])

    def test_handle_listing_upload_excel_list_sheets_error(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.xlsx", b"excel-bytes"),
            }
        )
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.list_excel_sheets",
            side_effect=ValueError("Lecture des feuilles impossible"),
        ):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("Lecture des feuilles impossible", state["listing_errors"])

    def test_handle_listing_upload_pdf_custom_rejects_invalid_page_range(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.pdf", b"%PDF-1.4"),
                "listing_pdf_pages_mode": "custom",
                "listing_pdf_page_start": "5",
                "listing_pdf_page_end": "2",
            }
        )
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.get_pdf_page_count", return_value=10):
            with mock.patch(
                "wms.pallet_listing_handlers.extract_tabular_data"
            ) as extract_mock:
                response = handle_pallet_listing_action(
                    request,
                    action="listing_upload",
                    listing_form=self._listing_form(valid=True),
                    state=state,
                )
        self.assertIsNone(response)
        self.assertIn("Plage de pages PDF invalide.", state["listing_errors"])
        self.assertEqual(state["listing_pdf_total_pages"], "10")
        extract_mock.assert_not_called()

    def test_handle_listing_upload_pdf_custom_page_count_error(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.pdf", b"%PDF-1.4"),
                "listing_pdf_pages_mode": "custom",
            }
        )
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.get_pdf_page_count",
            side_effect=ValueError("PDF invalide"),
        ):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("PDF invalide", state["listing_errors"])

    def test_handle_listing_upload_pdf_custom_invalid_page_values(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.pdf", b"%PDF-1.4"),
                "listing_pdf_pages_mode": "custom",
                "listing_pdf_page_start": "start",
                "listing_pdf_page_end": "end",
            }
        )
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.get_pdf_page_count", return_value=8):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("Page PDF début invalide.", state["listing_errors"])
        self.assertIn("Page PDF fin invalide.", state["listing_errors"])

    def test_handle_listing_upload_pdf_all_pages_extract_error(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.pdf", b"%PDF-1.4"),
                "listing_pdf_pages_mode": "all",
            }
        )
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.get_pdf_page_count", return_value=5):
            with mock.patch(
                "wms.pallet_listing_handlers.extract_tabular_data",
                side_effect=ValueError("Extraction impossible"),
            ):
                response = handle_pallet_listing_action(
                    request,
                    action="listing_upload",
                    listing_form=self._listing_form(valid=True),
                    state=state,
                )
        self.assertIsNone(response)
        self.assertIn("Extraction impossible", state["listing_errors"])
        self.assertEqual(state["listing_file_type"], "pdf")

    def test_handle_listing_upload_pdf_all_pages_count_error(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.pdf", b"%PDF-1.4"),
                "listing_pdf_pages_mode": "all",
            }
        )
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.get_pdf_page_count",
            side_effect=ValueError("Comptage impossible"),
        ):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("Comptage impossible", state["listing_errors"])

    def test_handle_listing_upload_extract_detects_empty_rows(self):
        request = self._request(
            {
                "listing_file": SimpleUploadedFile("listing.csv", b"a,b\n"),
            }
        )
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.extract_tabular_data",
            return_value=(["a", "b"], []),
        ):
            response = handle_pallet_listing_action(
                request,
                action="listing_upload",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertIsNone(response)
        self.assertIn("Fichier vide ou sans lignes exploitables.", state["listing_errors"])

    def test_handle_listing_map_expired_session_redirects(self):
        request = self._request({"pending_token": "nope"})
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.messages.error") as error_mock:
            response = handle_pallet_listing_action(
                request,
                action="listing_map",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        error_mock.assert_called_once_with(request, "Session d'import expirée.")

    def test_handle_listing_map_collects_duplicate_and_missing_required_errors(self):
        request = self._request(
            {
                "pending_token": "tok-map",
                "map_0": "name",
                "map_1": "name",
            }
        )
        request.session["pallet_listing_pending"] = {
            "token": "tok-map",
            "headers": ["Nom", "Quantite"],
        }
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.load_listing_table",
            return_value=(["Nom", "Quantite"], [["Masque", "3"]]),
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.build_listing_columns",
                return_value=[{"index": 0}],
            ):
                response = handle_pallet_listing_action(
                    request,
                    action="listing_map",
                    listing_form=self._listing_form(valid=True),
                    state=state,
                )
        self.assertIsNone(response)
        self.assertEqual(state["listing_stage"], "mapping")
        self.assertIn("Champ name assigne deux fois (1).", state["listing_errors"])
        self.assertIn(
            "Champs requis manquants: quantity",
            state["listing_errors"],
        )
        self.assertEqual(state["listing_columns"], [{"index": 0}])

    def test_handle_listing_map_success_moves_to_review(self):
        request = self._request(
            {
                "pending_token": "tok-review",
                "map_0": "name",
                "map_1": "quantity",
            }
        )
        pending = {
            "token": "tok-review",
            "headers": ["Nom", "Quantite"],
        }
        request.session["pallet_listing_pending"] = pending
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.load_listing_table",
            return_value=(["Nom", "Quantite"], [["Masque", "3"]]),
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.build_listing_review_rows",
                return_value=[{"index": 2, "values": {"name": "Masque"}}],
            ):
                response = handle_pallet_listing_action(
                    request,
                    action="listing_map",
                    listing_form=self._listing_form(valid=True),
                    state=state,
                )
        self.assertIsNone(response)
        self.assertEqual(state["listing_stage"], "review")
        self.assertEqual(state["listing_rows"], [{"index": 2, "values": {"name": "Masque"}}])
        self.assertEqual(
            request.session["pallet_listing_pending"]["mapping"],
            {0: "name", 1: "quantity"},
        )

    def test_handle_listing_map_ignorés_empty_mapping_fields(self):
        request = self._request(
            {
                "pending_token": "tok-empty-map",
                "map_0": "",
                "map_1": "quantity",
            }
        )
        request.session["pallet_listing_pending"] = {
            "token": "tok-empty-map",
            "headers": ["Nom", "Quantite"],
        }
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.load_listing_table",
            return_value=(["Nom", "Quantite"], [["Masque", "3"]]),
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.build_listing_columns",
                return_value=[{"index": 0}],
            ):
                response = handle_pallet_listing_action(
                    request,
                    action="listing_map",
                    listing_form=self._listing_form(valid=True),
                    state=state,
                )
        self.assertIsNone(response)
        self.assertIn("Champs requis manquants: name", state["listing_errors"])

    def test_handle_listing_confirm_expired_session_redirects(self):
        request = self._request({"pending_token": "wrong"})
        state = init_listing_state()
        with mock.patch("wms.pallet_listing_handlers.messages.error") as error_mock:
            response = handle_pallet_listing_action(
                request,
                action="listing_confirm",
                listing_form=self._listing_form(valid=True),
                state=state,
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        error_mock.assert_called_once_with(request, "Session d'import expirée.")

    def test_handle_listing_confirm_requires_default_warehouse(self):
        request = self._request({"pending_token": "tok-confirm"})
        request.session["pallet_listing_pending"] = {
            "token": "tok-confirm",
            "mapping": {0: "name"},
            "receipt_meta": {"received_on": "2026-01-10"},
        }
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.load_listing_table",
            return_value=(["Nom"], [["Masque"]]),
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.apply_listing_mapping",
                return_value=[{"name": "Masque"}],
            ):
                with mock.patch(
                    "wms.pallet_listing_handlers.resolve_default_warehouse",
                    return_value=None,
                ):
                    with mock.patch(
                        "wms.pallet_listing_handlers.messages.error"
                    ) as error_mock:
                        response = handle_pallet_listing_action(
                            request,
                            action="listing_confirm",
                            listing_form=self._listing_form(valid=True),
                            state=state,
                        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        error_mock.assert_called_once_with(request, "Aucun entrepôt configuré.")

    def test_handle_listing_confirm_import_reports_results_and_clears_pending(self):
        request = self._request(
            {
                "pending_token": "tok-import",
                "row_2_apply": "1",
                "row_2_name": "Masque modifie",
                "row_2_match": "product:42",
                "row_2_match_override": "ALT-001",
            }
        )
        request.session["pallet_listing_pending"] = {
            "token": "tok-import",
            "mapping": {0: "name", 1: "quantity"},
            "receipt_meta": {"received_on": "2026-01-10"},
        }
        state = init_listing_state()
        warehouse = SimpleNamespace(id=1)
        receipt = SimpleNamespace(reference="RCP-777")
        mapped_row = {
            "name": "Masque",
            "quantity": "2",
            "zone": "R1",
            "aisle": "A1",
            "shelf": "B1",
            "rack_color": "Blue",
        }
        with mock.patch(
            "wms.pallet_listing_handlers.load_listing_table",
            return_value=(["Nom", "Quantite"], [["Masque", "2"]]),
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.apply_listing_mapping",
                return_value=[mapped_row],
            ):
                with mock.patch(
                    "wms.pallet_listing_handlers.resolve_default_warehouse",
                    return_value=warehouse,
                ):
                    with mock.patch(
                        "wms.pallet_listing_handlers.apply_pallet_listing_import",
                        return_value=(2, 1, ["err-1", "err-2"], receipt),
                    ) as import_mock:
                        with mock.patch(
                            "wms.pallet_listing_handlers.clear_pending_listing"
                        ) as clear_mock:
                            with mock.patch(
                                "wms.pallet_listing_handlers.messages.error"
                            ) as error_mock:
                                with mock.patch(
                                    "wms.pallet_listing_handlers.messages.success"
                                ) as success_mock:
                                    with mock.patch(
                                        "wms.pallet_listing_handlers.messages.warning"
                                    ) as warning_mock:
                                        response = handle_pallet_listing_action(
                                            request,
                                            action="listing_confirm",
                                            listing_form=self._listing_form(valid=True),
                                            state=state,
                                        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        call_args, call_kwargs = import_mock.call_args
        self.assertEqual(call_kwargs["user"], self.user)
        self.assertEqual(call_kwargs["warehouse"], warehouse)
        self.assertEqual(call_kwargs["receipt_meta"], {"received_on": "2026-01-10"})
        self.assertEqual(len(call_args[0]), 1)
        payload = call_args[0][0]
        self.assertTrue(payload["apply"])
        self.assertEqual(payload["row_index"], 2)
        self.assertEqual(payload["row_data"]["name"], "Masque modifie")
        self.assertEqual(payload["row_data"]["quantity"], "2")
        self.assertEqual(payload["selection"], "product:42")
        self.assertEqual(payload["override_code"], "ALT-001")
        error_mock.assert_any_call(request, "Import terminé avec 2 erreur(s).")
        success_mock.assert_called_once_with(
            request,
            "2 ligne(s) réceptionnée(s) (ref RCP-777).",
        )
        warning_mock.assert_called_once_with(request, "1 ligne(s) ignorée(s).")
        clear_mock.assert_called_once_with(request)

    def test_handle_listing_confirm_when_nothing_created_adds_error(self):
        request = self._request({"pending_token": "tok-empty"})
        request.session["pallet_listing_pending"] = {
            "token": "tok-empty",
            "mapping": {0: "name", 1: "quantity"},
            "receipt_meta": {},
        }
        state = init_listing_state()
        with mock.patch(
            "wms.pallet_listing_handlers.load_listing_table",
            return_value=(["Nom", "Quantite"], [["Masque", "2"]]),
        ):
            with mock.patch(
                "wms.pallet_listing_handlers.apply_listing_mapping",
                return_value=[{"name": "Masque", "quantity": "2"}],
            ):
                with mock.patch(
                    "wms.pallet_listing_handlers.resolve_default_warehouse",
                    return_value=SimpleNamespace(id=1),
                ):
                    with mock.patch(
                        "wms.pallet_listing_handlers.apply_pallet_listing_import",
                        return_value=(0, 0, [], None),
                    ):
                        with mock.patch(
                            "wms.pallet_listing_handlers.clear_pending_listing"
                        ):
                            with mock.patch(
                                "wms.pallet_listing_handlers.messages.error"
                            ) as error_mock:
                                response = handle_pallet_listing_action(
                                    request,
                                    action="listing_confirm",
                                    listing_form=self._listing_form(valid=True),
                                    state=state,
                                )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        error_mock.assert_called_once_with(request, "Aucune ligne valide à importer.")

    def test_handle_listing_action_returns_none_for_unknown_action(self):
        request = self._request()
        state = init_listing_state()
        response = handle_pallet_listing_action(
            request,
            action="noop",
            listing_form=self._listing_form(valid=True),
            state=state,
        )
        self.assertIsNone(response)
