from django.db import transaction
from django.utils import timezone

from .models import Location, MovementType, Product, ProductLot, StockMovement
from .scan_helpers import resolve_product
from .services import StockError, fefo_lots, receive_stock

PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY = "preparateur_rangement_batch"
PREPARATEUR_RANGEMENT_MODE_SESSION_KEY = "preparateur_rangement_mode"
PREPARATEUR_RANGEMENT_BATCH_LIMIT = 5
PREPARATEUR_RANGEMENT_MODE_RECEIPT = "receipt"
PREPARATEUR_RANGEMENT_MODE_TRANSFER = "transfer"
PREPARATEUR_RANGEMENT_MODES = {
    PREPARATEUR_RANGEMENT_MODE_RECEIPT: "Entrée en stock",
    PREPARATEUR_RANGEMENT_MODE_TRANSFER: "Déplacement de stock",
}
NO_LOCATION_MESSAGE = "Emplacement par défaut manquant"
PENDING_STOCK_MESSAGE = "En attente de validation"
TRANSFER_REASON_CODE = "preparateur_rangement_transfer"


class PreparateurRangementError(ValueError):
    pass


def get_preparateur_rangement_batch(request):
    return list(request.session.get(PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY) or [])


def get_preparateur_rangement_mode(request):
    mode = request.session.get(PREPARATEUR_RANGEMENT_MODE_SESSION_KEY) or ""
    if mode in PREPARATEUR_RANGEMENT_MODES:
        return mode
    batch = get_preparateur_rangement_batch(request)
    if batch:
        item_mode = batch[0].get("mode") or ""
        if item_mode in PREPARATEUR_RANGEMENT_MODES:
            return item_mode
    return ""


def set_preparateur_rangement_mode(request, mode):
    mode = _validate_mode(mode)
    current_mode = get_preparateur_rangement_mode(request)
    if current_mode and current_mode != mode:
        raise PreparateurRangementError("Terminez le batch avant de changer de mode.")
    request.session[PREPARATEUR_RANGEMENT_MODE_SESSION_KEY] = mode
    request.session.modified = True
    return mode


def clear_preparateur_rangement_batch(request):
    request.session.pop(PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY, None)
    request.session.pop(PREPARATEUR_RANGEMENT_MODE_SESSION_KEY, None)
    request.session.modified = True


def _save_preparateur_rangement_batch(request, batch, *, mode):
    if batch:
        request.session[PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY] = batch
        request.session[PREPARATEUR_RANGEMENT_MODE_SESSION_KEY] = mode
    else:
        request.session.pop(PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY, None)
        request.session.pop(PREPARATEUR_RANGEMENT_MODE_SESSION_KEY, None)
    request.session.modified = True


def _validate_mode(mode):
    mode = (mode or "").strip()
    if mode not in PREPARATEUR_RANGEMENT_MODES:
        raise PreparateurRangementError("Choisissez un mode de rangement.")
    return mode


def _find_batch_index(batch, product):
    product_id = int(product.id)
    for index, item in enumerate(batch):
        if int(item.get("product_id") or 0) == product_id:
            return index
    return None


def _build_location_label(product):
    location = product.default_location
    return str(location) if location is not None else NO_LOCATION_MESSAGE


def _transfer_lots_for_product(product, *, to_location, for_update=False):
    return fefo_lots(product, for_update=for_update).exclude(location=to_location)


def _available_quantity(lot):
    return max(0, int(lot.quantity_on_hand or 0) - int(lot.quantity_reserved or 0))


def _build_transfer_source_summary(product, *, quantity, to_location):
    if to_location is None:
        return "", False
    remaining = int(quantity)
    source_parts = []
    for lot in _transfer_lots_for_product(product, to_location=to_location):
        available = _available_quantity(lot)
        if available <= 0:
            continue
        take = min(remaining, available)
        source_parts.append(f"{lot.location}: {take}")
        remaining -= take
        if remaining <= 0:
            break
    return ", ".join(source_parts), remaining <= 0


def _build_batch_item(*, product, quantity, mode):
    destination = product.default_location
    source_summary = ""
    has_transfer_stock = True
    if mode == PREPARATEUR_RANGEMENT_MODE_TRANSFER:
        source_summary, has_transfer_stock = _build_transfer_source_summary(
            product,
            quantity=quantity,
            to_location=destination,
        )

    is_valid = destination is not None and has_transfer_stock
    if destination is None:
        stock_status_label = NO_LOCATION_MESSAGE
    elif not has_transfer_stock:
        stock_status_label = "Stock disponible insuffisant"
    else:
        stock_status_label = PENDING_STOCK_MESSAGE

    return {
        "product_id": product.id,
        "mode": mode,
        "mode_label": PREPARATEUR_RANGEMENT_MODES[mode],
        "sku": product.sku,
        "name": product.name,
        "quantity": int(quantity),
        "location_id": destination.id if destination is not None else None,
        "location_label": _build_location_label(product),
        "source_label": source_summary,
        "is_valid": bool(is_valid),
        "stock_updated": False,
        "stock_status_label": stock_status_label,
    }


def resolve_preparateur_rangement_product(code):
    return resolve_product(code, include_kits=False)


def _get_batch_mode(request, mode):
    if mode:
        return set_preparateur_rangement_mode(request, mode)
    current_mode = get_preparateur_rangement_mode(request)
    if current_mode:
        return current_mode
    return _validate_mode(mode)


def add_product_to_preparateur_rangement_batch(request, *, product, quantity, mode=None):
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise PreparateurRangementError("Quantité invalide.")

    mode = _get_batch_mode(request, mode)
    batch = get_preparateur_rangement_batch(request)
    existing_index = _find_batch_index(batch, product)
    if existing_index is None and len(batch) >= PREPARATEUR_RANGEMENT_BATCH_LIMIT:
        raise PreparateurRangementError("Batch limité à 5 produits.")

    if existing_index is None:
        item = _build_batch_item(product=product, quantity=quantity, mode=mode)
        batch.append(item)
    else:
        quantity += int(batch[existing_index].get("quantity") or 0)
        item = _build_batch_item(product=product, quantity=quantity, mode=mode)
        batch[existing_index] = item

    _save_preparateur_rangement_batch(request, batch, mode=mode)
    return item


def add_created_product_to_preparateur_rangement_batch(request, *, product, quantity, mode=None):
    product = Product.objects.select_related("default_location", "default_location__warehouse").get(
        pk=product.pk
    )
    return add_product_to_preparateur_rangement_batch(
        request,
        product=product,
        quantity=quantity,
        mode=mode or PREPARATEUR_RANGEMENT_MODE_RECEIPT,
    )


def refresh_preparateur_rangement_batch(request):
    batch = get_preparateur_rangement_batch(request)
    mode = get_preparateur_rangement_mode(request)
    if not batch or not mode:
        return batch
    products = {
        product.id: product
        for product in Product.objects.filter(
            id__in=[item.get("product_id") for item in batch]
        ).select_related("default_location", "default_location__warehouse")
    }
    refreshed = []
    for item in batch:
        product = products.get(int(item.get("product_id") or 0))
        if product is None:
            continue
        refreshed.append(
            _build_batch_item(
                product=product,
                quantity=int(item.get("quantity") or 0),
                mode=mode,
            )
        )
    _save_preparateur_rangement_batch(request, refreshed, mode=mode)
    return refreshed


def set_default_location_for_rangement_product(request, *, product_id, location_id):
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        raise PreparateurRangementError("Produit introuvable.")
    location = Location.objects.filter(pk=location_id).first()
    if location is None:
        raise PreparateurRangementError("Emplacement introuvable.")
    product.default_location = location
    product.save(update_fields=["default_location"])
    return refresh_preparateur_rangement_batch(request)


def _copy_lot_to_location(*, lot, quantity, to_location):
    return ProductLot.objects.create(
        product=lot.product,
        lot_code=lot.lot_code,
        expires_on=lot.expires_on,
        received_on=lot.received_on,
        status=lot.status,
        quantity_on_hand=quantity,
        quantity_reserved=0,
        location=to_location,
        source_receipt=lot.source_receipt,
        storage_conditions=lot.storage_conditions,
        quarantine_reason=lot.quarantine_reason,
        released_by=lot.released_by,
        released_at=lot.released_at,
    )


def _apply_transfer(*, user, product, quantity, to_location):
    remaining = int(quantity)
    moved = []
    for lot in _transfer_lots_for_product(product, to_location=to_location, for_update=True):
        available = _available_quantity(lot)
        if available <= 0:
            continue
        take = min(remaining, available)
        from_location = lot.location
        if take == lot.quantity_on_hand and lot.quantity_reserved == 0:
            lot.location = to_location
            lot.save(update_fields=["location"])
            moved_lot = lot
        else:
            lot.quantity_on_hand -= take
            lot.save(update_fields=["quantity_on_hand"])
            moved_lot = _copy_lot_to_location(
                lot=lot,
                quantity=take,
                to_location=to_location,
            )
        StockMovement.objects.create(
            movement_type=MovementType.TRANSFER,
            product=product,
            product_lot=moved_lot,
            quantity=take,
            from_location=from_location,
            to_location=to_location,
            reason_code=TRANSFER_REASON_CODE,
            created_by=user,
        )
        moved.append(moved_lot)
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        raise StockError("Stock disponible insuffisant pour le déplacement.")
    return moved


@transaction.atomic
def validate_preparateur_rangement_batch(request):
    batch = refresh_preparateur_rangement_batch(request)
    mode = get_preparateur_rangement_mode(request)
    if not batch:
        raise PreparateurRangementError("Aucun produit à valider.")
    if not mode:
        raise PreparateurRangementError("Choisissez un mode de rangement.")
    if any(item.get("location_id") is None for item in batch):
        raise PreparateurRangementError("Définissez les emplacements manquants avant validation.")
    if any(not item.get("is_valid") for item in batch):
        raise PreparateurRangementError("Corrigez les lignes bloquées avant validation.")

    products = {
        product.id: product
        for product in Product.objects.filter(
            id__in=[item.get("product_id") for item in batch]
        ).select_related("default_location", "default_location__warehouse")
    }
    for item in batch:
        product = products.get(int(item.get("product_id") or 0))
        if product is None:
            raise PreparateurRangementError("Produit introuvable.")
        if product.default_location is None:
            raise PreparateurRangementError(
                "Définissez les emplacements manquants avant validation."
            )
        quantity = int(item.get("quantity") or 0)
        if mode == PREPARATEUR_RANGEMENT_MODE_RECEIPT:
            receive_stock(
                user=request.user,
                product=product,
                quantity=quantity,
                location=product.default_location,
                received_on=timezone.localdate(),
            )
        elif mode == PREPARATEUR_RANGEMENT_MODE_TRANSFER:
            _apply_transfer(
                user=request.user,
                product=product,
                quantity=quantity,
                to_location=product.default_location,
            )
        else:
            raise PreparateurRangementError("Mode de rangement invalide.")

    clear_preparateur_rangement_batch(request)
    return True
