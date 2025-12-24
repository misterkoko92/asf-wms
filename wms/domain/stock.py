import secrets
from dataclasses import dataclass

from django.db import connection, transaction
from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.utils import timezone

from .dto import PackCartonInput, ReceiveStockInput
from ..models import (
    Carton,
    CartonItem,
    CartonStatus,
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


class StockError(ValueError):
    pass


@dataclass
class StockConsumeResult:
    lot: ProductLot
    quantity: int


def generate_carton_code() -> str:
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"C-{timestamp}-{secrets.token_hex(2).upper()}"


def _prepare_carton(
    *,
    user,
    carton: Carton | None,
    shipment: Shipment | None,
    current_location=None,
    carton_code: str | None = None,
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
            status=CartonStatus.ASSIGNED if shipment else CartonStatus.DRAFT,
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
            carton.status = CartonStatus.ASSIGNED if shipment else CartonStatus.DRAFT
        carton.save()
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
    shipment = _get_optional(Shipment, payload.shipment_id, "Expedition")
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


@transaction.atomic
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


@transaction.atomic
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


@transaction.atomic
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
):
    carton = _prepare_carton(
        user=user,
        carton=carton,
        shipment=shipment,
        current_location=current_location,
        carton_code=carton_code,
    )

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


@transaction.atomic
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
