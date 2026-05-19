from django.db import connection, transaction

from contacts.models import Contact

from ..carton_status_events import set_carton_status
from ..models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    Destination,
    MovementType,
    Order,
    OrderLine,
    OrderReservation,
    OrderShipmentLink,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
)
from ..scan_helpers import build_packing_bins
from ..shipment_helpers import build_destination_label
from ..shipment_party_rules import (
    ShipmentPartyResolutionError,
    normalize_party_contact_to_org,
    resolve_recipient_binding_for_operation,
    resolve_shipper_for_operation,
)
from ..shipment_party_snapshot import build_shipment_party_snapshot_payload
from ..shipment_status import sync_shipment_ready_state
from .stock import (
    StockConsumeResult,
    StockError,
    _prepare_carton,
    ensure_carton_code,
    fefo_lots,
)

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
RECOMMENDED_CARTONS_PER_SHIPMENT = 10


def _normalized_text(value):
    return (value or "").strip()


def _positive_int(value, *, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value, *, default=0):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _active_contact(contact):
    if contact and contact.is_active:
        return contact
    return None


def _resolve_shipper_contact_for_order(order: Order):
    return _active_contact(order.shipper_contact) or _active_contact(order.association_contact)


def _resolve_recipient_contact_for_order(order: Order):
    return _active_contact(order.recipient_contact)


def _requires_recipient_binding_for_order(
    order: Order, *, recipient_contact: Contact | None
) -> bool:
    association_contact = _active_contact(order.association_contact)
    return bool(recipient_contact and recipient_contact != association_contact)


def _resolve_destination_for_order(
    order: Order,
    *,
    shipper_contact: Contact | None,
    recipient_contact: Contact | None,
):
    city = _normalized_text(order.destination_city)
    country = _normalized_text(order.destination_country)

    if city:
        destination_query = Destination.objects.filter(
            is_active=True,
            city__iexact=city,
        )
        if country:
            destination_query = destination_query.filter(country__iexact=country)
        destination = destination_query.order_by("id").first()
        if destination:
            return destination

    if city:
        fallback_query = Destination.objects.filter(
            is_active=True,
            city__iexact=city,
        )
        if country:
            fallback_query = fallback_query.filter(country__iexact=country)
        return fallback_query.order_by("id").first()
    return None


def _resolve_correspondent_contact_for_order(order: Order, *, destination: Destination | None):
    if _active_contact(order.correspondent_contact):
        return order.correspondent_contact
    if (
        destination
        and destination.correspondent_contact
        and destination.correspondent_contact.is_active
    ):
        return destination.correspondent_contact
    return None


def _build_shipment_defaults_from_order(order: Order):
    shipper_contact = _resolve_shipper_contact_for_order(order)
    recipient_contact = _resolve_recipient_contact_for_order(order)
    destination = _resolve_destination_for_order(
        order,
        shipper_contact=shipper_contact,
        recipient_contact=recipient_contact,
    )
    shipper_org = normalize_party_contact_to_org(shipper_contact)
    recipient_org = normalize_party_contact_to_org(recipient_contact)

    if shipper_contact is None:
        raise StockError("Expediteur requis.")
    if recipient_contact is None:
        raise StockError("Destinataire requis.")
    if destination is None:
        raise StockError("Escale requise.")
    try:
        resolve_shipper_for_operation(
            shipper_org=shipper_org,
            destination=destination,
        )
        if _requires_recipient_binding_for_order(order, recipient_contact=recipient_contact):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
            )
    except ShipmentPartyResolutionError as exc:
        raise StockError(str(exc)) from exc

    correspondent_contact = _resolve_correspondent_contact_for_order(
        order,
        destination=destination,
    )

    destination_address = _normalized_text(order.destination_address)
    destination_country = _normalized_text(order.destination_country) or "France"
    if destination:
        destination_address = build_destination_label(destination)
        destination_country = _normalized_text(destination.country) or destination_country

    shipper_name = _normalized_text(shipper_contact.name if shipper_contact else order.shipper_name)
    recipient_name = _normalized_text(
        recipient_contact.name if recipient_contact else order.recipient_name
    )
    correspondent_name = _normalized_text(
        correspondent_contact.name if correspondent_contact else order.correspondent_name
    )
    party_payload = build_shipment_party_snapshot_payload(
        shipper_contact=shipper_contact,
        recipient_contact=recipient_contact,
        correspondent_contact=correspondent_contact,
        shipper_name=shipper_name,
        recipient_name=recipient_name,
        correspondent_name=correspondent_name,
    )

    return {
        "shipper_name": shipper_name,
        "shipper_contact_ref": shipper_contact,
        "shipper_contact": shipper_name,
        "recipient_name": recipient_name,
        "recipient_contact_ref": recipient_contact,
        "recipient_contact": recipient_name,
        "correspondent_name": correspondent_name,
        "correspondent_contact_ref": correspondent_contact,
        "destination": destination,
        "destination_address": destination_address,
        "destination_country": destination_country,
        "requested_delivery_date": order.requested_delivery_date,
        "created_by": order.created_by,
        **party_payload,
    }


def _sync_existing_shipment_from_order(shipment: Shipment, *, defaults):
    snapshot_fields = {"party_snapshot"}
    snapshot_missing = not bool(getattr(shipment, "party_snapshot", None))
    update_fields = []
    for field_name, value in defaults.items():
        if field_name in snapshot_fields:
            if snapshot_missing and getattr(shipment, field_name, None) != value:
                setattr(shipment, field_name, value)
                update_fields.append(field_name)
            continue

        if field_name in {"shipper_name", "recipient_name", "correspondent_name"}:
            if value and not _normalized_text(getattr(shipment, field_name, "")):
                setattr(shipment, field_name, value)
                update_fields.append(field_name)
            continue

        current_value = getattr(shipment, field_name, None)
        if current_value in {None, ""} and value not in {None, ""}:
            setattr(shipment, field_name, value)
            update_fields.append(field_name)

    if update_fields:
        shipment.save(update_fields=sorted(set(update_fields)))


def create_shipment_for_order(*, order: Order, force_new: bool = False):
    defaults = _build_shipment_defaults_from_order(order)
    if order.shipment_id and not force_new:
        shipment = order.shipment
        _sync_existing_shipment_from_order(shipment, defaults=defaults)
        OrderShipmentLink.objects.get_or_create(
            order=order,
            shipment=shipment,
            defaults={"created_by": order.created_by},
        )
        return shipment
    shipment = Shipment.objects.create(
        status=ShipmentStatus.DRAFT,
        **defaults,
    )
    OrderShipmentLink.objects.get_or_create(
        order=order,
        shipment=shipment,
        defaults={"created_by": order.created_by},
    )
    if not order.shipment_id:
        order.shipment = shipment
        order.save(update_fields=["shipment"])
    return shipment


def _order_linked_shipments(order: Order):
    shipments = []
    seen = set()
    if order.shipment_id:
        shipments.append(order.shipment)
        seen.add(order.shipment_id)
        OrderShipmentLink.objects.get_or_create(
            order=order,
            shipment=order.shipment,
            defaults={"created_by": order.created_by},
        )
    for link in (
        OrderShipmentLink.objects.filter(order=order).select_related("shipment").order_by("id")
    ):
        shipment = link.shipment
        if shipment.id in seen:
            continue
        shipments.append(shipment)
        seen.add(shipment.id)
    return shipments


def _ensure_order_shipment_count(order: Order, shipment_count: int):
    create_shipment_for_order(order=order)
    shipments = _order_linked_shipments(order)
    target_count = _positive_int(shipment_count, default=1)
    while len(shipments) < target_count:
        shipment = create_shipment_for_order(order=order, force_new=True)
        shipments.append(shipment)
    return shipments


def _order_preparation_carton_size():
    carton_format = CartonFormat.objects.filter(is_default=True).first()
    if carton_format is None:
        carton_format = CartonFormat.objects.first()
    if carton_format is None:
        raise StockError("Format de carton manquant.")
    return {
        "length_cm": carton_format.length_cm,
        "width_cm": carton_format.width_cm,
        "height_cm": carton_format.height_cm,
        "max_weight_g": carton_format.max_weight_g,
    }


def _remaining_order_line_items(order: Order):
    return [
        {"product": line.product, "quantity": line.remaining_quantity}
        for line in order.lines.select_related("product")
        if line.remaining_quantity > 0
    ]


def estimate_order_preparation_carton_count(order: Order):
    line_items = _remaining_order_line_items(order)
    if not line_items:
        return 0, []
    bins, errors, warnings = build_packing_bins(
        line_items,
        _order_preparation_carton_size(),
        apply_defaults=True,
    )
    if errors:
        raise StockError(errors[0])
    return len(bins or []), warnings


def recommended_order_shipment_count(carton_count: int):
    carton_count = max(0, _positive_int(carton_count, default=0))
    if carton_count <= 0:
        return 1
    return max(
        1,
        (carton_count + RECOMMENDED_CARTONS_PER_SHIPMENT - 1) // RECOMMENDED_CARTONS_PER_SHIPMENT,
    )


def default_order_shipment_carton_counts(carton_count: int, shipment_count=None):
    carton_count = max(0, _non_negative_int(carton_count, default=0))
    target_count = _positive_int(
        shipment_count,
        default=recommended_order_shipment_count(carton_count),
    )
    counts = []
    remaining = carton_count
    for shipment_index in range(target_count):
        if remaining <= 0:
            counts.append(0)
            continue
        if shipment_index == target_count - 1:
            count = remaining
        else:
            count = min(RECOMMENDED_CARTONS_PER_SHIPMENT, remaining)
        counts.append(count)
        remaining -= count
    return counts


def normalize_order_shipment_carton_counts(carton_count, shipment_count, shipment_carton_counts):
    carton_count = max(0, _non_negative_int(carton_count, default=0))
    target_count = _positive_int(shipment_count, default=1)
    if shipment_carton_counts is None:
        return default_order_shipment_carton_counts(carton_count, target_count)
    normalized_counts = []
    for raw_count in shipment_carton_counts:
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise StockError("La répartition des colis contient une valeur invalide.") from exc
        if count < 0:
            raise StockError("La répartition des colis contient une valeur invalide.")
        normalized_counts.append(count)
    if len(normalized_counts) != target_count:
        raise StockError(f"La répartition doit contenir {target_count} expéditions.")
    distributed_total = sum(normalized_counts)
    if distributed_total != carton_count:
        raise StockError(
            f"La répartition indique {distributed_total} colis au lieu de {carton_count}."
        )
    return normalized_counts


def _shipment_for_generated_carton(
    *, carton_index, carton_count, shipments, shipment_carton_counts=None
):
    if not shipments:
        raise StockError("Expédition introuvable.")
    shipment_count = len(shipments)
    if shipment_count == 1 or carton_count <= 0:
        return shipments[0]
    if shipment_carton_counts is not None:
        upper_bound = 0
        for shipment_index, carton_limit in enumerate(shipment_carton_counts):
            upper_bound += carton_limit
            if carton_index < upper_bound:
                return shipments[min(shipment_index, shipment_count - 1)]
        return shipments[-1]
    recommended_count = recommended_order_shipment_count(carton_count)
    if shipment_count >= recommended_count:
        shipment_index = carton_index // RECOMMENDED_CARTONS_PER_SHIPMENT
    else:
        shipment_index = (carton_index * shipment_count) // carton_count
    return shipments[min(shipment_index, shipment_count - 1)]


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
                raise StockError(f"{line.product.name}: stock insuffisant ({available_total}).")
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
                OrderReservation.objects.create(order_line=line, product_lot=lot, quantity=take)
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
        raise StockError("Réservation insuffisante pour libérer.")


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
        raise StockError("Quantité invalide.")
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
    display_expires_on=None,
    prepared_by_user=None,
    volunteer_profile=None,
    actor_user=None,
):
    carton = _prepare_carton(
        user=user,
        carton=carton,
        shipment=shipment,
        current_location=current_location,
        carton_size=carton_size,
        prepared_by_user=prepared_by_user,
        volunteer_profile=volunteer_profile,
        actor_user=actor_user,
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
            carton=carton,
            product_lot=entry.lot,
            defaults={"quantity": 0, "display_expires_on": display_expires_on},
        )
        item.quantity += entry.quantity
        update_fields = ["quantity"]
        resolved_display_expires_on = item.display_expires_on
        if display_expires_on is not None:
            if resolved_display_expires_on is None:
                resolved_display_expires_on = display_expires_on
            else:
                resolved_display_expires_on = min(
                    resolved_display_expires_on,
                    display_expires_on,
                )
        if resolved_display_expires_on != item.display_expires_on:
            item.display_expires_on = resolved_display_expires_on
            update_fields.append("display_expires_on")
        item.save(update_fields=update_fields)
    target_status = None
    status_reason = ""
    if shipment is not None:
        target_status = CartonStatus.ASSIGNED
        status_reason = "order_pack_assign"
    elif carton.status == CartonStatus.DRAFT:
        target_status = CartonStatus.PICKING
        status_reason = "order_pack_start_picking"
    if target_status and carton.status != target_status:
        set_carton_status(
            carton=carton,
            new_status=target_status,
            reason=status_reason,
            user=user,
        )
    if shipment is not None:
        sync_shipment_ready_state(shipment)
    ensure_carton_code(carton)
    return carton


@transaction.atomic
def assign_ready_cartons_to_order(*, order: Order):
    if not order.shipment_id:
        create_shipment_for_order(order=order)
    shipment = order.shipment
    if shipment is None:
        raise StockError("Expédition introuvable.")
    if getattr(shipment, "is_disputed", False):
        raise StockError("Expédition en litige: affectation des colis impossible.")
    if shipment.status in LOCKED_SHIPMENT_STATUSES:
        raise StockError("Expédition verrouillée: affectation des colis impossible.")
    line_by_product = {line.product_id: line for line in order.lines.all()}
    remaining = {line.product_id: line.remaining_quantity for line in order.lines.all()}
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
        carton.shipment = shipment
        set_carton_status(
            carton=carton,
            new_status=CartonStatus.ASSIGNED,
            update_fields=["shipment"],
            reason="order_assign_ready_carton",
            user=order.created_by,
        )
        line.prepared_quantity += carton_qty
        line.save(update_fields=["prepared_quantity"])
        remaining[product_id] -= carton_qty
        if line.reserved_quantity:
            release_reserved_stock(line=line, quantity=carton_qty)
        assigned += 1
    sync_shipment_ready_state(shipment)
    return assigned


@transaction.atomic
def prepare_order(
    *,
    user,
    order: Order,
    shipment_count=1,
    prepared_by_user=None,
    volunteer_profile=None,
    actor_user=None,
    created_cartons=None,
    packing_warnings=None,
    prepared_shipments=None,
    shipment_carton_counts=None,
):
    if order.status not in {OrderStatus.RESERVED, OrderStatus.PREPARING}:
        raise StockError("Commande non réservée.")
    shipments = _ensure_order_shipment_count(order, _positive_int(shipment_count, default=1))
    if prepared_shipments is not None:
        prepared_shipments.extend(shipments)
    for shipment in shipments:
        if getattr(shipment, "is_disputed", False):
            raise StockError("Expédition en litige: préparation impossible.")
        if shipment.status in LOCKED_SHIPMENT_STATUSES:
            raise StockError("Expédition verrouillée: préparation impossible.")
    assigned = assign_ready_cartons_to_order(order=order)

    remaining_lines = [
        line for line in order.lines.select_related("product") if line.remaining_quantity > 0
    ]
    if remaining_lines:
        carton_size = _order_preparation_carton_size()
        line_items = [
            {"product": line.product, "quantity": line.remaining_quantity}
            for line in remaining_lines
        ]
        line_by_product = {line.product_id: line for line in remaining_lines}
        bins, errors, warnings = build_packing_bins(
            line_items,
            carton_size,
            apply_defaults=True,
        )
        if errors:
            raise StockError(errors[0])
        if packing_warnings is not None:
            packing_warnings.extend(warnings)
        carton_count = len(bins or [])
        carton_distribution = None
        if shipment_carton_counts is not None:
            carton_distribution = normalize_order_shipment_carton_counts(
                carton_count,
                len(shipments),
                shipment_carton_counts,
            )
        for carton_index, bin_data in enumerate(bins):
            shipment = _shipment_for_generated_carton(
                carton_index=carton_index,
                carton_count=carton_count,
                shipments=shipments,
                shipment_carton_counts=carton_distribution,
            )
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
                    prepared_by_user=prepared_by_user,
                    volunteer_profile=volunteer_profile,
                    actor_user=actor_user,
                )
            if carton is not None and created_cartons is not None:
                created_cartons.append(carton)
    order.refresh_from_db()
    if all(line.remaining_quantity == 0 for line in order.lines.all()):
        order.status = OrderStatus.READY
    else:
        order.status = OrderStatus.PREPARING
    order.save(update_fields=["status"])
    for shipment in shipments:
        sync_shipment_ready_state(shipment)
    return assigned
