from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from wms.models import OrderReviewStatus


class ScanOrdersViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-orders-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def test_scan_order_get_renders_context(self):
        order_state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_order": "ORD-1",
            "order_lines": [{"line": 1}],
            "remaining_total": 3,
        }
        with mock.patch(
            "wms.views_scan_orders.build_product_options",
            return_value=[{"id": 1}],
        ):
            with mock.patch(
                "wms.views_scan_orders.build_order_scan_state",
                return_value=order_state,
            ):
                with mock.patch(
                    "wms.views_scan_orders.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_order"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/order.html")
        self.assertEqual(response.context_data["active"], "order")
        self.assertEqual(response.context_data["products_json"], [{"id": 1}])
        self.assertEqual(response.context_data["selected_order"], "ORD-1")
        self.assertEqual(response.context_data["order_lines"], [{"line": 1}])
        self.assertEqual(response.context_data["remaining_total"], 3)

    def test_scan_order_post_returns_handler_response_when_available(self):
        order_state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_order": None,
            "order_lines": [],
            "remaining_total": 0,
        }
        with mock.patch(
            "wms.views_scan_orders.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_orders.build_order_scan_state",
                return_value=order_state,
            ):
                with mock.patch(
                    "wms.views_scan_orders.handle_order_action",
                    return_value=(HttpResponse("handled"), None, None),
                ):
                    response = self.client.post(
                        reverse("scan:scan_order"),
                        {"action": "receive_now"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")

    def test_scan_order_post_updates_lines_and_remaining(self):
        order_state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_order": None,
            "order_lines": [],
            "remaining_total": 0,
        }
        with mock.patch(
            "wms.views_scan_orders.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_orders.build_order_scan_state",
                return_value=order_state,
            ):
                with mock.patch(
                    "wms.views_scan_orders.handle_order_action",
                    return_value=(None, [{"line": 5}], 8),
                ):
                    with mock.patch(
                        "wms.views_scan_orders.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            reverse("scan:scan_order"),
                            {"action": "receive_now"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/order.html")
        self.assertEqual(response.context_data["order_lines"], [{"line": 5}])
        self.assertEqual(response.context_data["remaining_total"], 8)

    def test_scan_orders_view_get_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_orders.build_orders_view_rows",
            return_value=[{"id": 1, "reference": "ORD-1"}],
        ):
            with mock.patch(
                "wms.views_scan_orders.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_orders_view"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/orders_view.html")
        self.assertEqual(response.context_data["active"], "orders_view")
        self.assertEqual(response.context_data["orders"], [{"id": 1, "reference": "ORD-1"}])
        self.assertEqual(response.context_data["approved_status"], OrderReviewStatus.APPROVED)
        self.assertEqual(response.context_data["rejected_status"], OrderReviewStatus.REJECTED)
        self.assertEqual(
            response.context_data["changes_status"],
            OrderReviewStatus.CHANGES_REQUESTED,
        )

    def test_scan_orders_view_post_returns_handler_response_when_available(self):
        with mock.patch(
            "wms.views_scan_orders.handle_orders_view_action",
            return_value=HttpResponse("orders-handled"),
        ):
            response = self.client.post(
                reverse("scan:scan_orders_view"),
                {"action": "approve"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "orders-handled")

    def test_scan_orders_view_post_renders_when_handler_returns_none(self):
        with mock.patch(
            "wms.views_scan_orders.handle_orders_view_action",
            return_value=None,
        ):
            with mock.patch(
                "wms.views_scan_orders.build_orders_view_rows",
                return_value=[{"id": 2, "reference": "ORD-2"}],
            ):
                with mock.patch(
                    "wms.views_scan_orders.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.post(
                        reverse("scan:scan_orders_view"),
                        {"action": "noop"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/orders_view.html")
        self.assertEqual(response.context_data["orders"], [{"id": 2, "reference": "ORD-2"}])
