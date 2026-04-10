from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms.models import ReceiptConformityStatus, ReceiptStatus, ReceiptType
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
        self.assertIn((None, "Aucun entrepôt configuré."), form.errors)

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
            conformity_status=ReceiptConformityStatus.CONFORM,
            notes="",
            warehouse=warehouse,
            created_by=self.user,
        )
        success_mock.assert_called_once()

    def test_build_receive_pallet_state_post_calls_create_handler_only(self):
        request = self._request(data={"action": "pallet_create"})
        create_form = _FakeForm(valid=True)

        with mock.patch(
            "wms.receipt_pallet_state.ScanReceiptPalletForm",
            return_value=create_form,
        ) as form_cls:
            with mock.patch(
                "wms.receipt_pallet_state.handle_pallet_create_post",
                return_value="create-response",
            ) as create_mock:
                state = build_receive_pallet_state(request, action="pallet_create")

        self.assertEqual(state["response"], "create-response")
        self.assertIs(state["create_form"], create_form)
        form_cls.assert_called_once_with(request.POST)
        create_mock.assert_called_once_with(request, form=create_form)

    def test_build_receive_pallet_state_get_skips_post_handlers(self):
        request = self._request(method="GET")
        create_form = _FakeForm(valid=False)

        with mock.patch(
            "wms.receipt_pallet_state.ScanReceiptPalletForm",
            return_value=create_form,
        ) as form_cls:
            with mock.patch("wms.receipt_pallet_state.handle_pallet_create_post") as create_mock:
                state = build_receive_pallet_state(request, action="listing_upload")

        self.assertIsNone(state["response"])
        self.assertIs(state["create_form"], create_form)
        form_cls.assert_called_once_with(None)
        create_mock.assert_not_called()

    def test_build_receive_pallet_context_maps_manual_create_state_only(self):
        state = {
            "create_form": "create-form",
            "response": None,
        }

        context = build_receive_pallet_context(state)

        self.assertEqual(context["active"], "receive_pallet")
        self.assertEqual(context["create_form"], "create-form")
        self.assertNotIn("listing_form", context)
        self.assertNotIn("listing_stage", context)
        self.assertNotIn("listing_token", context)
