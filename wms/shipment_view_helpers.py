from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .contact_filters import TAG_RECIPIENT, TAG_SHIPPER
from .models import CartonStatus, Document, DocumentType, ShipmentStatus, ShipmentTrackingStatus
from .print_context import (
    build_carton_document_context,
    build_label_context,
    build_shipment_document_context,
)
from .print_renderer import get_template_layout, render_layout_from_layout
from .view_utils import resolve_contact_by_name

TEMPLATE_DYNAMIC_DOCUMENT = "print/dynamic_document.html"
TEMPLATE_DYNAMIC_LABELS = "print/dynamic_labels.html"
TEMPLATE_CARTON_PACKING_LIST = "print/liste_colisage_carton.html"
TEMPLATE_SHIPMENT_LABELS = "print/etiquette_expedition.html"

DOC_ROUTE_SHIPMENT = "scan:scan_shipment_document"
DOC_ROUTE_LABELS = "scan:scan_shipment_labels"
DOC_ROUTE_CARTON = "scan:scan_shipment_carton_document"

SHIPMENT_DOCUMENT_TEMPLATES = {
    "donation_certificate": "print/attestation_donation.html",
    "humanitarian_certificate": "print/attestation_aide_humanitaire.html",
    "customs": "print/attestation_douane.html",
    "shipment_note": "print/bon_expedition.html",
    "packing_list_shipment": "print/liste_colisage_lot.html",
}

SHIPMENT_DOCUMENT_LINKS = (
    ("Bon d'expédition", "shipment_note"),
    ("Liste colisage (lot)", "packing_list_shipment"),
    ("Attestation donation", "donation_certificate"),
    ("Attestation aide humanitaire", "humanitarian_certificate"),
    ("Attestation douane", "customs"),
)

STATUS_READY_CARTON = {CartonStatus.LABELED, CartonStatus.SHIPPED}
STATUS_LOCKED_SHIPMENT = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}


def _carton_total_weight(carton):
    weight_total = 0
    for item in carton.cartonitem_set.all():
        product_weight = item.product_lot.product.weight_g or 0
        weight_total += product_weight * item.quantity
    return weight_total


def _render_document_with_layout(request, *, doc_type, context, default_template):
    layout_override = get_template_layout(doc_type)
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, TEMPLATE_DYNAMIC_DOCUMENT, {"blocks": blocks})
    return render(request, default_template, context)


def _build_shipment_document_link(shipment, *, label, doc_type):
    return {
        "label": label,
        "url": reverse(DOC_ROUTE_SHIPMENT, args=[shipment.id, doc_type]),
    }


def _build_carton_document_link(shipment, carton):
    return {
        "label": carton.code,
        "url": reverse(DOC_ROUTE_CARTON, args=[shipment.id, carton.id]),
    }


def _build_label_link(shipment, *, public=False):
    shipment_identifier = shipment.reference if public else shipment.id
    return {"label": "Etiquettes colis", "url": reverse(DOC_ROUTE_LABELS, args=[shipment_identifier])}


def _build_label_payload(*, label_context, carton_id, fallback_qr_url):
    return {
        "city": label_context["label_city"],
        "iata": label_context["label_iata"],
        "shipment_ref": label_context["label_shipment_ref"],
        "position": label_context["label_position"],
        "total": label_context["label_total"],
        "qr_url": label_context.get("label_qr_url") or fallback_qr_url,
        "carton_id": carton_id,
    }


def _build_dynamic_label_context(label):
    return {
        "label_city": label["city"],
        "label_iata": label["iata"],
        "label_shipment_ref": label["shipment_ref"],
        "label_position": label["position"],
        "label_total": label["total"],
        "label_qr_url": label.get("qr_url", ""),
    }


def _shipment_carton_totals(shipment):
    total = shipment.carton_count if shipment.carton_count is not None else shipment.carton_set.count()
    ready = (
        shipment.ready_count
        if shipment.ready_count is not None
        else shipment.carton_set.filter(status__in=STATUS_READY_CARTON).count()
    )
    return total, ready


def _shipment_progress_label(*, total, ready):
    if total == 0:
        return "CREATION"
    if ready < total:
        return f"EN COURS ({ready}/{total})"
    return "PRET"


def _shipment_status_label(shipment, progress_label):
    if shipment.status in STATUS_LOCKED_SHIPMENT:
        try:
            base_label = ShipmentStatus(shipment.status).label
        except ValueError:
            base_label = shipment.status
    else:
        base_label = progress_label
    if getattr(shipment, "is_disputed", False):
        return f"Litige - {base_label}"
    return base_label


def _shipment_party_label(contact, fallback_name):
    if contact:
        organization = getattr(contact, "organization", None)
        organization_name = (getattr(organization, "name", "") or "").strip()
        if organization_name:
            return organization_name

        title = (getattr(contact, "title", "") or "").strip()
        first_name = (getattr(contact, "first_name", "") or "").strip()
        last_name = (getattr(contact, "last_name", "") or "").strip()
        if title or first_name or last_name:
            person_parts = [title, first_name, last_name.upper() if last_name else ""]
            return " ".join(part for part in person_parts if part)

        contact_name = (getattr(contact, "name", "") or "").strip()
        if contact_name:
            return contact_name

    return (fallback_name or "").strip()


def _resolve_shipment_party_contact(shipment, *, ref_attr, tag, fallback_name):
    contact_ref = getattr(shipment, ref_attr, None)
    if contact_ref:
        return contact_ref
    return resolve_contact_by_name(tag, fallback_name)


def build_carton_options(cartons):
    options = []
    for carton in cartons:
        options.append(
            {
                "id": carton.id,
                "code": carton.code,
                "weight_g": _carton_total_weight(carton),
            }
        )
    return options


def build_shipment_document_links(shipment, *, public=False):
    if public:
        return [], [], Document.objects.none()
    documents = [
        _build_shipment_document_link(shipment, label=label, doc_type=doc_type)
        for label, doc_type in SHIPMENT_DOCUMENT_LINKS
    ]
    documents.append(_build_label_link(shipment, public=public))
    carton_docs = [
        _build_carton_document_link(shipment, carton)
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
    template = SHIPMENT_DOCUMENT_TEMPLATES.get(doc_type)
    if template is None:
        raise Http404("Document type not found")
    context = build_shipment_document_context(shipment, doc_type)
    return _render_document_with_layout(
        request,
        doc_type=doc_type,
        context=context,
        default_template=template,
    )


def render_carton_document(request, shipment, carton):
    context = build_carton_document_context(shipment, carton)
    return _render_document_with_layout(
        request,
        doc_type="packing_list_carton",
        context=context,
        default_template=TEMPLATE_CARTON_PACKING_LIST,
    )


def render_shipment_labels(request, shipment):
    shipment.ensure_qr_code(request=request)
    cartons = list(shipment.carton_set.order_by("code"))
    total = len(cartons)
    qr_url = shipment.qr_code_image.url if shipment.qr_code_image else ""
    labels = []
    for index, carton in enumerate(cartons, start=1):
        label_context = build_label_context(shipment, position=index, total=total)
        labels.append(
            _build_label_payload(
                label_context=label_context,
                carton_id=carton.id,
                fallback_qr_url=qr_url,
            )
        )

    layout_override = get_template_layout("shipment_label")
    if layout_override:
        rendered_labels = []
        for label in labels:
            label_context = _build_dynamic_label_context(label)
            blocks = render_layout_from_layout(layout_override, label_context)
            rendered_labels.append({"blocks": blocks})
        return render(request, TEMPLATE_DYNAMIC_LABELS, {"labels": rendered_labels})
    return render(request, TEMPLATE_SHIPMENT_LABELS, {"labels": labels})


def build_shipments_ready_rows(shipments_qs):
    shipments = []
    for shipment in shipments_qs:
        total, ready = _shipment_carton_totals(shipment)
        progress_label = _shipment_progress_label(total=total, ready=ready)
        status_label = _shipment_status_label(shipment, progress_label)
        shipper_contact = _resolve_shipment_party_contact(
            shipment,
            ref_attr="shipper_contact_ref",
            tag=TAG_SHIPPER,
            fallback_name=shipment.shipper_name,
        )
        recipient_contact = _resolve_shipment_party_contact(
            shipment,
            ref_attr="recipient_contact_ref",
            tag=TAG_RECIPIENT,
            fallback_name=shipment.recipient_name,
        )
        shipments.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "tracking_token": shipment.tracking_token,
                "carton_count": total,
                "destination_iata": shipment.destination.iata_code
                if shipment.destination
                else "",
                "shipper_name": _shipment_party_label(
                    shipper_contact,
                    shipment.shipper_name,
                ),
                "recipient_name": _shipment_party_label(
                    recipient_contact,
                    shipment.recipient_name,
                ),
                "created_at": shipment.created_at,
                "ready_at": shipment.ready_at,
                "status_label": status_label,
                "can_edit": shipment.status not in STATUS_LOCKED_SHIPMENT,
            }
        )
    return shipments
