import math
import hashlib
from collections import defaultdict

from .models import Carton, CartonStatus, Document, DocumentType, OrderDocumentType
from .portal_helpers import get_association_profile, get_contact_address
from .scan_helpers import (
    get_carton_volume_cm3,
    get_product_volume_cm3,
    get_product_weight_g,
    parse_int,
)


def build_order_creator_info(order):
    contact = None
    if order.created_by:
        profile = get_association_profile(order.created_by)
        if profile:
            contact = profile.contact
    if not contact:
        contact = order.association_contact or order.recipient_contact

    name = "-"
    phone = ""
    email = ""
    if contact:
        name = contact.name
        phone = contact.phone or ""
        email = contact.email or ""
        address = get_contact_address(contact)
        if address:
            phone = phone or address.phone or ""
            email = email or address.email or ""
    if order.created_by and name == "-":
        name = (
            order.created_by.get_full_name()
            or order.created_by.username
            or order.created_by.email
            or "-"
        )
    if order.created_by and not email:
        email = order.created_by.email or ""
    return {"name": name, "phone": phone, "email": email}


def attach_order_documents_to_shipment(order, shipment):
    if not order or not shipment:
        return
    wanted_types = {
        OrderDocumentType.DONATION_ATTESTATION,
        OrderDocumentType.HUMANITARIAN_ATTESTATION,
    }
    existing_files = set(
        Document.objects.filter(
            shipment=shipment, doc_type=DocumentType.ADDITIONAL
        ).values_list("file", flat=True)
    )
    for doc in order.documents.filter(doc_type__in=wanted_types):
        if not doc.file:
            continue
        if doc.file.name in existing_files:
            continue
        Document.objects.create(
            shipment=shipment,
            doc_type=DocumentType.ADDITIONAL,
            file=doc.file,
        )


def estimate_cartons_for_line(*, product, quantity, carton_format):
    if not carton_format:
        return None
    weight_g = get_product_weight_g(product)
    volume = get_product_volume_cm3(product)
    carton_volume = get_carton_volume_cm3(
        {
            "length_cm": carton_format.length_cm,
            "width_cm": carton_format.width_cm,
            "height_cm": carton_format.height_cm,
        }
    )
    max_by_volume = None
    if volume and volume > 0 and carton_volume and carton_volume > 0:
        max_by_volume = int(carton_volume // volume)
        max_by_volume = max(1, max_by_volume)
    max_by_weight = None
    if weight_g and weight_g > 0 and carton_format.max_weight_g:
        max_by_weight = int(carton_format.max_weight_g // weight_g)
        max_by_weight = max(1, max_by_weight)
    if max_by_volume and max_by_weight:
        max_units = min(max_by_volume, max_by_weight)
    else:
        max_units = max_by_volume or max_by_weight
    if not max_units:
        return None
    return int(math.ceil(quantity / max_units))


def build_carton_format_data(carton_format):
    if not carton_format:
        return None
    return {
        "length_cm": float(carton_format.length_cm),
        "width_cm": float(carton_format.width_cm),
        "height_cm": float(carton_format.height_cm),
        "max_weight_g": float(carton_format.max_weight_g),
        "name": carton_format.name,
    }


def build_order_line_items(
    post_data, *, product_options, product_by_id, available_by_id
):
    line_items = []
    line_errors = {}
    line_quantities = {}
    for item in product_options:
        product_id = item.get("id")
        if not product_id:
            continue
        raw_qty = (post_data.get(f"product_{product_id}_qty") or "").strip()
        if raw_qty:
            line_quantities[str(product_id)] = raw_qty
        if not raw_qty:
            continue
        quantity = parse_int(raw_qty)
        if quantity is None or quantity <= 0:
            line_errors[str(product_id)] = "Quantité invalide."
            continue
        available = available_by_id.get(product_id, 0)
        if quantity > available:
            line_errors[str(product_id)] = "Stock insuffisant."
            continue
        product = product_by_id.get(product_id)
        if product:
            line_items.append((product, quantity))
    return line_items, line_quantities, line_errors


def build_order_product_rows(
    product_options, product_by_id, line_quantities, carton_format
):
    total_estimated_cartons = 0
    product_rows = []
    for item in product_options:
        product_id = item.get("id")
        if not product_id:
            continue
        quantity_raw = line_quantities.get(str(product_id), "")
        quantity_value = parse_int(quantity_raw) if quantity_raw else None
        estimate = None
        product = product_by_id.get(product_id)
        if product and quantity_value and quantity_value > 0:
            estimate = estimate_cartons_for_line(
                product=product,
                quantity=quantity_value,
                carton_format=carton_format,
            )
            if estimate:
                total_estimated_cartons += estimate
        product_rows.append(
            {
                "id": product_id,
                "name": item.get("name"),
                "available_stock": int(item.get("available_stock") or 0),
                "quantity": quantity_raw,
                "estimate": estimate,
            }
        )
    if total_estimated_cartons <= 0:
        total_estimated_cartons = None
    return product_rows, total_estimated_cartons


def _ready_carton_signature(*, product_lines, expires_on):
    line_signature = "|".join(
        f"{line['product_id']}:{line['quantity']}" for line in product_lines
    )
    expires_signature = expires_on.isoformat() if expires_on else ""
    return f"{line_signature}|{expires_signature}"


def build_ready_carton_rows(*, selected_quantities=None, line_errors=None):
    selected_quantities = selected_quantities or {}
    line_errors = line_errors or {}
    cartons = (
        Carton.objects.filter(status=CartonStatus.PACKED, shipment__isnull=True)
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code", "id")
    )

    grouped = {}
    for carton in cartons:
        product_qty_by_id = defaultdict(int)
        product_name_by_id = {}
        expires_dates = []
        for item in carton.cartonitem_set.all():
            product = item.product_lot.product
            product_qty_by_id[product.id] += item.quantity
            product_name_by_id[product.id] = product.name or "-"
            if item.product_lot.expires_on:
                expires_dates.append(item.product_lot.expires_on)
        if not product_qty_by_id:
            continue

        product_lines = [
            {
                "product_id": product_id,
                "product_name": product_name_by_id.get(product_id, "-"),
                "quantity": quantity,
            }
            for product_id, quantity in sorted(
                product_qty_by_id.items(),
                key=lambda pair: (
                    (product_name_by_id.get(pair[0]) or "").lower(),
                    pair[0],
                ),
            )
        ]
        expires_on = min(expires_dates) if expires_dates else None
        signature = _ready_carton_signature(
            product_lines=product_lines,
            expires_on=expires_on,
        )
        group = grouped.setdefault(
            signature,
            {
                "signature": signature,
                "product_lines": product_lines,
                "expires_on": expires_on,
                "carton_ids": [],
            },
        )
        group["carton_ids"].append(carton.id)

    rows = []
    for group in grouped.values():
        row_key = hashlib.sha256(
            group["signature"].encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:16]
        rows.append(
            {
                "row_key": row_key,
                "product_lines": group["product_lines"],
                "expires_on": group["expires_on"],
                "available_stock": len(group["carton_ids"]),
                "carton_ids": group["carton_ids"],
                "quantity": selected_quantities.get(row_key, ""),
                "line_error": line_errors.get(row_key, ""),
            }
        )
    rows.sort(
        key=lambda row: (
            " | ".join(
                f"{line['product_name']}:{line['quantity']}"
                for line in row["product_lines"]
            ).lower(),
            row["expires_on"] or "",
        )
    )
    return rows


def build_ready_carton_selection(post_data, *, ready_carton_rows):
    selected_carton_ids = []
    line_quantities = {}
    line_errors = {}
    selected_total = 0
    for row in ready_carton_rows:
        row_key = row.get("row_key")
        if not row_key:
            continue
        raw_qty = (post_data.get(f"ready_carton_{row_key}_qty") or "").strip()
        if raw_qty:
            line_quantities[row_key] = raw_qty
        if not raw_qty:
            continue
        quantity = parse_int(raw_qty)
        if quantity is None or quantity <= 0:
            line_errors[row_key] = "Quantité invalide."
            continue
        available_stock = int(row.get("available_stock") or 0)
        if quantity > available_stock:
            line_errors[row_key] = "Stock insuffisant."
            continue
        selected_total += quantity
        selected_carton_ids.extend(row.get("carton_ids", [])[:quantity])
    return selected_carton_ids, line_quantities, line_errors, selected_total


def build_order_line_estimates(lines, carton_format, *, estimate_key="estimate"):
    line_rows = []
    total_estimated_cartons = 0
    for line in lines:
        estimate = estimate_cartons_for_line(
            product=line.product,
            quantity=line.quantity,
            carton_format=carton_format,
        )
        if estimate:
            total_estimated_cartons += estimate
        row = {
            "product": line.product.name,
            "quantity": line.quantity,
        }
        if estimate_key:
            row[estimate_key] = estimate
        line_rows.append(row)
    if total_estimated_cartons <= 0:
        total_estimated_cartons = None
    return line_rows, total_estimated_cartons
