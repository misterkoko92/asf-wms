from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import ScanOutForm, ScanStockUpdateForm
from .models import WmsChange
from .scan_helpers import build_location_data, build_product_options
from .stock_out_handlers import handle_stock_out_post
from .stock_update_handlers import handle_stock_update_post
from .stock_view_helpers import build_stock_context

@login_required
def scan_stock(request):
    return render(request, "scan/stock.html", build_stock_context(request))


@login_required
@require_http_methods(["GET", "POST"])
def scan_stock_update(request):
    product_options = build_product_options()
    location_data = build_location_data()
    create_form = ScanStockUpdateForm(request.POST or None)
    if request.method == "POST":
        response = handle_stock_update_post(request, form=create_form)
        if response:
            return response
    return render(
        request,
        "scan/stock_update.html",
        {
            "active": "stock_update",
            "create_form": create_form,
            "products_json": product_options,
            "location_data": location_data,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_out(request):
    form = ScanOutForm(request.POST or None)
    product_options = build_product_options()
    if request.method == "POST":
        response = handle_stock_out_post(request, form=form)
        if response:
            return response
    return render(
        request,
        "scan/out.html",
        {"form": form, "active": "out", "products_json": product_options},
    )


@login_required
@require_http_methods(["GET"])
def scan_sync(request):
    state = WmsChange.get_state()
    return JsonResponse(
        {
            "version": state.version,
            "changed_at": state.last_changed_at.isoformat(),
        }
    )
