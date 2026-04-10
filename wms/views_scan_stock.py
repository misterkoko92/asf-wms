from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .application.scan.recipient_needs_queries import build_scan_recipient_needs_context
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


@scan_staff_required
def scan_stock(request):
    return render(request, TEMPLATE_STOCK, build_stock_context(request))


@scan_staff_required
@require_http_methods(["GET"])
def scan_recipient_needs(request):
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
