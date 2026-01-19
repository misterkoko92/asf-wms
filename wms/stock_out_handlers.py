from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect

from .models import MovementType
from .scan_helpers import resolve_product, resolve_shipment
from .services import StockError, consume_stock


def handle_stock_out_post(request, *, form):
    if not form.is_valid():
        return None
    product = resolve_product(form.cleaned_data["product_code"])
    if not product:
        form.add_error("product_code", "Produit introuvable.")
        return None

    shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
    if form.cleaned_data["shipment_reference"] and not shipment:
        form.add_error("shipment_reference", "Expedition introuvable.")
        return None

    try:
        with transaction.atomic():
            consume_stock(
                user=request.user,
                product=product,
                quantity=form.cleaned_data["quantity"],
                movement_type=MovementType.OUT,
                shipment=shipment,
                reason_code=form.cleaned_data["reason_code"] or "scan_out",
                reason_notes=form.cleaned_data["reason_notes"] or "",
            )
        messages.success(
            request,
            f"Suppression enregistree: {product.name} ({form.cleaned_data['quantity']}).",
        )
        return redirect("scan:scan_out")
    except StockError as exc:
        form.add_error(None, str(exc))
        return None
