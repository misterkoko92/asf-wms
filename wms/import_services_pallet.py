from django.utils import timezone

from contacts.models import Contact

from .import_services_locations import resolve_listing_location
from .import_services_products import import_product_row
from .import_utils import parse_int
from .models import Product, Receipt, ReceiptLine, ReceiptStatus, ReceiptType
from .scan_helpers import resolve_product
from .services import StockError, receive_receipt_line

def apply_pallet_listing_import(
    row_payloads,
    *,
    user,
    warehouse,
    receipt_meta,
):
    receipt = None
    created = 0
    skipped = 0
    errors = []
    for payload in row_payloads:
        if not payload.get("apply"):
            skipped += 1
            continue
        row_index = payload.get("row_index")
        row_data = payload.get("row_data") or {}
        selection = (payload.get("selection") or "").strip()
        override_code = (payload.get("override_code") or "").strip()

        quantity = parse_int(row_data.get("quantity"))
        if not quantity or quantity <= 0:
            errors.append(f"Ligne {row_index}: quantité invalide.")
            continue

        product = None
        if override_code:
            product = resolve_product(override_code)
            if not product:
                errors.append(
                    f"Ligne {row_index}: produit introuvable pour {override_code}."
                )
                continue
        if not product and selection.startswith("product:"):
            product_id = selection.split("product:", 1)[1]
            if product_id.isdigit():
                product = Product.objects.filter(id=int(product_id)).first()
            if not product:
                errors.append(f"Ligne {row_index}: produit cible introuvable.")
                continue
        if not product and selection == "new":
            new_row = dict(row_data)
            new_row.pop("quantity", None)
            try:
                product, _created, _warnings = import_product_row(
                    new_row,
                    user=user,
                )
            except ValueError as exc:
                errors.append(f"Ligne {row_index}: {exc}")
                continue
        if not product:
            errors.append(f"Ligne {row_index}: produit non déterminé.")
            continue

        try:
            location = resolve_listing_location(row_data, warehouse)
            if location is None:
                location = product.default_location
            if location is None:
                raise ValueError("Emplacement requis pour réception.")
            if receipt is None:
                receipt = Receipt.objects.create(
                    receipt_type=ReceiptType.PALLET,
                    status=ReceiptStatus.DRAFT,
                    source_contact=Contact.objects.filter(
                        id=receipt_meta.get("source_contact_id")
                    ).first(),
                    carrier_contact=Contact.objects.filter(
                        id=receipt_meta.get("carrier_contact_id")
                    ).first(),
                    received_on=receipt_meta.get("received_on") or timezone.localdate(),
                    pallet_count=receipt_meta.get("pallet_count") or 0,
                    transport_request_date=receipt_meta.get("transport_request_date")
                    or None,
                    warehouse=warehouse,
                    created_by=user,
                )
            line = ReceiptLine.objects.create(
                receipt=receipt,
                product=product,
                quantity=quantity,
                location=location,
                storage_conditions=product.storage_conditions or "",
            )
            receive_receipt_line(user=user, line=line)
            created += 1
        except (ValueError, StockError) as exc:
            errors.append(f"Ligne {row_index}: {exc}")
    return created, skipped, errors, receipt
