from decimal import Decimal, InvalidOperation

from django.db.models import F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from .models import (
    Carton,
    CartonFormat,
    CartonStatus,
    Location,
    Product,
    ProductLotStatus,
    Shipment,
    Warehouse,
)


def resolve_product(code: str, *, include_kits: bool = False):
    code = (code or "").strip()
    if not code:
        return None
    products = Product.objects.filter(is_active=True)
    if not include_kits:
        products = products.filter(kit_items__isnull=True)
    product = products.filter(barcode__iexact=code).first()
    if product:
        return product
    product = products.filter(ean__iexact=code).first()
    if product:
        return product
    product = products.filter(sku__iexact=code).first()
    if product:
        return product
    product = products.filter(name__iexact=code).first()
    if product:
        return product
    candidates = list(
        products.filter(name__istartswith=code).order_by("name")[:2]
    )
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_product_options(*, include_kits: bool = False):
    available_expr = ExpressionWrapper(
        F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
        output_field=IntegerField(),
    )
    base_qs = (
        Product.objects.filter(is_active=True, kit_items__isnull=True)
        .annotate(
            available_stock=Coalesce(
                Sum(
                    available_expr,
                    filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
                ),
                0,
            )
        )
        .order_by("name")
    )
    base_products = list(
        base_qs.values(
            "id",
            "name",
            "sku",
            "barcode",
            "ean",
            "brand",
            "default_location_id",
            "storage_conditions",
            "weight_g",
            "volume_cm3",
            "length_cm",
            "width_cm",
            "height_cm",
            "available_stock",
        )
    )
    if not include_kits:
        return base_products

    available_by_id = dict(base_qs.values_list("id", "available_stock"))
    kit_products = (
        Product.objects.filter(is_active=True, kit_items__isnull=False)
        .prefetch_related("kit_items__component")
        .order_by("name")
    )
    kit_options = []
    for kit in kit_products:
        kit_items = list(kit.kit_items.all())
        if not kit_items:
            continue
        max_units = []
        for item in kit_items:
            if item.quantity <= 0:
                continue
            available = int(available_by_id.get(item.component_id, 0) or 0)
            max_units.append(available // item.quantity)
        available_stock = min(max_units) if max_units else 0
        kit_options.append(
            {
                "id": kit.id,
                "name": kit.name,
                "sku": kit.sku,
                "barcode": kit.barcode,
                "ean": kit.ean,
                "brand": kit.brand,
                "default_location_id": kit.default_location_id,
                "storage_conditions": kit.storage_conditions,
                "weight_g": get_product_weight_g(kit),
                "volume_cm3": get_product_volume_cm3(kit),
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
                "available_stock": available_stock,
            }
        )

    combined = base_products + kit_options
    combined.sort(key=lambda item: (item["name"] or "").lower())
    return combined


def resolve_default_warehouse():
    return (
        Warehouse.objects.filter(code__iexact="REC").first()
        or Warehouse.objects.filter(name__iexact="Reception").first()
        or Warehouse.objects.order_by("name").first()
    )


def build_location_data():
    locations = list(
        Location.objects.select_related("warehouse").order_by(
            "warehouse__name", "zone", "aisle", "shelf"
        )
    )
    return [
        {"id": location.id, "label": str(location), "warehouse": location.warehouse.name}
        for location in locations
    ]


def build_available_cartons():
    cartons = (
        Carton.objects.filter(status=CartonStatus.PACKED, shipment__isnull=True)
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code")
    )
    options = []
    for carton in cartons:
        weight_total = 0
        for item in carton.cartonitem_set.all():
            product_weight = item.product_lot.product.weight_g or 0
            weight_total += product_weight * item.quantity
        options.append(
            {
                "id": carton.id,
                "code": carton.code,
                "weight_g": weight_total,
            }
        )
    return options


def build_carton_formats():
    formats = list(CartonFormat.objects.all().order_by("name"))
    default_format = next((fmt for fmt in formats if fmt.is_default), None)
    if default_format is None and formats:
        default_format = formats[0]
    data = []
    for fmt in formats:
        data.append(
            {
                "id": fmt.id,
                "name": fmt.name,
                "length_cm": fmt.length_cm,
                "width_cm": fmt.width_cm,
                "height_cm": fmt.height_cm,
                "max_weight_g": fmt.max_weight_g,
                "is_default": fmt.is_default,
            }
        )
    return data, default_format


def parse_decimal(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    value = value.replace(",", ".")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def parse_int(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _get_kit_items(product: Product):
    cached = getattr(product, "_prefetched_objects_cache", {}).get("kit_items")
    if cached is not None:
        return cached
    return list(product.kit_items.select_related("component"))


def get_product_weight_g(product: Product):
    kit_items = _get_kit_items(product)
    if kit_items:
        total = 0
        for item in kit_items:
            weight_g = (
                item.component.weight_g
                if item.component.weight_g and item.component.weight_g > 0
                else None
            )
            if weight_g is None:
                return None
            total += weight_g * item.quantity
        return total if total > 0 else None
    return product.weight_g if product.weight_g and product.weight_g > 0 else None


def _get_base_product_volume_cm3(product: Product):
    if product.volume_cm3:
        return Decimal(product.volume_cm3)
    if product.length_cm and product.width_cm and product.height_cm:
        return product.length_cm * product.width_cm * product.height_cm
    return None


def get_product_volume_cm3(product: Product):
    kit_items = _get_kit_items(product)
    if kit_items:
        total = Decimal("0")
        for item in kit_items:
            volume = _get_base_product_volume_cm3(item.component)
            if volume is None or volume <= 0:
                return None
            total += volume * item.quantity
        return total if total > 0 else None
    return _get_base_product_volume_cm3(product)


def get_carton_volume_cm3(carton_size):
    return (
        carton_size["length_cm"]
        * carton_size["width_cm"]
        * carton_size["height_cm"]
    )


def resolve_carton_size(
    *, carton_format_id: str | None, default_format: CartonFormat | None, data
):
    errors = []
    if not carton_format_id and default_format:
        carton_format_id = str(default_format.id)

    if carton_format_id and carton_format_id != "custom":
        try:
            format_id = int(carton_format_id)
        except ValueError:
            format_id = None
        format_obj = (
            CartonFormat.objects.filter(id=format_id).first() if format_id else None
        )
        if not format_obj:
            errors.append("Format de carton invalide.")
            return None, errors
        return (
            {
                "length_cm": format_obj.length_cm,
                "width_cm": format_obj.width_cm,
                "height_cm": format_obj.height_cm,
                "max_weight_g": format_obj.max_weight_g,
            },
            errors,
        )

    length_cm = parse_decimal(data.get("carton_length_cm"))
    width_cm = parse_decimal(data.get("carton_width_cm"))
    height_cm = parse_decimal(data.get("carton_height_cm"))
    max_weight_g = parse_int(data.get("carton_max_weight_g"))
    if length_cm is None or length_cm <= 0:
        errors.append("Longueur carton invalide.")
    if width_cm is None or width_cm <= 0:
        errors.append("Largeur carton invalide.")
    if height_cm is None or height_cm <= 0:
        errors.append("Hauteur carton invalide.")
    if max_weight_g is None or max_weight_g <= 0:
        errors.append("Poids max carton invalide.")
    if errors:
        return None, errors
    return (
        {
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "max_weight_g": max_weight_g,
        },
        errors,
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


def build_packing_bins(line_items, carton_size):
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
            rows[product.name] = rows.get(product.name, 0) + item.quantity
            aggregate[product.name] = aggregate.get(product.name, 0) + item.quantity
        items_sorted = [
            {"product": name, "quantity": qty}
            for name, qty in sorted(rows.items(), key=lambda row: row[0])
        ]
        carton_rows.append(
            {
                "code": carton.code,
                "items": items_sorted,
            }
        )

    aggregate_rows = [
        {"product": name, "quantity": qty}
        for name, qty in sorted(aggregate.items(), key=lambda row: row[0])
    ]
    return {"cartons": carton_rows, "aggregate": aggregate_rows}


def build_shipment_line_values(carton_count, data=None):
    lines = []
    for index in range(1, carton_count + 1):
        prefix = f"line_{index}_"
        lines.append(
            {
                "carton_id": (data.get(prefix + "carton_id") if data else "") or "",
                "product_code": (data.get(prefix + "product_code") if data else "") or "",
                "quantity": (data.get(prefix + "quantity") if data else "") or "",
            }
        )
    return lines


def resolve_shipment(reference: str):
    reference = (reference or "").strip()
    if not reference:
        return None
    return Shipment.objects.filter(reference__iexact=reference).first()
