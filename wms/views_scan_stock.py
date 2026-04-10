from urllib.parse import urlencode

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .application.scan.recipient_needs_queries import (
    FILTER_CATEGORY_PARAM,
    FILTER_DESTINATION_PARAM,
    FILTER_NEED_STATUS_PARAM,
    FILTER_PRIORITY_PARAM,
    FILTER_RECIPIENT_PARAM,
    build_scan_recipient_needs_context,
)
from .forms import ScanOutForm, ScanStockUpdateForm
from .models import WmsChange
from .scan_helpers import build_location_data, build_product_options
from .stock_out_handlers import handle_stock_out_post
from .stock_update_handlers import handle_stock_update_post
from .stock_view_helpers import build_stock_context
from .view_permissions import scan_staff_required

TEMPLATE_STOCK = "scan/stock.html"
TEMPLATE_RECIPIENT_NEEDS = "scan/recipient_needs_view.html"
TEMPLATE_STOCK_UPDATE = "scan/stock_update.html"
TEMPLATE_OUT = "scan/out.html"

ACTIVE_RECIPIENT_NEEDS = "recipient_needs"
ACTIVE_STOCK_UPDATE = "stock_update"
ACTIVE_OUT = "out"
PRODUCT_PICKER_SELECT_MAX_OPTIONS = 250
RECIPIENT_NEEDS_FILTER_PARAMS = (
    FILTER_DESTINATION_PARAM,
    FILTER_RECIPIENT_PARAM,
    FILTER_CATEGORY_PARAM,
    FILTER_NEED_STATUS_PARAM,
    FILTER_PRIORITY_PARAM,
)


def _resolve_product_picker_mode(product_options):
    if len(product_options) > PRODUCT_PICKER_SELECT_MAX_OPTIONS:
        return "datalist"
    return "filter_select"


def _render_stock_update(
    request, *, create_form, product_options, location_data, product_picker_mode
):
    return render(
        request,
        TEMPLATE_STOCK_UPDATE,
        {
            "active": ACTIVE_STOCK_UPDATE,
            "create_form": create_form,
            "products_json": product_options,
            "location_data": location_data,
            "product_picker_mode": product_picker_mode,
        },
    )


def _render_scan_out(request, *, form, product_options, product_picker_mode):
    return render(
        request,
        TEMPLATE_OUT,
        {
            "form": form,
            "active": ACTIVE_OUT,
            "products_json": product_options,
            "product_picker_mode": product_picker_mode,
            "scan_out_product_button_attrs": {"data-scan-target": "id_product_code"},
            "scan_out_shipment_button_attrs": {"data-scan-target": "id_shipment_reference"},
        },
    )


def _serialize_sync_state(state):
    return {
        "version": state.version,
        "changed_at": state.last_changed_at.isoformat(),
    }


def _recipient_needs_return_url(request):
    params = []
    for key in RECIPIENT_NEEDS_FILTER_PARAMS:
        value = (request.POST.get(key) or "").strip()
        if value:
            params.append((key, value))
    encoded = urlencode(params)
    base_url = reverse("scan:scan_recipient_needs")
    return f"{base_url}?{encoded}" if encoded else base_url


def _build_shipment_create_prefill_url(rows):
    first_row = rows[0]
    params = [
        ("destination", str(first_row["destination_id"])),
        ("shipper_contact", str(first_row["prepare_shipper_contact_id"])),
        ("recipient_contact", str(first_row["prepare_recipient_contact_id"])),
        ("carton_count", str(len(rows))),
    ]
    for index, row in enumerate(rows, start=1):
        params.append((f"line_{index}_product_code", str(row["prepare_product_code"])))
        params.append((f"line_{index}_quantity", str(row["prepare_quantity"])))
    return f'{reverse("scan:scan_shipment_create")}?{urlencode(params)}'


def _handle_scan_recipient_needs_post(request):
    context = build_scan_recipient_needs_context(request)
    rows_by_key = {row["selection_key"]: row for row in context["rows"]}
    single_key = (request.POST.get("prepare_single") or "").strip()
    selected_keys = [single_key] if single_key else request.POST.getlist("selected_row_keys")
    selected_keys = [key.strip() for key in selected_keys if (key or "").strip()]
    return_url = _recipient_needs_return_url(request)

    if not selected_keys:
        messages.error(request, "Aucune ligne sélectionnée pour la préparation.")
        return redirect(return_url)

    selected_rows = []
    for key in selected_keys:
        row = rows_by_key.get(key)
        if row is None:
            messages.error(request, "Sélection invalide ou obsolète.")
            return redirect(return_url)
        if not row.get("can_prepare"):
            messages.error(
                request,
                row.get("prepare_disabled_reason")
                or "Cette ligne ne peut pas être préparée automatiquement.",
            )
            return redirect(return_url)
        selected_rows.append(row)

    grouping_keys = {
        (
            row["destination_id"],
            row["prepare_shipper_contact_id"],
            row["prepare_recipient_contact_id"],
        )
        for row in selected_rows
    }
    if len(grouping_keys) != 1:
        messages.error(
            request,
            "La sélection doit partager la même destination, le même destinataire et le même expéditeur.",
        )
        return redirect(return_url)

    return redirect(_build_shipment_create_prefill_url(selected_rows))


@scan_staff_required
def scan_stock(request):
    return render(request, TEMPLATE_STOCK, build_stock_context(request))


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_recipient_needs(request):
    if request.method == "POST":
        return _handle_scan_recipient_needs_post(request)
    context = build_scan_recipient_needs_context(request)
    context.setdefault("active", ACTIVE_RECIPIENT_NEEDS)
    return render(request, TEMPLATE_RECIPIENT_NEEDS, context)


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_stock_update(request):
    product_options = build_product_options(compact=True)
    location_data = build_location_data()
    create_form = ScanStockUpdateForm(request.POST or None)
    product_picker_mode = _resolve_product_picker_mode(product_options)
    if request.method == "POST":
        response = handle_stock_update_post(request, form=create_form)
        if response:
            return response
    return _render_stock_update(
        request,
        create_form=create_form,
        product_options=product_options,
        location_data=location_data,
        product_picker_mode=product_picker_mode,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_out(request):
    form = ScanOutForm(request.POST or None)
    product_options = build_product_options(compact=True)
    product_picker_mode = _resolve_product_picker_mode(product_options)
    if request.method == "POST":
        response = handle_stock_out_post(request, form=form)
        if response:
            return response
    return _render_scan_out(
        request,
        form=form,
        product_options=product_options,
        product_picker_mode=product_picker_mode,
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_sync(request):
    state = WmsChange.get_state()
    return JsonResponse(_serialize_sync_state(state))
