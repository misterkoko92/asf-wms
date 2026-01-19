from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import Receipt, ReceiptHorsFormat, ReceiptStatus, ReceiptType
from .scan_helpers import parse_int, resolve_default_warehouse, resolve_product
from .services import StockError, receive_receipt_line


def get_receipt_lines_state(receipt):
    if not receipt:
        return [], 0
    receipt_lines = list(
        receipt.lines.select_related("product", "location", "received_lot").all()
    )
    pending_count = sum(1 for line in receipt_lines if not line.received_lot_id)
    return receipt_lines, pending_count


def build_hors_format_lines(request):
    line_count = parse_int(request.POST.get("hors_format_count")) or 0
    line_count = max(0, line_count)
    line_values = []
    for index in range(1, line_count + 1):
        description = (request.POST.get(f"line_{index}_description") or "").strip()
        line_values.append({"description": description})
    return line_count, line_values


def handle_receipt_association_post(
    request,
    *,
    create_form,
    line_values,
    line_count,
):
    line_errors = {}
    if create_form.is_valid():
        for index, line in enumerate(line_values, start=1):
            if not line["description"]:
                line_errors[str(index)] = ["Description requise."]

        if line_errors:
            create_form.add_error(None, "Renseignez les descriptions hors format.")
        else:
            warehouse = resolve_default_warehouse()
            if not warehouse:
                create_form.add_error(None, "Aucun entrepot configure.")
            else:
                receipt = Receipt.objects.create(
                    receipt_type=ReceiptType.ASSOCIATION,
                    status=ReceiptStatus.DRAFT,
                    source_contact=create_form.cleaned_data["source_contact"],
                    carrier_contact=create_form.cleaned_data["carrier_contact"],
                    received_on=create_form.cleaned_data["received_on"],
                    carton_count=create_form.cleaned_data["carton_count"],
                    hors_format_count=line_count or None,
                    warehouse=warehouse,
                    created_by=request.user,
                )
                for index, line in enumerate(line_values, start=1):
                    if line["description"]:
                        ReceiptHorsFormat.objects.create(
                            receipt=receipt,
                            line_number=index,
                            description=line["description"],
                        )
                messages.success(
                    request,
                    f"Reception association enregistree (ref {receipt.reference}).",
                )
                return redirect("scan:scan_receive_association"), line_errors
    return None, line_errors


def handle_receipt_action(
    request,
    *,
    action,
    select_form,
    create_form,
    line_form,
    selected_receipt,
):
    if action == "select_receipt" and select_form.is_valid():
        receipt = select_form.cleaned_data["receipt"]
        return redirect(f"{reverse('scan:scan_receive')}?receipt={receipt.id}"), None, None

    if action == "create_receipt" and create_form.is_valid():
        receipt = Receipt.objects.create(
            reference="",
            receipt_type=create_form.cleaned_data["receipt_type"],
            status=ReceiptStatus.DRAFT,
            source_contact=create_form.cleaned_data["source_contact"],
            carrier_contact=create_form.cleaned_data["carrier_contact"],
            origin_reference=create_form.cleaned_data["origin_reference"],
            carrier_reference=create_form.cleaned_data["carrier_reference"],
            received_on=create_form.cleaned_data["received_on"],
            warehouse=create_form.cleaned_data["warehouse"],
            created_by=request.user,
            notes=create_form.cleaned_data["notes"] or "",
        )
        messages.success(
            request,
            f"Reception creee: {receipt.reference or f'Reception {receipt.id}'}",
        )
        return redirect(f"{reverse('scan:scan_receive')}?receipt={receipt.id}"), None, None

    if action == "add_line":
        if not selected_receipt:
            line_form.add_error(None, "Selectionnez une reception.")
        elif selected_receipt.status != ReceiptStatus.DRAFT:
            line_form.add_error(None, "Reception deja cloturee.")
        elif line_form.is_valid():
            product = resolve_product(line_form.cleaned_data["product_code"])
            if not product:
                line_form.add_error("product_code", "Produit introuvable.")
            else:
                location = (
                    line_form.cleaned_data["location"] or product.default_location
                )
                if location is None:
                    line_form.add_error(
                        "location",
                        "Emplacement requis ou definir un emplacement par defaut.",
                    )
                else:
                    line = selected_receipt.lines.create(
                        product=product,
                        quantity=line_form.cleaned_data["quantity"],
                        lot_code=line_form.cleaned_data["lot_code"] or "",
                        expires_on=line_form.cleaned_data["expires_on"],
                        lot_status=line_form.cleaned_data["lot_status"] or "",
                        location=location,
                        storage_conditions=(
                            line_form.cleaned_data["storage_conditions"]
                            or product.storage_conditions
                        ),
                    )
                    if line_form.cleaned_data["receive_now"]:
                        try:
                            receive_receipt_line(user=request.user, line=line)
                            messages.success(
                                request,
                                f"Ligne receptionnee: {product.name} ({line.quantity}).",
                            )
                        except StockError as exc:
                            line_form.add_error(None, str(exc))
                            receipt_lines, pending_count = get_receipt_lines_state(
                                selected_receipt
                            )
                            return None, receipt_lines, pending_count
                    else:
                        messages.success(
                            request,
                            f"Ligne ajoutee: {product.name} ({line.quantity}).",
                        )
                    return (
                        redirect(
                            f"{reverse('scan:scan_receive')}?receipt={selected_receipt.id}"
                        ),
                        None,
                        None,
                    )

    if action == "receive_lines" and selected_receipt:
        processed = 0
        errors = []
        for line in selected_receipt.lines.select_related("product"):
            if line.received_lot_id:
                continue
            try:
                receive_receipt_line(user=request.user, line=line)
                processed += 1
            except StockError as exc:
                errors.append(str(exc))
        if processed:
            messages.success(request, f"{processed} ligne(s) receptionnee(s).")
        for error in errors:
            messages.error(request, error)
        return (
            redirect(f"{reverse('scan:scan_receive')}?receipt={selected_receipt.id}"),
            None,
            None,
        )

    return None, None, None
