from django.db.models import DateTimeField, F, Max, Q, Value
from django.db.models.functions import Coalesce

from wms.models import (
    Order,
    RecipientProductPreference,
    RecipientStructureDocument,
    ShipmentRecipientContact,
    ShipmentTrackingStatus,
    ShipmentValidationStatus,
)
from wms.portal_dashboard_helpers import (
    build_portal_dashboard_kpis,
    portal_order_next_step_label,
    portal_order_next_step_tone,
)
from wms.status_presenters import (
    present_order_review_status,
    present_order_shipment_status,
    present_order_status,
)


def decorate_portal_dashboard_order(order):
    order.order_status_display = present_order_status(order)
    order.review_status_display = present_order_review_status(order)
    order.shipment_status_display = present_order_shipment_status(order)
    order.next_step_label = portal_order_next_step_label(order)
    order.next_step_tone = portal_order_next_step_tone(order)
    return order


def _portal_dashboard_orders_queryset(profile):
    return (
        Order.objects.filter(association_contact=profile.contact)
        .select_related("shipment__destination")
        .annotate(
            escale_label=Coalesce(
                "shipment__destination__city",
                "destination_city",
                Value(""),
            ),
            shipped_at=Coalesce(
                Max(
                    "shipment__tracking_events__created_at",
                    filter=Q(shipment__tracking_events__status=ShipmentTrackingStatus.BOARDING_OK),
                ),
                F("shipment__created_at"),
                output_field=DateTimeField(),
            ),
            received_correspondent_at=Max(
                "shipment__tracking_events__created_at",
                filter=Q(
                    shipment__tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
                ),
            ),
            received_recipient_at=Max(
                "shipment__tracking_events__created_at",
                filter=Q(
                    shipment__tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT
                ),
            ),
        )
        .order_by("-created_at")
    )


def _portal_dashboard_order_row(order):
    return {
        "id": order.id,
        "reference": order.reference or f"CMD-{order.id}",
        "review_status": order.review_status,
        "review_status_label": order.get_review_status_display(),
        "shipment_id": order.shipment_id,
        "shipment_reference": order.shipment.reference if order.shipment_id else "",
        "next_step_label": order.next_step_label,
        "next_step_tone": order.next_step_tone,
        "requested_delivery_date": (
            order.requested_delivery_date.isoformat() if order.requested_delivery_date else None
        ),
        "created_at": order.created_at.isoformat(),
    }


def build_portal_dashboard_payload(*, profile, api_limit: int = 12):
    orders = [
        decorate_portal_dashboard_order(order)
        for order in _portal_dashboard_orders_queryset(profile)
    ]
    return {
        "orders": orders,
        "dashboard_kpis": build_portal_dashboard_kpis(orders),
        "order_rows": [_portal_dashboard_order_row(order) for order in orders[:api_limit]],
    }


def _recipient_scope_validation_status_display(recipient_organization):
    if recipient_organization.validation_status == ShipmentValidationStatus.VALIDATED:
        return {
            "label": "Valide",
            "badge_class": "portal-badge is-ready",
        }
    return {
        "label": "En attente",
        "badge_class": "portal-badge is-info",
    }


def _recipient_scope_address_lines(contact):
    address = contact.get_effective_address()
    if address is None:
        return []
    lines = [address.address_line1]
    if address.address_line2:
        lines.append(address.address_line2)
    city_line = " ".join(part for part in [address.postal_code, address.city] if part).strip()
    if city_line:
        lines.append(city_line)
    if address.country:
        lines.append(address.country)
    return [line for line in lines if line]


def _recipient_scope_contact_label(contact):
    full_name = " ".join(part for part in [contact.first_name, contact.last_name] if part).strip()
    return full_name or contact.name or "-"


def _recipient_scope_document_rows(recipient_organization):
    documents = (
        RecipientStructureDocument.objects.filter(contact=recipient_organization.organization)
        .select_related("uploaded_by")
        .order_by("doc_type", "-uploaded_at")
    )
    return [
        {
            "doc_type_label": document.get_doc_type_display(),
            "status_label": document.get_status_display(),
            "filename": document.file.name.rsplit("/", 1)[-1],
            "uploaded_at": document.uploaded_at,
        }
        for document in documents
    ]


def _recipient_scope_preference_target_label(preference):
    if preference.product_id:
        return preference.product.name
    parts = []
    current = preference.category
    while current is not None:
        parts.append(current.name)
        current = current.parent
    return " > ".join(reversed(parts))


def _recipient_scope_preference_rows(recipient_organization):
    preferences = (
        RecipientProductPreference.objects.filter(recipient_organization=recipient_organization)
        .select_related("product", "category", "category__parent")
        .order_by("id")
    )
    return [
        {
            "target_label": _recipient_scope_preference_target_label(preference),
            "scope_type_label": "Produit" if preference.product_id else "Categorie",
            "status_label": preference.get_status_display(),
            "quantity_target": preference.quantity_target,
            "period_unit_label": preference.get_period_unit_display()
            if preference.period_unit
            else "-",
            "notes": preference.notes or "",
        }
        for preference in preferences
    ]


def _recipient_scope_contact_rows(recipient_organization):
    recipient_contacts = (
        ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
        )
        .select_related("contact")
        .order_by("contact__last_name", "contact__first_name", "id")
    )
    return [
        {
            "name": _recipient_scope_contact_label(recipient_contact.contact),
            "role": recipient_contact.contact.role or "",
            "email": recipient_contact.contact.email or "",
            "phone": recipient_contact.contact.phone or "",
        }
        for recipient_contact in recipient_contacts
    ]


def build_recipient_scope_home_payload(*, recipient_organization):
    recipient_organization = (
        type(recipient_organization)
        .objects.filter(pk=recipient_organization.pk)
        .select_related("organization", "destination")
        .get()
    )
    organization = recipient_organization.organization
    return {
        "recipient_organization": recipient_organization,
        "recipient_validation_status_display": _recipient_scope_validation_status_display(
            recipient_organization
        ),
        "recipient_structure_name": organization.name,
        "recipient_destination_label": str(recipient_organization.destination),
        "recipient_address_lines": _recipient_scope_address_lines(organization),
        "recipient_legal_form_label": organization.get_legal_form_display()
        if organization.legal_form
        else "",
        "recipient_beneficiary_count": organization.beneficiary_count,
        "recipient_notes": organization.notes or "",
        "recipient_contact_rows": _recipient_scope_contact_rows(recipient_organization),
        "recipient_document_rows": _recipient_scope_document_rows(recipient_organization),
        "recipient_preference_rows": _recipient_scope_preference_rows(recipient_organization),
    }
