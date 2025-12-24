from django.conf import settings

from .models import CartonItem


def build_org_context():
    return {
        "org_name": getattr(settings, "ORG_NAME", "ORG_NAME"),
        "org_address": getattr(settings, "ORG_ADDRESS", ""),
        "org_contact": getattr(settings, "ORG_CONTACT", ""),
        "org_signatory": getattr(settings, "ORG_SIGNATORY", ""),
    }


def build_shipment_item_rows(shipment):
    items = (
        CartonItem.objects.filter(carton__shipment=shipment)
        .select_related("product_lot", "product_lot__product")
        .order_by("product_lot__product__name")
    )
    rows = []
    for item in items:
        rows.append(
            {
                "product": item.product_lot.product.name,
                "lot": item.product_lot.lot_code or "N/A",
                "quantity": item.quantity,
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


def build_carton_rows(cartons):
    rows = []
    for carton in cartons:
        items = carton.cartonitem_set.select_related(
            "product_lot", "product_lot__product"
        )
        weight_total = 0
        volume_total = 0
        for item in items:
            product = item.product_lot.product
            if product.weight_g:
                weight_total += product.weight_g * item.quantity
            if product.volume_cm3:
                volume_total += product.volume_cm3 * item.quantity
        rows.append(
            {
                "code": carton.code,
                "weight_g": weight_total,
                "volume_cm3": volume_total,
            }
        )
    return rows
