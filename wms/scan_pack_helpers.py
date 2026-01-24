from django.urls import reverse

from .models import Carton
from .scan_carton_helpers import get_carton_volume_cm3
from .scan_product_helpers import (

    build_product_group_key,
    build_product_label,
    get_product_volume_cm3,
    get_product_weight_g,
)


def build_pack_line_values(line_count, data=None):
    lines = []
    for index in range(1, line_count + 1):
        prefix = f"line_{index}_"
        lines.append(
            {
                "product_code": (data.get(prefix + "product_code") if data else "") or "",
                "quantity": (data.get(prefix + "quantity") if data else "") or "",
            }
        )
    return lines


def build_packing_bins(
    line_items,
    carton_size,
    *,
    apply_defaults=False,
    default_weight_g=5,
    default_volume_cm3=1,
):
    errors = []
    warnings = []
    if not carton_size:
        errors.append("Format de carton requis.")
        return None, errors, warnings

    carton_volume = get_carton_volume_cm3(carton_size)
    carton_volume_f = float(carton_volume)
    carton_weight_f = float(carton_size["max_weight_g"])

    items = []
    for line in line_items:
        product = line["product"]
        quantity = line["quantity"]
        weight_g = get_product_weight_g(product)
        volume = get_product_volume_cm3(product)
        volume_f = float(volume) if volume and volume > 0 else None

        if weight_g is None and volume_f is None:
            if apply_defaults:
                weight_g = default_weight_g
                volume_f = float(default_volume_cm3)
                warnings.append(
                    f"{product.name}: poids/volume manquants, valeurs par defaut appliquees."
                )
            else:
                errors.append(
                    f"{product.name}: poids et volume manquants pour la preparation."
                )
                continue
        if weight_g is None:
            warnings.append(f"{product.name}: poids manquant, calcul sur volume uniquement.")
        if volume_f is None:
            warnings.append(f"{product.name}: volume manquant, calcul sur poids uniquement.")

        if weight_g is not None and weight_g > carton_weight_f:
            errors.append(
                f"{product.name}: poids unitaire superieur au poids max du carton."
            )
        if volume_f is not None and volume_f > carton_volume_f:
            errors.append(
                f"{product.name}: volume unitaire superieur au volume max du carton."
            )

        items.append(
            {
                "product": product,
                "quantity": quantity,
                "weight": float(weight_g) if weight_g is not None else 0.0,
                "volume": float(volume_f) if volume_f is not None else 0.0,
            }
        )

    if errors:
        return None, errors, warnings

    def item_ratio(item):
        ratios = []
        if item["volume"] > 0 and carton_volume_f > 0:
            ratios.append(item["volume"] / carton_volume_f)
        if item["weight"] > 0 and carton_weight_f > 0:
            ratios.append(item["weight"] / carton_weight_f)
        return max(ratios) if ratios else 0

    items.sort(key=item_ratio, reverse=True)

    bins = []
    for item in items:
        remaining_qty = item["quantity"]
        while remaining_qty > 0:
            placed = False
            for bin_data in bins:
                if (
                    item["volume"] <= bin_data["remaining_volume"]
                    and item["weight"] <= bin_data["remaining_weight"]
                ):
                    max_fit = remaining_qty
                    if item["volume"] > 0:
                        max_fit = min(
                            max_fit, int(bin_data["remaining_volume"] // item["volume"])
                        )
                    if item["weight"] > 0:
                        max_fit = min(
                            max_fit, int(bin_data["remaining_weight"] // item["weight"])
                        )
                    if max_fit <= 0:
                        continue
                    bin_data["remaining_volume"] -= item["volume"] * max_fit
                    bin_data["remaining_weight"] -= item["weight"] * max_fit
                    entry = bin_data["items"].get(item["product"].id)
                    if entry:
                        entry["quantity"] += max_fit
                    else:
                        bin_data["items"][item["product"].id] = {
                            "product": item["product"],
                            "quantity": max_fit,
                        }
                    remaining_qty -= max_fit
                    placed = True
                    break
            if not placed:
                max_fit = remaining_qty
                if item["volume"] > 0:
                    max_fit = min(max_fit, int(carton_volume_f // item["volume"]))
                if item["weight"] > 0:
                    max_fit = min(max_fit, int(carton_weight_f // item["weight"]))
                if max_fit <= 0:
                    max_fit = 1
                bins.append(
                    {
                        "remaining_volume": carton_volume_f - item["volume"] * max_fit,
                        "remaining_weight": carton_weight_f - item["weight"] * max_fit,
                        "items": {
                            item["product"].id: {
                                "product": item["product"],
                                "quantity": max_fit,
                            }
                        },
                    }
                )
                remaining_qty -= max_fit
    return bins, errors, warnings


def build_packing_result(carton_ids):
    cartons = (
        Carton.objects.filter(id__in=carton_ids)
        .select_related("shipment")
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code")
    )
    order = {carton_id: index for index, carton_id in enumerate(carton_ids)}
    cartons_sorted = sorted(cartons, key=lambda carton: order.get(carton.id, 0))
    carton_rows = []
    aggregate = {}

    for carton in cartons_sorted:
        rows = {}
        for item in carton.cartonitem_set.all():
            product = item.product_lot.product
            lot_code = item.product_lot.lot_code
            key = build_product_group_key(product, lot_code)
            if key not in rows:
                rows[key] = {
                    "label": build_product_label(product, lot_code),
                    "quantity": 0,
                }
            rows[key]["quantity"] += item.quantity
            if key not in aggregate:
                aggregate[key] = {
                    "label": build_product_label(product, lot_code),
                    "quantity": 0,
                }
            aggregate[key]["quantity"] += item.quantity
        items_sorted = sorted(
            rows.values(), key=lambda row: row["label"]
        )
        if carton.shipment_id:
            packing_list_url = reverse(
                "scan:scan_shipment_carton_document",
                args=[carton.shipment_id, carton.id],
            )
        else:
            packing_list_url = reverse("scan:scan_carton_document", args=[carton.id])
        picking_url = reverse("scan:scan_carton_picking", args=[carton.id])
        carton_rows.append(
            {
                "code": carton.code,
                "items": items_sorted,
                "packing_list_url": packing_list_url,
                "picking_url": picking_url,
            }
        )

    aggregate_rows = sorted(aggregate.values(), key=lambda row: row["label"])
    return {"cartons": carton_rows, "aggregate": aggregate_rows}
