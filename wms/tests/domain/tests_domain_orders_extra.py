from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.domain.orders import (
    assign_ready_cartons_to_order,
    consume_reserved_stock,
    create_shipment_for_order,
    prepare_order,
    release_reserved_stock,
    reserve_stock_for_order,
)
from wms.domain.stock import StockError
from wms.models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    Location,
    MovementType,
    Order,
    OrderLine,
    OrderReservation,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    StockMovement,
    Warehouse,
)


class DomainOrdersExtraTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="domain-orders-user",
            password="pass1234",
        )
        self.warehouse = Warehouse.objects.create(name="Domain WH", code="DWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="DOMAIN-001",
            name="Domain Product",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.other_product = Product.objects.create(
            sku="DOMAIN-002",
            name="Other Product",
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )

    def _create_order(
        self,
        *,
        status=OrderStatus.DRAFT,
        quantity=5,
        reserved_quantity=0,
        prepared_quantity=0,
        product=None,
    ):
        order = Order.objects.create(
            status=status,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        line = OrderLine.objects.create(
            order=order,
            product=product or self.product,
            quantity=quantity,
            reserved_quantity=reserved_quantity,
            prepared_quantity=prepared_quantity,
        )
        return order, line

    def _create_lot(
        self,
        *,
        product,
        code,
        quantity_on_hand,
        quantity_reserved=0,
        expires_day=1,
    ):
        return ProductLot.objects.create(
            product=product,
            lot_code=code,
            expires_on=date(2026, 1, expires_day),
            received_on=date(2025, 12, min(28, expires_day)),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            location=self.location,
        )

    def _create_reservation(self, *, line, lot, quantity):
        return OrderReservation.objects.create(
            order_line=line,
            product_lot=lot,
            quantity=quantity,
        )

    def test_reserve_stock_rejects_cancelled_or_ready_orders(self):
        for status in (OrderStatus.CANCELLED, OrderStatus.READY):
            order, _line = self._create_order(status=status)
            with self.subTest(status=status):
                with self.assertRaisesMessage(StockError, "Commande non modifiable."):
                    reserve_stock_for_order(order=order)

    def test_create_shipment_for_order_returns_existing_shipment(self):
        order, _line = self._create_order(status=OrderStatus.DRAFT, quantity=1)
        shipment = create_shipment_for_order(order=order)

        same_shipment = create_shipment_for_order(order=order)

        self.assertEqual(same_shipment.id, shipment.id)

    def test_reserve_stock_skips_already_fully_reserved_line(self):
        order, line = self._create_order(
            status=OrderStatus.DRAFT,
            quantity=4,
            reserved_quantity=4,
        )

        reserve_stock_for_order(order=order)

        order.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.RESERVED)
        self.assertEqual(line.reserved_quantity, 4)
        self.assertEqual(line.reservations.count(), 0)

    def test_reserve_stock_raises_on_insufficient_available_quantity(self):
        order, _line = self._create_order(status=OrderStatus.DRAFT, quantity=3)
        self._create_lot(
            product=self.product,
            code="LOT-INSUF",
            quantity_on_hand=2,
            quantity_reserved=0,
            expires_day=1,
        )

        with self.assertRaisesMessage(StockError, "stock insuffisant"):
            reserve_stock_for_order(order=order)

    def test_reserve_stock_skips_empty_lot_and_breaks_when_done(self):
        order, line = self._create_order(status=OrderStatus.DRAFT, quantity=3)
        empty_lot = self._create_lot(
            product=self.product,
            code="LOT-EMPTY",
            quantity_on_hand=5,
            quantity_reserved=5,
            expires_day=1,
        )
        used_lot = self._create_lot(
            product=self.product,
            code="LOT-USED",
            quantity_on_hand=5,
            quantity_reserved=0,
            expires_day=2,
        )
        untouched_lot = self._create_lot(
            product=self.product,
            code="LOT-UNTOUCHED",
            quantity_on_hand=5,
            quantity_reserved=0,
            expires_day=3,
        )

        reserve_stock_for_order(order=order)

        line.refresh_from_db()
        empty_lot.refresh_from_db()
        used_lot.refresh_from_db()
        untouched_lot.refresh_from_db()
        self.assertEqual(line.reserved_quantity, 3)
        self.assertEqual(empty_lot.quantity_reserved, 5)
        self.assertEqual(used_lot.quantity_reserved, 3)
        self.assertEqual(untouched_lot.quantity_reserved, 0)
        self.assertEqual(line.reservations.count(), 1)

    def test_reserve_stock_skips_lot_with_no_available_quantity_from_fefo(self):
        order, line = self._create_order(status=OrderStatus.DRAFT, quantity=2)
        empty_lot = self._create_lot(
            product=self.product,
            code="LOT-FEFO-EMPTY",
            quantity_on_hand=5,
            quantity_reserved=5,
            expires_day=1,
        )
        used_lot = self._create_lot(
            product=self.product,
            code="LOT-FEFO-USED",
            quantity_on_hand=5,
            quantity_reserved=0,
            expires_day=2,
        )

        with mock.patch(
            "wms.domain.orders.fefo_lots",
            return_value=[empty_lot, used_lot],
        ):
            reserve_stock_for_order(order=order)

        line.refresh_from_db()
        empty_lot.refresh_from_db()
        used_lot.refresh_from_db()
        self.assertEqual(line.reserved_quantity, 2)
        self.assertEqual(empty_lot.quantity_reserved, 5)
        self.assertEqual(used_lot.quantity_reserved, 2)

    def test_release_reserved_stock_returns_immediately_for_non_positive_quantity(self):
        order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=3,
            reserved_quantity=2,
        )
        lot = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-0",
            quantity_on_hand=10,
            quantity_reserved=2,
            expires_day=1,
        )
        reservation = self._create_reservation(line=line, lot=lot, quantity=2)

        release_reserved_stock(line=line, quantity=0)

        reservation.refresh_from_db()
        line.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(reservation.quantity, 2)
        self.assertEqual(line.reserved_quantity, 2)
        self.assertEqual(lot.quantity_reserved, 2)

    def test_release_reserved_stock_deletes_updates_and_clamps_negative_lot_reserved(self):
        order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=5,
            reserved_quantity=3,
        )
        lot_1 = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-1",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=1,
        )
        lot_2 = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-2",
            quantity_on_hand=10,
            quantity_reserved=2,
            expires_day=2,
        )
        self._create_reservation(line=line, lot=lot_1, quantity=2)
        res_2 = self._create_reservation(line=line, lot=lot_2, quantity=2)

        release_reserved_stock(line=line, quantity=3)

        line.refresh_from_db()
        lot_1.refresh_from_db()
        lot_2.refresh_from_db()
        self.assertEqual(line.reserved_quantity, 0)
        self.assertFalse(OrderReservation.objects.filter(product_lot=lot_1).exists())
        res_2.refresh_from_db()
        self.assertEqual(res_2.quantity, 1)
        self.assertEqual(lot_1.quantity_reserved, 0)
        self.assertEqual(lot_2.quantity_reserved, 1)

    def test_release_reserved_stock_stops_iterating_once_quantity_is_fully_released(self):
        _order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=4,
            reserved_quantity=2,
        )
        lot_1 = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-BREAK-1",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=1,
        )
        lot_2 = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-BREAK-2",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=2,
        )
        lot_3 = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-BREAK-3",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=3,
        )
        self._create_reservation(line=line, lot=lot_1, quantity=1)
        self._create_reservation(line=line, lot=lot_2, quantity=1)
        res_3 = self._create_reservation(line=line, lot=lot_3, quantity=1)

        release_reserved_stock(line=line, quantity=2)

        line.refresh_from_db()
        res_3.refresh_from_db()
        lot_3.refresh_from_db()
        self.assertEqual(line.reserved_quantity, 0)
        self.assertEqual(res_3.quantity, 1)
        self.assertEqual(lot_3.quantity_reserved, 1)

    def test_release_reserved_stock_raises_when_requested_quantity_is_too_high(self):
        order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=4,
            reserved_quantity=1,
        )
        lot = self._create_lot(
            product=self.product,
            code="LOT-RELEASE-ERR",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=1,
        )
        self._create_reservation(line=line, lot=lot, quantity=1)

        with self.assertRaisesMessage(StockError, "Réservation insuffisante pour libérer."):
            release_reserved_stock(line=line, quantity=3)

        line.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(line.reserved_quantity, 1)
        self.assertEqual(lot.quantity_reserved, 1)
        self.assertEqual(line.reservations.count(), 1)

    def test_consume_reserved_stock_rejects_non_positive_quantity(self):
        _order, line = self._create_order(status=OrderStatus.RESERVED, quantity=2, reserved_quantity=2)
        with self.assertRaisesMessage(StockError, "Quantité invalide."):
            consume_reserved_stock(
                user=self.user,
                line=line,
                quantity=0,
                movement_type=MovementType.OUT,
            )

    def test_consume_reserved_stock_consumes_across_lots_and_updates_line(self):
        _order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=6,
            reserved_quantity=6,
        )
        lot_1 = self._create_lot(
            product=self.product,
            code="LOT-CONSUME-1",
            quantity_on_hand=10,
            quantity_reserved=2,
            expires_day=1,
        )
        lot_2 = self._create_lot(
            product=self.product,
            code="LOT-CONSUME-2",
            quantity_on_hand=10,
            quantity_reserved=3,
            expires_day=2,
        )
        lot_3 = self._create_lot(
            product=self.product,
            code="LOT-CONSUME-3",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=3,
        )
        self._create_reservation(line=line, lot=lot_1, quantity=2)
        res_2 = self._create_reservation(line=line, lot=lot_2, quantity=3)
        res_3 = self._create_reservation(line=line, lot=lot_3, quantity=1)

        consumed = consume_reserved_stock(
            user=self.user,
            line=line,
            quantity=4,
            movement_type=MovementType.OUT,
        )

        line.refresh_from_db()
        lot_1.refresh_from_db()
        lot_2.refresh_from_db()
        lot_3.refresh_from_db()
        res_2.refresh_from_db()
        res_3.refresh_from_db()

        self.assertEqual([entry.quantity for entry in consumed], [2, 2])
        self.assertEqual(line.reserved_quantity, 2)
        self.assertEqual(line.prepared_quantity, 4)
        self.assertEqual(lot_1.quantity_on_hand, 8)
        self.assertEqual(lot_1.quantity_reserved, 0)
        self.assertEqual(lot_2.quantity_on_hand, 8)
        self.assertEqual(lot_2.quantity_reserved, 1)
        self.assertEqual(lot_3.quantity_on_hand, 10)
        self.assertEqual(lot_3.quantity_reserved, 1)
        self.assertEqual(res_2.quantity, 1)
        self.assertEqual(res_3.quantity, 1)
        self.assertEqual(StockMovement.objects.count(), 2)

    def test_consume_reserved_stock_skips_zero_reservation_and_raises_if_insufficient(self):
        _order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=2,
            reserved_quantity=2,
        )
        lot_1 = self._create_lot(
            product=self.product,
            code="LOT-CONSUME-ZERO",
            quantity_on_hand=10,
            quantity_reserved=0,
            expires_day=1,
        )
        lot_2 = self._create_lot(
            product=self.product,
            code="LOT-CONSUME-ERR",
            quantity_on_hand=10,
            quantity_reserved=1,
            expires_day=2,
        )
        res_zero = self._create_reservation(line=line, lot=lot_1, quantity=1)
        OrderReservation.objects.filter(pk=res_zero.pk).update(quantity=0)
        self._create_reservation(line=line, lot=lot_2, quantity=1)

        with self.assertRaisesMessage(
            StockError,
            "Reservation insuffisante pour consommation.",
        ):
            consume_reserved_stock(
                user=self.user,
                line=line,
                quantity=2,
                movement_type=MovementType.OUT,
            )

        line.refresh_from_db()
        lot_2.refresh_from_db()
        self.assertEqual(line.reserved_quantity, 2)
        self.assertEqual(line.prepared_quantity, 0)
        self.assertEqual(lot_2.quantity_on_hand, 10)
        self.assertEqual(lot_2.quantity_reserved, 1)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_assign_ready_cartons_to_order_handles_all_skip_paths_and_assigns_matching_one(self):
        order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=5,
            reserved_quantity=5,
        )
        lot_main = self._create_lot(
            product=self.product,
            code="LOT-ASSIGN-MAIN",
            quantity_on_hand=20,
            quantity_reserved=0,
            expires_day=1,
        )
        lot_other = self._create_lot(
            product=self.other_product,
            code="LOT-ASSIGN-OTHER",
            quantity_on_hand=20,
            quantity_reserved=0,
            expires_day=2,
        )

        carton_empty = Carton.objects.create(code="C01", status=CartonStatus.PACKED)
        carton_multi = Carton.objects.create(code="C02", status=CartonStatus.PACKED)
        CartonItem.objects.create(carton=carton_multi, product_lot=lot_main, quantity=1)
        CartonItem.objects.create(carton=carton_multi, product_lot=lot_other, quantity=1)

        carton_other = Carton.objects.create(code="C03", status=CartonStatus.PACKED)
        CartonItem.objects.create(carton=carton_other, product_lot=lot_other, quantity=1)

        carton_zero = Carton.objects.create(code="C04", status=CartonStatus.PACKED)
        CartonItem.objects.create(carton=carton_zero, product_lot=lot_main, quantity=0)

        carton_too_large = Carton.objects.create(code="C05", status=CartonStatus.PACKED)
        CartonItem.objects.create(carton=carton_too_large, product_lot=lot_main, quantity=6)

        carton_ok = Carton.objects.create(code="C06", status=CartonStatus.PACKED)
        CartonItem.objects.create(carton=carton_ok, product_lot=lot_main, quantity=2)

        with mock.patch("wms.domain.orders.release_reserved_stock") as release_mock:
            assigned = assign_ready_cartons_to_order(order=order)

        order.refresh_from_db()
        line.refresh_from_db()
        carton_empty.refresh_from_db()
        carton_multi.refresh_from_db()
        carton_other.refresh_from_db()
        carton_zero.refresh_from_db()
        carton_too_large.refresh_from_db()
        carton_ok.refresh_from_db()

        self.assertEqual(assigned, 1)
        self.assertIsNotNone(order.shipment_id)
        self.assertEqual(line.prepared_quantity, 2)
        self.assertEqual(line.reserved_quantity, 5)
        release_mock.assert_called_once()
        call_kwargs = release_mock.call_args.kwargs
        self.assertEqual(call_kwargs["line"].id, line.id)
        self.assertEqual(call_kwargs["quantity"], 2)
        self.assertIsNone(carton_empty.shipment_id)
        self.assertIsNone(carton_multi.shipment_id)
        self.assertIsNone(carton_other.shipment_id)
        self.assertIsNone(carton_zero.shipment_id)
        self.assertIsNone(carton_too_large.shipment_id)
        self.assertEqual(carton_ok.shipment_id, order.shipment_id)

    def test_prepare_order_rejects_status_other_than_reserved_or_preparing(self):
        order, _line = self._create_order(status=OrderStatus.DRAFT, quantity=1)
        with self.assertRaisesMessage(StockError, "Commande non réservée."):
            prepare_order(user=self.user, order=order)

    def test_prepare_order_requires_carton_format_when_lines_remain(self):
        order, _line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=1,
            reserved_quantity=1,
        )
        with mock.patch("wms.domain.orders.assign_ready_cartons_to_order", return_value=0):
            with self.assertRaisesMessage(StockError, "Format de carton manquant."):
                prepare_order(user=self.user, order=order)

    def test_prepare_order_falls_back_to_first_carton_format_and_sets_preparing(self):
        order, line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=2,
            reserved_quantity=0,
        )
        carton_format = CartonFormat.objects.create(
            name="Fallback",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
            is_default=False,
        )
        with mock.patch("wms.domain.orders.assign_ready_cartons_to_order", return_value=0):
            with mock.patch(
                "wms.domain.orders.build_packing_bins",
                return_value=([], [], []),
            ) as bins_mock:
                assigned = prepare_order(user=self.user, order=order)

        order.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(assigned, 0)
        self.assertIsNotNone(order.shipment_id)
        self.assertEqual(order.status, OrderStatus.PREPARING)
        self.assertEqual(line.remaining_quantity, 2)

        _line_items, carton_size = bins_mock.call_args.args
        self.assertEqual(carton_size["length_cm"], carton_format.length_cm)
        self.assertEqual(carton_size["width_cm"], carton_format.width_cm)
        self.assertEqual(carton_size["height_cm"], carton_format.height_cm)
        self.assertEqual(carton_size["max_weight_g"], carton_format.max_weight_g)

    def test_prepare_order_raises_first_packing_error(self):
        order, _line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=1,
            reserved_quantity=1,
        )
        CartonFormat.objects.create(
            name="Default",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
            is_default=True,
        )
        with mock.patch("wms.domain.orders.assign_ready_cartons_to_order", return_value=0):
            with mock.patch(
                "wms.domain.orders.build_packing_bins",
                return_value=(None, ["planner failure"], []),
            ):
                with self.assertRaisesMessage(StockError, "planner failure"):
                    prepare_order(user=self.user, order=order)

    def test_prepare_order_raises_when_packing_bin_product_is_not_in_order(self):
        order, _line = self._create_order(
            status=OrderStatus.RESERVED,
            quantity=1,
            reserved_quantity=1,
        )
        CartonFormat.objects.create(
            name="Default",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
            is_default=True,
        )
        bins = [
            {
                "items": {
                    self.other_product.id: {
                        "product": self.other_product,
                        "quantity": 1,
                    }
                }
            }
        ]
        with mock.patch("wms.domain.orders.assign_ready_cartons_to_order", return_value=0):
            with mock.patch(
                "wms.domain.orders.build_packing_bins",
                return_value=(bins, [], []),
            ):
                with self.assertRaisesMessage(StockError, "Produit manquant dans la commande."):
                    prepare_order(user=self.user, order=order)


class _FakeLot:
    def __init__(self, *, quantity_reserved, quantity_on_hand=0):
        self.quantity_reserved = quantity_reserved
        self.quantity_on_hand = quantity_on_hand
        self.location = object()

    def save(self, update_fields=None):
        return None


class _FakeReservation:
    def __init__(self, *, quantity, lot):
        self.quantity = quantity
        self.product_lot = lot

    def delete(self):
        self.quantity = 0

    def save(self, update_fields=None):
        return None


class _FakeReservationsQuery:
    def __init__(self, reservations):
        self._reservations = reservations
        self.select_for_update_called = False

    def order_by(self, *_args):
        return self

    def select_for_update(self):
        self.select_for_update_called = True
        return self

    def __iter__(self):
        return iter(self._reservations)


class _FakeReservationsManager:
    def __init__(self, reservations):
        self.query = _FakeReservationsQuery(reservations)

    def select_related(self, *_args):
        return self.query


class _FakeLine:
    def __init__(self, *, reserved_quantity, prepared_quantity=0, reservations=None):
        self.reserved_quantity = reserved_quantity
        self.prepared_quantity = prepared_quantity
        self.reservations = _FakeReservationsManager(reservations or [])
        self.product = object()

    def save(self, update_fields=None):
        return None


class DomainOrdersSelectForUpdateBranchTests(TestCase):
    def test_release_reserved_stock_uses_select_for_update_when_supported(self):
        lot = _FakeLot(quantity_reserved=1)
        reservation = _FakeReservation(quantity=1, lot=lot)
        line = _FakeLine(reserved_quantity=1, reservations=[reservation])

        with mock.patch("wms.domain.orders.connection.features.has_select_for_update", True):
            release_reserved_stock(line=line, quantity=1)

        self.assertTrue(line.reservations.query.select_for_update_called)

    def test_consume_reserved_stock_uses_select_for_update_when_supported(self):
        lot = _FakeLot(quantity_reserved=1, quantity_on_hand=2)
        reservation = _FakeReservation(quantity=1, lot=lot)
        line = _FakeLine(reserved_quantity=1, reservations=[reservation])

        with mock.patch("wms.domain.orders.connection.features.has_select_for_update", True):
            with mock.patch("wms.domain.orders.StockMovement.objects.create"):
                consume_reserved_stock(
                    user=object(),
                    line=line,
                    quantity=1,
                    movement_type=MovementType.OUT,
                )

        self.assertTrue(line.reservations.query.select_for_update_called)
