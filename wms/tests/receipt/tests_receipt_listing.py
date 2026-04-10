from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

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
            "listing_errors": [],
            "listing_sheet_names": ["Sheet1"],
            "listing_sheet_name": "Sheet1",
            "listing_header_row": 2,
            "listing_pdf_pages_mode": "all",
            "listing_pdf_page_start": "",
            "listing_pdf_page_end": "",
            "listing_pdf_total_pages": "",
            "listing_file_type": "excel",
        }

    def test_build_receive_listing_state_post_calls_listing_handler(self):
        request = self._request(data={"action": "listing_upload"})
        request.session["pallet_listing_pending"] = {"token": "tok-pending"}
        listing_form = _FakeForm(valid=True)
        listing_state = self._listing_state()

        with mock.patch(
            "wms.receipt_listing_state.ScanReceiptPalletForm",
            return_value=listing_form,
        ) as form_cls:
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
        self.assertIs(state["listing_form"], listing_form)
        self.assertIs(state["listing_state"], listing_state)
        self.assertEqual(state["listing_meta"], {"received_on": "2026-01-10"})
        self.assertEqual(state["pending"], {"token": "tok-pending"})
        form_cls.assert_called_once_with(request.POST, prefix="listing")
        listing_action_mock.assert_called_once_with(
            request,
            action="listing_upload",
            listing_form=listing_form,
            state=listing_state,
        )
        hydrate_mock.assert_called_once_with(listing_state, {"token": "tok-pending"})

    def test_build_receive_listing_state_get_skips_post_handlers(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {"token": "tok-get"}
        listing_form = _FakeForm(valid=False)
        listing_state = self._listing_state()

        with mock.patch(
            "wms.receipt_listing_state.ScanReceiptPalletForm",
            return_value=listing_form,
        ) as form_cls:
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
        self.assertIs(state["listing_form"], listing_form)
        form_cls.assert_called_once_with(request.POST, prefix="listing")
        listing_action_mock.assert_not_called()
        hydrate_mock.assert_called_once_with(listing_state, {"token": "tok-get"})

    def test_build_receive_listing_context_maps_listing_state_and_pending_token(self):
        listing_state = self._listing_state()
        state = {
            "listing_form": "listing-form",
            "listing_state": listing_state,
            "listing_meta": {"meta": "value"},
            "pending": {"token": "tok-ctx"},
        }

        context = build_receive_listing_context(state)

        self.assertEqual(context["active"], "receive_listing")
        self.assertEqual(context["listing_form"], "listing-form")
        self.assertEqual(context["listing_stage"], "review")
        self.assertEqual(context["listing_columns"], ["reference"])
        self.assertEqual(context["listing_rows"], [{"reference": "A"}])
        self.assertEqual(context["listing_token"], "tok-ctx")
        self.assertEqual(context["listing_meta"], {"meta": "value"})
        self.assertEqual(context["listing_sheet_names"], ["Sheet1"])
        self.assertEqual(context["listing_file_type"], "excel")
