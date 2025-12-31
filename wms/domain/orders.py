from django.db import connection, transaction

from .stock import (
    StockConsumeResult,
    StockError,
    _prepare_carton,
    ensure_carton_code,
    fefo_lots,
)
from ..models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    MovementType,
    Order,
    OrderLine,
    OrderReservation,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
)
from ..scan_helpers import build_packing_bins


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


@transaction.atomic
def release_reserved_stock(*, line: OrderLine, quantity: int):
    if quantity <= 0:
        return
    remaining = quantity
    reservations_query = line.reservations.select_related("product_lot").order_by(
        "product_lot__expires_on", "product_lot__received_on", "product_lot__id"
    )
    if connection.features.has_select_for_update:
        reservations_query = reservations_query.select_for_update()
    reservations = list(reservations_query)
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


@transaction.atomic
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
    reservations_query = line.reservations.select_related("product_lot").order_by(
        "product_lot__expires_on", "product_lot__received_on", "product_lot__id"
    )
    if connection.features.has_select_for_update:
        reservations_query = reservations_query.select_for_update()
    reservations = list(reservations_query)
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


@transaction.atomic
def pack_carton_from_reserved(
    *,
    user,
    line: OrderLine,
    quantity: int,
    carton: Carton | None = None,
    shipment: Shipment | None = None,
    current_location=None,
    carton_size=None,
):
    carton = _prepare_carton(
        user=user,
        carton=carton,
        shipment=shipment,
        current_location=current_location,
        carton_size=carton_size,
    )

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
    if carton.status == CartonStatus.DRAFT:
        carton.status = CartonStatus.PICKING
        carton.save(update_fields=["status"])
    ensure_carton_code(carton)
    return carton


@transaction.atomic
def assign_ready_cartons_to_order(*, order: Order):
    if not order.shipment_id:
        create_shipment_for_order(order=order)
    line_by_product = {line.product_id: line for line in order.lines.all()}
    remaining = {
        line.product_id: line.remaining_quantity for line in order.lines.all()
    }
    ready_cartons = (
        Carton.objects.filter(status=CartonStatus.PACKED, shipment__isnull=True)
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
        carton.save(update_fields=["shipment"])
        line.prepared_quantity += carton_qty
        line.save(update_fields=["prepared_quantity"])
        remaining[product_id] -= carton_qty
        if line.reserved_quantity:
            release_reserved_stock(line=line, quantity=carton_qty)
        assigned += 1
    return assigned


@transaction.atomic
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
                    carton_size=carton_size,
                )
    order.refresh_from_db()
    if all(line.remaining_quantity == 0 for line in order.lines.all()):
        order.status = OrderStatus.READY
    else:
        order.status = OrderStatus.PREPARING
    order.save(update_fields=["status"])
    return assigned
