from collections import defaultdict

from django.db import transaction
from django.urls import reverse

from .carton_status_events import set_carton_status
from .domain.orders import create_shipment_for_order, pack_carton_from_reserved
from .domain.stock import StockError, ensure_carton_code, pack_carton
from .models import (
    CartonFormat,
    CartonStatus,
    OrderReviewStatus,
    OrderShipmentLink,
    OrderStatus,
    Shipment,
    ShipmentStatus,
)
from .order_list_queries import build_orders_queryset
from .pack_handlers import (
    PREPARATEUR_LOCATION_LABELS,
    _resolve_preparateur_location,
    _resolve_preparateur_pack_family,
)
from .scan_pack_helpers import build_packing_bins

PREPARATEUR_SELECTED_ORDER_SESSION_KEY = "preparateur_selected_order_id"
PREPARATEUR_ORDER_PLAN_SESSION_KEY = "preparateur_order_plan"
PREPARATEUR_ORDER_GROUPS = (
    ("100_percent", "Réalisables à 100%"),
    ("partial", "Réalisables partiellement"),
    ("unavailable", "Non réalisables pour le moment"),
)
PREPARATEUR_PLAN_STATUS_PENDING = "pending"
PREPARATEUR_PLAN_STATUS_READY = "ready"
PREPARATEUR_FALLBACK_CARTON_SIZE = {
    "length_cm": 40.0,
    "width_cm": 30.0,
    "height_cm": 30.0,
    "max_weight_g": 8000,
}
PREPARATEUR_FALLBACK_CARTON_FORMAT_LABEL = "Standard"


def build_preparateur_orders_queryset():
    return (
        build_orders_queryset()
        .filter(review_status=OrderReviewStatus.APPROVED)
        .prefetch_related("lines__product__productlot_set", "shipment__carton_set")
    )


def clear_preparateur_order_plan(request):
    if PREPARATEUR_ORDER_PLAN_SESSION_KEY in request.session:
        request.session.pop(PREPARATEUR_ORDER_PLAN_SESSION_KEY, None)


def clear_preparateur_selected_order(request):
    if PREPARATEUR_SELECTED_ORDER_SESSION_KEY in request.session:
        request.session.pop(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, None)
    clear_preparateur_order_plan(request)


def set_preparateur_selected_order(request, order):
    request.session[PREPARATEUR_SELECTED_ORDER_SESSION_KEY] = order.id
    clear_preparateur_order_plan(request)


def get_preparateur_selected_order(request):
    order_id = request.session.get(PREPARATEUR_SELECTED_ORDER_SESSION_KEY)
    if not order_id:
        return None
    order = build_preparateur_orders_queryset().filter(pk=order_id).first()
    if order is None:
        clear_preparateur_selected_order(request)
    return order


def get_preparateur_order_plan(request):
    plan = request.session.get(PREPARATEUR_ORDER_PLAN_SESSION_KEY)
    if not isinstance(plan, dict):
        return None
    if not isinstance(plan.get("cartons"), list):
        return None
    return plan


def set_preparateur_order_plan(request, plan):
    request.session[PREPARATEUR_ORDER_PLAN_SESSION_KEY] = plan


def build_preparateur_selected_order_summary(order):
    if order is None:
        return None
    destination_parts = [
        part for part in [order.destination_city, order.destination_country] if part
    ]
    return {
        "id": order.id,
        "reference_label": order.reference or f"CMD-{order.id}",
        "recipient_name": (order.recipient_name or "").strip(),
        "shipper_name": (order.shipper_name or "").strip(),
        "destination_label": " - ".join(destination_parts),
        "shipment_reference": getattr(getattr(order, "shipment", None), "reference", ""),
    }


def _build_preparateur_order_reference_label(order):
    return order.reference or f"CMD-{order.id}"


def _build_preparateur_order_card(order):
    destination_parts = [
        part for part in [order.destination_city, order.destination_country] if part
    ]
    return {
        "order": order,
        "reference_label": _build_preparateur_order_reference_label(order),
        "association_name": (
            getattr(getattr(order, "association_contact", None), "name", "")
            or (order.recipient_name or "").strip()
        ),
        "recipient_name": (order.recipient_name or "").strip(),
        "destination_label": " - ".join(destination_parts),
        "shipment_reference": getattr(getattr(order, "shipment", None), "reference", ""),
    }


def _build_line_available_stock(line):
    free_stock_now = sum(
        max(0, lot.quantity_on_hand - lot.quantity_reserved)
        for lot in line.product.productlot_set.all()
    )
    return max(0, line.reserved_quantity) + free_stock_now


def _classify_preparateur_order(order):
    remaining_lines = [line for line in order.lines.all() if line.remaining_quantity > 0]
    if not remaining_lines:
        return ""

    all_coverable = True
    any_available_stock = False
    for line in remaining_lines:
        available_stock = _build_line_available_stock(line)
        if available_stock > 0:
            any_available_stock = True
        if available_stock < line.remaining_quantity:
            all_coverable = False

    if all_coverable:
        return "100_percent"
    if any_available_stock:
        return "partial"
    return "unavailable"


def build_preparateur_order_groups(orders=None):
    if orders is None:
        orders = build_preparateur_orders_queryset().order_by("-created_at", "-id")
    groups = {key: [] for key, _label in PREPARATEUR_ORDER_GROUPS}
    for order in orders:
        group_key = _classify_preparateur_order(order)
        if not group_key:
            continue
        groups[group_key].append(_build_preparateur_order_card(order))
    return groups


def build_preparateur_order_group_sections(order_groups):
    return [
        {
            "key": key,
            "label": label,
            "orders": order_groups[key],
        }
        for key, label in PREPARATEUR_ORDER_GROUPS
    ]


def _build_preparateur_carton_size():
    default_format = CartonFormat.objects.filter(is_default=True).first()
    if default_format is None:
        default_format = CartonFormat.objects.first()
    if default_format is None:
        return PREPARATEUR_FALLBACK_CARTON_SIZE.copy(), PREPARATEUR_FALLBACK_CARTON_FORMAT_LABEL
    return (
        {
            "length_cm": float(default_format.length_cm),
            "width_cm": float(default_format.width_cm),
            "height_cm": float(default_format.height_cm),
            "max_weight_g": int(default_format.max_weight_g),
        },
        default_format.name,
    )


def _build_location_label(location):
    if location is None:
        return "-"
    return f"{location.zone} - {location.aisle} - {location.shelf}"


def _build_preparateur_product_location(product):
    lots = product.productlot_set.select_related("location").order_by(
        "expires_on", "received_on", "id"
    )
    for lot in lots:
        if max(0, lot.quantity_on_hand - lot.quantity_reserved) > 0 and lot.location is not None:
            return lot.location
    return product.default_location


def _build_preparateur_plan_missing_row(line, *, available_quantity):
    location = _build_preparateur_product_location(line.product)
    return {
        "product_id": line.product_id,
        "product_name": line.product.name,
        "available_quantity": available_quantity,
        "missing_quantity": max(0, line.remaining_quantity - available_quantity),
        "remaining_quantity": line.remaining_quantity,
        "location_label": _build_location_label(location),
    }


def _build_plan_item(line, *, quantity):
    location = _build_preparateur_product_location(line.product)
    return {
        "line_id": line.id,
        "product_id": line.product_id,
        "product_name": line.product.name,
        "quantity": quantity,
        "location_label": _build_location_label(location),
    }


def _build_preparateur_plan_cartons(*, grouped_lines, carton_size):
    cartons = []
    warnings = []
    next_index = 1
    for family, lines in grouped_lines.items():
        line_items = [
            {"product": line["product"], "quantity": line["planned_quantity"]}
            for line in lines
            if line["planned_quantity"] > 0
        ]
        if not line_items:
            continue
        bins, _errors, family_warnings = build_packing_bins(
            line_items,
            carton_size,
            apply_defaults=True,
        )
        warnings.extend(family_warnings)
        line_by_product_id = {line["product_id"]: line for line in lines}
        for bin_data in bins or []:
            item_rows = []
            for entry in sorted(
                bin_data["items"].values(),
                key=lambda row: (row["product"].name.lower(), row["product"].id),
            ):
                line = line_by_product_id.get(entry["product"].id)
                if line is None:
                    continue
                item_rows.append(_build_plan_item(line["line"], quantity=entry["quantity"]))
            if not item_rows:
                continue
            zone_label = PREPARATEUR_LOCATION_LABELS.get(family, "")
            cartons.append(
                {
                    "index": next_index,
                    "label": f"Colis {next_index}",
                    "family": family,
                    "zone_label": zone_label,
                    "status": PREPARATEUR_PLAN_STATUS_PENDING,
                    "carton_id": None,
                    "carton_code": "",
                    "items": item_rows,
                }
            )
            next_index += 1
    return cartons, warnings


def _build_preparateur_order_plan_from_order(order):
    lines = [
        line
        for line in order.lines.select_related(
            "product", "product__default_location", "product__category"
        )
        .prefetch_related("product__productlot_set")
        .all()
        if line.remaining_quantity > 0
    ]
    carton_size, carton_format_label = _build_preparateur_carton_size()
    grouped_lines = defaultdict(list)
    unavailable_rows = []

    for line in lines:
        available_quantity = min(line.remaining_quantity, _build_line_available_stock(line))
        planned_quantity = max(0, available_quantity)
        family = _resolve_preparateur_pack_family(line.product, "")
        if planned_quantity > 0:
            grouped_lines[family].append(
                {
                    "line": line,
                    "product": line.product,
                    "product_id": line.product_id,
                    "planned_quantity": planned_quantity,
                }
            )
        if available_quantity < line.remaining_quantity:
            unavailable_rows.append(
                _build_preparateur_plan_missing_row(line, available_quantity=available_quantity)
            )

    cartons, warnings = _build_preparateur_plan_cartons(
        grouped_lines=grouped_lines,
        carton_size=carton_size,
    )
    return {
        "order_id": order.id,
        "reference_label": _build_preparateur_order_reference_label(order),
        "carton_format_label": carton_format_label,
        "carton_size": carton_size,
        "cartons": cartons,
        "warnings": sorted(set(warnings)),
        "unavailable_rows": unavailable_rows,
    }


def ensure_preparateur_order_plan(request, *, order):
    plan = get_preparateur_order_plan(request)
    if plan and plan.get("order_id") == order.id:
        return plan
    plan = _build_preparateur_order_plan_from_order(order)
    set_preparateur_order_plan(request, plan)
    return plan


def _resolve_preparateur_ready_location(family):
    if family not in PREPARATEUR_LOCATION_LABELS:
        return None
    try:
        return _resolve_preparateur_location(PREPARATEUR_LOCATION_LABELS[family])
    except ValueError:
        return None


def _ensure_preparateur_shipment(*, order, user):
    if order.shipment_id and order.shipment is not None:
        return order.shipment
    try:
        return create_shipment_for_order(order=order)
    except StockError:
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=(order.shipper_name or "").strip() or "ASF",
            recipient_name=(order.recipient_name or "").strip() or "-",
            destination_address=(order.destination_address or "").strip() or "-",
            destination_country=(order.destination_country or "").strip() or "France",
            created_by=order.created_by or user,
        )
        OrderShipmentLink.objects.get_or_create(
            order=order,
            shipment=shipment,
            defaults={"created_by": order.created_by or user},
        )
        order.shipment = shipment
        order.save(update_fields=["shipment"])
        return shipment


def build_preparateur_order_ready_cartons(order):
    if order is None or not order.shipment_id:
        return []
    cartons = (
        order.shipment.carton_set.all()
        .select_related("current_location")
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code", "id")
    )
    rows = []
    for carton in cartons:
        item_rows = []
        for item in carton.cartonitem_set.all():
            item_rows.append(
                {
                    "label": item.product_lot.product.name,
                    "quantity": item.quantity,
                }
            )
        rows.append(
            {
                "id": carton.id,
                "code": carton.code,
                "status": carton.status,
                "status_label": carton.get_status_display(),
                "edit_url": reverse("scan:scan_carton_edit", args=[carton.id]),
                "items": sorted(item_rows, key=lambda row: row["label"].lower()),
                "location_label": str(carton.current_location) if carton.current_location else "",
            }
        )
    return rows


def build_preparateur_order_picking_context(plan):
    cartons = []
    for carton in plan.get("cartons", []):
        item_rows = [
            {
                "label": row["product_name"],
                "quantity": row["quantity"],
                "location": row["location_label"],
            }
            for row in carton.get("items", [])
        ]
        cartons.append(
            {
                "carton_code": carton.get("carton_code") or carton.get("label") or "-",
                "item_rows": item_rows,
            }
        )
    return {
        "carton_blocks": cartons,
        "picking_title": "Liste picking - commande",
    }


def _find_preparateur_plan_carton(plan, *, carton_index):
    for carton in plan.get("cartons", []):
        if int(carton.get("index") or 0) == carton_index:
            return carton
    return None


@transaction.atomic
def mark_preparateur_plan_carton_ready(*, user, order, plan, carton_index):
    target_carton = _find_preparateur_plan_carton(plan, carton_index=carton_index)
    if target_carton is None:
        raise ValueError("Colis introuvable dans le plan.")
    if target_carton.get("status") == PREPARATEUR_PLAN_STATUS_READY and target_carton.get(
        "carton_id"
    ):
        return target_carton["carton_id"]

    shipment = _ensure_preparateur_shipment(order=order, user=user)
    line_by_id = {line.id: line for line in order.lines.select_related("product").all()}
    carton_size = plan.get("carton_size") or PREPARATEUR_FALLBACK_CARTON_SIZE.copy()
    current_location = _resolve_preparateur_ready_location(target_carton.get("family", ""))
    created_carton = None

    for item in target_carton.get("items", []):
        line = line_by_id.get(item.get("line_id"))
        if line is None:
            raise ValueError("Ligne de commande introuvable.")
        quantity = int(item.get("quantity") or 0)
        if quantity <= 0:
            continue
        if quantity > int(line.remaining_quantity or 0):
            raise ValueError("La quantité restante de la commande a changé, rechargez le plan.")
        reserved_quantity = min(int(line.reserved_quantity or 0), quantity)
        if reserved_quantity > 0:
            created_carton = pack_carton_from_reserved(
                user=user,
                line=line,
                quantity=reserved_quantity,
                carton=created_carton,
                shipment=shipment,
                current_location=current_location,
                carton_size=carton_size,
            )
        remaining_quantity = quantity - reserved_quantity
        if remaining_quantity > 0:
            created_carton = pack_carton(
                user=user,
                product=line.product,
                quantity=remaining_quantity,
                carton=created_carton,
                shipment=shipment,
                current_location=current_location,
                carton_size=carton_size,
            )
            line.prepared_quantity += remaining_quantity
            line.save(update_fields=["prepared_quantity"])

    if created_carton is None:
        raise ValueError("Le colis ne contient aucun produit préparé.")

    if created_carton.status != CartonStatus.PACKED:
        set_carton_status(
            carton=created_carton,
            new_status=CartonStatus.PACKED,
            reason="scan_preparateur_order_ready",
            user=user,
        )
    ensure_carton_code(created_carton, type_code=target_carton.get("family") or None)

    order.refresh_from_db()
    remaining_lines = list(order.lines.all())
    order.status = (
        OrderStatus.READY
        if remaining_lines and all(line.remaining_quantity == 0 for line in remaining_lines)
        else OrderStatus.PREPARING
    )
    order.save(update_fields=["status"])

    target_carton["status"] = PREPARATEUR_PLAN_STATUS_READY
    target_carton["carton_id"] = created_carton.id
    target_carton["carton_code"] = created_carton.code
    return created_carton.id
