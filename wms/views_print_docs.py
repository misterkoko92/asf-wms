from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Carton, Shipment
from .print_context import build_carton_document_context, build_carton_picking_context
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_document_handlers import (
    handle_shipment_document_delete,
    handle_shipment_document_upload,
)
from .shipment_view_helpers import render_carton_document, render_shipment_document


@login_required
@require_http_methods(["GET"])
def scan_shipment_document(request, shipment_id, doc_type):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    return render_shipment_document(request, shipment, doc_type)


@login_required
@require_http_methods(["GET"])
def scan_shipment_document_public(request, shipment_ref, doc_type):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    return render_shipment_document(request, shipment, doc_type)


@login_required
@require_http_methods(["GET"])
def scan_shipment_carton_document(request, shipment_id, carton_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return render_carton_document(request, shipment, carton)


@login_required
@require_http_methods(["GET"])
def scan_shipment_carton_document_public(request, shipment_ref, carton_id):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return render_carton_document(request, shipment, carton)


@login_required
@require_http_methods(["GET"])
def scan_carton_document(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.select_related("shipment"),
        pk=carton_id,
    )
    if carton.shipment_id:
        shipment = carton.shipment
        context = build_carton_document_context(shipment, carton)
    else:
        item_rows = []
        weight_total_g = 0
        for item in carton.cartonitem_set.select_related(
            "product_lot", "product_lot__product"
        ):
            product = item.product_lot.product
            if product.weight_g:
                weight_total_g += product.weight_g * item.quantity
            item_rows.append(
                {
                    "product": item.product_lot.product.name,
                    "lot": item.product_lot.lot_code or "N/A",
                    "quantity": item.quantity,
                    "expires_on": item.product_lot.expires_on,
                }
            )
        context = {
            "document_date": timezone.localdate(),
            "shipment_ref": "-",
            "carton_code": carton.code,
            "item_rows": item_rows,
            "carton_weight_kg": weight_total_g / 1000 if weight_total_g else None,
            "hide_footer": True,
        }
    layout_override = get_template_layout("packing_list_carton")
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, "print/dynamic_document.html", {"blocks": blocks})
    return render(request, "print/liste_colisage_carton.html", context)


@login_required
@require_http_methods(["GET"])
def scan_carton_picking(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.prefetch_related(
            "cartonitem_set__product_lot__product",
            "cartonitem_set__product_lot__location",
        ),
        pk=carton_id,
    )
    context = build_carton_picking_context(carton)
    return render(request, "print/picking_list_carton.html", context)


@login_required
@require_http_methods(["POST"])
def scan_shipment_document_upload(request, shipment_id):
    return handle_shipment_document_upload(request, shipment_id=shipment_id)


@login_required
@require_http_methods(["POST"])
def scan_shipment_document_delete(request, shipment_id, document_id):
    return handle_shipment_document_delete(
        request, shipment_id=shipment_id, document_id=document_id
    )
