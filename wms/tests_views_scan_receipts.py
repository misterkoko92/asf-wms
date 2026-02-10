from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from wms.models import Receipt, ReceiptType, Warehouse


class ScanReceiptsViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-receipts-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.warehouse = Warehouse.objects.create(name="Reception", code="REC")

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _create_receipt(self, receipt_type):
        return Receipt.objects.create(
            receipt_type=receipt_type,
            warehouse=self.warehouse,
        )

    def test_scan_receipts_view_filters_pallet_receipts(self):
        self._create_receipt(ReceiptType.PALLET)
        self._create_receipt(ReceiptType.ASSOCIATION)

        with mock.patch(
            "wms.views_scan_receipts.build_receipts_view_rows",
            side_effect=lambda qs: [item.receipt_type for item in qs],
        ):
            with mock.patch(
                "wms.views_scan_receipts.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(
                    f"{reverse('scan:scan_receipts_view')}?type=pallet"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receipts_view.html")
        self.assertEqual(response.context_data["filter_value"], "pallet")
        self.assertEqual(response.context_data["receipts"], [ReceiptType.PALLET])

    def test_scan_receipts_view_filters_association_receipts(self):
        self._create_receipt(ReceiptType.PALLET)
        self._create_receipt(ReceiptType.ASSOCIATION)

        with mock.patch(
            "wms.views_scan_receipts.build_receipts_view_rows",
            side_effect=lambda qs: [item.receipt_type for item in qs],
        ):
            with mock.patch(
                "wms.views_scan_receipts.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(
                    f"{reverse('scan:scan_receipts_view')}?type=association"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["filter_value"], "association")
        self.assertEqual(response.context_data["receipts"], [ReceiptType.ASSOCIATION])

    def test_scan_receipts_view_defaults_to_all_for_unknown_filter(self):
        self._create_receipt(ReceiptType.PALLET)
        self._create_receipt(ReceiptType.ASSOCIATION)

        with mock.patch(
            "wms.views_scan_receipts.build_receipts_view_rows",
            side_effect=lambda qs: [item.receipt_type for item in qs],
        ):
            with mock.patch(
                "wms.views_scan_receipts.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(
                    f"{reverse('scan:scan_receipts_view')}?type=unknown"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["filter_value"], "all")
        self.assertEqual(
            sorted(response.context_data["receipts"]),
            sorted([ReceiptType.PALLET, ReceiptType.ASSOCIATION]),
        )

    def test_scan_receive_get_renders_state_context(self):
        state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_receipt": "RCP-1",
            "receipt_lines": [{"line": 1}],
            "pending_count": 2,
        }
        with mock.patch(
            "wms.views_scan_receipts.build_product_options",
            return_value=[{"id": 1}],
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receipt_scan_state",
                return_value=state,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive.html")
        self.assertEqual(response.context_data["products_json"], [{"id": 1}])
        self.assertEqual(response.context_data["selected_receipt"], "RCP-1")
        self.assertEqual(response.context_data["receipt_lines"], [{"line": 1}])
        self.assertEqual(response.context_data["pending_count"], 2)

    def test_scan_receive_post_returns_handler_response_when_available(self):
        state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_receipt": None,
            "receipt_lines": [],
            "pending_count": 0,
        }
        with mock.patch(
            "wms.views_scan_receipts.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receipt_scan_state",
                return_value=state,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_action",
                    return_value=(HttpResponse("handled"), None, None),
                ):
                    response = self.client.post(
                        reverse("scan:scan_receive"),
                        {"action": "receive_now"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")

    def test_scan_receive_post_updates_lines_and_pending_when_handler_returns_data(self):
        state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_receipt": None,
            "receipt_lines": [],
            "pending_count": 0,
        }
        with mock.patch(
            "wms.views_scan_receipts.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receipt_scan_state",
                return_value=state,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_action",
                    return_value=(None, [{"line": 99}], 4),
                ):
                    with mock.patch(
                        "wms.views_scan_receipts.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            reverse("scan:scan_receive"),
                            {"action": "receive_now"},
                        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive.html")
        self.assertEqual(response.context_data["receipt_lines"], [{"line": 99}])
        self.assertEqual(response.context_data["pending_count"], 4)

    def test_scan_receive_pallet_returns_state_response_when_present(self):
        with mock.patch(
            "wms.views_scan_receipts.build_receive_pallet_state",
            return_value={"response": HttpResponse("pallet-response")},
        ):
            response = self.client.post(
                reverse("scan:scan_receive_pallet"),
                {"action": "create"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "pallet-response")

    def test_scan_receive_pallet_renders_context_when_no_state_response(self):
        state = {"response": None, "key": "value"}
        with mock.patch(
            "wms.views_scan_receipts.build_receive_pallet_state",
            return_value=state,
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receive_pallet_context",
                return_value={"context_key": "pallet"},
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_pallet.html")
        self.assertEqual(response.context_data["context_key"], "pallet")

    def test_scan_receive_association_get_renders_context(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_receipts.build_hors_format_lines",
            return_value=(2, [{"line": 1}, {"line": 2}]),
        ):
            with mock.patch(
                "wms.views_scan_receipts.ScanReceiptAssociationForm",
                return_value=fake_form,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_association.html")
        self.assertEqual(response.context_data["line_count"], 2)
        self.assertEqual(response.context_data["line_values"], [{"line": 1}, {"line": 2}])
        self.assertEqual(response.context_data["line_errors"], {})
        self.assertIs(response.context_data["create_form"], fake_form)

    def test_scan_receive_association_post_returns_handler_response(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_receipts.build_hors_format_lines",
            return_value=(1, [{"line": 1}]),
        ):
            with mock.patch(
                "wms.views_scan_receipts.ScanReceiptAssociationForm",
                return_value=fake_form,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_association_post",
                    return_value=(HttpResponse("association-response"), {}),
                ):
                    response = self.client.post(
                        reverse("scan:scan_receive_association"),
                        {"action": "create"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "association-response")

    def test_scan_receive_association_post_renders_with_line_errors(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_receipts.build_hors_format_lines",
            return_value=(1, [{"line": 1}]),
        ):
            with mock.patch(
                "wms.views_scan_receipts.ScanReceiptAssociationForm",
                return_value=fake_form,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_association_post",
                    return_value=(None, {"0": "invalid"}),
                ):
                    with mock.patch(
                        "wms.views_scan_receipts.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            reverse("scan:scan_receive_association"),
                            {"action": "create"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_association.html")
        self.assertEqual(response.context_data["line_errors"], {"0": "invalid"})
