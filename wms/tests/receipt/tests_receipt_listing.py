from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms.models import Receipt, ReceiptType, Warehouse
from wms.receipt_listing_state import build_receive_listing_context, build_receive_listing_state


class _FakeForm:
    def __init__(self, *, valid, cleaned_data=None):
        self._valid = valid
        self.cleaned_data = cleaned_data or {}

    def is_valid(self):
        return self._valid


class ReceiptListingFlowTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=17, username="listing-user")
        self.warehouse = Warehouse.objects.create(name="Listing", code="LST")
        self.source_contact = Contact.objects.create(
            name="Donateur A",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.carrier_contact = Contact.objects.create(
            name="Transporteur B",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.receipt = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.warehouse,
            received_on=date(2026, 1, 10),
            pallet_count=3,
            source_contact=self.source_contact,
            carrier_contact=self.carrier_contact,
        )

    def _request(self, *, method="POST", data=None):
        if method == "POST":
            request = self.factory.post("/scan/receive-listing/", data or {})
        else:
            request = self.factory.get("/scan/receive-listing/", data or {})
        request.user = self.user
        request.session = {}
        return request

    def _listing_state(self):
        return {
            "listing_stage": "review",
            "listing_columns": ["reference"],
            "listing_rows": [{"reference": "A"}],
            "listing_group_suggestions": [{"id": "brand:mask"}],
            "listing_errors": [],
            "listing_sheet_names": ["Sheet1"],
            "listing_sheet_name": "Sheet1",
            "listing_header_row": 2,
            "listing_pdf_pages_mode": "all",
            "listing_pdf_page_start": "",
            "listing_pdf_page_end": "",
            "listing_pdf_total_pages": "",
            "listing_pdf_analysis": None,
            "listing_file_type": "excel",
            "listing_entry_file_type": "",
            "listing_entry_receipt_id": "",
            "listing_selected_receipt": None,
        }

    def test_build_receive_listing_state_binds_entry_form_on_listing_configure(self):
        request = self._request(
            data={
                "action": "listing_configure",
                "listing_entry_file_type": "pdf",
                "listing_entry_receipt_id": "",
            }
        )

        state = build_receive_listing_state(request, action="listing_configure")

        self.assertTrue(state["listing_entry_form"].is_bound)

    def test_build_receive_listing_state_configure_requires_receipt(self):
        request = self._request(
            data={
                "action": "listing_configure",
                "listing_entry_file_type": "pdf",
                "listing_entry_receipt_id": "",
            }
        )

        state = build_receive_listing_state(request, action="listing_configure")

        self.assertIsNone(state["response"])
        self.assertNotIn("pallet_listing_pending", request.session)
        self.assertIn("listing_entry_receipt_id", state["listing_entry_form"].errors)

    def test_build_receive_listing_state_configure_success_persists_pending_and_redirects(self):
        request = self._request(
            data={
                "action": "listing_configure",
                "listing_entry_file_type": "pdf",
                "listing_entry_receipt_id": str(self.receipt.id),
            }
        )
        request.session["pallet_listing_last_incomplete_product_ids"] = [11, 12]

        state = build_receive_listing_state(request, action="listing_configure")

        self.assertEqual(state["response"].status_code, 302)
        self.assertEqual(state["response"].url, "/scan/receive-listing/")
        self.assertEqual(
            request.session["pallet_listing_pending"],
            {
                "entry_file_type": "pdf",
                "receipt_id": self.receipt.id,
                "stage": "upload",
            },
        )
        self.assertNotIn("pallet_listing_last_incomplete_product_ids", request.session)

    def test_build_receive_listing_state_post_calls_listing_handler(self):
        request = self._request(data={"action": "listing_upload"})
        request.session["pallet_listing_pending"] = {"token": "tok-pending"}
        listing_state = self._listing_state()
        with mock.patch(
            "wms.receipt_listing_state.init_listing_state",
            return_value=listing_state,
        ):
            with mock.patch(
                "wms.receipt_listing_state.handle_pallet_listing_action",
                return_value="listing-response",
            ) as listing_action_mock:
                with mock.patch(
                    "wms.receipt_listing_state.hydrate_listing_state_from_pending",
                    return_value={"received_on": "2026-01-10"},
                ) as hydrate_mock:
                    state = build_receive_listing_state(request, action="listing_upload")

        self.assertEqual(state["response"], "listing-response")
        self.assertIs(state["listing_state"], listing_state)
        self.assertEqual(state["listing_meta"], {"received_on": "2026-01-10"})
        self.assertEqual(state["pending"], {"token": "tok-pending"})
        listing_action_mock.assert_called_once_with(
            request,
            action="listing_upload",
            state=listing_state,
        )
        self.assertEqual(
            hydrate_mock.call_args_list,
            [
                mock.call(listing_state, {"token": "tok-pending"}),
                mock.call(listing_state, {"token": "tok-pending"}),
            ],
        )

    def test_build_receive_listing_state_get_restores_review_stage_from_pending(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {
            "token": "tok-review",
            "stage": "review",
            "mapping": {0: "name", 1: "quantity"},
            "review_overrides": {"row-2": {"selection": "new", "values": {"brand": "BRAUN"}}},
            "dismissed_suggestion_ids": ["brand:other"],
        }
        listing_state = self._listing_state()
        listing_state["listing_stage"] = None
        listing_state["listing_rows"] = []
        listing_state["listing_group_suggestions"] = []

        with mock.patch(
            "wms.receipt_listing_state.init_listing_state",
            return_value=listing_state,
        ):
            with mock.patch(
                "wms.receipt_listing_state.hydrate_listing_state_from_pending",
                return_value={"received_on": "2026-01-10"},
            ):
                with mock.patch(
                    "wms.receipt_listing_state.load_listing_table",
                    return_value=(["Nom", "Quantite"], [["Masque", "3"]]),
                ) as load_mock:
                    with mock.patch(
                        "wms.receipt_listing_state.build_listing_review_state",
                        return_value={
                            "rows": [{"index": 2, "values": {"name": "Masque"}}],
                            "group_suggestions": [{"id": "brand:braun"}],
                        },
                    ) as review_mock:
                        state = build_receive_listing_state(request, action="")

        self.assertIsNone(state["response"])
        self.assertEqual(state["listing_state"]["listing_stage"], "review")
        self.assertEqual(
            state["listing_state"]["listing_rows"], [{"index": 2, "values": {"name": "Masque"}}]
        )
        self.assertEqual(
            state["listing_state"]["listing_group_suggestions"], [{"id": "brand:braun"}]
        )
        load_mock.assert_called_once_with(request.session["pallet_listing_pending"])
        review_mock.assert_called_once_with(
            [["Masque", "3"]],
            {0: "name", 1: "quantity"},
            review_overrides={"row-2": {"selection": "new", "values": {"brand": "BRAUN"}}},
            dismissed_suggestion_ids=["brand:other"],
        )

    def test_build_receive_listing_state_get_restores_suggestions_stage_from_pending(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {
            "token": "tok-suggestions",
            "stage": "suggestions",
            "mapping": {0: "name", 1: "quantity"},
        }
        listing_state = self._listing_state()
        listing_state["listing_stage"] = None
        listing_state["listing_rows"] = []
        listing_state["listing_group_suggestions"] = []

        with mock.patch(
            "wms.receipt_listing_state.init_listing_state",
            return_value=listing_state,
        ):
            with mock.patch(
                "wms.receipt_listing_state.hydrate_listing_state_from_pending",
                return_value={"received_on": "2026-01-10"},
            ):
                with mock.patch(
                    "wms.receipt_listing_state.load_listing_table",
                    return_value=(["Nom", "Quantite"], [["Masque", "3"]]),
                ):
                    with mock.patch(
                        "wms.receipt_listing_state.build_listing_review_state",
                        return_value={
                            "rows": [{"index": 2, "values": {"name": "Masque"}}],
                            "group_suggestions": [{"id": "brand:braun"}],
                        },
                    ):
                        state = build_receive_listing_state(request, action="")

        self.assertIsNone(state["response"])
        self.assertEqual(state["listing_state"]["listing_stage"], "suggestions")
        self.assertEqual(
            state["listing_state"]["listing_group_suggestions"], [{"id": "brand:braun"}]
        )

    def test_build_receive_listing_state_get_infers_mapping_stage_from_pending_headers(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {
            "token": "tok-mapping",
            "headers": ["Nom", "Quantite"],
            "mapping": {0: "name", 1: "quantity"},
        }
        listing_state = self._listing_state()
        listing_state["listing_stage"] = None
        listing_state["listing_columns"] = []

        with mock.patch(
            "wms.receipt_listing_state.init_listing_state",
            return_value=listing_state,
        ):
            with mock.patch(
                "wms.receipt_listing_state.hydrate_listing_state_from_pending",
                return_value={},
            ):
                with mock.patch(
                    "wms.receipt_listing_state.load_listing_table",
                    return_value=(["Nom", "Quantite"], [["Masque", "3"]]),
                ):
                    with mock.patch(
                        "wms.receipt_listing_state.build_listing_columns",
                        return_value=[{"index": 0, "mapped": "name"}],
                    ):
                        state = build_receive_listing_state(request, action="")

        self.assertEqual(state["listing_state"]["listing_stage"], "mapping")
        self.assertEqual(
            state["listing_state"]["listing_columns"], [{"index": 0, "mapped": "name"}]
        )

    def test_build_receive_listing_state_get_ignores_restore_errors(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {
            "token": "tok-restore-error",
            "stage": "review",
            "mapping": {0: "name"},
        }
        listing_state = self._listing_state()
        listing_state["listing_stage"] = None
        listing_state["listing_rows"] = []

        with mock.patch(
            "wms.receipt_listing_state.init_listing_state",
            return_value=listing_state,
        ):
            with mock.patch(
                "wms.receipt_listing_state.hydrate_listing_state_from_pending",
                return_value={},
            ):
                with mock.patch(
                    "wms.receipt_listing_state.load_listing_table",
                    side_effect=ValueError("boom"),
                ):
                    state = build_receive_listing_state(request, action="")

        self.assertEqual(state["listing_state"]["listing_stage"], "review")
        self.assertEqual(state["listing_state"]["listing_rows"], [])

    def test_build_receive_listing_state_get_skips_post_handlers(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {"token": "tok-get"}
        listing_state = self._listing_state()
        with mock.patch(
            "wms.receipt_listing_state.init_listing_state",
            return_value=listing_state,
        ):
            with mock.patch(
                "wms.receipt_listing_state.handle_pallet_listing_action"
            ) as listing_action_mock:
                with mock.patch(
                    "wms.receipt_listing_state.hydrate_listing_state_from_pending",
                    return_value={"sheet_name": "Sheet1"},
                ) as hydrate_mock:
                    state = build_receive_listing_state(request, action="listing_upload")

        self.assertIsNone(state["response"])
        self.assertEqual(state["listing_meta"], {"sheet_name": "Sheet1"})
        listing_action_mock.assert_not_called()
        hydrate_mock.assert_called_once_with(listing_state, {"token": "tok-get"})

    def test_build_receive_listing_context_maps_listing_state_and_pending_token(self):
        listing_state = self._listing_state()
        state = {
            "listing_entry_form": "entry-form",
            "listing_state": listing_state,
            "listing_meta": {"meta": "value"},
            "pending": {"token": "tok-ctx"},
        }

        context = build_receive_listing_context(state)

        self.assertEqual(context["active"], "receive_listing")
        self.assertEqual(context["listing_entry_form"], "entry-form")
        self.assertNotIn("listing_receipt_draft_form", context)
        self.assertNotIn("listing_form", context)
        self.assertEqual(context["listing_stage"], "review")
        self.assertEqual(context["listing_columns"], ["reference"])
        self.assertEqual(context["listing_rows"], [{"reference": "A"}])
        self.assertEqual(context["listing_group_suggestions"], [{"id": "brand:mask"}])
        self.assertEqual(context["listing_token"], "tok-ctx")
        self.assertEqual(context["listing_meta"], {"meta": "value"})
        self.assertEqual(context["listing_sheet_names"], ["Sheet1"])
        self.assertEqual(context["listing_file_type"], "excel")
        self.assertEqual(context["listing_entry_file_type"], "")
        self.assertEqual(context["listing_entry_receipt_id"], "")
        self.assertIsNone(context["listing_pdf_analysis"])
        self.assertEqual(context["listing_focus_card_id"], "scan-receive-pallet-review-card")
        self.assertEqual(context["listing_suggestions_total_count"], 1)

    def test_build_receive_listing_context_resolves_focus_cards_for_suggestions_and_mapping(self):
        suggestions_state = self._listing_state()
        suggestions_state["listing_stage"] = "suggestions"
        mapping_state = self._listing_state()
        mapping_state["listing_stage"] = "mapping"
        mapping_state["listing_rows"] = []
        mapping_state["listing_group_suggestions"] = []

        suggestions_context = build_receive_listing_context(
            {
                "listing_entry_form": "entry-form",
                "listing_state": suggestions_state,
                "listing_meta": {},
                "pending": {"token": "tok-suggestions"},
            }
        )
        mapping_context = build_receive_listing_context(
            {
                "listing_entry_form": "entry-form",
                "listing_state": mapping_state,
                "listing_meta": {},
                "pending": {"token": "tok-mapping"},
            }
        )

        self.assertEqual(
            suggestions_context["listing_focus_card_id"],
            "scan-receive-listing-suggestions-card",
        )
        self.assertEqual(
            mapping_context["listing_focus_card_id"],
            "scan-receive-pallet-mapping-card",
        )
