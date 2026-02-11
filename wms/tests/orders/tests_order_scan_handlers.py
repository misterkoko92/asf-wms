from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms.models import (
    Location,
    Order,
    OrderLine,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Warehouse,
)
from wms.order_scan_handlers import handle_order_action
from wms.services import StockError


class _DummyForm:
    def __init__(self, *, is_valid, cleaned_data=None):
        self._is_valid = is_valid
        self.cleaned_data = cleaned_data or {}
        self.errors = []

    def is_valid(self):
        return self._is_valid

    def add_error(self, field, message):
        self.errors.append((field, message))


class OrderScanHandlersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="scan-order-user",
            password="pass1234",
        )
        self.factory = RequestFactory()
        self.warehouse = Warehouse.objects.create(name="Scan WH", code="SWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="SCAN-001",
            name="Scan Product",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-SCAN",
            expires_on=date(2026, 1, 1),
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            location=self.location,
        )

    def _request(self):
        request = self.factory.post("/scan/order/")
        request.user = self.user
        return request

    def _make_order(self, *, status=OrderStatus.DRAFT):
        return Order.objects.create(
            status=status,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_handle_order_action_select_order_redirects(self):
        order = self._make_order()
        select_form = _DummyForm(is_valid=True, cleaned_data={"order": order})

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="select_order",
            select_form=select_form,
            create_form=_DummyForm(is_valid=False),
            line_form=_DummyForm(is_valid=False),
            selected_order=None,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('scan:scan_order')}?order={order.id}",
        )
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)

    def test_handle_order_action_add_line_requires_selected_order(self):
        line_form = _DummyForm(
            is_valid=True,
            cleaned_data={"product_code": self.product.sku, "quantity": 1},
        )

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="add_line",
            select_form=_DummyForm(is_valid=False),
            create_form=_DummyForm(is_valid=False),
            line_form=line_form,
            selected_order=None,
        )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        self.assertIn((None, "Sélectionnez une commande."), line_form.errors)

    def test_handle_order_action_add_line_rejects_cancelled_or_ready_order(self):
        for status in (OrderStatus.CANCELLED, OrderStatus.READY):
            with self.subTest(status=status):
                line_form = _DummyForm(
                    is_valid=True,
                    cleaned_data={"product_code": self.product.sku, "quantity": 1},
                )
                order = self._make_order(status=status)

                response, order_lines, remaining_total = handle_order_action(
                    self._request(),
                    action="add_line",
                    select_form=_DummyForm(is_valid=False),
                    create_form=_DummyForm(is_valid=False),
                    line_form=line_form,
                    selected_order=order,
                )

                self.assertIsNone(response)
                self.assertIsNone(order_lines)
                self.assertIsNone(remaining_total)
                self.assertIn((None, "Commande annulée."), line_form.errors)

    def test_handle_order_action_add_line_rejects_preparing_order(self):
        line_form = _DummyForm(
            is_valid=True,
            cleaned_data={"product_code": self.product.sku, "quantity": 1},
        )
        order = self._make_order(status=OrderStatus.PREPARING)

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="add_line",
            select_form=_DummyForm(is_valid=False),
            create_form=_DummyForm(is_valid=False),
            line_form=line_form,
            selected_order=order,
        )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        self.assertIn((None, "Commande en préparation."), line_form.errors)

    def test_handle_order_action_add_line_adds_error_when_product_not_found(self):
        line_form = _DummyForm(
            is_valid=True,
            cleaned_data={"product_code": "UNKNOWN", "quantity": 1},
        )
        order = self._make_order(status=OrderStatus.DRAFT)

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="add_line",
            select_form=_DummyForm(is_valid=False),
            create_form=_DummyForm(is_valid=False),
            line_form=line_form,
            selected_order=order,
        )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        self.assertIn(("product_code", "Produit introuvable."), line_form.errors)

    def test_handle_order_action_add_line_rolls_back_quantity_on_reservation_error(self):
        line_form = _DummyForm(
            is_valid=True,
            cleaned_data={"product_code": self.product.sku, "quantity": 2},
        )
        order = self._make_order(status=OrderStatus.DRAFT)
        line = OrderLine.objects.create(order=order, product=self.product, quantity=5)

        with mock.patch(
            "wms.order_scan_handlers.reserve_stock_for_order",
            side_effect=StockError("reserve error"),
        ):
            response, order_lines, remaining_total = handle_order_action(
                self._request(),
                action="add_line",
                select_form=_DummyForm(is_valid=False),
                create_form=_DummyForm(is_valid=False),
                line_form=line_form,
                selected_order=order,
            )

        line.refresh_from_db()
        self.assertIsNone(response)
        self.assertEqual(line.quantity, 5)
        self.assertIn((None, "reserve error"), line_form.errors)
        self.assertIsNotNone(order_lines)
        self.assertEqual(remaining_total, 5)

    def test_handle_order_action_prepare_order_handles_stock_error(self):
        order = self._make_order(status=OrderStatus.RESERVED)

        with mock.patch(
            "wms.order_scan_handlers.prepare_order",
            side_effect=StockError("prepare failed"),
        ):
            with mock.patch("wms.order_scan_handlers.messages.error") as error_mock:
                response, order_lines, remaining_total = handle_order_action(
                    self._request(),
                    action="prepare_order",
                    select_form=_DummyForm(is_valid=False),
                    create_form=_DummyForm(is_valid=False),
                    line_form=_DummyForm(is_valid=False),
                    selected_order=order,
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('scan:scan_order')}?order={order.id}",
        )
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        error_mock.assert_called_once()

    def test_handle_order_action_returns_empty_tuple_for_unknown_action(self):
        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="unknown",
            select_form=_DummyForm(is_valid=False),
            create_form=_DummyForm(is_valid=False),
            line_form=_DummyForm(is_valid=False),
            selected_order=None,
        )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
