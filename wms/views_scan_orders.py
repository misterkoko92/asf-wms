from urllib.parse import urlencode

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
    build_preparateur_orders_queryset,
    set_preparateur_selected_order,
)
from .scan_helpers import build_product_options
from .scan_permissions import user_is_preparateur
from .view_permissions import scan_staff_required
from .view_utils import sorted_choices

TEMPLATE_SCAN_ORDER = "scan/order.html"
TEMPLATE_ORDERS_VIEW = "scan/orders_view.html"
TEMPLATE_ORDER_DETAIL = "scan/order_detail.html"
TEMPLATE_PREPARATEUR_ORDER_SELECT = "scan/preparateur_order_select.html"

ACTIVE_ORDER = "order"
ACTIVE_ORDERS_VIEW = "orders_view"
ACTIVE_PREPARATEUR_ORDER_SELECT = "preparateur_order_select"


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


def _render_preparateur_order_select(request, *, orders):
    return render(
        request,
        TEMPLATE_PREPARATEUR_ORDER_SELECT,
        {
            "active": ACTIVE_PREPARATEUR_ORDER_SELECT,
            "orders": orders,
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
        redirect_url = reverse("scan:scan_pack")
        if order.shipment_id and order.shipment and order.shipment.reference:
            shipment_query = urlencode({"shipment_reference": order.shipment.reference})
            return redirect(f"{redirect_url}?{shipment_query}")
        return redirect(redirect_url)

    return _render_preparateur_order_select(
        request,
        orders=orders_qs,
    )
