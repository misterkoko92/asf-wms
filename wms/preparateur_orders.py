from .models import OrderReviewStatus
from .order_list_queries import build_orders_queryset

PREPARATEUR_SELECTED_ORDER_SESSION_KEY = "preparateur_selected_order_id"


def build_preparateur_orders_queryset():
    return build_orders_queryset().filter(review_status=OrderReviewStatus.APPROVED)


def clear_preparateur_selected_order(request):
    if PREPARATEUR_SELECTED_ORDER_SESSION_KEY in request.session:
        request.session.pop(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, None)


def set_preparateur_selected_order(request, order):
    request.session[PREPARATEUR_SELECTED_ORDER_SESSION_KEY] = order.id


def get_preparateur_selected_order(request):
    order_id = request.session.get(PREPARATEUR_SELECTED_ORDER_SESSION_KEY)
    if not order_id:
        return None
    order = build_preparateur_orders_queryset().filter(pk=order_id).first()
    if order is None:
        clear_preparateur_selected_order(request)
    return order


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
