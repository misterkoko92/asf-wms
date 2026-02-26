from collections import defaultdict

from django.db.models import Max

from .kit_components import KitCycleError, get_unit_component_quantities
from .models import Carton, CartonStatus, Product, StockMovement
from .scan_product_helpers import build_product_options


def _build_theoretical_kit_stock():
    product_options = build_product_options(include_kits=True)
    return {
        int(item["id"]): int(item.get("available_stock") or 0)
        for item in product_options
        if item.get("id")
    }


def _kit_units_in_carton(*, carton_quantities, kit_component_quantities):
    if not carton_quantities or not kit_component_quantities:
        return 0
    if set(carton_quantities.keys()) != set(kit_component_quantities.keys()):
        return 0
    ratio = None
    for component_id, required_quantity in kit_component_quantities.items():
        if required_quantity <= 0:
            return 0
        carton_quantity = carton_quantities.get(component_id, 0)
        if carton_quantity <= 0 or carton_quantity % required_quantity != 0:
            return 0
        current_ratio = carton_quantity // required_quantity
        if current_ratio <= 0:
            return 0
        if ratio is None:
            ratio = current_ratio
        elif ratio != current_ratio:
            return 0
    return int(ratio or 0)


def _build_carton_kit_stock_by_status(*, kits, component_quantities_by_kit_id):
    in_preparation_by_kit_id = defaultdict(int)
    ready_by_kit_id = defaultdict(int)
    carton_dates_by_kit_id = defaultdict(list)

    cartons = (
        Carton.objects.filter(
            shipment__isnull=True,
            status__in=[CartonStatus.PICKING, CartonStatus.PACKED],
            cartonitem__isnull=False,
        )
        .prefetch_related("cartonitem_set")
        .order_by("id")
        .distinct()
    )
    for carton in cartons:
        carton_quantities = defaultdict(int)
        for item in carton.cartonitem_set.all():
            carton_quantities[item.product_lot.product_id] += item.quantity
        if not carton_quantities:
            continue
        matched_kit_id = None
        matched_units = 0
        for kit in kits:
            units = _kit_units_in_carton(
                carton_quantities=carton_quantities,
                kit_component_quantities=component_quantities_by_kit_id.get(kit.id, {}),
            )
            if units > 0:
                matched_kit_id = kit.id
                matched_units = units
                break
        if matched_kit_id is None:
            continue
        if carton.status == CartonStatus.PICKING:
            in_preparation_by_kit_id[matched_kit_id] += matched_units
        elif carton.status == CartonStatus.PACKED:
            ready_by_kit_id[matched_kit_id] += matched_units
        carton_dates_by_kit_id[matched_kit_id].append(carton.created_at)
    return in_preparation_by_kit_id, ready_by_kit_id, carton_dates_by_kit_id


def build_kits_view_rows():
    kits = list(
        Product.objects.filter(is_active=True, kit_items__isnull=False)
        .select_related(
            "category",
            "category__parent",
            "category__parent__parent",
            "category__parent__parent__parent",
        )
        .prefetch_related("kit_items__component")
        .distinct()
        .order_by("name", "id")
    )
    theoretical_stock_by_kit_id = _build_theoretical_kit_stock()

    component_quantities_by_kit_id = {}
    all_component_ids = set()
    for kit in kits:
        try:
            component_quantities = get_unit_component_quantities(kit)
        except KitCycleError:
            component_quantities = {}
        component_quantities_by_kit_id[kit.id] = component_quantities
        all_component_ids.update(component_quantities.keys())

    (
        in_preparation_by_kit_id,
        ready_by_kit_id,
        carton_dates_by_kit_id,
    ) = _build_carton_kit_stock_by_status(
        kits=kits,
        component_quantities_by_kit_id=component_quantities_by_kit_id,
    )

    component_name_by_id = dict(
        Product.objects.filter(id__in=all_component_ids).values_list("id", "name")
    )
    component_last_movement_by_id = dict(
        StockMovement.objects.filter(product_id__in=all_component_ids)
        .values("product_id")
        .annotate(last=Max("created_at"))
        .values_list("product_id", "last")
    )

    rows = []
    for kit in kits:
        component_quantities = component_quantities_by_kit_id.get(kit.id, {})
        composition_lines = [
            f"{component_name_by_id.get(component_id, '-')} - {quantity} unite(s)"
            for component_id, quantity in sorted(
                component_quantities.items(),
                key=lambda pair: ((component_name_by_id.get(pair[0]) or "").lower(), pair[0]),
            )
            if quantity > 0
        ]
        movement_dates = [
            component_last_movement_by_id.get(component_id)
            for component_id in component_quantities.keys()
            if component_last_movement_by_id.get(component_id) is not None
        ]
        ready_dates = carton_dates_by_kit_id.get(kit.id, [])
        last_modified_at = max(movement_dates + ready_dates) if (movement_dates or ready_dates) else None
        rows.append(
            {
                "id": kit.id,
                "name": kit.name,
                "composition_lines": composition_lines,
                "theoretical_stock": theoretical_stock_by_kit_id.get(kit.id, 0),
                "real_stock": ready_by_kit_id.get(kit.id, 0),
                "in_preparation_stock": in_preparation_by_kit_id.get(kit.id, 0),
                "category": str(kit.category) if kit.category else "",
                "last_modified_at": last_modified_at,
            }
        )
    return rows
