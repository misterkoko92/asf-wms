from django.conf import settings

from contacts.models import Contact, ContactType

from .contact_filters import contacts_with_tags
from .models import CartonItem


def build_org_context():
    return {
        "org_name": getattr(settings, "ORG_NAME", "ORG_NAME"),
        "org_address": getattr(settings, "ORG_ADDRESS", ""),
        "org_contact": getattr(settings, "ORG_CONTACT", ""),
        "org_signatory": getattr(settings, "ORG_SIGNATORY", ""),
    }


def build_shipment_item_rows(shipment, *, carton_labels=None):
    items = (
        CartonItem.objects.filter(carton__shipment=shipment)
        .select_related("carton", "product_lot", "product_lot__product")
        .order_by("carton__code", "product_lot__product__name")
    )
    rows = []
    for item in items:
        carton_label = None
        if carton_labels is not None:
            carton_label = carton_labels.get(item.carton_id)
        rows.append(
            {
                "product": item.product_lot.product.name,
                "lot": item.product_lot.lot_code or "N/A",
                "quantity": item.quantity,
                "expires_on": item.product_lot.expires_on,
                "carton_label": carton_label,
            }
        )
    return rows


def build_shipment_aggregate_rows(shipment):
    rows = {}
    items = CartonItem.objects.filter(carton__shipment=shipment).select_related(
        "product_lot", "product_lot__product"
    )
    for item in items:
        product = item.product_lot.product
        entry = rows.get(product.id)
        if not entry:
            entry = {
                "product": product.name,
                "quantity": 0,
                "lots": set(),
            }
            rows[product.id] = entry
        entry["quantity"] += item.quantity
        entry["lots"].add(item.product_lot.lot_code or "N/A")
    ordered = sorted(rows.values(), key=lambda row: row["product"])
    for row in ordered:
        row["lots"] = ", ".join(sorted(row["lots"]))
    return ordered


def build_carton_rows(cartons, *, default_format=None):
    rows = []
    for carton in cartons:
        items = carton.cartonitem_set.select_related(
            "product_lot", "product_lot__product"
        )
        weight_total = 0
        volume_total = None
        for item in items:
            product = item.product_lot.product
            if product.weight_g:
                weight_total += product.weight_g * item.quantity
        length_cm = carton.length_cm or (default_format.length_cm if default_format else None)
        width_cm = carton.width_cm or (default_format.width_cm if default_format else None)
        height_cm = carton.height_cm or (default_format.height_cm if default_format else None)
        if length_cm and width_cm and height_cm:
            volume_total = length_cm * width_cm * height_cm
        rows.append(
            {
                "carton_id": carton.id,
                "code": carton.code,
                "weight_g": weight_total,
                "volume_cm3": volume_total,
                "length_cm": length_cm,
                "width_cm": width_cm,
                "height_cm": height_cm,
            }
        )
    return rows


def compute_weight_total_g(carton_rows):
    return sum(row.get("weight_g") or 0 for row in carton_rows)


def build_shipment_type_labels(shipment):
    items = (
        CartonItem.objects.filter(carton__shipment=shipment)
        .select_related("product_lot__product__category__parent")
        .order_by("id")
    )
    roots = set()
    for item in items:
        category = item.product_lot.product.category
        while category and category.parent_id:
            category = category.parent
        if category:
            roots.add(category.name)
    return ", ".join(sorted(roots)) if roots else "-"


def _resolve_contact(tag_names, fallback_name):
    if not fallback_name:
        return None
    contact = contacts_with_tags(tag_names).filter(name__iexact=fallback_name).first()
    if contact:
        return contact
    return Contact.objects.filter(name__iexact=fallback_name).first()


def _format_contact_address(address):
    if not address:
        return ""
    lines = [address.address_line1]
    if address.address_line2:
        lines.append(address.address_line2)
    city_line = " ".join(part for part in [address.postal_code, address.city] if part)
    if city_line:
        lines.append(city_line)
    if address.region:
        lines.append(address.region)
    if address.country:
        lines.append(address.country)
    return "\n".join(lines)


def build_contact_info(tag_names, fallback_name):
    contact = _resolve_contact(tag_names, fallback_name)
    if contact:
        address = (
            contact.addresses.filter(is_default=True).first()
            or contact.addresses.first()
        )
        phone = contact.phone or (address.phone if address else "")
        email = contact.email or (address.email if address else "")
        if contact.contact_type == ContactType.PERSON:
            person_name = contact.name
            company_name = ""
        else:
            person_name = contact.notes or ""
            company_name = contact.name
        return {
            "name": contact.name,
            "person": person_name,
            "company": company_name,
            "address": _format_contact_address(address),
            "phone": phone,
            "email": email,
        }
    return {
        "name": fallback_name or "",
        "person": fallback_name or "",
        "company": fallback_name or "",
        "address": "",
        "phone": "",
        "email": "",
    }
