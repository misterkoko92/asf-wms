from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .carton_activity import find_last_carton_for_volunteer
from .domain.orders import prepare_order, reserve_stock_for_order
from .models import Order, OrderReviewStatus, OrderStatus
from .order_helpers import attach_order_documents_to_shipment
from .preparateur_home_queries import build_preparateur_order_groups
from .preparateur_session import (
    build_preparateur_volunteer_label,
    list_active_preparateur_volunteers,
    set_active_preparateur_volunteer,
)
from .services import StockError
from .view_permissions import scan_staff_required

TEMPLATE_PREPARATEUR_HOME = "scan/preparateur_home.html"
ACTIVE_PREPARATEUR_HOME = "preparateur_home"


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparateur_home(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "set_active_volunteer":
            volunteer_id = (request.POST.get("volunteer_id") or "").strip()
            volunteer = next(
                (
                    volunteer
                    for volunteer in list_active_preparateur_volunteers()
                    if str(volunteer.id) == volunteer_id
                ),
                None,
            )
            if volunteer is None:
                messages.error(request, "Bénévole introuvable.")
            else:
                set_active_preparateur_volunteer(request, volunteer=volunteer)
                messages.success(
                    request,
                    f"Bénévole actif : {build_preparateur_volunteer_label(volunteer)}.",
                )
            return redirect("scan:scan_preparateur_home")
        active_volunteer = getattr(request, "scan_active_volunteer", None)
        if active_volunteer is None:
            messages.error(request, "Choisissez un bénévole avant de continuer.")
            return redirect("scan:scan_preparateur_home")
        if action == "prepare_order":
            order_id = (request.POST.get("order_id") or "").strip()
            order = (
                Order.objects.filter(id=order_id, review_status=OrderReviewStatus.APPROVED)
                .prefetch_related("lines")
                .first()
            )
            if order is None:
                messages.error(request, "Commande introuvable.")
                return redirect("scan:scan_preparateur_home")
            created_cartons = []
            try:
                if order.status == OrderStatus.DRAFT:
                    reserve_stock_for_order(order=order)
                prepare_order(
                    user=request.user,
                    order=order,
                    prepared_by_user=active_volunteer.user,
                    volunteer_profile=active_volunteer,
                    actor_user=request.user,
                    created_cartons=created_cartons,
                )
            except StockError as exc:
                messages.error(request, str(exc))
                return redirect("scan:scan_preparateur_home")
            order.refresh_from_db()
            shipment = getattr(order, "shipment", None)
            if shipment is not None:
                attach_order_documents_to_shipment(order, shipment)
            if created_cartons:
                messages.success(
                    request,
                    "Préparation lancée: colis créés et rattachés à l'expédition.",
                )
                return redirect("scan:scan_carton_edit", carton_id=created_cartons[-1].id)
            messages.success(request, "Préparation lancée.")
            return redirect("scan:scan_preparateur_home")
        if action == "view_last_carton":
            last_carton = find_last_carton_for_volunteer(active_volunteer)
            if last_carton is None:
                messages.error(request, "Aucun carton trouvé pour ce bénévole.")
                return redirect("scan:scan_preparateur_home")
            return redirect("scan:scan_carton_edit", carton_id=last_carton.id)
        messages.error(request, "Action préparateur inconnue.")
        return redirect("scan:scan_preparateur_home")

    active_volunteer = getattr(request, "scan_active_volunteer", None)
    order_groups, selected_order_id = (
        build_preparateur_order_groups() if active_volunteer is not None else ([], None)
    )
    last_carton = find_last_carton_for_volunteer(active_volunteer) if active_volunteer else None
    volunteer_options = [
        {
            "id": volunteer.id,
            "label": build_preparateur_volunteer_label(volunteer),
        }
        for volunteer in list_active_preparateur_volunteers()
    ]
    return render(
        request,
        TEMPLATE_PREPARATEUR_HOME,
        {
            "active": ACTIVE_PREPARATEUR_HOME,
            "volunteer_options": volunteer_options,
            "selected_volunteer_id": getattr(active_volunteer, "id", None),
            "has_active_volunteer": active_volunteer is not None,
            "order_groups": order_groups,
            "selected_order_id": selected_order_id,
            "last_carton_id": getattr(last_carton, "id", None),
        },
    )
