from django.db.models import DateTimeField, F, Max, Q, Value
from django.db.models.functions import Coalesce

from wms.models import Order, ShipmentTrackingStatus
from wms.portal_dashboard_helpers import (
    build_portal_dashboard_kpis,
    portal_order_next_step_label,
    portal_order_next_step_tone,
)
from wms.status_presenters import (
    present_order_review_status,
    present_order_shipment_status,
    present_order_status,
)


def decorate_portal_dashboard_order(order):
    order.order_status_display = present_order_status(order)
    order.review_status_display = present_order_review_status(order)
    order.shipment_status_display = present_order_shipment_status(order)
    order.next_step_label = portal_order_next_step_label(order)
    order.next_step_tone = portal_order_next_step_tone(order)
    return order


def _portal_dashboard_orders_queryset(profile):
    return (
        Order.objects.filter(association_contact=profile.contact)
        .select_related("shipment__destination")
        .annotate(
            escale_label=Coalesce(
                "shipment__destination__city",
                "destination_city",
                Value(""),
            ),
            shipped_at=Coalesce(
                Max(
                    "shipment__tracking_events__created_at",
                    filter=Q(shipment__tracking_events__status=ShipmentTrackingStatus.BOARDING_OK),
                ),
                F("shipment__created_at"),
                output_field=DateTimeField(),
            ),
            received_correspondent_at=Max(
                "shipment__tracking_events__created_at",
                filter=Q(
                    shipment__tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
                ),
            ),
            received_recipient_at=Max(
                "shipment__tracking_events__created_at",
                filter=Q(
                    shipment__tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT
                ),
            ),
        )
        .order_by("-created_at")
    )


def _portal_dashboard_order_row(order):
    return {
        "id": order.id,
        "reference": order.reference or f"CMD-{order.id}",
        "review_status": order.review_status,
        "review_status_label": order.get_review_status_display(),
        "shipment_id": order.shipment_id,
        "shipment_reference": order.shipment.reference if order.shipment_id else "",
        "next_step_label": order.next_step_label,
        "next_step_tone": order.next_step_tone,
        "requested_delivery_date": (
            order.requested_delivery_date.isoformat() if order.requested_delivery_date else None
        ),
        "created_at": order.created_at.isoformat(),
    }


def build_portal_dashboard_payload(*, profile, api_limit: int = 12):
    orders = [
        decorate_portal_dashboard_order(order)
        for order in _portal_dashboard_orders_queryset(profile)
    ]
    return {
        "orders": orders,
        "dashboard_kpis": build_portal_dashboard_kpis(orders),
        "order_rows": [_portal_dashboard_order_row(order) for order in orders[:api_limit]],
    }
