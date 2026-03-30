from .models import OrderDocumentType, OrderReviewStatus
from .order_helpers import build_order_creator_info
from .status_presenters import present_order_review_status, present_order_shipment_status


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
    shipment = getattr(order, "shipment", None)

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
    if review_status == OrderReviewStatus.APPROVED and shipment is None:
        return {
            "label": "Créer l'expédition",
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


def build_orders_view_rows(orders_qs):
    wanted_docs = {
        OrderDocumentType.DONATION_ATTESTATION,
        OrderDocumentType.HUMANITARIAN_ATTESTATION,
    }
    rows = []
    for order in orders_qs:
        association_contact = order.association_contact or order.recipient_contact
        association_name = (
            association_contact.name if association_contact else order.recipient_name or "-"
        )
        creator = build_order_creator_info(order)
        next_action = _order_next_action_payload(order)
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
            }
        )
    return rows
