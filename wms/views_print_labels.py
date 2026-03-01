from django.http import Http404
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Shipment
from .print_pack_engine import generate_pack
from .print_pack_routing import resolve_shipment_labels_pack, resolve_single_label_pack
from .view_permissions import scan_staff_required

def _base_shipment_queryset():
    return Shipment.objects.select_related("destination")


def _get_shipment_by_id(shipment_id):
    return get_object_or_404(_base_shipment_queryset(), pk=shipment_id)


def _get_shipment_by_reference(shipment_ref):
    return get_object_or_404(_base_shipment_queryset(), reference=shipment_ref)


def _artifact_pdf_response(artifact):
    filename = (artifact.pdf_file.name or "").split("/")[-1] or "labels.pdf"
    response = FileResponse(
        artifact.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_labels(request, shipment_id):
    shipment = _get_shipment_by_id(shipment_id)
    pack_route = resolve_shipment_labels_pack()
    artifact = generate_pack(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        user=getattr(request, "user", None),
        variant=pack_route.variant,
    )
    return _artifact_pdf_response(artifact)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_labels_public(request, shipment_ref):
    shipment = _get_shipment_by_reference(shipment_ref)
    pack_route = resolve_shipment_labels_pack()
    artifact = generate_pack(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        user=getattr(request, "user", None),
        variant=pack_route.variant,
    )
    return _artifact_pdf_response(artifact)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_label(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    pack_route = resolve_single_label_pack()
    artifact = generate_pack(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        user=getattr(request, "user", None),
        variant=pack_route.variant,
    )
    return _artifact_pdf_response(artifact)
