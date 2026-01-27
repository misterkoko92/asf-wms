from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .models import CartonStatus, Document, DocumentType, ShipmentStatus, ShipmentTrackingStatus
from .print_context import (
    build_carton_document_context,
    build_label_context,
    build_shipment_document_context,
)
from .print_renderer import get_template_layout, render_layout_from_layout


def build_carton_options(cartons):
    options = []
    for carton in cartons:
        weight_total = 0
        for item in carton.cartonitem_set.all():
            product_weight = item.product_lot.product.weight_g or 0
            weight_total += product_weight * item.quantity
        options.append(
            {
                "id": carton.id,
                "code": carton.code,
                "weight_g": weight_total,
            }
        )
    return options


def build_shipment_document_links(shipment, *, public=False):
    if public:
        return [], [], Document.objects.none()
    doc_route = "scan:scan_shipment_document"
    label_route = "scan:scan_shipment_labels"
    carton_route = "scan:scan_shipment_carton_document"

    def doc_args(doc_type):
        return [shipment.id, doc_type]

    def carton_args(carton_id):
        return [shipment.id, carton_id]

    documents = [
        {
            "label": "Bon d'expedition",
            "url": reverse(doc_route, args=doc_args("shipment_note")),
        },
        {
            "label": "Liste colisage (lot)",
            "url": reverse(doc_route, args=doc_args("packing_list_shipment")),
        },
        {
            "label": "Attestation donation",
            "url": reverse(doc_route, args=doc_args("donation_certificate")),
        },
        {
            "label": "Attestation aide humanitaire",
            "url": reverse(doc_route, args=doc_args("humanitarian_certificate")),
        },
        {
            "label": "Attestation douane",
            "url": reverse(doc_route, args=doc_args("customs")),
        },
        {
            "label": "Etiquettes colis",
            "url": reverse(
                label_route, args=[shipment.reference if public else shipment.id]
            ),
        },
    ]
    carton_docs = [
        {
            "label": carton.code,
            "url": reverse(carton_route, args=carton_args(carton.id)),
        }
        for carton in shipment.carton_set.all().order_by("code")
    ]
    additional_docs = Document.objects.filter(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL
    ).order_by("-generated_at")
    return documents, carton_docs, additional_docs


def next_tracking_status(last_status):
    choices = [choice[0] for choice in ShipmentTrackingStatus.choices]
    if not choices:
        return None
    if not last_status or last_status not in choices:
        return choices[0]
    index = choices.index(last_status)
    if index + 1 < len(choices):
        return choices[index + 1]
    return last_status


def render_shipment_document(request, shipment, doc_type):
    allowed = {
        "donation_certificate": "print/attestation_donation.html",
        "humanitarian_certificate": "print/attestation_aide_humanitaire.html",
        "customs": "print/attestation_douane.html",
        "shipment_note": "print/bon_expedition.html",
        "packing_list_shipment": "print/liste_colisage_lot.html",
    }
    template = allowed.get(doc_type)
    if template is None:
        raise Http404("Document type not found")
    context = build_shipment_document_context(shipment, doc_type)
    layout_override = get_template_layout(doc_type)
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, "print/dynamic_document.html", {"blocks": blocks})
    return render(request, template, context)


def render_carton_document(request, shipment, carton):
    context = build_carton_document_context(shipment, carton)
    doc_type = "packing_list_carton"
    layout_override = get_template_layout(doc_type)
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, "print/dynamic_document.html", {"blocks": blocks})
    return render(request, "print/liste_colisage_carton.html", context)


def render_shipment_labels(request, shipment):
    shipment.ensure_qr_code(request=request)
    cartons = list(shipment.carton_set.order_by("code"))
    total = len(cartons)
    qr_url = shipment.qr_code_image.url if shipment.qr_code_image else ""
    labels = []
    for index, carton in enumerate(cartons, start=1):
        label_context = build_label_context(shipment, position=index, total=total)
        labels.append(
            {
                "city": label_context["label_city"],
                "iata": label_context["label_iata"],
                "shipment_ref": label_context["label_shipment_ref"],
                "position": label_context["label_position"],
                "total": label_context["label_total"],
                "qr_url": label_context.get("label_qr_url") or qr_url,
                "carton_id": carton.id,
            }
        )

    layout_override = get_template_layout("shipment_label")
    if layout_override:
        rendered_labels = []
        for label in labels:
            label_context = {
                "label_city": label["city"],
                "label_iata": label["iata"],
                "label_shipment_ref": label["shipment_ref"],
                "label_position": label["position"],
                "label_total": label["total"],
                "label_qr_url": label.get("qr_url", ""),
            }
            blocks = render_layout_from_layout(layout_override, label_context)
            rendered_labels.append({"blocks": blocks})
        return render(request, "print/dynamic_labels.html", {"labels": rendered_labels})
    return render(request, "print/etiquette_expedition.html", {"labels": labels})


def build_shipments_ready_rows(shipments_qs):
    shipments = []
    for shipment in shipments_qs:
        total = (
            shipment.carton_count
            if shipment.carton_count is not None
            else shipment.carton_set.count()
        )
        ready = (
            shipment.ready_count
            if shipment.ready_count is not None
            else shipment.carton_set.filter(
                status__in=[CartonStatus.PACKED, CartonStatus.SHIPPED]
            ).count()
        )
        if total == 0 or ready == 0:
            progress_label = "DRAFT"
        elif ready < total:
            progress_label = f"PARTIEL ({ready}/{total})"
        else:
            progress_label = "READY"
        if shipment.status in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}:
            status_label = ShipmentStatus(shipment.status).label
        else:
            status_label = progress_label
        shipments.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "carton_count": total,
                "destination_iata": shipment.destination.iata_code
                if shipment.destination
                else "",
                "shipper_name": shipment.shipper_name,
                "recipient_name": shipment.recipient_name,
                "created_at": shipment.created_at,
                "ready_at": shipment.ready_at,
                "status_label": status_label,
                "can_edit": shipment.status
                not in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED},
            }
        )
    return shipments
