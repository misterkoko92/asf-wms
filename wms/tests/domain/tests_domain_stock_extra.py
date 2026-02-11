from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from wms.domain.stock import (
    _carton_date_str,
    _dominant_type_code,
    _get_optional,
    _get_required,
    _next_carton_sequence,
    _normalize_type_code,
    _prepare_carton,
    _root_category_name,
    adjust_stock,
    consume_stock,
    ensure_carton_code,
    fefo_lots,
    pack_carton_from_input,
    receive_receipt_line,
    receive_stock,
    receive_stock_from_input,
    transfer_stock,
    unpack_carton,
    StockError,
)
from wms.domain.dto import PackCartonInput, ReceiveStockInput
from wms.models import (
    Carton,
    CartonItem,
    CartonStatus,
    Location,
    MovementType,
    Product,
    ProductCategory,
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


class DomainStockExtraTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="domain-stock-user",
            password="pass1234",
        )
        self.warehouse = Warehouse.objects.create(name="Stock WH", code="SWH")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.other_location = Location.objects.create(
            warehouse=self.warehouse,
            zone="B",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="STOCK-001",
            name="Stock Product",
            weight_g=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )

    def _create_product(self, *, sku, name, category=None, weight_g=100):
        return Product.objects.create(
            sku=sku,
            name=name,
            category=category,
            weight_g=weight_g,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )

    def _create_lot(
        self,
        *,
        product=None,
        code="LOT-1",
        quantity_on_hand=10,
        quantity_reserved=0,
        expires_day=1,
    ):
        return ProductLot.objects.create(
            product=product or self.product,
            lot_code=code,
            expires_on=date(2026, 1, expires_day),
            received_on=date(2025, 12, min(28, expires_day)),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            location=self.location,
        )

    def _create_receipt(self, *, status=ReceiptStatus.DRAFT):
        return Receipt.objects.create(
            receipt_type="donation",
            status=status,
            received_on=date(2025, 12, 20),
            warehouse=self.warehouse,
            created_by=self.user,
        )

    def _create_shipment(self, *, status=ShipmentStatus.DRAFT):
        return Shipment.objects.create(
            status=status,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_carton_date_str_uses_today_when_created_at_missing(self):
        carton = SimpleNamespace(created_at=None)
        with mock.patch("wms.domain.stock.timezone.localdate", return_value=date(2026, 2, 3)):
            self.assertEqual(_carton_date_str(carton), "20260203")

    def test_normalize_type_code_handles_empty_multiword_and_padding(self):
        self.assertEqual(_normalize_type_code(""), "XX")
        self.assertEqual(_normalize_type_code("Medical Kit"), "MK")
        self.assertEqual(_normalize_type_code("A"), "AX")

    def test_root_category_name_walks_up_to_parent(self):
        root = ProductCategory.objects.create(name="Root")
        child = ProductCategory.objects.create(name="Child", parent=root)
        product = self._create_product(
            sku="STOCK-ROOT",
            name="Root Product",
            category=child,
        )
        self.assertEqual(_root_category_name(product), "ROOT")

    def test_dominant_type_code_handles_empty_carton_and_qty_fallback(self):
        empty_carton = Carton.objects.create(code="CT-EMPTY", status=CartonStatus.DRAFT)
        self.assertEqual(_dominant_type_code(empty_carton), "XX")

        cat_alpha = ProductCategory.objects.create(name="Alpha")
        cat_beta = ProductCategory.objects.create(name="Beta")
        product_a = self._create_product(
            sku="STOCK-A",
            name="A Product",
            category=cat_alpha,
            weight_g=0,
        )
        product_b = self._create_product(
            sku="STOCK-B",
            name="B Product",
            category=cat_beta,
            weight_g=0,
        )
        lot_a = self._create_lot(product=product_a, code="LOT-A")
        lot_b = self._create_lot(product=product_b, code="LOT-B")
        carton = Carton.objects.create(code="CT-QTY", status=CartonStatus.DRAFT)
        CartonItem.objects.create(carton=carton, product_lot=lot_a, quantity=1)
        CartonItem.objects.create(carton=carton, product_lot=lot_b, quantity=3)

        self.assertEqual(_dominant_type_code(carton), "BE")

    def test_next_carton_sequence_ignorés_invalid_code_and_increments(self):
        Carton.objects.create(code="XX-20260101-2", status=CartonStatus.DRAFT)
        Carton.objects.create(code="BAD-CODE", status=CartonStatus.DRAFT)
        Carton.objects.create(code="XX-20260102-7", status=CartonStatus.DRAFT)

        self.assertEqual(_next_carton_sequence("20260101"), 3)

    def test_next_carton_sequence_ignorés_non_integer_seq_values(self):
        fake_match = SimpleNamespace(
            group=lambda key: {"date": "20260101", "seq": "NaN"}[key]
        )
        fake_regex = SimpleNamespace(match=lambda _code: fake_match)
        with mock.patch("wms.domain.stock.CARTON_CODE_RE", fake_regex):
            Carton.objects.create(code="XX-20260101-2", status=CartonStatus.DRAFT)
            self.assertEqual(_next_carton_sequence("20260101"), 1)

    def test_fefo_lots_can_set_select_for_update_flag(self):
        self._create_lot(code="LOT-FEFO")

        with mock.patch("wms.domain.stock.connection.features.has_select_for_update", True):
            queryset = fefo_lots(self.product, for_update=True)

        self.assertTrue(queryset.query.select_for_update)

    def test_get_required_and_optional_validation_paths(self):
        with self.assertRaisesMessage(StockError, "Produit requis."):
            _get_required(Product, None, "Produit")
        with self.assertRaisesMessage(StockError, "Produit introuvable."):
            _get_required(Product, 999999, "Produit")

        self.assertIsNone(_get_optional(Product, None, "Produit"))
        with self.assertRaisesMessage(StockError, "Produit introuvable."):
            _get_optional(Product, 999999, "Produit")

    def test_receive_stock_rejects_non_positive_quantity(self):
        with self.assertRaisesMessage(StockError, "Quantité invalide."):
            receive_stock(
                user=self.user,
                product=self.product,
                quantity=0,
                location=self.location,
            )

    def test_receive_receipt_line_rejects_already_processed_line(self):
        receipt = self._create_receipt(status=ReceiptStatus.DRAFT)
        lot = self._create_lot(code="LOT-REC-1")
        line = ReceiptLine.objects.create(
            receipt=receipt,
            product=self.product,
            quantity=1,
            location=self.location,
            received_lot=lot,
        )

        with self.assertRaisesMessage(StockError, "Ligne de réception déjà traitée."):
            receive_receipt_line(user=self.user, line=line)

    def test_receive_receipt_line_rejects_cancelled_receipt(self):
        receipt = self._create_receipt(status=ReceiptStatus.CANCELLED)
        line = ReceiptLine.objects.create(
            receipt=receipt,
            product=self.product,
            quantity=1,
            location=self.location,
        )

        with self.assertRaisesMessage(StockError, "Réception annulée."):
            receive_receipt_line(user=self.user, line=line)

    def test_receive_receipt_line_requires_location_when_missing_everywhere(self):
        product = Product.objects.create(
            sku="STOCK-NOLOC",
            name="No Loc Product",
            default_location=None,
            qr_code_image="qr_codes/test.png",
        )
        receipt = self._create_receipt(status=ReceiptStatus.DRAFT)
        line = ReceiptLine.objects.create(
            receipt=receipt,
            product=product,
            quantity=1,
            location=None,
        )

        with self.assertRaisesMessage(StockError, "Emplacement requis pour réception."):
            receive_receipt_line(user=self.user, line=line)

    def test_adjust_stock_validation_errors(self):
        lot = self._create_lot(code="LOT-ADJ-ERR", quantity_on_hand=5, quantity_reserved=3)

        with self.assertRaisesMessage(StockError, "Quantité nulle."):
            adjust_stock(user=self.user, lot=lot, delta=0, reason_code="", reason_notes="")
        with self.assertRaisesMessage(StockError, "Stock insuffisant pour ajustement."):
            adjust_stock(user=self.user, lot=lot, delta=-6, reason_code="", reason_notes="")
        with self.assertRaisesMessage(StockError, "Ajustement impossible: stock réservé."):
            adjust_stock(user=self.user, lot=lot, delta=-3, reason_code="", reason_notes="")

    def test_adjust_stock_creates_movement_for_negative_and_positive_delta(self):
        lot = self._create_lot(code="LOT-ADJ-OK", quantity_on_hand=8, quantity_reserved=2)

        adjust_stock(user=self.user, lot=lot, delta=-1, reason_code="damage", reason_notes="broken")
        adjust_stock(user=self.user, lot=lot, delta=2, reason_code="count", reason_notes="recount")

        lot.refresh_from_db()
        self.assertEqual(lot.quantity_on_hand, 9)
        movements = list(
            StockMovement.objects.filter(product_lot=lot).order_by("created_at")
        )
        self.assertEqual(len(movements), 2)
        self.assertEqual(movements[0].from_location_id, self.location.id)
        self.assertIsNone(movements[0].to_location_id)
        self.assertIsNone(movements[1].from_location_id)
        self.assertEqual(movements[1].to_location_id, self.location.id)

    def test_transfer_stock_rejects_same_location_and_moves_lot(self):
        lot = self._create_lot(code="LOT-TRANSFER", quantity_on_hand=6)

        with self.assertRaisesMessage(StockError, "Le lot est déjà à cet emplacement."):
            transfer_stock(user=self.user, lot=lot, to_location=self.location)

        transfer_stock(user=self.user, lot=lot, to_location=self.other_location)

        lot.refresh_from_db()
        self.assertEqual(lot.location_id, self.other_location.id)
        movement = StockMovement.objects.get(product_lot=lot, movement_type=MovementType.TRANSFER)
        self.assertEqual(movement.from_location_id, self.location.id)
        self.assertEqual(movement.to_location_id, self.other_location.id)

    def test_consume_stock_rejects_non_positive_quantity(self):
        with self.assertRaisesMessage(StockError, "Quantité invalide."):
            consume_stock(
                user=self.user,
                product=self.product,
                quantity=0,
                movement_type=MovementType.OUT,
            )

    def test_consume_stock_skips_empty_lot_and_breaks_when_remaining_is_zero(self):
        lot_empty = self._create_lot(
            code="LOT-CONSUME-EMPTY",
            quantity_on_hand=5,
            quantity_reserved=5,
            expires_day=1,
        )
        lot_used = self._create_lot(
            code="LOT-CONSUME-USED",
            quantity_on_hand=5,
            quantity_reserved=0,
            expires_day=2,
        )
        lot_untouched = self._create_lot(
            code="LOT-CONSUME-UNTOUCHED",
            quantity_on_hand=5,
            quantity_reserved=0,
            expires_day=3,
        )
        with mock.patch(
            "wms.domain.stock.fefo_lots",
            return_value=[lot_empty, lot_used, lot_untouched],
        ):
            consumed = consume_stock(
                user=self.user,
                product=self.product,
                quantity=2,
                movement_type=MovementType.OUT,
            )

        lot_empty.refresh_from_db()
        lot_used.refresh_from_db()
        lot_untouched.refresh_from_db()
        self.assertEqual([entry.quantity for entry in consumed], [2])
        self.assertEqual(lot_empty.quantity_on_hand, 5)
        self.assertEqual(lot_used.quantity_on_hand, 3)
        self.assertEqual(lot_untouched.quantity_on_hand, 5)

    def test_unpack_carton_rejects_shipped_and_empty_cartons(self):
        shipped_carton = Carton.objects.create(code="CT-SHIPPED", status=CartonStatus.SHIPPED)
        empty_carton = Carton.objects.create(code="CT-EMPTY-2", status=CartonStatus.DRAFT)

        with self.assertRaisesMessage(StockError, "Impossible de modifier un carton expédié."):
            unpack_carton(user=self.user, carton=shipped_carton)
        with self.assertRaisesMessage(StockError, "Carton vide."):
            unpack_carton(user=self.user, carton=empty_carton)

    def test_unpack_carton_restores_stock_and_resets_carton(self):
        lot = self._create_lot(code="LOT-UNPACK", quantity_on_hand=4)
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = Carton.objects.create(
            code="CT-UNPACK",
            status=CartonStatus.PICKING,
            shipment=shipment,
        )
        CartonItem.objects.create(carton=carton, product_lot=lot, quantity=3)

        unpack_carton(user=self.user, carton=carton)

        lot.refresh_from_db()
        carton.refresh_from_db()
        self.assertEqual(lot.quantity_on_hand, 7)
        self.assertEqual(carton.status, CartonStatus.DRAFT)
        self.assertIsNone(carton.shipment_id)
        self.assertEqual(carton.cartonitem_set.count(), 0)
        movement = StockMovement.objects.get(
            movement_type=MovementType.UNPACK,
            product_lot=lot,
            related_carton=carton,
        )
        self.assertEqual(movement.related_shipment_id, shipment.id)

    def test_prepare_carton_finds_existing_by_code_and_updates_fields(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = Carton.objects.create(
            code="CT-BY-CODE",
            status=CartonStatus.DRAFT,
            current_location=self.location,
        )

        updated = _prepare_carton(
            user=self.user,
            carton=None,
            shipment=shipment,
            current_location=self.other_location,
            carton_code="CT-BY-CODE",
        )

        updated.refresh_from_db()
        self.assertEqual(updated.id, carton.id)
        self.assertEqual(updated.shipment_id, shipment.id)
        self.assertEqual(updated.current_location_id, self.other_location.id)
        self.assertTrue(getattr(updated, "_manual_code", False))

    def test_prepare_carton_rejects_shipped_carton_shipment_or_conflict(self):
        shipped_carton = Carton.objects.create(code="CT-SHIPPED-2", status=CartonStatus.SHIPPED)
        with self.assertRaisesMessage(StockError, "Impossible de modifier un carton expédié."):
            _prepare_carton(user=self.user, carton=shipped_carton, shipment=None)

        shipped_shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)
        with self.assertRaisesMessage(
            StockError,
            "Impossible de modifier une expédition expédiée ou livrée.",
        ):
            _prepare_carton(user=self.user, carton=None, shipment=shipped_shipment)

        shipment_a = self._create_shipment(status=ShipmentStatus.DRAFT)
        shipment_b = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = Carton.objects.create(
            code="CT-CONFLICT",
            status=CartonStatus.DRAFT,
            shipment=shipment_a,
        )
        with self.assertRaisesMessage(StockError, "Carton déjà lié à une autre expédition."):
            _prepare_carton(user=self.user, carton=carton, shipment=shipment_b)

    def test_prepare_carton_retries_when_generated_code_is_not_unique(self):
        created_carton = Carton.objects.create(code="XX-20260101-2", status=CartonStatus.DRAFT)
        with mock.patch("wms.domain.stock.timezone.localdate", return_value=date(2026, 1, 1)):
            with mock.patch(
                "wms.domain.stock.generate_carton_code",
                side_effect=["XX-20260101-1", "XX-20260101-2"],
            ):
                with mock.patch(
                    "wms.domain.stock.Carton.objects.create",
                    side_effect=[IntegrityError("duplicate"), created_carton],
                ):
                    carton = _prepare_carton(
                        user=self.user,
                        carton=None,
                        shipment=None,
                        current_location=self.location,
                    )

        self.assertEqual(carton.code, "XX-20260101-2")

    def test_prepare_carton_with_manual_code_marks_carton_or_raises_conflict(self):
        with mock.patch("wms.domain.stock.Carton.objects.filter") as filter_mock:
            filter_mock.return_value.first.return_value = None
            with mock.patch(
                "wms.domain.stock.Carton.objects.create",
                side_effect=IntegrityError("duplicate"),
            ):
                with self.assertRaises(IntegrityError):
                    _prepare_carton(
                        user=self.user,
                        carton=None,
                        shipment=None,
                        carton_code="CT-MANUAL",
                        current_location=self.location,
                    )

        carton = _prepare_carton(
            user=self.user,
            carton=None,
            shipment=None,
            carton_code="CT-MANUAL-2",
            current_location=self.location,
        )
        self.assertEqual(carton.code, "CT-MANUAL-2")
        self.assertTrue(getattr(carton, "_manual_code", False))

    def test_ensure_carton_code_skips_manual_and_non_automatic_codes(self):
        manual_carton = Carton.objects.create(code="CT-MANUAL-SKIP", status=CartonStatus.DRAFT)
        manual_carton._manual_code = True
        ensure_carton_code(manual_carton)
        manual_carton.refresh_from_db()
        self.assertEqual(manual_carton.code, "CT-MANUAL-SKIP")

        non_auto = Carton.objects.create(code="CUSTOM-CODE", status=CartonStatus.DRAFT)
        ensure_carton_code(non_auto)
        non_auto.refresh_from_db()
        self.assertEqual(non_auto.code, "CUSTOM-CODE")

    def test_ensure_carton_code_replaces_legacy_code_and_handles_collision(self):
        legacy_carton = Carton.objects.create(code="C-LEGACY", status=CartonStatus.DRAFT)
        Carton.objects.create(code="XX-20260101-1", status=CartonStatus.DRAFT)

        with mock.patch("wms.domain.stock._carton_date_str", return_value="20260101"):
            with mock.patch("wms.domain.stock._dominant_type_code", return_value="XX"):
                with mock.patch("wms.domain.stock._next_carton_sequence", side_effect=[1, 2]):
                    ensure_carton_code(legacy_carton)

        legacy_carton.refresh_from_db()
        self.assertEqual(legacy_carton.code, "XX-20260101-2")

    def test_ensure_carton_code_retries_and_can_raise_after_integrity_errors(self):
        carton = Carton.objects.create(code="C-ERR", status=CartonStatus.DRAFT)

        with mock.patch("wms.domain.stock._carton_date_str", return_value="20260101"):
            with mock.patch("wms.domain.stock._dominant_type_code", return_value="AB"):
                with mock.patch("wms.domain.stock._next_carton_sequence", side_effect=[1, 2, 3]):
                    with mock.patch(
                        "wms.domain.stock.Carton.objects.filter"
                    ) as filter_mock:
                        filter_mock.return_value.exclude.return_value.exists.return_value = False
                        with mock.patch.object(
                            carton,
                            "save",
                            side_effect=[IntegrityError("dup"), None],
                        ):
                            ensure_carton_code(carton)

        self.assertEqual(carton.code, "AB-20260101-2")
        carton.code = "C-ERR-SECOND"

        with mock.patch("wms.domain.stock._carton_date_str", return_value="20260101"):
            with mock.patch("wms.domain.stock._dominant_type_code", return_value="AB"):
                with mock.patch("wms.domain.stock._next_carton_sequence", side_effect=[1, 2, 3]):
                    with mock.patch(
                        "wms.domain.stock.Carton.objects.filter"
                    ) as filter_mock:
                        filter_mock.return_value.exclude.return_value.exists.return_value = False
                        with mock.patch.object(
                            carton,
                            "save",
                            side_effect=[IntegrityError("dup-1"), IntegrityError("dup-2")],
                        ):
                            with self.assertRaises(IntegrityError):
                                ensure_carton_code(carton)

    def test_input_helpers_validate_required_entities(self):
        valid_receive_payload = ReceiveStockInput(
            product_id=self.product.id,
            quantity=2,
            location_id=self.location.id,
        )
        receive_stock_from_input(user=self.user, payload=valid_receive_payload)

        invalid_receive_payload = ReceiveStockInput(
            product_id=999999,
            quantity=2,
            location_id=self.location.id,
        )
        with self.assertRaisesMessage(StockError, "Produit introuvable."):
            receive_stock_from_input(user=self.user, payload=invalid_receive_payload)

        valid_pack_payload = PackCartonInput(
            product_id=self.product.id,
            quantity=1,
            carton_id=None,
            carton_code=None,
            shipment_id=None,
            current_location_id=self.location.id,
        )
        pack_carton_from_input(user=self.user, payload=valid_pack_payload)

        invalid_pack_payload = PackCartonInput(
            product_id=self.product.id,
            quantity=1,
            carton_id=None,
            carton_code=None,
            shipment_id=None,
            current_location_id=999999,
        )
        with self.assertRaisesMessage(StockError, "Emplacement introuvable."):
            pack_carton_from_input(user=self.user, payload=invalid_pack_payload)

    def test_dto_validate_raises_on_invalid_payloads(self):
        with self.assertRaisesMessage(ValueError, "Quantité invalide."):
            ReceiveStockInput(product_id=1, quantity=0, location_id=1).validate()

        with self.assertRaisesMessage(ValueError, "Quantité invalide."):
            PackCartonInput(product_id=1, quantity=0).validate()

        with self.assertRaisesMessage(ValueError, "Choisissez carton_id ou carton_code."):
            PackCartonInput(
                product_id=1,
                quantity=1,
                carton_id=10,
                carton_code="CART-10",
            ).validate()
