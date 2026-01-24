from django.contrib.auth.decorators import login_required
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


@login_required
@require_http_methods(["GET"])
def scan_receipts_view(request):
    filter_value = (request.GET.get("type") or "all").strip().lower()
    receipts_qs = (
        Receipt.objects.select_related("source_contact", "carrier_contact")
        .prefetch_related("hors_format_items")
        .order_by("-received_on", "-created_at")
    )
    if filter_value == "pallet":
        receipts_qs = receipts_qs.filter(receipt_type=ReceiptType.PALLET)
    elif filter_value == "association":
        receipts_qs = receipts_qs.filter(receipt_type=ReceiptType.ASSOCIATION)
    else:
        filter_value = "all"
    receipts = build_receipts_view_rows(receipts_qs)

    return render(
        request,
        "scan/receipts_view.html",
        {
            "active": "receipts_view",
            "filter_value": filter_value,
            "receipts": receipts,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    receipt_state = build_receipt_scan_state(request, action=action)
    select_form = receipt_state["select_form"]
    create_form = receipt_state["create_form"]
    line_form = receipt_state["line_form"]
    selected_receipt = receipt_state["selected_receipt"]
    receipt_lines = receipt_state["receipt_lines"]
    pending_count = receipt_state["pending_count"]

    if request.method == "POST":
        response, handler_lines, handler_pending = handle_receipt_action(
            request,
            action=action,
            select_form=select_form,
            create_form=create_form,
            line_form=line_form,
            selected_receipt=selected_receipt,
        )
        if response:
            return response
        if handler_lines is not None:
            receipt_lines = handler_lines
            pending_count = handler_pending
    return render(
        request,
        "scan/receive.html",
        {
            "active": "receive",
            "products_json": product_options,
            "select_form": select_form,
            "create_form": create_form,
            "line_form": line_form,
            "selected_receipt": selected_receipt,
            "receipt_lines": receipt_lines,
            "pending_count": pending_count,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    action = request.POST.get("action", "")
    state = build_receive_pallet_state(request, action=action)
    if state["response"]:
        return state["response"]

    return render(
        request,
        "scan/receive_pallet.html",
        build_receive_pallet_context(state),
    )


@login_required
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

    return render(
        request,
        "scan/receive_association.html",
        {
            "active": "receive_association",
            "create_form": create_form,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
        },
    )
