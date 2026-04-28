from django.utils import timezone

from .models import Product
from .scan_helpers import resolve_product
from .services import receive_stock

PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY = "preparateur_rangement_batch"
PREPARATEUR_RANGEMENT_BATCH_LIMIT = 5
NO_LOCATION_MESSAGE = "Pas d'emplacement défini, demander conseil"


class PreparateurRangementError(ValueError):
    pass


def get_preparateur_rangement_batch(request):
    return list(request.session.get(PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY) or [])


def clear_preparateur_rangement_batch(request):
    request.session.pop(PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY, None)
    request.session.modified = True


def _save_preparateur_rangement_batch(request, batch):
    request.session[PREPARATEUR_RANGEMENT_BATCH_SESSION_KEY] = batch
    request.session.modified = True


def _find_batch_index(batch, product):
    product_id = int(product.id)
    for index, item in enumerate(batch):
        if int(item.get("product_id") or 0) == product_id:
            return index
    return None


def _build_location_label(product):
    location = product.default_location
    return str(location) if location is not None else NO_LOCATION_MESSAGE


def _build_batch_item(*, product, quantity, stock_updated):
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "quantity": int(quantity),
        "location_label": _build_location_label(product),
        "stock_updated": bool(stock_updated),
        "stock_status_label": "Stock ajouté" if stock_updated else "Stock non modifié",
    }


def resolve_preparateur_rangement_product(code):
    return resolve_product(code, include_kits=False)


def add_product_to_preparateur_rangement_batch(
    request,
    *,
    product,
    quantity,
    stock_already_updated=False,
):
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise PreparateurRangementError("Quantité invalide.")

    batch = get_preparateur_rangement_batch(request)
    existing_index = _find_batch_index(batch, product)
    if existing_index is None and len(batch) >= PREPARATEUR_RANGEMENT_BATCH_LIMIT:
        raise PreparateurRangementError("Batch limité à 5 produits.")

    location = product.default_location
    stock_updated = bool(stock_already_updated)
    if location is not None and not stock_already_updated:
        receive_stock(
            user=request.user,
            product=product,
            quantity=quantity,
            location=location,
            received_on=timezone.localdate(),
        )
        stock_updated = True

    if existing_index is None:
        item = _build_batch_item(
            product=product,
            quantity=quantity,
            stock_updated=stock_updated,
        )
        batch.append(item)
    else:
        item = batch[existing_index]
        item["quantity"] = int(item.get("quantity") or 0) + quantity
        item["location_label"] = _build_location_label(product)
        item["stock_updated"] = bool(item.get("stock_updated")) or stock_updated
        item["stock_status_label"] = (
            "Stock ajouté" if item["stock_updated"] else "Stock non modifié"
        )

    _save_preparateur_rangement_batch(request, batch)
    return item


def add_created_product_to_preparateur_rangement_batch(request, *, product, quantity):
    product = Product.objects.select_related("default_location", "default_location__warehouse").get(
        pk=product.pk
    )
    return add_product_to_preparateur_rangement_batch(
        request,
        product=product,
        quantity=quantity,
        stock_already_updated=True,
    )
