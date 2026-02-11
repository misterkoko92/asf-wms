from django.contrib import messages
from django.shortcuts import redirect

from .models import Receipt, ReceiptStatus, ReceiptType
from .scan_helpers import resolve_default_warehouse


def handle_pallet_create_post(request, *, form):
    if not form.is_valid():
        return None
    warehouse = resolve_default_warehouse()
    if not warehouse:
        form.add_error(None, "Aucun entrepôt configuré.")
        return None
    receipt = Receipt.objects.create(
        receipt_type=ReceiptType.PALLET,
        status=ReceiptStatus.DRAFT,
        source_contact=form.cleaned_data["source_contact"],
        carrier_contact=form.cleaned_data["carrier_contact"],
        received_on=form.cleaned_data["received_on"],
        pallet_count=form.cleaned_data["pallet_count"],
        transport_request_date=form.cleaned_data["transport_request_date"],
        warehouse=warehouse,
        created_by=request.user,
    )
    messages.success(
        request,
        f"Réception palette enregistrée (ref {receipt.reference}).",
    )
    return redirect("scan:scan_receive_pallet")
