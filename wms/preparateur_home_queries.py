from datetime import date

from django.db.models import F, IntegerField, Sum, Value
from django.db.models.functions import Coalesce

from .models import Order, OrderReviewStatus, OrderStatus, ProductLot, ProductLotStatus

ORDER_GROUP_CRITICAL = "Les 3 commandes les plus critiques"
ORDER_GROUP_ALL = "Toutes les commandes"


def _available_stock_by_product_id():
    rows = (
        ProductLot.objects.filter(status=ProductLotStatus.AVAILABLE)
        .annotate(available=F("quantity_on_hand") - F("quantity_reserved"))
        .values("product_id")
        .annotate(total_available=Coalesce(Sum("available"), Value(0), output_field=IntegerField()))
    )
    return {row["product_id"]: int(row["total_available"] or 0) for row in rows}


def _shipper_display_name(order):
    shipper_contact = getattr(order, "shipper_contact", None)
    shipper_name = (
        getattr(shipper_contact, "name", "") if shipper_contact is not None else order.shipper_name
    )
    return (shipper_name or order.shipper_name or order.reference or f"Commande {order.id}").strip()


def _remaining_total(order):
    return sum(max(0, int(line.remaining_quantity or 0)) for line in order.lines.all())


def _order_is_realisable_now(order, *, available_stock_by_product_id):
    if _remaining_total(order) <= 0:
        return False
    if order.status in {OrderStatus.RESERVED, OrderStatus.PREPARING}:
        return True
    for line in order.lines.all():
        remaining_quantity = max(0, int(line.remaining_quantity or 0))
        if remaining_quantity <= 0:
            continue
        if int(available_stock_by_product_id.get(line.product_id, 0) or 0) < remaining_quantity:
            return False
    return True


def _critical_sort_key(order):
    requested_delivery_date = order.requested_delivery_date
    return (
        requested_delivery_date is None,
        requested_delivery_date or date.max,
        order.created_at,
        order.id,
    )


def _alphabetical_sort_key(order):
    return (
        _shipper_display_name(order).casefold(),
        order.created_at,
        order.id,
    )


def _build_order_option(order):
    reference = (order.reference or f"CMD-{order.id}").strip()
    remaining_total = _remaining_total(order)
    requested_delivery_date = (
        order.requested_delivery_date.strftime("%d/%m/%Y") if order.requested_delivery_date else "-"
    )
    return {
        "order": order,
        "label": (
            f"{_shipper_display_name(order)} · {reference} · "
            f"reste {remaining_total} · livraison {requested_delivery_date}"
        ),
    }


def _candidate_orders_queryset():
    return (
        Order.objects.filter(review_status=OrderReviewStatus.APPROVED)
        .exclude(status__in={OrderStatus.CANCELLED, OrderStatus.READY})
        .select_related("shipper_contact")
        .prefetch_related("lines")
    )


def build_preparateur_order_groups():
    available_stock_by_product_id = _available_stock_by_product_id()
    realizable_orders = [
        order
        for order in _candidate_orders_queryset()
        if _order_is_realisable_now(
            order, available_stock_by_product_id=available_stock_by_product_id
        )
    ]
    critical_orders = sorted(realizable_orders, key=_critical_sort_key)[:3]
    all_orders = sorted(realizable_orders, key=_alphabetical_sort_key)
    order_groups = [
        {
            "label": ORDER_GROUP_CRITICAL,
            "options": [_build_order_option(order) for order in critical_orders],
        },
        {
            "label": ORDER_GROUP_ALL,
            "options": [_build_order_option(order) for order in all_orders],
        },
    ]
    selected_order_id = None
    if critical_orders:
        selected_order_id = critical_orders[0].id
    elif all_orders:
        selected_order_id = all_orders[0].id
    return order_groups, selected_order_id
