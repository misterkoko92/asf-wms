import re
import unicodedata
from dataclasses import dataclass

from django.db import IntegrityError, connection, transaction
from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.utils import timezone

from .dto import PackCartonInput, ReceiveStockInput
from ..carton_status_events import set_carton_status
from ..kit_components import KitCycleError, get_component_quantities
from ..models import (
    Carton,
    CartonItem,
    CartonStatus,
    CartonFormat,
    Location,
    MovementType,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptLine,
    ReceiptStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
)
from ..shipment_status import sync_shipment_ready_state


class StockError(ValueError):
    pass


@dataclass
class StockConsumeResult:
    lot: ProductLot
    quantity: int


CARTON_CODE_RE = re.compile(r"^(?P<type>[A-Z0-9]{2})-(?P<date>\d{8})-(?P<seq>\d+)$")


def _carton_date_str(carton):
    if carton.created_at:
        return timezone.localdate(carton.created_at).strftime("%Y%m%d")
    return timezone.localdate().strftime("%Y%m%d")


def _normalize_type_code(label):
    normalized = unicodedata.normalize("NFKD", label or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    words = [word for word in re.split(r"[^A-Za-z0-9]+", ascii_value) if word]
    if not words:
        return "XX"
    if len(words) >= 2:
        code = f"{words[0][0]}{words[1][0]}"
    else:
        code = words[0][:2]
    code = code.upper()
    return code.ljust(2, "X")[:2]


def _root_category_name(product):
    category = product.category
    while category and category.parent_id:
        category = category.parent
    return category.name if category else ""


def _dominant_type_code(carton):
    weight_by_type = {}
    qty_by_type = {}
    items = carton.cartonitem_set.select_related(
        "product_lot__product__category__parent"
    )
    for item in items:
        product = item.product_lot.product
        type_label = _root_category_name(product)
        type_code = _normalize_type_code(type_label)
        weight = (product.weight_g or 0) * item.quantity
        weight_by_type[type_code] = weight_by_type.get(type_code, 0) + weight
        qty_by_type[type_code] = qty_by_type.get(type_code, 0) + item.quantity
    if not weight_by_type:
        return "XX"
    max_weight = max(weight_by_type.values())
    if max_weight > 0:
        return max(weight_by_type, key=weight_by_type.get)
    return max(qty_by_type, key=qty_by_type.get)


def _resolve_carton_dimensions(*, carton_size=None):
    if carton_size:
        return (
            carton_size.get("length_cm"),
            carton_size.get("width_cm"),
            carton_size.get("height_cm"),
        )
    default_format = CartonFormat.objects.filter(is_default=True).first()
    if default_format is None:
        default_format = CartonFormat.objects.first()
    if default_format:
        return (
            default_format.length_cm,
            default_format.width_cm,
            default_format.height_cm,
        )
    return (None, None, None)


def _next_carton_sequence(date_str):
    max_seq = 0
    for code in Carton.objects.filter(code__contains=f"-{date_str}-").values_list(
        "code", flat=True
    ):
        match = CARTON_CODE_RE.match(code or "")
        if match and match.group("date") == date_str:
            try:
                seq = int(match.group("seq"))
            except ValueError:
                continue
            max_seq = max(max_seq, seq)
    return max_seq + 1


def _format_carton_code(type_code, date_str, sequence):
    return f"{type_code}-{date_str}-{sequence}"


def generate_carton_code(*, type_code=None, date_str=None) -> str:
    date_str = date_str or timezone.localdate().strftime("%Y%m%d")
    type_code = type_code or "XX"
    sequence = _next_carton_sequence(date_str)
    return _format_carton_code(type_code, date_str, sequence)


def ensure_carton_code(carton):
    if getattr(carton, "_manual_code", False):
        return
    current = carton.code or ""
    match = CARTON_CODE_RE.match(current)
    date_str = _carton_date_str(carton)
    is_legacy_auto = current.startswith("C-") and not match
    if not match and not is_legacy_auto:
        return
    type_code = _dominant_type_code(carton)
    if match and match.group("date") == date_str:
        sequence = int(match.group("seq"))
    else:
        sequence = _next_carton_sequence(date_str)
    new_code = _format_carton_code(type_code, date_str, sequence)
    if new_code == current:
        return
    if Carton.objects.filter(code=new_code).exclude(pk=carton.pk).exists():
        sequence = _next_carton_sequence(date_str)
        new_code = _format_carton_code(type_code, date_str, sequence)
    last_error = None
    for _ in range(2):
        try:
            carton.code = new_code
            carton.save(update_fields=["code"])
            return
        except IntegrityError as exc:
            last_error = exc
            sequence = _next_carton_sequence(date_str)
            new_code = _format_carton_code(type_code, date_str, sequence)
    if last_error:
        raise last_error


def _prepare_carton(
    *,
    user,
    carton: Carton | None,
    shipment: Shipment | None,
    current_location=None,
    carton_code: str | None = None,
    carton_size=None,
):
    if carton is None and carton_code:
        carton = Carton.objects.filter(code=carton_code).first()
    if carton and carton.status == CartonStatus.SHIPPED:
        raise StockError("Impossible de modifier un carton expédié.")
    if shipment and getattr(shipment, "is_disputed", False):
        raise StockError("Impossible de modifier une expédition en litige.")
    if shipment and shipment.status in {
        ShipmentStatus.PLANNED,
        ShipmentStatus.SHIPPED,
        ShipmentStatus.RECEIVED_CORRESPONDENT,
        ShipmentStatus.DELIVERED,
    }:
        raise StockError("Impossible de modifier une expédition expédiée ou livrée.")
    if carton is None:
        date_str = timezone.localdate().strftime("%Y%m%d")
        while True:
            code = carton_code or generate_carton_code(
                type_code="XX", date_str=date_str
            )
            try:
                carton = Carton.objects.create(
                    code=code,
                    status=CartonStatus.DRAFT,
                    shipment=shipment,
                    current_location=current_location,
                    prepared_by=user,
                )
            except IntegrityError:
                if carton_code:
                    raise
                continue
            break
        if carton_code:
            carton._manual_code = True
    else:
        if carton_code:
            carton._manual_code = True
        if shipment and carton.shipment and carton.shipment != shipment:
            raise StockError("Carton déjà lié à une autre expédition.")
        if shipment and carton.shipment is None:
            carton.shipment = shipment
        if current_location is not None:
            carton.current_location = current_location
        carton.save()
    length_cm, width_cm, height_cm = _resolve_carton_dimensions(carton_size=carton_size)
    updates = {}
    if carton.length_cm is None and length_cm is not None:
        updates["length_cm"] = length_cm
        carton.length_cm = length_cm
    if carton.width_cm is None and width_cm is not None:
        updates["width_cm"] = width_cm
        carton.width_cm = width_cm
    if carton.height_cm is None and height_cm is not None:
        updates["height_cm"] = height_cm
        carton.height_cm = height_cm
    if updates:
        carton.save(update_fields=list(updates))
    return carton


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


def _get_required(model, object_id, label):
    if object_id is None:
        raise StockError(f"{label} requis.")
    obj = model.objects.filter(pk=object_id).first()
    if obj is None:
        raise StockError(f"{label} introuvable.")
    return obj


def _get_optional(model, object_id, label):
    if object_id is None:
        return None
    obj = model.objects.filter(pk=object_id).first()
    if obj is None:
        raise StockError(f"{label} introuvable.")
    return obj


def receive_stock_from_input(*, user, payload: ReceiveStockInput):
    payload.validate()
    product = _get_required(Product, payload.product_id, "Produit")
    location = _get_required(Location, payload.location_id, "Emplacement")
    source_receipt = _get_optional(Receipt, payload.source_receipt_id, "Reception")
    return receive_stock(
        user=user,
        product=product,
        quantity=payload.quantity,
        location=location,
        lot_code=payload.lot_code or "",
        received_on=payload.received_on,
        expires_on=payload.expires_on,
        status=payload.status or None,
        storage_conditions=payload.storage_conditions,
        source_receipt=source_receipt,
    )


def pack_carton_from_input(*, user, payload: PackCartonInput):
    payload.validate()
    product = _get_required(Product, payload.product_id, "Produit")
    carton = _get_optional(Carton, payload.carton_id, "Carton")
    shipment = _get_optional(Shipment, payload.shipment_id, "Expédition")
    current_location = _get_optional(Location, payload.current_location_id, "Emplacement")
    return pack_carton(
        user=user,
        product=product,
        quantity=payload.quantity,
        carton=carton,
        carton_code=payload.carton_code,
        shipment=shipment,
        current_location=current_location,
    )


@transaction.atomic
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
        raise StockError("Quantité invalide.")
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


@transaction.atomic
def receive_receipt_line(*, user, line: ReceiptLine):
    if line.received_lot_id:
        raise StockError("Ligne de réception déjà traitée.")
    if line.receipt.status == ReceiptStatus.CANCELLED:
        raise StockError("Réception annulée.")
    location = line.location or line.product.default_location
    if location is None:
        raise StockError("Emplacement requis pour réception.")
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


@transaction.atomic
def adjust_stock(*, user, lot: ProductLot, delta: int, reason_code: str, reason_notes: str):
    if delta == 0:
        raise StockError("Quantité nulle.")
    if lot.quantity_on_hand + delta < 0:
        raise StockError("Stock insuffisant pour ajustement.")
    if delta < 0 and lot.quantity_on_hand + delta < lot.quantity_reserved:
        raise StockError("Ajustement impossible: stock réservé.")
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


@transaction.atomic
def transfer_stock(*, user, lot: ProductLot, to_location):
    if lot.location_id == to_location.id:
        raise StockError("Le lot est déjà à cet emplacement.")
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
        raise StockError("Quantité invalide.")
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


@transaction.atomic
def pack_carton(
    *,
    user,
    product: Product,
    quantity: int,
    carton: Carton | None = None,
    carton_code: str | None = None,
    shipment: Shipment | None = None,
    current_location=None,
    carton_size=None,
):
    carton = _prepare_carton(
        user=user,
        carton=carton,
        shipment=shipment,
        current_location=current_location,
        carton_code=carton_code,
        carton_size=carton_size,
    )

    movement_type = MovementType.OUT if shipment else MovementType.PRECONDITION
    try:
        component_requirements = get_component_quantities(product, quantity=quantity)
    except KitCycleError as exc:
        raise StockError("Composition de kit invalide: cycle detecte.") from exc
    if not component_requirements:
        raise StockError("Le kit ne contient aucun composant valide.")
    components_by_id = {
        component.id: component
        for component in Product.objects.filter(id__in=component_requirements.keys())
    }
    for component_id, component_quantity in component_requirements.items():
        component = components_by_id.get(component_id)
        if component is None:
            raise StockError("Composant de kit introuvable.")
        consumed = consume_stock(
            user=user,
            product=component,
            quantity=component_quantity,
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
    target_status = None
    status_reason = ""
    if shipment is not None:
        target_status = CartonStatus.ASSIGNED
        status_reason = "stock_pack_assign"
    elif carton.status == CartonStatus.DRAFT:
        target_status = CartonStatus.PICKING
        status_reason = "stock_pack_start_picking"
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
def unpack_carton(*, user, carton: Carton):
    shipment = carton.shipment
    if shipment and getattr(shipment, "is_disputed", False):
        raise StockError("Impossible de modifier une expédition en litige.")
    if shipment and shipment.status in {
        ShipmentStatus.PLANNED,
        ShipmentStatus.SHIPPED,
        ShipmentStatus.RECEIVED_CORRESPONDENT,
        ShipmentStatus.DELIVERED,
    }:
        raise StockError("Impossible de modifier une expédition expédiée ou livrée.")
    if carton.status == CartonStatus.SHIPPED:
        raise StockError("Impossible de modifier un carton expédié.")
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
    carton.shipment = None
    set_carton_status(
        carton=carton,
        new_status=CartonStatus.DRAFT,
        update_fields=["shipment"],
        reason="stock_unpack",
        user=user,
    )
    if shipment is not None:
        sync_shipment_ready_state(shipment)
    return carton
