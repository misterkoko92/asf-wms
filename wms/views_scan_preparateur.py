from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .preparateur_orders import clear_preparateur_selected_order
from .preparateur_session import (
    build_preparateur_volunteer_label,
    build_preparateur_volunteer_queryset,
    clear_active_preparateur_volunteer,
    get_active_preparateur_volunteer,
    set_active_preparateur_volunteer,
)
from .scan_permissions import user_is_preparateur
from .view_permissions import scan_staff_required

TEMPLATE_PREPARATEUR_HOME = "scan/preparateur_home.html"
ACTIVE_PREPARATEUR_HOME = "preparateur_home"


def _build_preparateur_home_context(*, active_volunteer):
    volunteer_options = [
        {
            "id": volunteer.id,
            "label": build_preparateur_volunteer_label(volunteer),
        }
        for volunteer in build_preparateur_volunteer_queryset()
    ]
    return {
        "active": ACTIVE_PREPARATEUR_HOME,
        "active_volunteer": active_volunteer,
        "active_volunteer_id": active_volunteer.id if active_volunteer is not None else "",
        "has_active_volunteer": active_volunteer is not None,
        "volunteer_options": volunteer_options,
    }


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparateur_home(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_dashboard")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        volunteer_id = (request.POST.get("volunteer_id") or "").strip()
        volunteer = (
            build_preparateur_volunteer_queryset().filter(pk=volunteer_id).first()
            if volunteer_id
            else None
        )
        if volunteer is not None:
            set_active_preparateur_volunteer(request, volunteer)
        elif not action:
            clear_active_preparateur_volunteer(request)

        active_volunteer = volunteer or get_active_preparateur_volunteer(request)
        if action == "prepare_order":
            if active_volunteer is None:
                return redirect("scan:scan_preparateur_home")
            return redirect("scan:scan_preparateur_order_select")
        if action == "prepare_cartons":
            if active_volunteer is None:
                return redirect("scan:scan_preparateur_home")
            clear_preparateur_selected_order(request)
            return redirect("scan:scan_pack")
        return redirect("scan:scan_preparateur_home")

    active_volunteer = get_active_preparateur_volunteer(request)
    return render(
        request,
        TEMPLATE_PREPARATEUR_HOME,
        _build_preparateur_home_context(active_volunteer=active_volunteer),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_preparateur_pack_start(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_pack")
    clear_preparateur_selected_order(request)
    return redirect("scan:scan_pack")
