from .models import OrderDocumentType
from .order_helpers import build_order_creator_info


def build_orders_view_rows(orders_qs):
    wanted_docs = {
        OrderDocumentType.DONATION_ATTESTATION,
        OrderDocumentType.HUMANITARIAN_ATTESTATION,
    }
    rows = []
    for order in orders_qs:
        association_contact = order.association_contact or order.recipient_contact
        association_name = (
            association_contact.name
            if association_contact
            else order.recipient_name
            or "-"
        )
        creator = build_order_creator_info(order)
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
            }
        )
    return rows
