from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse


class ScanStockViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-stock-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def test_scan_stock_renders_context_from_helper(self):
        with mock.patch(
            "wms.views_scan_stock.build_stock_context",
            return_value={"active": "stock", "rows": [1]},
        ):
            with mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/stock.html")
        self.assertEqual(response.context_data, {"active": "stock", "rows": [1]})

    def test_scan_stock_update_get_renders_context(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_stock.ScanStockUpdateForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[{"id": 1}],
            ):
                with mock.patch(
                    "wms.views_scan_stock.build_location_data",
                    return_value=[{"id": "A-01-001"}],
                ):
                    with mock.patch(
                        "wms.views_scan_stock.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.get(reverse("scan:scan_stock_update"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/stock_update.html")
        self.assertEqual(response.context_data["active"], "stock_update")
        self.assertIs(response.context_data["create_form"], fake_form)
        self.assertEqual(response.context_data["products_json"], [{"id": 1}])
        self.assertEqual(response.context_data["location_data"], [{"id": "A-01-001"}])

    def test_scan_stock_update_post_returns_handler_response_when_available(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_stock.ScanStockUpdateForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_stock.build_location_data",
                    return_value=[],
                ):
                    with mock.patch(
                        "wms.views_scan_stock.handle_stock_update_post",
                        return_value=HttpResponse("updated"),
                    ):
                        response = self.client.post(
                            reverse("scan:scan_stock_update"),
                            {"action": "save"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "updated")

    def test_scan_out_get_renders_context(self):
        fake_form = object()
        with mock.patch("wms.views_scan_stock.ScanOutForm", return_value=fake_form):
            with mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[{"id": 2}],
            ):
                with mock.patch(
                    "wms.views_scan_stock.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_out"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/out.html")
        self.assertIs(response.context_data["form"], fake_form)
        self.assertEqual(response.context_data["active"], "out")
        self.assertEqual(response.context_data["products_json"], [{"id": 2}])

    def test_scan_out_post_returns_handler_response_when_available(self):
        fake_form = object()
        with mock.patch("wms.views_scan_stock.ScanOutForm", return_value=fake_form):
            with mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_stock.handle_stock_out_post",
                    return_value=HttpResponse("out-post"),
                ):
                    response = self.client.post(reverse("scan:scan_out"), {"qty": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "out-post")

    def test_scan_sync_returns_json_state(self):
        fake_state = mock.Mock()
        fake_state.version = 12
        fake_state.last_changed_at = datetime(2026, 1, 5, 10, 30, 0)
        with mock.patch("wms.views_scan_stock.WmsChange.get_state", return_value=fake_state):
            response = self.client.get(reverse("scan:scan_sync"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 12)
        self.assertEqual(payload["changed_at"], "2026-01-05T10:30:00")
