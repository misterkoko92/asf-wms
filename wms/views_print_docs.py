from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Carton, Shipment
from .print_context import build_carton_picking_context
from .print_pack_engine import (
    PrintPackEngineError,
    generate_pack,
    render_pack_xlsx_documents,
)
from .print_pack_graph import GraphPdfConversionError
from .print_pack_routing import (
    resolve_carton_packing_pack,
    resolve_carton_picking_pack,
    resolve_pack_request,
)
from .print_pack_xlsx import build_xlsx_fallback_response
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_document_handlers import (
    handle_shipment_document_delete,
    handle_shipment_document_upload,
)
from .shipment_view_helpers import render_carton_document, render_shipment_document
from .view_permissions import scan_staff_required

TEMPLATE_DYNAMIC_DOCUMENT = "print/dynamic_document.html"
TEMPLATE_PACKING_LIST_CARTON = "print/liste_colisage_carton.html"
TEMPLATE_PICKING_LIST_CARTON = "print/picking_list_carton.html"


def _get_shipment_by_id(shipment_id):
    return get_object_or_404(Shipment, pk=shipment_id)


def _get_shipment_by_reference(shipment_ref):
    return get_object_or_404(Shipment, reference=shipment_ref)


def _get_shipment_carton_or_404(shipment, carton_id):
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return carton


def _build_standalone_carton_context(carton):
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
                "product": product.name,
                "lot": item.product_lot.lot_code or "N/A",
                "quantity": item.quantity,
                "expires_on": item.product_lot.expires_on,
            }
        )
    return {
        "document_date": timezone.localdate(),
        "shipment_ref": "-",
        "carton_code": carton.code,
        "item_rows": item_rows,
        "carton_weight_kg": weight_total_g / 1000 if weight_total_g else None,
        "hide_footer": True,
    }


def _render_carton_document_with_layout(request, context):
    layout_override = get_template_layout("packing_list_carton")
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, TEMPLATE_DYNAMIC_DOCUMENT, {"blocks": blocks})
    return render(request, TEMPLATE_PACKING_LIST_CARTON, context)


def _artifact_pdf_response(artifact):
    filename = (artifact.pdf_file.name or "").split("/")[-1] or "document.pdf"
    response = FileResponse(
        artifact.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def _generate_pack_pdf_response(
    request, *, pack_code, shipment=None, carton=None, variant=None
):
    artifact = generate_pack(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        user=getattr(request, "user", None),
        variant=variant,
    )
    return _artifact_pdf_response(artifact)


def _is_xlsx_fallback_enabled():
    return bool(getattr(settings, "PRINT_PACK_XLSX_FALLBACK_ENABLED", False))


def _generate_pack_xlsx_response(*, pack_code, shipment=None, carton=None, variant=None):
    documents = render_pack_xlsx_documents(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        variant=variant,
    )
    return build_xlsx_fallback_response(documents=documents, pack_code=pack_code)


def _try_generate_pack_pdf_response(
    request,
    *,
    pack_code,
    shipment=None,
    carton=None,
    variant=None,
    fallback_renderer,
):
    try:
        return _generate_pack_pdf_response(
            request,
            pack_code=pack_code,
            shipment=shipment,
            carton=carton,
            variant=variant,
        )
    except GraphPdfConversionError:
        if _is_xlsx_fallback_enabled():
            return _generate_pack_xlsx_response(
                pack_code=pack_code,
                shipment=shipment,
                carton=carton,
                variant=variant,
            )
        return fallback_renderer()
    except PrintPackEngineError:
        return fallback_renderer()


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_document(request, shipment_id, doc_type):
    shipment = _get_shipment_by_id(shipment_id)
    pack_route = resolve_pack_request(doc_type)
    if pack_route:
        return _try_generate_pack_pdf_response(
            request,
            pack_code=pack_route.pack_code,
            shipment=shipment,
            variant=pack_route.variant,
            fallback_renderer=lambda: render_shipment_document(request, shipment, doc_type),
        )
    return render_shipment_document(request, shipment, doc_type)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_document_public(request, shipment_ref, doc_type):
    shipment = _get_shipment_by_reference(shipment_ref)
    pack_route = resolve_pack_request(doc_type)
    if pack_route:
        return _try_generate_pack_pdf_response(
            request,
            pack_code=pack_route.pack_code,
            shipment=shipment,
            variant=pack_route.variant,
            fallback_renderer=lambda: render_shipment_document(request, shipment, doc_type),
        )
    return render_shipment_document(request, shipment, doc_type)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_carton_document(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    carton = _get_shipment_carton_or_404(shipment, carton_id)
    pack_route = resolve_carton_packing_pack()
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=lambda: render_carton_document(request, shipment, carton),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_carton_document_public(request, shipment_ref, carton_id):
    shipment = _get_shipment_by_reference(shipment_ref)
    carton = _get_shipment_carton_or_404(shipment, carton_id)
    pack_route = resolve_carton_packing_pack()
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=lambda: render_carton_document(request, shipment, carton),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_carton_document(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.select_related("shipment"),
        pk=carton_id,
    )
    pack_route = resolve_carton_packing_pack()
    if carton.shipment_id:
        fallback_renderer = lambda: render_carton_document(
            request,
            carton.shipment,
            carton,
        )
    else:
        fallback_renderer = lambda: _render_carton_document_with_layout(
            request,
            _build_standalone_carton_context(carton),
        )
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=carton.shipment if carton.shipment_id else None,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=fallback_renderer,
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_carton_picking(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.prefetch_related(
            "cartonitem_set__product_lot__product",
            "cartonitem_set__product_lot__location",
        ),
        pk=carton_id,
    )
    pack_route = resolve_carton_picking_pack()
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=carton.shipment,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=lambda: render(
            request,
            TEMPLATE_PICKING_LIST_CARTON,
            build_carton_picking_context(carton),
        ),
    )


@scan_staff_required
@require_http_methods(["POST"])
def scan_shipment_document_upload(request, shipment_id):
    return handle_shipment_document_upload(request, shipment_id=shipment_id)


@scan_staff_required
@require_http_methods(["POST"])
def scan_shipment_document_delete(request, shipment_id, document_id):
    return handle_shipment_document_delete(
        request, shipment_id=shipment_id, document_id=document_id
    )
