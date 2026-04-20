from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import OrderReviewStatus
from .order_list_queries import build_orders_list_context, build_orders_queryset
from .order_scan_handlers import handle_order_action
from .order_scan_state import build_order_scan_state
from .order_view_handlers import handle_order_detail_action, handle_orders_view_action
from .order_view_helpers import build_order_detail_payload
from .preparateur_orders import (
    build_preparateur_order_group_sections,
    build_preparateur_order_groups,
    build_preparateur_order_picking_context,
    build_preparateur_order_ready_cartons,
    build_preparateur_orders_queryset,
    build_preparateur_selected_order_summary,
    ensure_preparateur_order_plan,
    get_preparateur_selected_order,
    mark_preparateur_plan_carton_ready,
    set_preparateur_order_plan,
    set_preparateur_selected_order,
)
from .scan_helpers import build_product_options
from .scan_permissions import user_is_preparateur
from .services import StockError
from .view_permissions import scan_staff_required
from .view_utils import sorted_choices

TEMPLATE_SCAN_ORDER = "scan/order.html"
TEMPLATE_ORDERS_VIEW = "scan/orders_view.html"
TEMPLATE_ORDER_DETAIL = "scan/order_detail.html"
TEMPLATE_PREPARATEUR_ORDER_SELECT = "scan/preparateur_order_select.html"
TEMPLATE_PREPARATEUR_ORDER_PREPARE = "scan/preparateur_order_prepare.html"
TEMPLATE_PREPARATEUR_ORDER_PICKING = "print/picking_list_kits.html"

ACTIVE_ORDER = "order"
ACTIVE_ORDERS_VIEW = "orders_view"
ACTIVE_PREPARATEUR_ORDER_SELECT = "preparateur_order_select"
ACTIVE_PREPARATEUR_ORDER_PREPARE = "preparateur_order_prepare"


def _render_scan_order(request, *, product_options, order_state):
    return render(
        request,
        TEMPLATE_SCAN_ORDER,
        {
            "active": ACTIVE_ORDER,
            "products_json": product_options,
            "select_form": order_state["select_form"],
            "create_form": order_state["create_form"],
            "line_form": order_state["line_form"],
            "selected_order": order_state["selected_order"],
            "order_lines": order_state["order_lines"],
            "remaining_total": order_state["remaining_total"],
        },
    )


def _render_orders_view(request, *, list_context):
    return render(
        request,
        TEMPLATE_ORDERS_VIEW,
        {
            "active": ACTIVE_ORDERS_VIEW,
            **list_context,
            "approved_status": OrderReviewStatus.APPROVED,
            "rejected_status": OrderReviewStatus.REJECTED,
            "changes_status": OrderReviewStatus.CHANGES_REQUESTED,
        },
    )


def _render_order_detail(request, *, detail):
    return render(
        request,
        TEMPLATE_ORDER_DETAIL,
        {
            "active": ACTIVE_ORDERS_VIEW,
            "detail": detail,
            "review_status_choices": sorted_choices(OrderReviewStatus.choices),
        },
    )


def _render_preparateur_order_select(request, *, order_group_sections, order_groups):
    return render(
        request,
        TEMPLATE_PREPARATEUR_ORDER_SELECT,
        {
            "active": ACTIVE_PREPARATEUR_ORDER_SELECT,
            "order_group_sections": order_group_sections,
            "order_groups": order_groups,
        },
    )


def _render_preparateur_order_prepare(request, *, order, plan):
    pending_cartons = [
        carton for carton in plan.get("cartons", []) if carton.get("status") != "ready"
    ]
    return render(
        request,
        TEMPLATE_PREPARATEUR_ORDER_PREPARE,
        {
            "active": ACTIVE_PREPARATEUR_ORDER_PREPARE,
            "order": order,
            "order_summary": build_preparateur_selected_order_summary(order),
            "plan": plan,
            "pending_cartons": pending_cartons,
            "ready_cartons": build_preparateur_order_ready_cartons(order),
            "picking_url": reverse("scan:scan_preparateur_order_prepare_picking"),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_order(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    order_state = build_order_scan_state(request, action=action)

    if request.method == "POST":
        response, handler_lines, handler_remaining = handle_order_action(
            request,
            action=action,
            select_form=order_state["select_form"],
            create_form=order_state["create_form"],
            line_form=order_state["line_form"],
            selected_order=order_state["selected_order"],
        )
        if response:
            return response
        if handler_lines is not None:
            order_state["order_lines"] = handler_lines
            order_state["remaining_total"] = handler_remaining

    return _render_scan_order(
        request,
        product_options=product_options,
        order_state=order_state,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_orders_view(request):
    orders_qs = build_orders_queryset()

    if request.method == "POST":
        response = handle_orders_view_action(request, orders_qs=orders_qs)
        if response:
            return response

    return _render_orders_view(
        request,
        list_context=build_orders_list_context(request),
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_order_detail(request, order_id):
    order = get_object_or_404(build_orders_queryset(), id=order_id)
    if request.method == "POST":
        response = handle_order_detail_action(request, order=order)
        if response:
            return response
    detail = build_order_detail_payload(order)
    return _render_order_detail(request, detail=detail)


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparateur_order_select(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_orders_view")

    orders_qs = build_preparateur_orders_queryset().order_by("-created_at", "-id")
    if request.method == "POST":
        order = get_object_or_404(orders_qs, pk=request.POST.get("order_id"))
        set_preparateur_selected_order(request, order)
        return redirect(reverse("scan:scan_preparateur_order_prepare"))

    order_groups = build_preparateur_order_groups(orders_qs)
    return _render_preparateur_order_select(
        request,
        order_group_sections=build_preparateur_order_group_sections(order_groups),
        order_groups=order_groups,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparateur_order_prepare(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_orders_view")

    order = get_preparateur_selected_order(request)
    if order is None:
        return redirect("scan:scan_preparateur_order_select")

    plan = ensure_preparateur_order_plan(request, order=order)
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "mark_carton_ready":
            try:
                carton_index = int(request.POST.get("carton_index") or 0)
                carton_id = mark_preparateur_plan_carton_ready(
                    user=request.user,
                    order=order,
                    plan=plan,
                    carton_index=carton_index,
                )
            except (TypeError, ValueError, StockError) as exc:
                messages.error(request, str(exc))
            else:
                set_preparateur_order_plan(request, plan)
                messages.success(request, "Le colis a été marqué prêt.")
        return redirect("scan:scan_preparateur_order_prepare")

    return _render_preparateur_order_prepare(request, order=order, plan=plan)


@scan_staff_required
@require_http_methods(["GET"])
def scan_preparateur_order_prepare_picking(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_orders_view")

    order = get_preparateur_selected_order(request)
    if order is None:
        return redirect("scan:scan_preparateur_order_select")

    plan = ensure_preparateur_order_plan(request, order=order)
    return render(
        request,
        TEMPLATE_PREPARATEUR_ORDER_PICKING,
        build_preparateur_order_picking_context(plan),
    )
