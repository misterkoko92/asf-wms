from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import Shipment
from .print_context import build_label_context
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_view_helpers import render_shipment_labels
from .view_permissions import scan_staff_required

TEMPLATE_DYNAMIC_LABELS = "print/dynamic_labels.html"
TEMPLATE_SHIPMENT_LABEL = "print/etiquette_expedition.html"


def _base_shipment_queryset():
    return Shipment.objects.select_related("destination")


def _get_shipment_by_id(shipment_id):
    return get_object_or_404(_base_shipment_queryset(), pk=shipment_id)


def _get_shipment_by_reference(shipment_ref):
    return get_object_or_404(_base_shipment_queryset(), reference=shipment_ref)


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


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_labels(request, shipment_id):
    shipment = _get_shipment_by_id(shipment_id)
    return render_shipment_labels(request, shipment)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_labels_public(request, shipment_ref):
    shipment = _get_shipment_by_reference(shipment_ref)
    return render_shipment_labels(request, shipment)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_label(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    shipment.ensure_qr_code(request=request)
    cartons = list(shipment.carton_set.order_by("code"))
    position = _find_carton_position(cartons, carton_id)
    if position is None:
        raise Http404("Carton not found for shipment")
    label_context = build_label_context(
        shipment,
        position=position,
        total=len(cartons),
    )
    label_context["label_qr_url"] = label_context.get("label_qr_url") or ""
    label_context["carton_id"] = carton_id
    return _render_shipment_label(request, label_context=label_context)
