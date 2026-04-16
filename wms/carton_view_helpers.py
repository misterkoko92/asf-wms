from django.urls import reverse
from django.utils.translation import gettext as _

from .models import CartonFormat, CartonStatus, ShipmentStatus
from .scan_helpers import build_product_group_key, build_product_label
from .status_badges import resolve_status_tone

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}

PREPARATION_STATUSES = {
    CartonStatus.DRAFT,
    CartonStatus.PICKING,
    CartonStatus.PACKED,
}

VISIBLE_CARTON_FLOW = (
    CartonStatus.DRAFT,
    CartonStatus.PICKING,
    CartonStatus.PACKED,
    CartonStatus.ASSIGNED,
    CartonStatus.LABELED,
)

VISIBLE_CARTON_STEP_LABELS = {
    CartonStatus.DRAFT: CartonStatus.DRAFT.label,
    CartonStatus.PICKING: CartonStatus.PICKING.label,
    CartonStatus.PACKED: _("Disponible"),
    CartonStatus.ASSIGNED: CartonStatus.ASSIGNED.label,
    CartonStatus.LABELED: CartonStatus.LABELED.label,
}

MUTATION_BLOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}


def _html_delivery_url(url):
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}delivery=html"


def get_carton_capacity_cm3():
    default_format = CartonFormat.objects.filter(is_default=True).first()
    if default_format is None:
        default_format = CartonFormat.objects.first()
    if not default_format:
        return None
    return default_format.length_cm * default_format.width_cm * default_format.height_cm


def _build_shipment_reference(carton):
    shipment = getattr(carton, "shipment", None)
    if shipment:
        return shipment.reference
    preassigned_destination = getattr(carton, "preassigned_destination", None)
    iata_code = getattr(preassigned_destination, "iata_code", "") if preassigned_destination else ""
    if iata_code:
        return f"({iata_code})"
    return ""


def _build_status_label(status_value):
    try:
        return CartonStatus(status_value).label
    except ValueError:
        return status_value


def _iter_status_events(carton):
    status_events = getattr(carton, "status_events", None)
    if not status_events:
        return []
    if hasattr(status_events, "all"):
        return list(status_events.all())
    return list(status_events)


def _resolve_preparation_status(carton):
    status_value = getattr(carton, "status", "")
    if status_value in PREPARATION_STATUSES:
        return status_value
    if status_value in {CartonStatus.LABELED, CartonStatus.SHIPPED}:
        return CartonStatus.LABELED
    if status_value == CartonStatus.ASSIGNED:
        for event in _iter_status_events(carton):
            previous_status = getattr(event, "previous_status", None)
            if previous_status in PREPARATION_STATUSES:
                return previous_status
        return CartonStatus.PACKED
    return ""


def build_carton_visible_progress_steps(carton):
    preparation_status = _resolve_preparation_status(carton)
    achieved_steps = [CartonStatus.DRAFT]

    if preparation_status in {CartonStatus.PICKING, CartonStatus.PACKED, CartonStatus.LABELED}:
        achieved_steps.append(CartonStatus.PICKING)
    if preparation_status in {CartonStatus.PACKED, CartonStatus.LABELED}:
        achieved_steps.append(CartonStatus.PACKED)

    assignment_achieved = bool(getattr(carton, "shipment_id", None)) or getattr(
        carton, "status", ""
    ) in {CartonStatus.ASSIGNED, CartonStatus.LABELED, CartonStatus.SHIPPED}
    if assignment_achieved:
        achieved_steps.append(CartonStatus.ASSIGNED)

    if getattr(carton, "status", "") in {CartonStatus.LABELED, CartonStatus.SHIPPED}:
        achieved_steps.append(CartonStatus.LABELED)

    return achieved_steps


def build_skipped_visible_status_labels(carton, *, target_status):
    if target_status not in VISIBLE_CARTON_FLOW:
        return []
    current_steps = set(build_carton_visible_progress_steps(carton))
    required_steps = VISIBLE_CARTON_FLOW[: VISIBLE_CARTON_FLOW.index(target_status)]
    return [
        VISIBLE_CARTON_STEP_LABELS[step] for step in required_steps if step not in current_steps
    ]


def _build_preparation_status_badge(carton):
    status_value = _resolve_preparation_status(carton)
    if status_value in PREPARATION_STATUSES:
        return {
            "label": {
                CartonStatus.DRAFT: CartonStatus.DRAFT.label,
                CartonStatus.PICKING: CartonStatus.PICKING.label,
                CartonStatus.PACKED: _("Disponible"),
            }[status_value],
            "variant": f"prep-{status_value}",
        }
    if status_value == CartonStatus.LABELED:
        return {
            "label": CartonStatus.LABELED.label,
            "variant": "prep-labeled",
        }
    return {
        "label": _("Prépa inconnue"),
        "variant": "prep-unknown",
    }


def _build_assignment_status_badge(carton):
    status_value = getattr(carton, "status", "")
    if status_value == CartonStatus.SHIPPED:
        return {
            "label": CartonStatus.SHIPPED.label,
            "variant": "assignment-shipped",
        }
    if status_value in {CartonStatus.ASSIGNED, CartonStatus.LABELED} or getattr(
        carton, "shipment_id", None
    ):
        return {
            "label": CartonStatus.ASSIGNED.label,
            "variant": "assignment-assigned",
        }
    return {
        "label": _("Libre"),
        "variant": "assignment-free",
    }


def _carton_allows_mutation(carton):
    if carton.status == CartonStatus.SHIPPED:
        return False
    shipment = getattr(carton, "shipment", None)
    if not shipment:
        return True
    if getattr(shipment, "is_disputed", False):
        return False
    return getattr(shipment, "status", None) not in MUTATION_BLOCKED_SHIPMENT_STATUSES


def build_carton_ready_row(carton, *, carton_capacity_cm3):
    product_totals = {}
    product_display_totals = {}
    weight_total_g = 0
    volume_total_cm3 = 0
    missing_weight = False
    missing_volume = False
    for item in carton.cartonitem_set.all():
        product = item.product_lot.product
        lot_code = item.product_lot.lot_code
        key = build_product_group_key(product, lot_code)
        if key not in product_totals:
            product_totals[key] = {
                "label": build_product_label(product, lot_code),
                "quantity": 0,
            }
        product_totals[key]["quantity"] += item.quantity
        display_label = (getattr(product, "name", "") or "").strip() or build_product_label(
            product,
            lot_code,
        )
        if display_label not in product_display_totals:
            product_display_totals[display_label] = {
                "label": display_label,
                "quantity": 0,
            }
        product_display_totals[display_label]["quantity"] += item.quantity
        if product.weight_g:
            weight_total_g += product.weight_g * item.quantity
        else:
            missing_weight = True
        if product.volume_cm3:
            volume_total_cm3 += product.volume_cm3 * item.quantity
        else:
            missing_volume = True
    packing_list = sorted(product_totals.values(), key=lambda row: row["label"])
    product_rows = sorted(product_display_totals.values(), key=lambda row: row["label"])
    product_rows = [
        {
            "label": item["label"],
            "quantity": item["quantity"],
            "display": _("%(label)s x %(quantity)s")
            % {"label": item["label"], "quantity": item["quantity"]},
        }
        for item in product_rows
    ]
    if weight_total_g == 0 and missing_weight:
        weight_kg = None
    else:
        weight_kg = weight_total_g / 1000 if weight_total_g else None
    if carton_capacity_cm3 and volume_total_cm3 and not missing_volume:
        volume_percent = round(float(volume_total_cm3) / float(carton_capacity_cm3) * 100)
    else:
        volume_percent = None
    is_assigned = carton.shipment_id is not None
    shipment_status = getattr(getattr(carton, "shipment", None), "status", None)
    shipment_locked = (
        carton.shipment_id is not None
        and carton.shipment
        and shipment_status in LOCKED_SHIPMENT_STATUSES
    )
    status_label = _build_status_label(carton.status)
    preparation_status_value = _resolve_preparation_status(carton)
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
    return {
        "id": carton.id,
        "code": carton.code,
        "created_at": carton.created_at,
        "status_label": status_label,
        "status_value": carton.status,
        "status_tone": resolve_status_tone(carton.status, domain="carton"),
        "status_badges": [
            _build_preparation_status_badge(carton),
            _build_assignment_status_badge(carton),
        ],
        "preparation_status_value": preparation_status_value,
        "is_assigned": is_assigned,
        "shipment_id": carton.shipment_id,
        "product_rows": product_rows,
        "can_toggle": (not is_assigned) and carton.status != CartonStatus.SHIPPED,
        "can_mark_labeled": is_assigned
        and not shipment_locked
        and carton.status in {CartonStatus.ASSIGNED, CartonStatus.PACKED},
        "can_mark_assigned": is_assigned
        and not shipment_locked
        and carton.status == CartonStatus.LABELED,
        "can_edit": _carton_allows_mutation(carton),
        "can_delete": _carton_allows_mutation(carton),
        "can_bulk_mark_labeled": is_assigned
        and not shipment_locked
        and carton.status in {CartonStatus.ASSIGNED, CartonStatus.PACKED},
        "can_bulk_mark_assigned": is_assigned
        and not shipment_locked
        and carton.status == CartonStatus.LABELED,
        "shipment_reference": _build_shipment_reference(carton),
        "location": carton.current_location,
        "detail_url": reverse("scan:scan_carton_edit", args=[carton.id]),
        "summary_line_count": len(packing_list),
        "summary_total_quantity": sum(item["quantity"] for item in packing_list),
        "has_packing_list": bool(packing_list_url),
        "has_picking": bool(picking_url),
        "packing_list": packing_list,
        "packing_list_url": packing_list_url,
        "picking_url": picking_url,
        "weight_kg": weight_kg,
        "volume_percent": volume_percent,
    }


def build_cartons_ready_rows(cartons_qs, *, carton_capacity_cm3):
    return [
        build_carton_ready_row(carton, carton_capacity_cm3=carton_capacity_cm3)
        for carton in cartons_qs
    ]
