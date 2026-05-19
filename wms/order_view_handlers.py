from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import OrderReviewStatus
from .order_helpers import attach_order_documents_to_shipment
from .scan_helpers import parse_int
from .services import (
    StockError,
    create_shipment_for_order,
    default_order_shipment_carton_counts,
    estimate_order_preparation_carton_count,
    normalize_order_shipment_carton_counts,
    prepare_order,
)


def _update_review_status(request, *, order):
    status = (request.POST.get("review_status") or "").strip()
    valid = {choice[0] for choice in OrderReviewStatus.choices}
    if status not in valid:
        messages.error(request, "Statut invalide.")
        return

    order.review_status = status
    if status == OrderReviewStatus.PENDING:
        order.reviewed_at = None
    else:
        order.reviewed_at = timezone.now()
    order.save(update_fields=["review_status", "reviewed_at"])
    messages.success(request, "Statut de validation mis à jour.")


def _create_shipment(request, *, order):
    if order.review_status != OrderReviewStatus.APPROVED:
        messages.error(request, "Commande non validée.")
        return redirect("scan:scan_order_detail", order_id=order.id)
    shipment = create_shipment_for_order(order=order)
    attach_order_documents_to_shipment(order, shipment)
    return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)


def _prepare_confirmation_url(order):
    return f"{reverse('scan:scan_order_detail', args=[order.id])}?prepare_confirm=1"


def _parse_shipment_count(request, *, default=1):
    try:
        shipment_count = int((request.POST.get("shipment_count") or "").strip())
    except (TypeError, ValueError):
        return default
    return shipment_count if shipment_count > 0 else default


def _carton_counts_from_request(request):
    values = request.POST.getlist("cartons_per_shipment")
    return values if values else None


def _prepare_shipment_and_cartons(request, *, order):
    if order.review_status != OrderReviewStatus.APPROVED:
        messages.error(request, "Commande non validée.")
        return redirect("scan:scan_order_detail", order_id=order.id)
    confirmed_multi_shipment = (request.POST.get("multi_shipment_confirmed") or "").strip() == "1"
    estimated_carton_count = None
    try:
        estimated_carton_count, _warnings = estimate_order_preparation_carton_count(order)
    except StockError as exc:
        messages.error(request, str(exc))
        return redirect("scan:scan_order_detail", order_id=order.id)

    if not confirmed_multi_shipment:
        if estimated_carton_count > 10:
            return redirect(_prepare_confirmation_url(order))

    shipment_count = _parse_shipment_count(
        request,
        default=1,
    )
    shipment_carton_counts = None
    if confirmed_multi_shipment:
        requested_carton_counts = _carton_counts_from_request(request)
        try:
            shipment_carton_counts = normalize_order_shipment_carton_counts(
                estimated_carton_count,
                shipment_count,
                requested_carton_counts
                or default_order_shipment_carton_counts(
                    estimated_carton_count,
                    shipment_count,
                ),
            )
        except StockError as exc:
            messages.error(request, str(exc))
            return redirect(_prepare_confirmation_url(order))
    packing_warnings = []
    prepared_shipments = []
    try:
        prepare_order(
            user=request.user,
            order=order,
            shipment_count=shipment_count,
            shipment_carton_counts=shipment_carton_counts,
            packing_warnings=packing_warnings,
            prepared_shipments=prepared_shipments,
        )
    except StockError as exc:
        messages.error(request, str(exc))
        return redirect("scan:scan_order_detail", order_id=order.id)
    order.refresh_from_db()
    shipment = prepared_shipments[0] if prepared_shipments else getattr(order, "shipment", None)
    if shipment is not None:
        for prepared_shipment in prepared_shipments or [shipment]:
            attach_order_documents_to_shipment(order, prepared_shipment)
        for warning in packing_warnings:
            messages.warning(request, warning)
        if len(prepared_shipments) > 1:
            messages.success(
                request,
                (
                    "Préparation lancée: colis créés et répartis sur "
                    f"{len(prepared_shipments)} expéditions."
                ),
            )
        else:
            messages.success(
                request,
                "Préparation lancée: colis créés et rattachés à l'expédition.",
            )
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)
    messages.success(request, "Préparation lancée.")
    return redirect("scan:scan_order_detail", order_id=order.id)


def handle_orders_view_action(request, *, orders_qs):
    action = (request.POST.get("action") or "").strip()
    order_id = parse_int(request.POST.get("order_id"))
    order = orders_qs.filter(id=order_id).first() if order_id else None
    if not order:
        messages.error(request, "Commande introuvable.")
        return redirect("scan:scan_orders_view")

    if action == "update_status":
        _update_review_status(request, order=order)
        return redirect("scan:scan_orders_view")

    if action == "create_shipment":
        if order.review_status != OrderReviewStatus.APPROVED:
            messages.error(request, "Commande non validée.")
            return redirect("scan:scan_orders_view")
        shipment = create_shipment_for_order(order=order)
        attach_order_documents_to_shipment(order, shipment)
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    return None


def handle_order_detail_action(request, *, order):
    action = (request.POST.get("action") or "").strip()

    if action == "update_status":
        _update_review_status(request, order=order)
        return redirect("scan:scan_order_detail", order_id=order.id)

    if action == "create_shipment":
        return _create_shipment(request, order=order)

    if action == "create_shipment_and_cartons":
        return _prepare_shipment_and_cartons(request, order=order)

    return None
