from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from .models import OrderReviewStatus
from .order_helpers import attach_order_documents_to_shipment
from .scan_helpers import parse_int
from .services import create_shipment_for_order


def handle_orders_view_action(request, *, orders_qs):
    action = (request.POST.get("action") or "").strip()
    order_id = parse_int(request.POST.get("order_id"))
    order = orders_qs.filter(id=order_id).first() if order_id else None
    if not order:
        messages.error(request, "Commande introuvable.")
        return redirect("scan:scan_orders_view")

    if action == "update_status":
        status = (request.POST.get("review_status") or "").strip()
        valid = {choice[0] for choice in OrderReviewStatus.choices}
        if status not in valid:
            messages.error(request, "Statut invalide.")
        else:
            order.review_status = status
            if status == OrderReviewStatus.PENDING:
                order.reviewed_at = None
            else:
                order.reviewed_at = timezone.now()
            order.save(update_fields=["review_status", "reviewed_at"])
            messages.success(request, "Statut de validation mis à jour.")
        return redirect("scan:scan_orders_view")

    if action == "create_shipment":
        if order.review_status != OrderReviewStatus.APPROVED:
            messages.error(request, "Commande non validée.")
            return redirect("scan:scan_orders_view")
        shipment = create_shipment_for_order(order=order)
        attach_order_documents_to_shipment(order, shipment)
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    return None
