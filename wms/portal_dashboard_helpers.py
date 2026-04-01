from .models import OrderReviewStatus, ShipmentStatus

IN_PROGRESS_SHIPMENT_STATUSES = {
    ShipmentStatus.DRAFT,
    ShipmentStatus.PICKING,
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
}


def build_portal_dashboard_kpis(orders):
    return {
        "orders_total": len(orders),
        "orders_pending_review": sum(
            1 for order in orders if order.review_status == OrderReviewStatus.PENDING
        ),
        "orders_changes_requested": sum(
            1 for order in orders if order.review_status == OrderReviewStatus.CHANGES_REQUESTED
        ),
        "orders_with_shipment": sum(1 for order in orders if order.shipment_id),
        "orders_shipments_in_progress": sum(
            1
            for order in orders
            if order.shipment_id
            and getattr(order.shipment, "status", None) in IN_PROGRESS_SHIPMENT_STATUSES
        ),
    }


def portal_order_next_step_label(order):
    if order.review_status == OrderReviewStatus.CHANGES_REQUESTED:
        return "Corriger la commande"
    if order.review_status == OrderReviewStatus.PENDING:
        return "Attendre la validation ASF"
    if not order.shipment_id:
        return "Préparation ASF en cours"

    shipment_status = getattr(order.shipment, "status", "")
    if shipment_status == ShipmentStatus.DELIVERED:
        return "Réception confirmée"
    if shipment_status == ShipmentStatus.RECEIVED_CORRESPONDENT:
        return "Attendre la livraison destinataire"
    return "Suivre l'expédition"


def portal_order_next_step_tone(order):
    if order.review_status == OrderReviewStatus.CHANGES_REQUESTED:
        return "warning"
    if order.review_status == OrderReviewStatus.PENDING:
        return "info"
    if not order.shipment_id:
        return "info"

    shipment_status = getattr(order.shipment, "status", "")
    if shipment_status == ShipmentStatus.DELIVERED:
        return "ready"
    return "info"
