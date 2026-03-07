from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import translation

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
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
from wms.organization_role_resolvers import OrganizationRoleResolutionError
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

    def _create_order_form(self, **overrides):
        cleaned_data = {
            "shipper_name": "Sender",
            "recipient_name": "Recipient",
            "correspondent_name": "",
            "shipper_contact": None,
            "recipient_contact": None,
            "correspondent_contact": None,
            "destination_address": "10 Rue Test",
            "destination_city": "Paris",
            "destination_country": "France",
            "requested_delivery_date": None,
            "notes": "",
        }
        cleaned_data.update(overrides)
        return _DummyForm(is_valid=True, cleaned_data=cleaned_data)

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

    def test_handle_order_action_create_order_not_blocked_when_legacy_write_is_disabled(self):
        create_form = self._create_order_form()

        with mock.patch("wms.order_scan_handlers.messages.success"):
            response, order_lines, remaining_total = handle_order_action(
                self._request(),
                action="create_order",
                select_form=_DummyForm(is_valid=False),
                create_form=create_form,
                line_form=_DummyForm(is_valid=False),
                selected_order=None,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(create_form.errors, [])
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)

    @mock.patch("wms.order_scan_handlers.is_org_roles_engine_enabled", return_value=True)
    def test_handle_order_action_create_order_with_org_roles_adds_required_errors(
        self, _engine_mock
    ):
        create_form = self._create_order_form(
            shipper_contact=None,
            recipient_contact=None,
            destination_city="",
            destination_country="",
        )

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="create_order",
            select_form=_DummyForm(is_valid=False),
            create_form=create_form,
            line_form=_DummyForm(is_valid=False),
            selected_order=None,
        )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        self.assertIn(("shipper_contact", "Expediteur requis."), create_form.errors)
        self.assertIn(("recipient_contact", "Destinataire requis."), create_form.errors)
        self.assertIn(
            ("destination_city", "Escale invalide pour le mode organization roles."),
            create_form.errors,
        )
        self.assertEqual(Order.objects.count(), 0)

    @mock.patch("wms.order_scan_handlers.is_org_roles_engine_enabled", return_value=True)
    def test_handle_order_action_create_order_with_org_roles_translates_errors_in_english(
        self, _engine_mock
    ):
        create_form = self._create_order_form(
            shipper_contact=None,
            recipient_contact=None,
            destination_city="",
            destination_country="",
        )

        with translation.override("en"):
            response, order_lines, remaining_total = handle_order_action(
                self._request(),
                action="create_order",
                select_form=_DummyForm(is_valid=False),
                create_form=create_form,
                line_form=_DummyForm(is_valid=False),
                selected_order=None,
            )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        self.assertIn(("shipper_contact", "Shipper required."), create_form.errors)
        self.assertIn(("recipient_contact", "Recipient required."), create_form.errors)
        self.assertIn(
            ("destination_city", "Invalid stopover for organization roles mode."),
            create_form.errors,
        )
        self.assertEqual(Order.objects.count(), 0)

    @mock.patch("wms.order_scan_handlers.is_org_roles_engine_enabled", return_value=True)
    @mock.patch("wms.order_scan_handlers.resolve_recipient_binding_for_operation")
    @mock.patch("wms.order_scan_handlers.resolve_shipper_for_operation")
    def test_handle_order_action_create_order_with_org_roles_resolution_error(
        self,
        resolve_shipper_mock,
        resolve_binding_mock,
        _engine_mock,
    ):
        correspondent = Contact.objects.create(
            name="Corr Paris",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        create_form = self._create_order_form(
            shipper_contact=shipper,
            recipient_contact=recipient,
            destination_city="Paris",
            destination_country="France",
        )
        resolve_shipper_mock.return_value = None
        resolve_binding_mock.side_effect = OrganizationRoleResolutionError("binding failure")

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="create_order",
            select_form=_DummyForm(is_valid=False),
            create_form=create_form,
            line_form=_DummyForm(is_valid=False),
            selected_order=None,
        )

        self.assertIsNone(response)
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)
        self.assertIn((None, "binding failure"), create_form.errors)
        self.assertEqual(Order.objects.count(), 0)

    @mock.patch("wms.order_scan_handlers.messages.success")
    @mock.patch("wms.order_scan_handlers.create_shipment_for_order")
    @mock.patch("wms.order_scan_handlers.resolve_recipient_binding_for_operation")
    @mock.patch("wms.order_scan_handlers.resolve_shipper_for_operation")
    @mock.patch("wms.order_scan_handlers.is_org_roles_engine_enabled", return_value=True)
    def test_handle_order_action_create_order_with_org_roles_success(
        self,
        _engine_mock,
        resolve_shipper_mock,
        resolve_binding_mock,
        create_shipment_mock,
        _messages_success_mock,
    ):
        correspondent = Contact.objects.create(
            name="Corr Lyon",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Destination.objects.create(
            city="Lyon",
            iata_code="LYN",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Shipper Lyon",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient = Contact.objects.create(
            name="Recipient Lyon",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        create_form = self._create_order_form(
            shipper_contact=shipper,
            recipient_contact=recipient,
            shipper_name="",
            recipient_name="",
            destination_city="Lyon",
            destination_country="France",
        )
        resolve_shipper_mock.return_value = None
        resolve_binding_mock.return_value = None

        response, order_lines, remaining_total = handle_order_action(
            self._request(),
            action="create_order",
            select_form=_DummyForm(is_valid=False),
            create_form=create_form,
            line_form=_DummyForm(is_valid=False),
            selected_order=None,
        )

        self.assertEqual(response.status_code, 302)
        created_order = Order.objects.get()
        self.assertEqual(created_order.shipper_name, "Shipper Lyon")
        self.assertEqual(created_order.recipient_name, "Recipient Lyon")
        create_shipment_mock.assert_called_once_with(order=created_order)
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

    def test_handle_order_action_add_line_requires_selected_order_in_english(self):
        line_form = _DummyForm(
            is_valid=True,
            cleaned_data={"product_code": self.product.sku, "quantity": 1},
        )

        with translation.override("en"):
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
        self.assertIn((None, "Select an order."), line_form.errors)

    @mock.patch("wms.order_scan_handlers.messages.success")
    @mock.patch("wms.order_scan_handlers.create_shipment_for_order")
    def test_handle_order_action_create_order_translates_success_message_in_english(
        self,
        create_shipment_mock,
        success_mock,
    ):
        create_form = self._create_order_form()

        with translation.override("en"):
            response, order_lines, remaining_total = handle_order_action(
                self._request(),
                action="create_order",
                select_form=_DummyForm(is_valid=False),
                create_form=create_form,
                line_form=_DummyForm(is_valid=False),
                selected_order=None,
            )

        self.assertEqual(response.status_code, 302)
        created_order = Order.objects.get()
        create_shipment_mock.assert_called_once_with(order=created_order)
        success_mock.assert_called_once_with(
            mock.ANY,
            f"Order created: {created_order.reference or f'Order {created_order.id}'}",
        )
        self.assertIsNone(order_lines)
        self.assertIsNone(remaining_total)

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
