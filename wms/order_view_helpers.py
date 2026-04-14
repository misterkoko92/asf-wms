from django.urls import reverse

from .models import OrderDocumentType, OrderReviewStatus
from .order_helpers import build_order_creator_info
from .status_presenters import (
    present_order_review_status,
    present_order_shipment_status,
    present_shipment_status,
)


def _order_reference_label(order):
    reference = (getattr(order, "reference", "") or "").strip()
    if reference:
        return reference
    order_id = getattr(order, "id", None)
    if order_id:
        return f"CMD-{order_id}"
    return "Commande"


def _order_next_action_payload(order):
    review_status = getattr(order, "review_status", "") or ""

    if review_status == OrderReviewStatus.PENDING:
        return {
            "label": "Valider ou demander des modifications",
            "tone": "warning",
            "can_create_shipment": False,
        }
    if review_status == OrderReviewStatus.CHANGES_REQUESTED:
        return {
            "label": "Recontacter l'association",
            "tone": "warning",
            "can_create_shipment": False,
        }
    if review_status == OrderReviewStatus.APPROVED:
        return {
            "label": "Créer une expédition",
            "tone": "ready",
            "can_create_shipment": True,
        }
    if review_status == OrderReviewStatus.REJECTED:
        return {
            "label": "Expliquer le refus",
            "tone": "error",
            "can_create_shipment": False,
        }
    return {
        "label": "Aucune action",
        "tone": "info",
        "can_create_shipment": False,
    }


def _linked_shipment_rows(order):
    rows = []
    shipment_links = getattr(order, "shipment_links", None)
    if shipment_links is None:
        return rows
    for link in shipment_links.all():
        shipment = getattr(link, "shipment", None)
        if shipment is None:
            continue
        rows.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "status_display": present_order_shipment_status(order)
                if getattr(order, "shipment_id", None) == shipment.id
                else present_shipment_status(shipment),
            }
        )
    return rows


def _order_inbound_delivery(order):
    try:
        return order.inbound_delivery
    except AttributeError:
        return None
    except type(order).inbound_delivery.RelatedObjectDoesNotExist:
        return None


def _inbound_workflow_summary(order):
    inbound_delivery = _order_inbound_delivery(order)
    if inbound_delivery is None:
        return {}
    receipt = getattr(inbound_delivery, "receipt", None)
    receipt_cartons = []
    if receipt is not None:
        receipt_cartons = list(receipt.shipper_cartons.all())
    unassigned_carton_count = sum(
        1 for carton in receipt_cartons if not getattr(carton, "shipment_id", None)
    )
    linked_shipments = _linked_shipment_rows(order)
    return {
        "has_inbound_delivery": True,
        "declared_carton_count": int(getattr(inbound_delivery, "declared_carton_count", 0) or 0),
        "arrival_mode_label": inbound_delivery.get_arrival_mode_display(),
        "receipt": receipt,
        "receipt_reference": getattr(receipt, "reference", ""),
        "receipt_shortcut_url": f"{reverse('scan:scan_receive_association')}?order_id={order.id}",
        "shipper_received_unassigned_carton_count": unassigned_carton_count,
        "linked_shipments": linked_shipments,
        "create_shipment_label": "Créer une expédition liée",
    }


def build_orders_view_rows(orders_qs):
    wanted_docs = {
        OrderDocumentType.DONATION_ATTESTATION,
        OrderDocumentType.HUMANITARIAN_ATTESTATION,
        OrderDocumentType.PACKING_LIST_GLOBAL,
        OrderDocumentType.PACKING_LIST_BY_CARTON,
    }
    rows = []
    for order in orders_qs:
        association_contact = order.association_contact or order.recipient_contact
        association_name = (
            association_contact.name if association_contact else order.recipient_name or "-"
        )
        creator = build_order_creator_info(order)
        next_action = _order_next_action_payload(order)
        inbound_summary = _inbound_workflow_summary(order)
        if getattr(
            order, "review_status", ""
        ) == OrderReviewStatus.APPROVED and inbound_summary.get("has_inbound_delivery"):
            if not inbound_summary.get("receipt_reference"):
                next_action["label"] = "Enregistrer la réception"
                next_action["tone"] = "warning"
            elif inbound_summary.get("linked_shipments"):
                next_action["label"] = "Ouvrir ou compléter une expédition"
                next_action["tone"] = "info"
            else:
                next_action["label"] = "Créer une expédition liée"
                next_action["tone"] = "ready"
        docs = [
            {"label": doc.get_doc_type_display(), "url": doc.file.url}
            for doc in order.documents.all()
            if doc.doc_type in wanted_docs and doc.file
        ]
        rows.append(
            {
                "order": order,
                "association_name": association_name,
                "creator": creator,
                "documents": docs,
                "reference_label": _order_reference_label(order),
                "review_status_value": getattr(order, "review_status", "") or "",
                "review_status_display": present_order_review_status(order),
                "shipment_status_display": present_order_shipment_status(order),
                "next_action_label": next_action["label"],
                "next_action_tone": next_action["tone"],
                "can_create_shipment": next_action["can_create_shipment"],
                "create_shipment_label": inbound_summary.get(
                    "create_shipment_label",
                    "Créer l'expédition",
                ),
                **inbound_summary,
            }
        )
    return rows
