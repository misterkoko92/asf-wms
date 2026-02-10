from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms.models import ReceiptStatus, ReceiptType
from wms.receipt_pallet_handlers import handle_pallet_create_post
from wms.receipt_pallet_state import build_receive_pallet_context, build_receive_pallet_state


class _FakeForm:
    def __init__(self, *, valid, cleaned_data=None):
        self._valid = valid
        self.cleaned_data = cleaned_data or {}
        self.errors = []

    def is_valid(self):
        return self._valid

    def add_error(self, field, error):
        self.errors.append((field, str(error)))


class ReceiptPalletFlowTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=7, username="pallet-user")

    def _request(self, *, method="POST", data=None):
        if method == "POST":
            request = self.factory.post("/scan/receive-pallet/", data or {})
        else:
            request = self.factory.get("/scan/receive-pallet/", data or {})
        request.user = self.user
        request.session = {}
        return request

    def _valid_create_cleaned_data(self):
        return {
            "source_contact": "source",
            "carrier_contact": "carrier",
            "received_on": "2026-01-10",
            "pallet_count": 4,
            "transport_request_date": "2026-01-08",
        }

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

    def test_handle_pallet_create_post_returns_none_when_form_invalid(self):
        request = self._request()
        form = _FakeForm(valid=False)
        with mock.patch("wms.receipt_pallet_handlers.resolve_default_warehouse") as warehouse_mock:
            response = handle_pallet_create_post(request, form=form)
        self.assertIsNone(response)
        warehouse_mock.assert_not_called()

    def test_handle_pallet_create_post_adds_error_without_default_warehouse(self):
        request = self._request()
        form = _FakeForm(valid=True, cleaned_data=self._valid_create_cleaned_data())
        with mock.patch("wms.receipt_pallet_handlers.resolve_default_warehouse", return_value=None):
            response = handle_pallet_create_post(request, form=form)
        self.assertIsNone(response)
        self.assertIn((None, "Aucun entrepot configure."), form.errors)

    def test_handle_pallet_create_post_success_creates_receipt_and_redirects(self):
        request = self._request()
        form = _FakeForm(valid=True, cleaned_data=self._valid_create_cleaned_data())
        warehouse = SimpleNamespace(id=4)
        receipt = SimpleNamespace(reference="RCP-PL-001")
        with mock.patch(
            "wms.receipt_pallet_handlers.resolve_default_warehouse",
            return_value=warehouse,
        ):
            with mock.patch(
                "wms.receipt_pallet_handlers.Receipt.objects.create",
                return_value=receipt,
            ) as create_mock:
                with mock.patch("wms.receipt_pallet_handlers.messages.success") as success_mock:
                    response = handle_pallet_create_post(request, form=form)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_pallet"))
        create_mock.assert_called_once_with(
            receipt_type=ReceiptType.PALLET,
            status=ReceiptStatus.DRAFT,
            source_contact="source",
            carrier_contact="carrier",
            received_on="2026-01-10",
            pallet_count=4,
            transport_request_date="2026-01-08",
            warehouse=warehouse,
            created_by=self.user,
        )
        success_mock.assert_called_once()

    def test_build_receive_pallet_state_post_calls_listing_then_create_handler(self):
        request = self._request(data={"action": "pallet_create"})
        request.session["pallet_listing_pending"] = {"token": "tok-pending"}
        create_form = _FakeForm(valid=True)
        listing_form = _FakeForm(valid=False)
        listing_state = self._listing_state()

        with mock.patch(
            "wms.receipt_pallet_state.ScanReceiptPalletForm",
            side_effect=[create_form, listing_form],
        ) as form_cls:
            with mock.patch(
                "wms.receipt_pallet_state.init_listing_state",
                return_value=listing_state,
            ):
                with mock.patch(
                    "wms.receipt_pallet_state.handle_pallet_listing_action",
                    return_value=None,
                ) as listing_action_mock:
                    with mock.patch(
                        "wms.receipt_pallet_state.handle_pallet_create_post",
                        return_value="create-response",
                    ) as create_mock:
                        with mock.patch(
                            "wms.receipt_pallet_state.hydrate_listing_state_from_pending",
                            return_value={"received_on": "2026-01-10"},
                        ) as hydrate_mock:
                            state = build_receive_pallet_state(request, action="pallet_create")

        self.assertEqual(state["response"], "create-response")
        self.assertIs(state["create_form"], create_form)
        self.assertIs(state["listing_form"], listing_form)
        self.assertIs(state["listing_state"], listing_state)
        self.assertEqual(state["listing_meta"], {"received_on": "2026-01-10"})
        self.assertEqual(state["pending"], {"token": "tok-pending"})
        form_cls.assert_has_calls([mock.call(request.POST), mock.call(None, prefix="listing")])
        listing_action_mock.assert_called_once_with(
            request,
            action="pallet_create",
            listing_form=listing_form,
            state=listing_state,
        )
        create_mock.assert_called_once_with(request, form=create_form)
        hydrate_mock.assert_called_once_with(listing_state, {"token": "tok-pending"})

    def test_build_receive_pallet_state_get_skips_post_handlers(self):
        request = self._request(method="GET")
        request.session["pallet_listing_pending"] = {"token": "tok-get"}
        create_form = _FakeForm(valid=False)
        listing_form = _FakeForm(valid=False)
        listing_state = self._listing_state()

        with mock.patch(
            "wms.receipt_pallet_state.ScanReceiptPalletForm",
            side_effect=[create_form, listing_form],
        ) as form_cls:
            with mock.patch(
                "wms.receipt_pallet_state.init_listing_state",
                return_value=listing_state,
            ):
                with mock.patch(
                    "wms.receipt_pallet_state.handle_pallet_listing_action"
                ) as listing_action_mock:
                    with mock.patch(
                        "wms.receipt_pallet_state.handle_pallet_create_post"
                    ) as create_mock:
                        with mock.patch(
                            "wms.receipt_pallet_state.hydrate_listing_state_from_pending",
                            return_value={"sheet_name": "Sheet1"},
                        ) as hydrate_mock:
                            state = build_receive_pallet_state(request, action="listing_upload")

        self.assertIsNone(state["response"])
        self.assertEqual(state["listing_meta"], {"sheet_name": "Sheet1"})
        form_cls.assert_has_calls(
            [
                mock.call(None),
                mock.call(request.POST, prefix="listing"),
            ]
        )
        listing_action_mock.assert_not_called()
        create_mock.assert_not_called()
        hydrate_mock.assert_called_once_with(listing_state, {"token": "tok-get"})

    def test_build_receive_pallet_context_maps_state_and_pending_token(self):
        listing_state = self._listing_state()
        state = {
            "create_form": "create-form",
            "listing_form": "listing-form",
            "listing_state": listing_state,
            "listing_meta": {"meta": "value"},
            "pending": {"token": "tok-ctx"},
        }

        context = build_receive_pallet_context(state)

        self.assertEqual(context["active"], "receive_pallet")
        self.assertEqual(context["create_form"], "create-form")
        self.assertEqual(context["listing_form"], "listing-form")
        self.assertEqual(context["listing_stage"], "review")
        self.assertEqual(context["listing_columns"], ["reference"])
        self.assertEqual(context["listing_rows"], [{"reference": "A"}])
        self.assertEqual(context["listing_token"], "tok-ctx")
        self.assertEqual(context["listing_meta"], {"meta": "value"})

        state["pending"] = None
        context_without_pending = build_receive_pallet_context(state)
        self.assertEqual(context_without_pending["listing_token"], "")
