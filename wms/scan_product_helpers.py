from decimal import Decimal

from django.db.models import Case, F, IntegerField, Q, Sum, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from .models import Product, ProductLotStatus

def resolve_product(code: str, *, include_kits: bool = False):
    code = (code or "").strip()
    if not code:
        return None
    products = Product.objects.filter(is_active=True)
    if not include_kits:
        products = products.filter(kit_items__isnull=True)
    product = (
        products.filter(
            Q(barcode__iexact=code)
            | Q(ean__iexact=code)
            | Q(sku__iexact=code)
            | Q(name__iexact=code)
        )
        .annotate(
            match_rank=Case(
                When(barcode__iexact=code, then=Value(1)),
                When(ean__iexact=code, then=Value(2)),
                When(sku__iexact=code, then=Value(3)),
                When(name__iexact=code, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
        .order_by("match_rank", "name")
        .first()
    )
    if product:
        return product
    candidates = list(
        products.filter(name__istartswith=code).order_by("name")[:2]
    )
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_product_group_key(product, lot_code):
    sku = (product.sku or "").strip() or str(product.id)
    lot_code = (lot_code or "").strip()
    if lot_code:
        return (sku, lot_code.upper())
    brand = (product.brand or "").strip().upper()
    return (sku, brand)


def build_product_label(product, lot_code):
    label = product.name
    if product.brand:
        label = f"{label} ({product.brand})"
    lot_code = (lot_code or "").strip()
    if lot_code:
        label = f"{label} - Lot {lot_code}"
    return label


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


def build_product_selection_data(*, include_kits: bool = False):
    product_options = build_product_options(include_kits=include_kits)
    product_ids = [item["id"] for item in product_options if item.get("id")]
    products = Product.objects.filter(id__in=product_ids, is_active=True).select_related(
        "category",
        "category__parent",
        "category__parent__parent",
        "category__parent__parent__parent",
    )
    product_by_id = {product.id: product for product in products}
    available_by_id = {
        item["id"]: int(item.get("available_stock") or 0) for item in product_options
    }
    return product_options, product_by_id, available_by_id


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
