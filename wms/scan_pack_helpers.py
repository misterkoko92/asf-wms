from django.urls import reverse

from .models import Carton
from .scan_carton_helpers import get_carton_volume_cm3
from .scan_product_helpers import (
    build_product_group_key,
    build_product_label,
    get_product_volume_cm3,
    get_product_weight_g,
)


def _html_delivery_url(url):
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}delivery=html"


def build_pack_line_values(line_count, data=None):
    lines = []
    for index in range(1, line_count + 1):
        prefix = f"line_{index}_"
        lines.append(
            {
                "product_code": (data.get(prefix + "product_code") if data else "") or "",
                "quantity": (data.get(prefix + "quantity") if data else "") or "",
                "expires_on": (data.get(prefix + "expires_on") if data else "") or "",
                "pack_family_override": (
                    (data.get(prefix + "pack_family_override") if data else "") or ""
                ),
            }
        )
    return lines


def parse_forced_carton_count(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        forced_count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Nombre de colis invalide.") from exc
    if forced_count <= 0:
        raise ValueError("Nombre de colis invalide.")
    return forced_count


def build_forced_packing_bins(line_items, forced_carton_count):
    total_quantity = sum(max(0, int(item.get("quantity") or 0)) for item in line_items)
    if total_quantity <= 0:
        return []
    carton_count = max(1, min(int(forced_carton_count or 0), total_quantity))
    base_quantity = total_quantity // carton_count
    remainder = total_quantity % carton_count
    targets = [base_quantity + (1 if index < remainder else 0) for index in range(carton_count)]
    bins = [{"items": {}} for _index in range(carton_count)]
    filled = [0 for _index in range(carton_count)]
    carton_index = 0

    for item in line_items:
        product = item["product"]
        expires_on = item.get("expires_on")
        remaining = max(0, int(item.get("quantity") or 0))
        while remaining > 0 and carton_index < carton_count:
            available = targets[carton_index] - filled[carton_index]
            if available <= 0:
                carton_index += 1
                continue
            chunk = min(remaining, available)
            row = bins[carton_index]["items"].setdefault(
                product.id,
                {
                    "product": product,
                    "quantity": 0,
                    "expires_on": expires_on,
                },
            )
            row["quantity"] += chunk
            if expires_on is not None:
                if row["expires_on"] is None:
                    row["expires_on"] = expires_on
                else:
                    row["expires_on"] = min(row["expires_on"], expires_on)
            filled[carton_index] += chunk
            remaining -= chunk
            if filled[carton_index] >= targets[carton_index]:
                carton_index += 1

    return [bin_data for bin_data in bins if bin_data["items"]]


def build_forced_carton_warnings(*, bins, carton_size, carton_format_label):
    warnings = []
    carton_volume = (
        float(carton_size["length_cm"])
        * float(carton_size["width_cm"])
        * float(carton_size["height_cm"])
    )
    max_weight_g = int(carton_size["max_weight_g"] or 0)
    for index, bin_data in enumerate(bins, start=1):
        total_volume = 0.0
        total_weight = 0
        for entry in bin_data["items"].values():
            quantity = int(entry.get("quantity") or 0)
            product = entry["product"]
            product_volume = get_product_volume_cm3(product) or 1
            product_weight = get_product_weight_g(product) or 5
            total_volume += float(product_volume) * quantity
            total_weight += int(product_weight) * quantity
        if carton_volume > 0 and total_volume > carton_volume:
            warnings.append(
                f"Colis forcé {index} dépasse le volume du format {carton_format_label}."
            )
        if max_weight_g > 0 and total_weight > max_weight_g:
            warnings.append(
                f"Colis forcé {index} dépasse le poids max du format {carton_format_label}."
            )
    return warnings


def build_identical_carton_batch_bins(line_items, carton_size, carton_count, *, apply_defaults):
    bins, errors, warnings = build_packing_bins(
        line_items,
        carton_size,
        apply_defaults=apply_defaults,
    )
    if errors:
        return None, errors, warnings
    if len(bins or []) != 1:
        return None, ["Le colis type doit tenir dans un seul colis."], warnings

    source_items = bins[0]["items"]
    batch_bins = []
    for _index in range(carton_count):
        batch_bins.append(
            {
                "items": {
                    product_id: {
                        "product": entry["product"],
                        "quantity": entry["quantity"],
                        "expires_on": entry.get("expires_on"),
                    }
                    for product_id, entry in source_items.items()
                }
            }
        )
    return batch_bins, [], warnings


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
                    f"{product.name}: poids/volume manquants, valeurs par défaut appliquées."
                )
            else:
                errors.append(f"{product.name}: poids et volume manquants pour la préparation.")
                continue
        if weight_g is None:
            warnings.append(f"{product.name}: poids manquant, calcul sur volume uniquement.")
        if volume_f is None:
            warnings.append(f"{product.name}: volume manquant, calcul sur poids uniquement.")

        if weight_g is not None and weight_g > carton_weight_f:
            errors.append(f"{product.name}: poids unitaire superieur au poids max du carton.")
        if volume_f is not None and volume_f > carton_volume_f:
            errors.append(f"{product.name}: volume unitaire superieur au volume max du carton.")

        items.append(
            {
                "product": product,
                "quantity": quantity,
                "weight": float(weight_g) if weight_g is not None else 0.0,
                "volume": float(volume_f) if volume_f is not None else 0.0,
                "expires_on": line.get("expires_on"),
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
                        max_fit = min(max_fit, int(bin_data["remaining_volume"] // item["volume"]))
                    if item["weight"] > 0:
                        max_fit = min(max_fit, int(bin_data["remaining_weight"] // item["weight"]))
                    if max_fit <= 0:
                        continue
                    bin_data["remaining_volume"] -= item["volume"] * max_fit
                    bin_data["remaining_weight"] -= item["weight"] * max_fit
                    entry = bin_data["items"].get(item["product"].id)
                    if entry:
                        entry["quantity"] += max_fit
                        if item["expires_on"] is not None:
                            if entry["expires_on"] is None:
                                entry["expires_on"] = item["expires_on"]
                            else:
                                entry["expires_on"] = min(
                                    entry["expires_on"],
                                    item["expires_on"],
                                )
                    else:
                        bin_data["items"][item["product"].id] = {
                            "product": item["product"],
                            "quantity": max_fit,
                            "expires_on": item["expires_on"],
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
                                "expires_on": item["expires_on"],
                            }
                        },
                    }
                )
                remaining_qty -= max_fit
    return bins, errors, warnings


def build_packing_result(carton_ids):
    result_entries = []
    for entry in carton_ids:
        if isinstance(entry, dict):
            carton_id = entry.get("carton_id") or entry.get("id")
            if carton_id is None:
                continue
            result_entries.append(
                {
                    "carton_id": carton_id,
                    "zone_label": entry.get("zone_label") or "",
                    "family": entry.get("family") or "",
                }
            )
        else:
            result_entries.append(
                {
                    "carton_id": entry,
                    "zone_label": "",
                    "family": "",
                }
            )
    resolved_carton_ids = [entry["carton_id"] for entry in result_entries]
    cartons = (
        Carton.objects.filter(id__in=resolved_carton_ids)
        .select_related("shipment", "current_location")
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code")
    )
    order = {entry["carton_id"]: index for index, entry in enumerate(result_entries)}
    metadata_by_carton_id = {entry["carton_id"]: entry for entry in result_entries}
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
        items_sorted = sorted(rows.values(), key=lambda row: row["label"])
        if carton.shipment_id:
            packing_list_url = _html_delivery_url(
                reverse(
                    "scan:scan_shipment_carton_document",
                    args=[carton.shipment_id, carton.id],
                )
            )
        else:
            packing_list_url = _html_delivery_url(
                reverse("scan:scan_carton_document", args=[carton.id])
            )
        picking_url = reverse("scan:scan_carton_picking", args=[carton.id])
        metadata = metadata_by_carton_id.get(carton.id, {})
        zone_label = metadata.get("zone_label") or ""
        if not zone_label and getattr(carton, "current_location", None):
            zone_label = str(carton.current_location)
        carton_rows.append(
            {
                "code": carton.code,
                "items": items_sorted,
                "packing_list_url": packing_list_url,
                "picking_url": picking_url,
                "zone_label": zone_label,
                "family": metadata.get("family") or "",
            }
        )

    aggregate_rows = sorted(aggregate.values(), key=lambda row: row["label"])
    return {
        "cartons": carton_rows,
        "print_urls": [
            carton_row["packing_list_url"]
            for carton_row in carton_rows
            if carton_row.get("packing_list_url")
        ],
        "aggregate": aggregate_rows,
        "show_success_modal": bool(carton_rows),
    }
