from io import BytesIO

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .local_document_helper import (
    build_local_helper_document_response,
    build_local_helper_job_response,
    get_local_helper_document_index,
    is_local_helper_job_request,
)
from .models import Shipment
from .print_context import build_label_context
from .print_pack_engine import (
    PrintPackEngineError,
    generate_pack,
    render_pack_xlsx_documents,
)
from .print_pack_graph import GraphPdfConversionError
from .print_pack_routing import resolve_shipment_labels_pack, resolve_single_label_pack
from .print_pack_xlsx import build_xlsx_fallback_response
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_view_helpers import render_shipment_labels
from .view_permissions import scan_staff_required

TEMPLATE_DYNAMIC_LABELS = "print/dynamic_labels.html"
TEMPLATE_SHIPMENT_LABEL = "print/etiquette_expedition.html"


def _find_carton_position(cartons, carton_id):
    for index, carton in enumerate(cartons, start=1):
        if carton.id == carton_id:
            return index
    return None


def _build_default_label_payload(label_context, carton_id):
    return [
        {
            "city": label_context["label_city"],
            "iata": label_context["label_iata"],
            "shipment_ref": label_context["label_shipment_ref"],
            "position": label_context["label_position"],
            "total": label_context["label_total"],
            "qr_url": label_context.get("label_qr_url") or "",
            "carton_id": carton_id,
        }
    ]


def _render_shipment_label(request, *, label_context):
    layout_override = get_template_layout("shipment_label")
    if layout_override:
        blocks = render_layout_from_layout(layout_override, label_context)
        return render(
            request,
            TEMPLATE_DYNAMIC_LABELS,
            {"labels": [{"blocks": blocks}]},
        )
    labels = _build_default_label_payload(label_context, label_context["carton_id"])
    return render(request, TEMPLATE_SHIPMENT_LABEL, {"labels": labels})


def _base_shipment_queryset():
    return Shipment.objects.select_related("destination")


def _get_shipment_by_id(shipment_id):
    return get_object_or_404(_base_shipment_queryset(), pk=shipment_id)


def _get_shipment_by_reference(shipment_ref):
    return get_object_or_404(_base_shipment_queryset(), reference=shipment_ref)


def _artifact_pdf_response(artifact):
    filename = (artifact.pdf_file.name or "").split("/")[-1] or "labels.pdf"
    with artifact.pdf_file.open("rb") as pdf_stream:
        response = FileResponse(BytesIO(pdf_stream.read()), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


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


def _render_pack_xlsx_documents(*, pack_code, shipment=None, carton=None, variant=None):
    return render_pack_xlsx_documents(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        variant=variant,
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_labels(request, shipment_id):
    shipment = _get_shipment_by_id(shipment_id)
    pack_route = resolve_shipment_labels_pack()
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=None,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=shipment,
        )
    try:
        artifact = generate_pack(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            user=getattr(request, "user", None),
            variant=pack_route.variant,
        )
    except GraphPdfConversionError:
        if _is_xlsx_fallback_enabled():
            return _generate_pack_xlsx_response(
                pack_code=pack_route.pack_code,
                shipment=shipment,
                carton=None,
                variant=pack_route.variant,
            )
        return render_shipment_labels(request, shipment)
    except PrintPackEngineError:
        return render_shipment_labels(request, shipment)
    return _artifact_pdf_response(artifact)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_labels_public(request, shipment_ref):
    shipment = _get_shipment_by_reference(shipment_ref)
    pack_route = resolve_shipment_labels_pack()
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=None,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=shipment,
        )
    try:
        artifact = generate_pack(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            user=getattr(request, "user", None),
            variant=pack_route.variant,
        )
    except GraphPdfConversionError:
        if _is_xlsx_fallback_enabled():
            return _generate_pack_xlsx_response(
                pack_code=pack_route.pack_code,
                shipment=shipment,
                carton=None,
                variant=pack_route.variant,
            )
        return render_shipment_labels(request, shipment)
    except PrintPackEngineError:
        return render_shipment_labels(request, shipment)
    return _artifact_pdf_response(artifact)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_label(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404(_("Carton introuvable pour cette expédition."))
    pack_route = resolve_single_label_pack()
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=shipment,
            carton=carton,
        )
    try:
        artifact = generate_pack(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            carton=carton,
            user=getattr(request, "user", None),
            variant=pack_route.variant,
        )
    except GraphPdfConversionError:
        if _is_xlsx_fallback_enabled():
            return _generate_pack_xlsx_response(
                pack_code=pack_route.pack_code,
                shipment=shipment,
                carton=carton,
                variant=pack_route.variant,
            )
        shipment.ensure_qr_code(request=request)
        cartons = list(shipment.carton_set.order_by("code"))
        position = _find_carton_position(cartons, carton_id)
        if position is None:
            raise Http404(_("Carton introuvable pour cette expédition."))
        label_context = build_label_context(
            shipment,
            position=position,
            total=len(cartons),
        )
        label_context["label_qr_url"] = label_context.get("label_qr_url") or ""
        label_context["carton_id"] = carton_id
        return _render_shipment_label(request, label_context=label_context)
    except PrintPackEngineError:
        shipment.ensure_qr_code(request=request)
        cartons = list(shipment.carton_set.order_by("code"))
        position = _find_carton_position(cartons, carton_id)
        if position is None:
            raise Http404(_("Carton introuvable pour cette expédition."))
        label_context = build_label_context(
            shipment,
            position=position,
            total=len(cartons),
        )
        label_context["label_qr_url"] = label_context.get("label_qr_url") or ""
        label_context["carton_id"] = carton_id
        return _render_shipment_label(request, label_context=label_context)
    return _artifact_pdf_response(artifact)
