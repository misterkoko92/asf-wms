from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonSourceKind,
    CartonStatus,
    Order,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderReviewStatus,
    OrderShipmentLink,
    Receipt,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    Warehouse,
)
from wms.order_view_helpers import build_orders_view_rows


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
        rows = [
            {
                "id": 1,
                "reference": "ORD-1",
                "review_status_value": OrderReviewStatus.PENDING,
                "can_create_shipment": False,
            },
            {
                "id": 2,
                "reference": "ORD-2",
                "review_status_value": OrderReviewStatus.CHANGES_REQUESTED,
                "can_create_shipment": False,
            },
            {
                "id": 3,
                "reference": "ORD-3",
                "review_status_value": OrderReviewStatus.APPROVED,
                "can_create_shipment": True,
            },
            {
                "id": 4,
                "reference": "ORD-4",
                "review_status_value": OrderReviewStatus.REJECTED,
                "can_create_shipment": False,
            },
        ]
        with mock.patch(
            "wms.views_scan_orders.build_orders_view_rows",
            return_value=rows,
        ):
            with mock.patch(
                "wms.views_scan_orders.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_orders_view"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/orders_view.html")
        self.assertEqual(response.context_data["active"], "orders_view")
        self.assertEqual(response.context_data["orders"], rows)
        self.assertEqual(
            [card["id"] for card in response.context_data["summary_cards"]],
            [
                "to-validate",
                "changes-requested",
                "approved-without-shipment",
                "rejected-orders",
            ],
        )
        self.assertEqual(
            [card["value"] for card in response.context_data["summary_cards"]],
            [1, 1, 1, 1],
        )
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

    def test_build_orders_view_rows_allows_creating_additional_shipments_for_approved_order(self):
        shipment = Shipment.objects.create(
            reference="EXP-ORDERS-001",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            association_contact=None,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            shipment=shipment,
        )

        rows = build_orders_view_rows(Order.objects.filter(id=order.id))

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["can_create_shipment"])

    def test_build_orders_view_rows_exposes_inbound_receipt_shortcut_and_linked_shipments(self):
        warehouse = Warehouse.objects.create(name="Scan Orders", code="SO")
        source_contact = Contact.objects.create(
            name="Association inbound",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=warehouse,
            source_contact=source_contact,
        )
        shipment = Shipment.objects.create(
            reference="EXP-ORDERS-INBOUND",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            association_contact=source_contact,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
        )
        OrderInboundDelivery.objects.create(
            order=order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=3,
            receipt=receipt,
        )
        Carton.objects.create(
            code="AS-ORDERS-001",
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=receipt,
        )
        OrderShipmentLink.objects.create(order=order, shipment=shipment, created_by=self.staff_user)

        rows = build_orders_view_rows(Order.objects.filter(id=order.id))

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["receipt_shortcut_url"],
            f"{reverse('scan:scan_receive_association')}?order_id={order.id}",
        )
        self.assertEqual(rows[0]["shipper_received_unassigned_carton_count"], 1)
        self.assertEqual(rows[0]["linked_shipments"][0]["reference"], shipment.reference)

    def test_scan_orders_view_create_shipment_uses_force_new_for_approved_order(self):
        existing_shipment = Shipment.objects.create(
            reference="EXP-ORDERS-EXISTING",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        new_shipment = Shipment.objects.create(
            reference="EXP-ORDERS-NEW",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            association_contact=None,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            shipment=existing_shipment,
        )

        with (
            mock.patch(
                "wms.order_view_handlers.create_shipment_for_order",
                return_value=new_shipment,
            ) as create_shipment_mock,
            mock.patch("wms.order_view_handlers.attach_order_documents_to_shipment") as attach_mock,
        ):
            response = self.client.post(
                reverse("scan:scan_orders_view"),
                {
                    "action": "create_shipment",
                    "order_id": str(order.id),
                },
            )

        self.assertEqual(response.status_code, 302)
        create_shipment_mock.assert_called_once_with(order=order, force_new=True)
        attach_mock.assert_called_once_with(order, new_shipment)
