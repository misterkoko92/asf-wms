from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Order, OrderReviewStatus
from .order_scan_handlers import handle_order_action
from .order_scan_state import build_order_scan_state
from .order_view_handlers import handle_orders_view_action
from .order_view_helpers import build_orders_view_rows
from .scan_helpers import build_product_options
from .view_permissions import scan_staff_required
from .view_utils import sorted_choices

TEMPLATE_SCAN_ORDER = "scan/order.html"
TEMPLATE_ORDERS_VIEW = "scan/orders_view.html"

ACTIVE_ORDER = "order"
ACTIVE_ORDERS_VIEW = "orders_view"


def _build_orders_queryset():
    return (
        Order.objects.select_related(
            "association_contact",
            "recipient_contact",
            "created_by",
            "shipment",
        )
        .prefetch_related("documents")
        .order_by("-created_at")
    )


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


def _render_orders_view(request, *, rows):
    return render(
        request,
        TEMPLATE_ORDERS_VIEW,
        {
            "active": ACTIVE_ORDERS_VIEW,
            "orders": rows,
            "review_status_choices": sorted_choices(OrderReviewStatus.choices),
            "approved_status": OrderReviewStatus.APPROVED,
            "rejected_status": OrderReviewStatus.REJECTED,
            "changes_status": OrderReviewStatus.CHANGES_REQUESTED,
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
    orders_qs = _build_orders_queryset()

    if request.method == "POST":
        response = handle_orders_view_action(request, orders_qs=orders_qs)
        if response:
            return response

    rows = build_orders_view_rows(orders_qs)
    return _render_orders_view(request, rows=rows)
