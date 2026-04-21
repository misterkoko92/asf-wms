from collections import defaultdict
from decimal import Decimal

from django.db.models import Case, F, IntegerField, Q, Sum, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from .kit_components import KitCycleError, get_unit_component_quantities
from .models import Product, ProductKitItem, ProductLotStatus


def get_product_root_category_name(product):
    category = getattr(product, "category", None)
    while category and category.parent_id:
        category = category.parent
    return (category.name or "").strip() if category else ""


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
    candidates = list(products.filter(name__istartswith=code).order_by("name")[:2])
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


def _product_row_volume_cm3(product_row):
    volume = product_row.get("volume_cm3")
    if volume:
        return Decimal(volume)
    length = product_row.get("length_cm")
    width = product_row.get("width_cm")
    height = product_row.get("height_cm")
    if length and width and height:
        return length * width * height
    return None


def _build_component_quantities_by_kit_id(kit_products):
    kit_ids = [product.id for product in kit_products if getattr(product, "id", None)]
    if not kit_ids:
        return {}

    kit_items_by_kit_id = defaultdict(list)
    for kit_item in ProductKitItem.objects.filter(kit_id__in=kit_ids).select_related("component"):
        kit_items_by_kit_id[kit_item.kit_id].append(kit_item)

    memo = {}

    def _resolve(product_id, stack):
        cached = memo.get(product_id)
        if cached is not None:
            return cached
        if product_id in stack:
            cycle_start = stack.index(product_id)
            raise KitCycleError(stack[cycle_start:] + [product_id])

        stack.append(product_id)
        kit_items = kit_items_by_kit_id.get(product_id) or []
        if not kit_items:
            result = {product_id: 1}
        else:
            totals = defaultdict(int)
            for kit_item in kit_items:
                quantity = int(kit_item.quantity or 0)
                if quantity <= 0:
                    continue
                for component_id, component_quantity in _resolve(
                    kit_item.component_id,
                    stack,
                ).items():
                    totals[component_id] += component_quantity * quantity
            result = dict(totals)
        stack.pop()
        memo[product_id] = result
        return result

    component_quantities_by_kit_id = {}
    for kit in kit_products:
        if getattr(kit, "id", None) is None:
            continue
        try:
            component_quantities_by_kit_id[kit.id] = _resolve(kit.id, [])
        except KitCycleError:
            component_quantities_by_kit_id[kit.id] = {}
    return component_quantities_by_kit_id


def build_product_options(*, include_kits: bool = False, compact: bool = False):
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
    if compact and not include_kits:
        return list(
            base_qs.values(
                "id",
                "name",
                "sku",
                "barcode",
                "ean",
                "brand",
                "default_location_id",
                "storage_conditions",
            )
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

    available_by_id = {item["id"]: int(item.get("available_stock") or 0) for item in base_products}
    base_weight_by_id = {item["id"]: item.get("weight_g") for item in base_products}
    base_volume_by_id = {
        item["id"]: _product_row_volume_cm3(item) for item in base_products if item.get("id")
    }
    kit_products = list(
        Product.objects.filter(is_active=True, kit_items__isnull=False).order_by("name")
    )
    component_quantities_by_kit_id = _build_component_quantities_by_kit_id(kit_products)
    kit_options = []
    for kit in kit_products:
        if getattr(kit, "id", None) is None:
            continue
        component_quantities = component_quantities_by_kit_id.get(kit.id, {})
        max_units = []
        weight_total = 0
        weight_known = True
        volume_total = Decimal("0")
        volume_known = True
        for component_id, required_quantity in component_quantities.items():
            if required_quantity <= 0:
                continue
            available = int(available_by_id.get(component_id, 0) or 0)
            max_units.append(available // required_quantity)
            weight_g = base_weight_by_id.get(component_id)
            if weight_g is None or weight_g <= 0:
                weight_known = False
            elif weight_known:
                weight_total += int(weight_g) * required_quantity
            volume_cm3 = base_volume_by_id.get(component_id)
            if volume_cm3 is None or volume_cm3 <= 0:
                volume_known = False
            elif volume_known:
                volume_total += volume_cm3 * required_quantity
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
                "weight_g": weight_total if weight_known and weight_total > 0 else None,
                "volume_cm3": volume_total if volume_known and volume_total > 0 else None,
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
                "available_stock": available_stock,
            }
        )

    combined = base_products + kit_options
    product_ids = [item["id"] for item in combined if item.get("id")]
    products = Product.objects.filter(id__in=product_ids, is_active=True).select_related(
        "category",
        "category__parent",
        "category__parent__parent",
        "category__parent__parent__parent",
    )
    root_category_by_id = {
        product.id: get_product_root_category_name(product) for product in products
    }
    for item in combined:
        item["category_root"] = root_category_by_id.get(item.get("id"), "")
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


def get_product_weight_g(product: Product):
    try:
        component_quantities = get_unit_component_quantities(product)
    except KitCycleError:
        return None
    if not component_quantities:
        return None
    weights_by_id = dict(
        Product.objects.filter(id__in=component_quantities.keys()).values_list("id", "weight_g")
    )
    total = 0
    for component_id, component_quantity in component_quantities.items():
        weight_g = weights_by_id.get(component_id)
        if weight_g is None or weight_g <= 0:
            return None
        total += int(weight_g) * component_quantity
    return total if total > 0 else None


def _get_base_product_volume_cm3(product: Product):
    if product.volume_cm3:
        return Decimal(product.volume_cm3)
    if product.length_cm and product.width_cm and product.height_cm:
        return product.length_cm * product.width_cm * product.height_cm
    return None


def get_product_volume_cm3(product: Product):
    try:
        component_quantities = get_unit_component_quantities(product)
    except KitCycleError:
        return None
    if not component_quantities:
        return None
    components = Product.objects.filter(id__in=component_quantities.keys())
    products_by_id = {component.id: component for component in components}
    total = Decimal("0")
    for component_id, component_quantity in component_quantities.items():
        component = products_by_id.get(component_id)
        if component is None:
            return None
        volume = _get_base_product_volume_cm3(component)
        if volume is None or volume <= 0:
            return None
        total += volume * component_quantity
    return total if total > 0 else None
