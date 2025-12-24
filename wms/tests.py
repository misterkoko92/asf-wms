from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import (
    Carton,
    CartonFormat,
    CartonStatus,
    Location,
    MovementType,
    Order,
    OrderLine,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptLine,
    ReceiptStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
    Warehouse,
)
from .services import (
    StockError,
    consume_stock,
    pack_carton,
    prepare_order,
    receive_receipt_line,
    reserve_stock_for_order,
)


class StockFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester", password="pass1234"
        )
        self.warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="A", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            name="Test product",
            brand="Test",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )

    def _create_lot(self, *, quantity, expires_on):
        return ProductLot.objects.create(
            product=self.product,
            lot_code="LOT",
            expires_on=expires_on,
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity,
            location=self.location,
            storage_conditions="dry",
        )

    def test_consume_stock_follows_fefo(self):
        lot_early = self._create_lot(quantity=5, expires_on=date(2026, 1, 10))
        lot_late = self._create_lot(quantity=10, expires_on=date(2026, 2, 10))

        consume_stock(
            user=self.user,
            product=self.product,
            quantity=7,
            movement_type=MovementType.OUT,
        )

        lot_early.refresh_from_db()
        lot_late.refresh_from_db()
        self.assertEqual(lot_early.quantity_on_hand, 0)
        self.assertEqual(lot_late.quantity_on_hand, 8)

    def test_pack_carton_precondition(self):
        self._create_lot(quantity=20, expires_on=date(2026, 1, 10))
        carton = pack_carton(
            user=self.user,
            product=self.product,
            quantity=5,
            carton=None,
            carton_code=None,
            shipment=None,
            current_location=self.location,
        )
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PICKING)
        movement_types = set(
            StockMovement.objects.filter(related_carton=carton).values_list(
                "movement_type", flat=True
            )
        )
        self.assertEqual(movement_types, {MovementType.PRECONDITION})

    def test_pack_carton_for_shipment(self):
        self._create_lot(quantity=20, expires_on=date(2026, 1, 10))
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=self.user,
        )
        carton = pack_carton(
            user=self.user,
            product=self.product,
            quantity=4,
            carton=None,
            carton_code=None,
            shipment=shipment,
            current_location=self.location,
        )
        carton.refresh_from_db()
        self.assertEqual(carton.status, CartonStatus.PICKING)
        self.assertEqual(carton.shipment_id, shipment.id)
        movement_types = set(
            StockMovement.objects.filter(related_carton=carton).values_list(
                "movement_type", flat=True
            )
        )
        self.assertEqual(movement_types, {MovementType.OUT})

    def test_pack_carton_rolls_back_on_insufficient_stock(self):
        with self.assertRaises(StockError):
            pack_carton(
                user=self.user,
                product=self.product,
                quantity=1,
                carton=None,
                carton_code=None,
                shipment=None,
                current_location=self.location,
            )
        self.assertEqual(Carton.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)


class ShipmentReferenceTests(TestCase):
    def _create_shipment(self, user):
        return Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=user,
        )

    def test_shipment_reference_sequence_increments(self):
        user = get_user_model().objects.create_user(
            username="sequser", password="pass1234"
        )
        with mock.patch("wms.models.timezone.localdate", return_value=date(2026, 1, 2)):
            shipment_1 = self._create_shipment(user)
            shipment_2 = self._create_shipment(user)
        self.assertEqual(shipment_1.reference, "260001")
        self.assertEqual(shipment_2.reference, "260002")

    def test_shipment_reference_resets_each_year(self):
        user = get_user_model().objects.create_user(
            username="sequser2", password="pass1234"
        )
        with mock.patch("wms.models.timezone.localdate", return_value=date(2027, 1, 2)):
            shipment = self._create_shipment(user)
        self.assertEqual(shipment.reference, "270001")


class ModelValidationTests(TestCase):
    def test_product_validators_reject_negative_values(self):
        product = Product(
            sku="TEST-NEG",
            name="Bad product",
            weight_g=-1,
            volume_cm3=-10,
            length_cm=-1,
            width_cm=-1,
            height_cm=-1,
            qr_code_image="qr_codes/test.png",
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_carton_format_validators_reject_negative_values(self):
        carton_format = CartonFormat(
            name="Bad format",
            length_cm=-1,
            width_cm=-1,
            height_cm=-1,
            max_weight_g=-5,
        )
        with self.assertRaises(ValidationError):
            carton_format.full_clean()


class ReceiptTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="receipt-user", password="pass1234"
        )
        self.warehouse = Warehouse.objects.create(name="Reception", code="REC")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="R", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            name="Receipt product",
            brand="Brand",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.receipt = Receipt.objects.create(
            receipt_type="donation",
            status=ReceiptStatus.DRAFT,
            received_on=date(2025, 12, 20),
            warehouse=self.warehouse,
            created_by=self.user,
        )

    def test_receive_receipt_line_creates_lot(self):
        line = ReceiptLine.objects.create(
            receipt=self.receipt,
            product=self.product,
            quantity=12,
            lot_code="LOT-R1",
            expires_on=date(2026, 5, 1),
            location=self.location,
        )
        lot = receive_receipt_line(user=self.user, line=line)
        line.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertEqual(line.received_lot_id, lot.id)
        self.assertEqual(line.received_by_id, self.user.id)
        self.assertEqual(self.receipt.status, ReceiptStatus.RECEIVED)


class OrderReservationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="order-user", password="pass1234"
        )
        self.warehouse = Warehouse.objects.create(name="Stock", code="STK")
        self.location = Location.objects.create(
            warehouse=self.warehouse, zone="S", aisle="01", shelf="001"
        )
        self.product = Product.objects.create(
            name="Order product",
            brand="Brand",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )
        self.lot = ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-ORD",
            expires_on=date(2026, 2, 1),
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=self.location,
        )
        CartonFormat.objects.create(
            name="Carton standard",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )

    def test_reserve_stock_for_order(self):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=8)
        reserve_stock_for_order(order=order)
        self.lot.refresh_from_db()
        order.refresh_from_db()
        line = order.lines.first()
        self.assertEqual(order.status, OrderStatus.RESERVED)
        self.assertEqual(line.reserved_quantity, 8)
        self.assertEqual(self.lot.quantity_reserved, 8)

    def test_prepare_order_consumes_reserved(self):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=6)
        reserve_stock_for_order(order=order)
        prepare_order(user=self.user, order=order)
        self.lot.refresh_from_db()
        line = order.lines.first()
        self.assertEqual(line.prepared_quantity, 6)
        self.assertEqual(line.reserved_quantity, 0)
        self.assertEqual(self.lot.quantity_reserved, 0)
