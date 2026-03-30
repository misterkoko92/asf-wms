from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .contact_labels import build_contact_select_label
from .models import (
    CartonStatus,
    Document,
    DocumentType,
    ShipmentStatus,
    ShipmentTrackingStatus,
    ShipmentUnitEquivalenceRule,
)
from .print_context import (
    build_carton_document_context,
    build_contact_sheet_context,
    build_label_context,
    build_shipment_document_context,
)
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_helpers import build_destination_label
from .status_badges import BADGE_TONE_PROGRESS, BADGE_TONE_READY, resolve_status_tone
from .status_presenters import present_shipment_status
from .unit_equivalence import ShipmentUnitInput, resolve_shipment_unit_count

TEMPLATE_DYNAMIC_DOCUMENT = "print/dynamic_document.html"
TEMPLATE_DYNAMIC_LABELS = "print/dynamic_labels.html"
TEMPLATE_CARTON_PACKING_LIST = "print/liste_colisage_carton.html"
TEMPLATE_SHIPMENT_LABELS = "print/etiquette_expedition.html"

DOC_ROUTE_SHIPMENT = "scan:scan_shipment_document"
DOC_ROUTE_SHIPMENT_VIEW = "scan:scan_shipment_view_document"
DOC_ROUTE_LABELS = "scan:scan_shipment_labels"
DOC_ROUTE_CARTON = "scan:scan_shipment_carton_document"
DOC_ROUTE_SHIPMENT_BUNDLE_PDF = "scan:scan_shipment_view_bundle_pdf"

SHIPMENT_DOCUMENT_TEMPLATES = {
    "contact_label": "print/feuille_contact.html",
    "donation_certificate": "print/attestation_donation.html",
    "humanitarian_certificate": "print/attestation_aide_humanitaire.html",
    "customs": "print/attestation_douane.html",
    "shipment_note": "print/bon_expedition.html",
    "packing_list_shipment": "print/liste_colisage_lot.html",
}

SHIPMENT_DOCUMENT_LINKS = (
    (_("Bon d'expédition"), "shipment_note"),
    (_("Liste colisage (lot)"), "packing_list_shipment"),
    (_("Attestation donation"), "donation_certificate"),
    (_("Attestation aide humanitaire"), "humanitarian_certificate"),
    (_("Attestation douane"), "customs"),
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


def _build_carton_option(carton):
    preassigned_destination = getattr(carton, "preassigned_destination", None)
    preassigned_destination_id = getattr(carton, "preassigned_destination_id", None)
    preassigned_destination_iata = (
        getattr(preassigned_destination, "iata_code", "") if preassigned_destination else ""
    )
    label = carton.code
    if preassigned_destination_iata:
        label = f"{label} ({preassigned_destination_iata})"
    return {
        "id": carton.id,
        "code": carton.code,
        "label": label,
        "weight_g": _carton_total_weight(carton),
        "preassigned_destination_id": preassigned_destination_id,
        "preassigned_destination_iata": preassigned_destination_iata,
        "preassigned_destination_label": (
            build_destination_label(preassigned_destination) if preassigned_destination else ""
        ),
    }


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
    return {
        "label": _("Étiquettes colis"),
        "url": reverse(DOC_ROUTE_LABELS, args=[shipment_identifier]),
    }


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


def _build_future_shipment_bundle_url(shipment, bundle_key):
    return f"/scan/shipment/{shipment.id}/print-bundle/{bundle_key}/"


def _build_future_carton_action_url(shipment, carton, action_key):
    if action_key == "contact_label":
        return reverse("scan:scan_shipment_contact_label", args=[shipment.id, carton.id])
    if action_key == "donation_certificate":
        return reverse("scan:scan_shipment_donation_certificate", args=[shipment.id, carton.id])
    raise ValueError(f"Unknown carton action: {action_key}")


def _pdf_delivery_url(url):
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}delivery=pdf"


def _html_delivery_url(url):
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}delivery=html"


def build_shipment_dossier_print_actions(shipment):
    grouped_print_actions = [
        {
            "label": _("Imprimer tous les documents d'expédition"),
            "url": _build_future_shipment_bundle_url(shipment, "all"),
        },
        {
            "label": _("Imprimer dossier papier"),
            "url": _build_future_shipment_bundle_url(shipment, "paper"),
        },
        {
            "label": _("Imprimer toutes les listes colisage carton (rouleau continu)"),
            "url": _build_future_shipment_bundle_url(shipment, "carton_lists"),
        },
        {
            "label": _("Imprimer toutes les listes par carton"),
            "url": _build_future_shipment_bundle_url(shipment, "carton_lists_a4"),
        },
        {
            "label": _("Imprimer toutes les étiquettes standard"),
            "url": _build_future_shipment_bundle_url(shipment, "standard_labels"),
        },
    ]
    paper_print_actions = [
        {
            "label": _("Imprimer bon d'expédition"),
            "url": reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "shipment_note"]),
        },
        {
            "label": _("Imprimer document douane"),
            "url": reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "customs"]),
        },
        {
            "label": _("Imprimer liste générale"),
            "url": reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "packing_list"]),
        },
    ]
    carton_print_rows = []
    for carton in shipment.carton_set.all().order_by("code"):
        carton_print_rows.append(
            {
                "code": carton.code,
                "actions": [
                    {
                        "label": _("Liste colisage"),
                        "url": _html_delivery_url(
                            reverse(DOC_ROUTE_CARTON, args=[shipment.id, carton.id])
                        ),
                    },
                    {
                        "label": _("Étiquette colis"),
                        "url": _html_delivery_url(
                            reverse("scan:scan_shipment_label", args=[shipment.id, carton.id])
                        ),
                    },
                    {
                        "label": _("Étiquette contact"),
                        "url": _build_future_carton_action_url(
                            shipment,
                            carton,
                            "contact_label",
                        ),
                    },
                    {
                        "label": _("Attestation donation"),
                        "url": _build_future_carton_action_url(
                            shipment,
                            carton,
                            "donation_certificate",
                        ),
                    },
                ],
            }
        )
    pdf_export_actions = [
        {
            "label": _("Télécharger dossier papier (PDF)"),
            "url": reverse(DOC_ROUTE_SHIPMENT_BUNDLE_PDF, args=[shipment.id, "a4"]),
        },
        {
            "label": _("Télécharger bon d'expédition (PDF)"),
            "url": _pdf_delivery_url(
                reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "shipment_note"])
            ),
        },
        {
            "label": _("Télécharger document douane (PDF)"),
            "url": _pdf_delivery_url(
                reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "customs"])
            ),
        },
        {
            "label": _("Télécharger liste générale (PDF)"),
            "url": _pdf_delivery_url(
                reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "packing_list"])
            ),
        },
        {
            "label": _("Télécharger attestation donation (PDF)"),
            "url": _pdf_delivery_url(
                reverse(DOC_ROUTE_SHIPMENT_VIEW, args=[shipment.id, "donation"])
            ),
        },
    ]
    return {
        "grouped_print_actions": grouped_print_actions,
        "paper_print_actions": paper_print_actions,
        "carton_print_rows": carton_print_rows,
        "pdf_export_actions": pdf_export_actions,
    }


def _shipment_carton_totals(shipment):
    total = (
        getattr(shipment, "carton_count", None)
        if getattr(shipment, "carton_count", None) is not None
        else shipment.carton_set.count()
    )
    ready = (
        getattr(shipment, "ready_count", None)
        if getattr(shipment, "ready_count", None) is not None
        else shipment.carton_set.filter(status__in=STATUS_READY_CARTON).count()
    )
    return total, ready


def _shipment_progress_label(*, total, ready):
    if total == 0:
        return _("Création")
    if ready < total:
        return _("En cours (%(ready)s/%(total)s)") % {"ready": ready, "total": total}
    return present_shipment_status(ShipmentStatus.PACKED)["label"]


def _shipment_status_label(shipment, progress_label):
    if shipment.status == ShipmentStatus.DRAFT:
        return present_shipment_status(
            shipment,
            is_disputed=getattr(shipment, "is_disputed", False),
        )["label"]
    elif shipment.status in STATUS_LOCKED_SHIPMENT:
        return present_shipment_status(
            shipment,
            is_disputed=getattr(shipment, "is_disputed", False),
        )["label"]
    base_label = progress_label
    if getattr(shipment, "is_disputed", False):
        return _("Litige - %(label)s") % {"label": base_label}
    return base_label


def _shipment_status_tone(shipment, *, total, ready):
    if getattr(shipment, "is_disputed", False):
        return resolve_status_tone(
            shipment.status,
            domain="shipment",
            is_disputed=True,
        )
    if shipment.status in STATUS_LOCKED_SHIPMENT or shipment.status == ShipmentStatus.DRAFT:
        return resolve_status_tone(shipment.status, domain="shipment")
    if total > 0 and ready >= total:
        return BADGE_TONE_READY
    return BADGE_TONE_PROGRESS


def _shipment_status_variant(shipment, *, total, ready):
    if getattr(shipment, "is_disputed", False):
        return "disputed"
    if shipment.status == ShipmentStatus.DRAFT:
        return "draft"
    if shipment.status == ShipmentStatus.PLANNED:
        return "planned"
    if shipment.status == ShipmentStatus.SHIPPED:
        return "shipped"
    if shipment.status == ShipmentStatus.RECEIVED_CORRESPONDENT:
        return "received"
    if shipment.status == ShipmentStatus.DELIVERED:
        return "delivered"
    if total > 0 and ready >= total:
        return "ready"
    return "in-progress"


def _build_shipment_equivalence_items(shipment):
    items = []
    carton_set = getattr(shipment, "carton_set", None)
    if carton_set is None:
        return items
    if hasattr(carton_set, "all"):
        cartons = carton_set.all()
    else:
        try:
            cartons = list(carton_set)
        except TypeError:
            cartons = []
    for carton in cartons:
        for carton_item in carton.cartonitem_set.all():
            items.append(
                ShipmentUnitInput(
                    product=carton_item.product_lot.product,
                    quantity=carton_item.quantity,
                )
            )
    return items


def _normalized_text(value):
    return str(value or "").strip()


def _shipment_party_snapshot_entry(shipment, party_key):
    snapshot = getattr(shipment, "party_snapshot", None) or {}
    if not isinstance(snapshot, dict):
        return {}
    entry = snapshot.get(party_key) or {}
    return entry if isinstance(entry, dict) else {}


def _shipment_party_label(shipment, *, party_key, ref_attr, fallback_name):
    snapshot_entry = _shipment_party_snapshot_entry(shipment, party_key)
    snapshot_label = _normalized_text(snapshot_entry.get("label"))
    if snapshot_label:
        return snapshot_label
    contact = getattr(shipment, ref_attr, None)
    if contact is not None:
        return build_contact_select_label(contact)
    return _normalized_text(fallback_name)


def _resolve_shipment_party_contact(shipment, *, ref_attr):
    return getattr(shipment, ref_attr, None)


def _shipment_document_counts(shipment):
    shipment_pk = getattr(shipment, "pk", None)
    if shipment_pk is None:
        return len(SHIPMENT_DOCUMENT_LINKS) + 1, 0
    documents, _carton_docs, additional_docs = build_shipment_document_links(shipment)
    return len(documents), additional_docs.count()


def build_carton_options(cartons):
    return [_build_carton_option(carton) for carton in cartons]


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
    if doc_type == "contact_label":
        context = build_contact_sheet_context(shipment)
    else:
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
    equivalence_rules = list(
        ShipmentUnitEquivalenceRule.objects.filter(is_active=True).select_related(
            "category",
            "category__parent",
        )
    )
    shipments = []
    for shipment in shipments_qs:
        total, ready = _shipment_carton_totals(shipment)
        generated_document_count, additional_document_count = _shipment_document_counts(shipment)
        progress_label = _shipment_progress_label(total=total, ready=ready)
        status_label = _shipment_status_label(shipment, progress_label)
        status_tone = _shipment_status_tone(shipment, total=total, ready=ready)
        status_variant = _shipment_status_variant(shipment, total=total, ready=ready)
        documents_summary = _("%(generated)s docs") % {"generated": generated_document_count}
        if additional_document_count:
            documents_summary = _("%(generated)s docs + %(additional)s ajoutés") % {
                "generated": generated_document_count,
                "additional": additional_document_count,
            }
        shipments.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "tracking_token": shipment.tracking_token,
                "carton_count": total,
                "equivalent_carton_count": resolve_shipment_unit_count(
                    items=_build_shipment_equivalence_items(shipment),
                    rules=equivalence_rules,
                ),
                "destination_iata": shipment.destination.iata_code if shipment.destination else "",
                "shipper_name": _shipment_party_label(
                    shipment,
                    party_key="shipper",
                    ref_attr="shipper_contact_ref",
                    fallback_name=shipment.shipper_name,
                ),
                "recipient_name": _shipment_party_label(
                    shipment,
                    party_key="recipient",
                    ref_attr="recipient_contact_ref",
                    fallback_name=shipment.recipient_name,
                ),
                "created_at": shipment.created_at,
                "ready_at": shipment.ready_at,
                "status_label": status_label,
                "status_tone": status_tone,
                "status_variant": status_variant,
                "can_edit": shipment.status not in STATUS_LOCKED_SHIPMENT,
                "generated_document_count": generated_document_count,
                "additional_document_count": additional_document_count,
                "documents_summary": documents_summary,
            }
        )
    return shipments


def build_shipments_tracking_rows(shipments_qs):
    shipments = []
    for shipment in shipments_qs:
        planned_at = getattr(shipment, "planned_at", None)
        boarding_ok_at = getattr(shipment, "boarding_ok_at", None)
        shipped_at = getattr(shipment, "shipped_tracking_at", None) or boarding_ok_at
        received_correspondent_at = getattr(shipment, "received_correspondent_at", None)
        delivered_at = getattr(shipment, "delivered_at", None)

        tracking_steps_complete = all(
            [
                planned_at,
                boarding_ok_at,
                shipped_at,
                received_correspondent_at,
                delivered_at,
            ]
        )
        is_fully_completed = tracking_steps_complete and shipment.status == ShipmentStatus.DELIVERED
        is_disputed = bool(getattr(shipment, "is_disputed", False))
        is_closed = bool(getattr(shipment, "closed_at", None))

        shipments.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "tracking_token": shipment.tracking_token,
                "carton_count": shipment.carton_count
                if shipment.carton_count is not None
                else shipment.carton_set.count(),
                "shipper_name": _shipment_party_label(
                    shipment,
                    party_key="shipper",
                    ref_attr="shipper_contact_ref",
                    fallback_name=shipment.shipper_name,
                ),
                "recipient_name": _shipment_party_label(
                    shipment,
                    party_key="recipient",
                    ref_attr="recipient_contact_ref",
                    fallback_name=shipment.recipient_name,
                ),
                "planned_at": planned_at,
                "boarding_ok_at": boarding_ok_at,
                "shipped_at": shipped_at,
                "received_correspondent_at": received_correspondent_at,
                "delivered_at": delivered_at,
                "is_disputed": is_disputed,
                "is_closed": is_closed,
                "closed_at": getattr(shipment, "closed_at", None),
                "closed_by": getattr(shipment, "closed_by", None),
                "can_close": is_fully_completed and not is_disputed and not is_closed,
            }
        )

    return shipments
