from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import ScanReceiptAssociationForm
from .models import Receipt, ReceiptType
from .receipt_handlers import (
    build_hors_format_lines,
    handle_receipt_action,
    handle_receipt_association_post,
)
from .receipt_pallet_state import (
    build_receive_pallet_context,
    build_receive_pallet_state,
)
from .receipt_scan_state import build_receipt_scan_state
from .receipt_view_helpers import build_receipts_view_rows
from .scan_helpers import build_product_options
from .view_permissions import scan_staff_required

TEMPLATE_RECEIPTS_VIEW = "scan/receipts_view.html"
TEMPLATE_RECEIVE = "scan/receive.html"
TEMPLATE_RECEIVE_PALLET = "scan/receive_pallet.html"
TEMPLATE_RECEIVE_ASSOCIATION = "scan/receive_association.html"

ACTIVE_RECEIPTS_VIEW = "receipts_view"
ACTIVE_RECEIVE = "receive"
ACTIVE_RECEIVE_ASSOCIATION = "receive_association"

RECEIPT_FILTER_MAP = {
    "pallet": ReceiptType.PALLET,
    "association": ReceiptType.ASSOCIATION,
}


def _resolve_receipts_filter(raw_filter_value):
    filter_value = (raw_filter_value or "all").strip().lower()
    if filter_value in RECEIPT_FILTER_MAP:
        return filter_value
    return "all"


def _build_receipts_queryset(filter_value):
    receipts_qs = (
        Receipt.objects.select_related("source_contact", "carrier_contact")
        .prefetch_related("hors_format_items")
        .order_by("-received_on", "-created_at")
    )
    receipt_type = RECEIPT_FILTER_MAP.get(filter_value)
    if receipt_type:
        receipts_qs = receipts_qs.filter(receipt_type=receipt_type)
    return receipts_qs


def _render_scan_receive(request, *, product_options, receipt_state):
    return render(
        request,
        TEMPLATE_RECEIVE,
        {
            "active": ACTIVE_RECEIVE,
            "products_json": product_options,
            "select_form": receipt_state["select_form"],
            "create_form": receipt_state["create_form"],
            "line_form": receipt_state["line_form"],
            "selected_receipt": receipt_state["selected_receipt"],
            "receipt_lines": receipt_state["receipt_lines"],
            "pending_count": receipt_state["pending_count"],
        },
    )


def _render_receive_association(
    request,
    *,
    create_form,
    line_count,
    line_values,
    line_errors,
):
    return render(
        request,
        TEMPLATE_RECEIVE_ASSOCIATION,
        {
            "active": ACTIVE_RECEIVE_ASSOCIATION,
            "create_form": create_form,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_receipts_view(request):
    filter_value = _resolve_receipts_filter(request.GET.get("type"))
    receipts_qs = _build_receipts_queryset(filter_value)
    receipts = build_receipts_view_rows(receipts_qs)

    return render(
        request,
        TEMPLATE_RECEIPTS_VIEW,
        {
            "active": ACTIVE_RECEIPTS_VIEW,
            "filter_value": filter_value,
            "receipts": receipts,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    receipt_state = build_receipt_scan_state(request, action=action)

    if request.method == "POST":
        response, handler_lines, handler_pending = handle_receipt_action(
            request,
            action=action,
            select_form=receipt_state["select_form"],
            create_form=receipt_state["create_form"],
            line_form=receipt_state["line_form"],
            selected_receipt=receipt_state["selected_receipt"],
        )
        if response:
            return response
        if handler_lines is not None:
            receipt_state["receipt_lines"] = handler_lines
            receipt_state["pending_count"] = handler_pending
    return _render_scan_receive(
        request,
        product_options=product_options,
        receipt_state=receipt_state,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    action = request.POST.get("action", "")
    state = build_receive_pallet_state(request, action=action)
    if state["response"]:
        return state["response"]

    return render(
        request,
        TEMPLATE_RECEIVE_PALLET,
        build_receive_pallet_context(state),
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_association(request):
    line_count, line_values = build_hors_format_lines(request)
    line_errors = {}
    create_form = ScanReceiptAssociationForm(request.POST or None)
    if request.method == "POST":
        response, line_errors = handle_receipt_association_post(
            request,
            create_form=create_form,
            line_values=line_values,
            line_count=line_count,
        )
        if response:
            return response

    return _render_receive_association(
        request,
        create_form=create_form,
        line_count=line_count,
        line_values=line_values,
        line_errors=line_errors,
    )
