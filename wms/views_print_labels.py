from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from .models import Shipment
from .print_context import build_label_context
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_view_helpers import render_shipment_labels

@login_required
@require_http_methods(["GET"])
def scan_shipment_labels(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), pk=shipment_id
    )
    return render_shipment_labels(request, shipment)


@login_required
@require_http_methods(["GET"])
def scan_shipment_labels_public(request, shipment_ref):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), reference=shipment_ref
    )
    return render_shipment_labels(request, shipment)


@login_required
@require_http_methods(["GET"])
def scan_shipment_label(request, shipment_id, carton_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), pk=shipment_id
    )
    shipment.ensure_qr_code(request=request)
    cartons = list(shipment.carton_set.order_by("code"))
    total = len(cartons)
    position = None
    for index, carton in enumerate(cartons, start=1):
        if carton.id == carton_id:
            position = index
            break
    if position is None:
        raise Http404("Carton not found for shipment")
    label_context = build_label_context(shipment, position=position, total=total)
    qr_url = label_context.get("label_qr_url") or ""
    labels = [
        {
            "city": label_context["label_city"],
            "iata": label_context["label_iata"],
            "shipment_ref": label_context["label_shipment_ref"],
            "position": label_context["label_position"],
            "total": label_context["label_total"],
            "qr_url": qr_url,
            "carton_id": carton_id,
        }
    ]
    layout_override = get_template_layout("shipment_label")
    if layout_override:
        label_context["label_qr_url"] = qr_url
        blocks = render_layout_from_layout(layout_override, label_context)
        return render(
            request, "print/dynamic_labels.html", {"labels": [{"blocks": blocks}]}
        )
    return render(request, "print/etiquette_expedition.html", {"labels": labels})
