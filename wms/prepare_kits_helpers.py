from collections import defaultdict
from urllib.parse import urlencode

from django.db import transaction
from django.db.models import F, IntegerField, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.urls import reverse

from .kit_components import KitCycleError, get_unit_component_quantities
from .models import Carton, Product, ProductLot, ProductLotStatus
from .scan_carton_helpers import build_carton_formats
from .scan_product_helpers import (
    build_product_group_key,
    build_product_label,
    get_product_volume_cm3,
    get_product_weight_g,
)
from .services import pack_carton


def _location_label(location):
    if location is None:
        return "-"
    return f"{location.zone} - {location.aisle} - {location.shelf}"


def _parse_carton_ids(value):
    carton_ids = []
    for raw in (value or "").split(","):
        raw_value = (raw or "").strip()
        if not raw_value:
            continue
        try:
            carton_id = int(raw_value)
        except ValueError:
            continue
        if carton_id > 0:
            carton_ids.append(carton_id)
    return carton_ids


def _compute_max_kits_per_carton(*, kit, default_carton_format):
    if default_carton_format is None:
        return None
    carton_volume_cm3 = (
        default_carton_format.length_cm
        * default_carton_format.width_cm
        * default_carton_format.height_cm
    )
    kit_weight_g = get_product_weight_g(kit)
    kit_volume_cm3 = get_product_volume_cm3(kit)

    max_by_volume = None
    if kit_volume_cm3 and kit_volume_cm3 > 0 and carton_volume_cm3 > 0:
        max_by_volume = int(carton_volume_cm3 // kit_volume_cm3)
        max_by_volume = max(1, max_by_volume)

    max_by_weight = None
    if kit_weight_g and kit_weight_g > 0 and default_carton_format.max_weight_g:
        max_by_weight = int(default_carton_format.max_weight_g // kit_weight_g)
        max_by_weight = max(1, max_by_weight)

    if max_by_volume and max_by_weight:
        return min(max_by_volume, max_by_weight)
    return max_by_volume or max_by_weight


def _build_available_by_component_ids(component_ids):
    if not component_ids:
        return {}
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    return dict(
        ProductLot.objects.filter(
            product_id__in=component_ids,
            status=ProductLotStatus.AVAILABLE,
        )
        .annotate(available=available_expr)
        .values("product_id")
        .annotate(total_available=Coalesce(Sum("available"), 0))
        .values_list("product_id", "total_available")
    )


def _build_first_location_by_component_ids(component_ids):
    if not component_ids:
        return {}
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    lots = (
        ProductLot.objects.filter(
            product_id__in=component_ids,
            status=ProductLotStatus.AVAILABLE,
        )
        .annotate(available=available_expr)
        .select_related("location")
        .order_by("product_id", "expires_on", "received_on", "id")
    )
    first_location_by_component_id = {}
    for lot in lots:
        if lot.available <= 0:
            continue
        if lot.product_id in first_location_by_component_id:
            continue
        first_location_by_component_id[lot.product_id] = lot.location
    return first_location_by_component_id


def _build_prepare_result(prepared_carton_ids):
    prepared_carton_ids = [int(carton_id) for carton_id in (prepared_carton_ids or [])]
    if not prepared_carton_ids:
        return None
    if len(prepared_carton_ids) == 1:
        picking_url = reverse("scan:scan_carton_picking", args=[prepared_carton_ids[0]])
    else:
        picking_url = (
            reverse("scan:scan_prepare_kits_picking")
            + "?"
            + urlencode({"carton_ids": ",".join(str(carton_id) for carton_id in prepared_carton_ids)})
        )
    return {
        "carton_count": len(prepared_carton_ids),
        "carton_ids": prepared_carton_ids,
        "picking_url": picking_url,
    }


def build_prepare_kits_page_context(*, selected_kit_id=None, prepared_carton_ids=None):
    kits = list(
        Product.objects.filter(is_active=True, kit_items__isnull=False)
        .prefetch_related("kit_items__component__default_location")
        .distinct()
        .order_by("name", "id")
    )
    component_quantities_by_kit_id = {}
    component_ids = set()
    for kit in kits:
        try:
            component_quantities = get_unit_component_quantities(kit)
        except KitCycleError:
            component_quantities = {}
        component_quantities_by_kit_id[kit.id] = component_quantities
        component_ids.update(component_quantities.keys())

    component_by_id = {
        component.id: component
        for component in Product.objects.filter(id__in=component_ids).select_related(
            "default_location"
        )
    }
    available_by_component_id = _build_available_by_component_ids(component_ids)
    first_location_by_component_id = _build_first_location_by_component_ids(component_ids)
    _carton_formats, default_carton_format = build_carton_formats()

    kit_cards = []
    for kit in kits:
        component_quantities = component_quantities_by_kit_id.get(kit.id, {})
        component_rows = []
        max_theoretical_units = []
        for component_id, required_quantity in sorted(
            component_quantities.items(),
            key=lambda pair: ((component_by_id.get(pair[0]).name if component_by_id.get(pair[0]) else "").lower(), pair[0]),
        ):
            if required_quantity <= 0:
                continue
            component = component_by_id.get(component_id)
            if component is None:
                continue
            available_units = int(available_by_component_id.get(component_id, 0) or 0)
            max_theoretical_units.append(available_units // required_quantity)
            location = first_location_by_component_id.get(component_id) or component.default_location
            component_rows.append(
                {
                    "name": component.name,
                    "quantity": required_quantity,
                    "location": _location_label(location),
                }
            )
        theoretical_stock = min(max_theoretical_units) if max_theoretical_units else 0
        kit_cards.append(
            {
                "id": kit.id,
                "name": kit.name,
                "theoretical_stock": theoretical_stock,
                "max_per_carton": _compute_max_kits_per_carton(
                    kit=kit,
                    default_carton_format=default_carton_format,
                ),
                "component_rows": component_rows,
            }
        )

    selected_kit = None
    if selected_kit_id is not None:
        try:
            selected_kit_id = int(selected_kit_id)
        except (TypeError, ValueError):
            selected_kit_id = None
    for kit in kit_cards:
        if selected_kit_id is not None and kit["id"] == selected_kit_id:
            selected_kit = kit
            break
    if selected_kit is None and kit_cards:
        selected_kit = kit_cards[0]

    return {
        "kit_options": [{"id": kit["id"], "name": kit["name"]} for kit in kit_cards],
        "selected_kit": selected_kit,
        "kit_data": kit_cards,
        "kit_create_url": reverse("admin:wms_product_add"),
        "prepare_result": _build_prepare_result(prepared_carton_ids),
    }


def prepare_kits(*, user, kit, quantity):
    prepared_carton_ids = []
    quantity = int(quantity)
    with transaction.atomic():
        for _ in range(quantity):
            carton = pack_carton(
                user=user,
                product=kit,
                quantity=1,
                carton=None,
                carton_code=None,
                shipment=None,
                current_location=None,
                carton_size=None,
            )
            prepared_carton_ids.append(carton.id)
    return prepared_carton_ids


def build_prepare_kits_picking_context(carton_ids):
    carton_ids = [int(carton_id) for carton_id in carton_ids if carton_id]
    cartons = list(
        Carton.objects.filter(id__in=carton_ids)
        .prefetch_related("cartonitem_set__product_lot__product", "cartonitem_set__product_lot__location")
        .order_by("code", "id")
    )
    if not cartons:
        return None

    rows_by_key = {}
    for carton in cartons:
        for item in carton.cartonitem_set.all():
            product = item.product_lot.product
            location = item.product_lot.location
            location_label = _location_label(location)
            group_key = build_product_group_key(product, item.product_lot.lot_code)
            row_key = (group_key, location.id if location else None)
            if row_key not in rows_by_key:
                rows_by_key[row_key] = {
                    "label": build_product_label(product, item.product_lot.lot_code),
                    "quantity": item.quantity,
                    "location": location_label,
                }
            else:
                rows_by_key[row_key]["quantity"] += item.quantity

    item_rows = sorted(rows_by_key.values(), key=lambda row: (row["label"], row["location"]))
    return {
        "carton_ids": [carton.id for carton in cartons],
        "carton_codes": [carton.code for carton in cartons],
        "item_rows": item_rows,
    }


__all__ = [
    "build_prepare_kits_page_context",
    "build_prepare_kits_picking_context",
    "prepare_kits",
    "_parse_carton_ids",
]
