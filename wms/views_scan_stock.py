from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import ScanOutForm, ScanStockUpdateForm
from .models import WmsChange
from .scan_helpers import build_location_data, build_product_options
from .stock_out_handlers import handle_stock_out_post
from .stock_update_handlers import handle_stock_update_post
from .stock_view_helpers import build_stock_context
from .view_permissions import scan_staff_required

TEMPLATE_STOCK = "scan/stock.html"
TEMPLATE_STOCK_UPDATE = "scan/stock_update.html"
TEMPLATE_OUT = "scan/out.html"

ACTIVE_STOCK_UPDATE = "stock_update"
ACTIVE_OUT = "out"


def _render_stock_update(request, *, create_form, product_options, location_data):
    return render(
        request,
        TEMPLATE_STOCK_UPDATE,
        {
            "active": ACTIVE_STOCK_UPDATE,
            "create_form": create_form,
            "products_json": product_options,
            "location_data": location_data,
        },
    )


def _render_scan_out(request, *, form, product_options):
    return render(
        request,
        TEMPLATE_OUT,
        {"form": form, "active": ACTIVE_OUT, "products_json": product_options},
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
@require_http_methods(["GET", "POST"])
def scan_stock_update(request):
    product_options = build_product_options()
    location_data = build_location_data()
    create_form = ScanStockUpdateForm(request.POST or None)
    if request.method == "POST":
        response = handle_stock_update_post(request, form=create_form)
        if response:
            return response
    return _render_stock_update(
        request,
        create_form=create_form,
        product_options=product_options,
        location_data=location_data,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_out(request):
    form = ScanOutForm(request.POST or None)
    product_options = build_product_options()
    if request.method == "POST":
        response = handle_stock_out_post(request, form=form)
        if response:
            return response
    return _render_scan_out(request, form=form, product_options=product_options)


@scan_staff_required
@require_http_methods(["GET"])
def scan_sync(request):
    state = WmsChange.get_state()
    return JsonResponse(_serialize_sync_state(state))
