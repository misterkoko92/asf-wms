import secrets
from dataclasses import dataclass

from django.db import connection, transaction
from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.utils import timezone

from .models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    MovementType,
    Order,
    OrderLine,
    OrderReservation,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    ReceiptLine,
    ReceiptStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
)
from .scan_helpers import build_packing_bins


class StockError(ValueError):
    pass


@dataclass
class StockConsumeResult:
    lot: ProductLot
    quantity: int


def generate_carton_code() -> str:
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"C-{timestamp}-{secrets.token_hex(2).upper()}"


def fefo_lots(product: Product, *, for_update: bool = False):
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"), output_field=IntegerField()
    )
    queryset = (
        ProductLot.objects.filter(
            product=product,
            status=ProductLotStatus.AVAILABLE,
        )
        .annotate(
            expires_null=Case(
                When(expires_on__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .annotate(available=available_expr)
        .filter(available__gt=0)
        .order_by("expires_null", "expires_on", "received_on", "id")
    )
    if for_update and connection.features.has_select_for_update:
        queryset = queryset.select_for_update()
    return queryset


def receive_stock(
    *,
    user,
    product: Product,
    quantity: int,
    location,
    lot_code: str = "",
    received_on=None,
    expires_on=None,
    status: str | None = None,
    storage_conditions: str | None = None,
    source_receipt=None,
):
    if quantity <= 0:
        raise StockError("Quantite invalide.")
    if status is None:
        status = (
            ProductLotStatus.QUARANTINED
            if product.quarantine_default
            else ProductLotStatus.AVAILABLE
        )
    lot = ProductLot.objects.create(
        product=product,
        lot_code=lot_code or "",
        expires_on=expires_on,
        received_on=received_on,
        status=status,
        quantity_on_hand=quantity,
        location=location,
        source_receipt=source_receipt,
        storage_conditions=storage_conditions or product.storage_conditions,
    )
    StockMovement.objects.create(
        movement_type=MovementType.IN,
        product=product,
        product_lot=lot,
        quantity=quantity,
        to_location=location,
        reason_code="receive",
        created_by=user,
    )
    return lot


def receive_receipt_line(*, user, line: ReceiptLine):
    if line.received_lot_id:
        raise StockError("Ligne de reception deja traitee.")
    if line.receipt.status == ReceiptStatus.CANCELLED:
        raise StockError("Reception annulee.")
    location = line.location or line.product.default_location
    if location is None:
        raise StockError("Emplacement requis pour reception.")
    status = line.lot_status or None
    lot = receive_stock(
        user=user,
        product=line.product,
        quantity=line.quantity,
        location=location,
        lot_code=line.lot_code or "",
        received_on=line.receipt.received_on,
        expires_on=line.expires_on,
        status=status,
        source_receipt=line.receipt,
        storage_conditions=line.storage_conditions or line.product.storage_conditions,
    )
    line.received_lot = lot
    line.received_by = user
    line.received_at = timezone.now()
    line.save(update_fields=["received_lot", "received_by", "received_at"])

    receipt = line.receipt
    if receipt.status == ReceiptStatus.DRAFT:
        remaining = receipt.lines.filter(received_lot__isnull=True).exists()
        if not remaining:
            receipt.status = ReceiptStatus.RECEIVED
            receipt.save(update_fields=["status"])
    return lot


def create_shipment_for_order(*, order: Order):
    if order.shipment_id:
        return order.shipment
    shipment = Shipment.objects.create(
        status=ShipmentStatus.DRAFT,
        shipper_name=order.shipper_name,
        recipient_name=order.recipient_name,
        correspondent_name=order.correspondent_name,
        destination_address=order.destination_address,
        destination_country=order.destination_country or "France",
        requested_delivery_date=order.requested_delivery_date,
        created_by=order.created_by,
    )
    order.shipment = shipment
    order.save(update_fields=["shipment"])
    return shipment


def reserve_stock_for_order(*, order: Order):
    if order.status in {OrderStatus.CANCELLED, OrderStatus.READY}:
        raise StockError("Commande non modifiable.")
    with transaction.atomic():
        for line in order.lines.select_related("product").all():
            needed = line.quantity - line.reserved_quantity
            if needed <= 0:
                continue
            lots = list(fefo_lots(line.product, for_update=True))
            available_total = sum(
                max(0, lot.quantity_on_hand - lot.quantity_reserved) for lot in lots
            )
            if available_total < needed:
                raise StockError(
                    f"{line.product.name}: stock insuffisant ({available_total})."
                )
            remaining = needed
            for lot in lots:
                if remaining <= 0:
                    break
                available = lot.quantity_on_hand - lot.quantity_reserved
                if available <= 0:
                    continue
                take = min(remaining, available)
                lot.quantity_reserved += take
                lot.save(update_fields=["quantity_reserved"])
                OrderReservation.objects.create(
                    order_line=line, product_lot=lot, quantity=take
                )
                remaining -= take
            line.reserved_quantity += needed
            line.save(update_fields=["reserved_quantity"])
        order.status = OrderStatus.RESERVED
        order.save(update_fields=["status"])


def release_reserved_stock(*, line: OrderLine, quantity: int):
    if quantity <= 0:
        return
    remaining = quantity
    reservations = list(
        line.reservations.select_related("product_lot").order_by(
            "product_lot__expires_on", "product_lot__received_on", "product_lot__id"
        )
    )
    for reservation in reservations:
        if remaining <= 0:
            break
        take = min(remaining, reservation.quantity)
        reservation.quantity -= take
        if reservation.quantity <= 0:
            reservation.delete()
        else:
            reservation.save(update_fields=["quantity"])
        lot = reservation.product_lot
        lot.quantity_reserved -= take
        if lot.quantity_reserved < 0:
            lot.quantity_reserved = 0
        lot.save(update_fields=["quantity_reserved"])
        remaining -= take
    line.reserved_quantity = max(0, line.reserved_quantity - (quantity - remaining))
    line.save(update_fields=["reserved_quantity"])
    if remaining > 0:
        raise StockError("Reservation insuffisante pour liberer.")


def consume_reserved_stock(
    *,
    user,
    line: OrderLine,
    quantity: int,
    movement_type: str,
    shipment: Shipment | None = None,
    carton: Carton | None = None,
):
    if quantity <= 0:
        raise StockError("Quantite invalide.")
    remaining = quantity
    consumed: list[StockConsumeResult] = []
    reservations = list(
        line.reservations.select_related("product_lot").order_by(
            "product_lot__expires_on", "product_lot__received_on", "product_lot__id"
        )
    )
    for reservation in reservations:
        if remaining <= 0:
            break
        take = min(remaining, reservation.quantity)
        if take <= 0:
            continue
        reservation.quantity -= take
        if reservation.quantity <= 0:
            reservation.delete()
        else:
            reservation.save(update_fields=["quantity"])
        lot = reservation.product_lot
        lot.quantity_reserved -= take
        lot.quantity_on_hand -= take
        lot.save(update_fields=["quantity_reserved", "quantity_on_hand"])
        StockMovement.objects.create(
            movement_type=movement_type,
            product=line.product,
            product_lot=lot,
            quantity=take,
            from_location=lot.location,
            related_carton=carton,
            related_shipment=shipment,
            created_by=user,
        )
        consumed.append(StockConsumeResult(lot=lot, quantity=take))
        remaining -= take
    if remaining > 0:
        raise StockError("Reservation insuffisante pour consommation.")
    line.reserved_quantity = max(0, line.reserved_quantity - quantity)
    line.prepared_quantity += quantity
    line.save(update_fields=["reserved_quantity", "prepared_quantity"])
    return consumed


def pack_carton_from_reserved(
    *,
    user,
    line: OrderLine,
    quantity: int,
    carton: Carton | None = None,
    shipment: Shipment | None = None,
    current_location=None,
):
    if carton and carton.status == CartonStatus.SHIPPED:
        raise StockError("Impossible de modifier un carton expedie.")
    if shipment and shipment.status in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}:
        raise StockError("Impossible de modifier une expedition expediee ou livree.")
    if carton is None:
        code = generate_carton_code()
        carton = Carton.objects.create(
            code=code,
            status=CartonStatus.ASSIGNED if shipment else CartonStatus.READY,
            shipment=shipment,
            current_location=current_location,
            prepared_by=user,
        )
    else:
        if shipment and carton.shipment and carton.shipment != shipment:
            raise StockError("Carton deja lie a une autre expedition.")
        if shipment and carton.shipment is None:
            carton.shipment = shipment
        if current_location is not None:
            carton.current_location = current_location
        if carton.status in {CartonStatus.DRAFT, CartonStatus.READY}:
            carton.status = CartonStatus.ASSIGNED if shipment else CartonStatus.READY
        carton.save()

    movement_type = MovementType.OUT if shipment else MovementType.PRECONDITION
    consumed = consume_reserved_stock(
        user=user,
        line=line,
        quantity=quantity,
        movement_type=movement_type,
        shipment=shipment,
        carton=carton,
    )
    for entry in consumed:
        item, _ = CartonItem.objects.get_or_create(
            carton=carton, product_lot=entry.lot, defaults={"quantity": 0}
        )
        item.quantity += entry.quantity
        item.save(update_fields=["quantity"])
    return carton


def assign_ready_cartons_to_order(*, order: Order):
    if not order.shipment_id:
        create_shipment_for_order(order=order)
    line_by_product = {line.product_id: line for line in order.lines.all()}
    remaining = {
        line.product_id: line.remaining_quantity for line in order.lines.all()
    }
    ready_cartons = (
        Carton.objects.filter(status=CartonStatus.READY, shipment__isnull=True)
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code")
    )
    assigned = 0
    for carton in ready_cartons:
        items = list(carton.cartonitem_set.all())
        if not items:
            continue
        product_ids = {item.product_lot.product_id for item in items}
        if len(product_ids) != 1:
            continue
        product_id = next(iter(product_ids))
        if product_id not in remaining:
            continue
        carton_qty = sum(item.quantity for item in items)
        if carton_qty <= 0:
            continue
        if remaining[product_id] < carton_qty:
            continue
        line = line_by_product[product_id]
        carton.shipment = order.shipment
        carton.status = CartonStatus.ASSIGNED
        carton.save(update_fields=["shipment", "status"])
        line.prepared_quantity += carton_qty
        line.save(update_fields=["prepared_quantity"])
        remaining[product_id] -= carton_qty
        if line.reserved_quantity:
            release_reserved_stock(line=line, quantity=carton_qty)
        assigned += 1
    return assigned


def prepare_order(*, user, order: Order):
    if order.status not in {OrderStatus.RESERVED, OrderStatus.PREPARING}:
        raise StockError("Commande non reservee.")
    shipment = create_shipment_for_order(order=order)
    assigned = assign_ready_cartons_to_order(order=order)

    remaining_lines = [
        line
        for line in order.lines.select_related("product")
        if line.remaining_quantity > 0
    ]
    if remaining_lines:
        carton_format = CartonFormat.objects.filter(is_default=True).first()
        if carton_format is None:
            carton_format = CartonFormat.objects.first()
        if carton_format is None:
            raise StockError("Format de carton manquant.")
        carton_size = {
            "length_cm": carton_format.length_cm,
            "width_cm": carton_format.width_cm,
            "height_cm": carton_format.height_cm,
            "max_weight_g": carton_format.max_weight_g,
        }
        line_items = [
            {"product": line.product, "quantity": line.remaining_quantity}
            for line in remaining_lines
        ]
        line_by_product = {line.product_id: line for line in remaining_lines}
        bins, errors, warnings = build_packing_bins(line_items, carton_size)
        if errors:
            raise StockError(errors[0])
        for bin_data in bins:
            carton = None
            for entry in bin_data["items"].values():
                line = line_by_product.get(entry["product"].id)
                if line is None:
                    raise StockError("Produit manquant dans la commande.")
                carton = pack_carton_from_reserved(
                    user=user,
                    line=line,
                    quantity=entry["quantity"],
                    carton=carton,
                    shipment=shipment,
                )
    order.refresh_from_db()
    if all(line.remaining_quantity == 0 for line in order.lines.all()):
        order.status = OrderStatus.READY
    else:
        order.status = OrderStatus.PREPARING
    order.save(update_fields=["status"])
    return assigned
def adjust_stock(*, user, lot: ProductLot, delta: int, reason_code: str, reason_notes: str):
    if delta == 0:
        raise StockError("Quantite nulle.")
    if lot.quantity_on_hand + delta < 0:
        raise StockError("Stock insuffisant pour ajustement.")
    if delta < 0 and lot.quantity_on_hand + delta < lot.quantity_reserved:
        raise StockError("Ajustement impossible: stock reserve.")
    lot.quantity_on_hand += delta
    lot.save(update_fields=["quantity_on_hand"])
    StockMovement.objects.create(
        movement_type=MovementType.ADJUST,
        product=lot.product,
        product_lot=lot,
        quantity=abs(delta),
        from_location=lot.location if delta < 0 else None,
        to_location=lot.location if delta > 0 else None,
        reason_code=reason_code or "",
        reason_notes=reason_notes or "",
        created_by=user,
    )
    return lot


def transfer_stock(*, user, lot: ProductLot, to_location):
    if lot.location_id == to_location.id:
        raise StockError("Le lot est deja a cet emplacement.")
    from_location = lot.location
    lot.location = to_location
    lot.save(update_fields=["location"])
    StockMovement.objects.create(
        movement_type=MovementType.TRANSFER,
        product=lot.product,
        product_lot=lot,
        quantity=lot.quantity_on_hand,
        from_location=from_location,
        to_location=to_location,
        created_by=user,
    )
    return lot


def consume_stock(
    *,
    user,
    product: Product,
    quantity: int,
    movement_type: str,
    shipment: Shipment | None = None,
    carton: Carton | None = None,
    reason_code: str = "",
    reason_notes: str = "",
):
    if quantity <= 0:
        raise StockError("Quantite invalide.")
    with transaction.atomic():
        lots = list(fefo_lots(product, for_update=True))
        available_total = sum(
            max(0, lot.quantity_on_hand - lot.quantity_reserved) for lot in lots
        )
        if available_total < quantity:
            raise StockError(f"Stock insuffisant: {available_total} disponible(s).")
        remaining = quantity
        consumed: list[StockConsumeResult] = []
        for lot in lots:
            if remaining <= 0:
                break
            available = lot.quantity_on_hand - lot.quantity_reserved
            take = min(remaining, max(0, available))
            if take <= 0:
                continue
            lot.quantity_on_hand -= take
            lot.save(update_fields=["quantity_on_hand"])
            StockMovement.objects.create(
                movement_type=movement_type,
                product=product,
                product_lot=lot,
                quantity=take,
                from_location=lot.location,
                related_carton=carton,
                related_shipment=shipment,
                reason_code=reason_code,
                reason_notes=reason_notes,
                created_by=user,
            )
            consumed.append(StockConsumeResult(lot=lot, quantity=take))
            remaining -= take
        return consumed


def pack_carton(
    *,
    user,
    product: Product,
    quantity: int,
    carton: Carton | None = None,
    carton_code: str | None = None,
    shipment: Shipment | None = None,
    current_location=None,
):
    if carton is None and carton_code:
        carton = Carton.objects.filter(code=carton_code).first()
    if carton and carton.status == CartonStatus.SHIPPED:
        raise StockError("Impossible de modifier un carton expedie.")
    if shipment and shipment.status in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}:
        raise StockError("Impossible de modifier une expedition expediee ou livree.")
    if carton is None:
        code = carton_code or generate_carton_code()
        carton = Carton.objects.create(
            code=code,
            status=CartonStatus.ASSIGNED if shipment else CartonStatus.READY,
            shipment=shipment,
            current_location=current_location,
            prepared_by=user,
        )
    else:
        if shipment and carton.shipment and carton.shipment != shipment:
            raise StockError("Carton deja lie a une autre expedition.")
        if shipment and carton.shipment is None:
            carton.shipment = shipment
        if current_location is not None:
            carton.current_location = current_location
        if carton.status in {CartonStatus.DRAFT, CartonStatus.READY}:
            carton.status = CartonStatus.ASSIGNED if shipment else CartonStatus.READY
        carton.save()

    movement_type = MovementType.OUT if shipment else MovementType.PRECONDITION
    consumed = consume_stock(
        user=user,
        product=product,
        quantity=quantity,
        movement_type=movement_type,
        shipment=shipment,
        carton=carton,
    )
    for entry in consumed:
        item, _ = CartonItem.objects.get_or_create(
            carton=carton, product_lot=entry.lot, defaults={"quantity": 0}
        )
        item.quantity += entry.quantity
        item.save(update_fields=["quantity"])
    return carton


def unpack_carton(*, user, carton: Carton):
    if carton.status == CartonStatus.SHIPPED:
        raise StockError("Impossible de modifier un carton expedie.")
    items = list(carton.cartonitem_set.select_related("product_lot", "product_lot__product"))
    if not items:
        raise StockError("Carton vide.")
    for item in items:
        lot = item.product_lot
        lot.quantity_on_hand += item.quantity
        lot.save(update_fields=["quantity_on_hand"])
        StockMovement.objects.create(
            movement_type=MovementType.UNPACK,
            product=lot.product,
            product_lot=lot,
            quantity=item.quantity,
            to_location=lot.location,
            related_carton=carton,
            related_shipment=carton.shipment,
            created_by=user,
        )
    carton.cartonitem_set.all().delete()
    carton.status = CartonStatus.DRAFT
    carton.shipment = None
    carton.save(update_fields=["status", "shipment"])
    return carton
