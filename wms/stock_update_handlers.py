from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from .models import Receipt, ReceiptStatus, ReceiptType
from .services import StockError, receive_stock


def handle_stock_update_post(request, *, form):
    if not form.is_valid():
        return None
    product = getattr(form, "product", None)
    location = product.default_location if product else None
    if location is None:
        form.add_error(None, "Emplacement requis pour ce produit.")
        return None
    try:
        source_receipt = None
        donor_contact = form.cleaned_data.get("donor_contact")
        if donor_contact:
            source_receipt = Receipt.objects.create(
                receipt_type=ReceiptType.DONATION,
                status=ReceiptStatus.RECEIVED,
                source_contact=donor_contact,
                received_on=timezone.localdate(),
                warehouse=location.warehouse,
                created_by=request.user,
                notes="Auto MAJ stock",
            )
        receive_stock(
            user=request.user,
            product=product,
            quantity=form.cleaned_data["quantity"],
            location=location,
            lot_code=form.cleaned_data["lot_code"] or "",
            received_on=timezone.localdate(),
            expires_on=form.cleaned_data["expires_on"],
            source_receipt=source_receipt,
        )
        messages.success(request, "Stock mis a jour.")
        return redirect("scan:scan_stock_update")
    except StockError as exc:
        form.add_error(None, str(exc))
        return None
