from __future__ import annotations

from wms.models import AssociationRecipient


def refresh_legacy_association_recipient_projection(
    *,
    projection=None,
    association_contact,
    synced_contact,
    recipient_organization,
    shipment_contact,
    structure_name="",
    contact_title="",
    contact_first_name="",
    contact_last_name="",
    emails="",
    phones="",
    address_line1="",
    address_line2="",
    postal_code="",
    city="",
    country="France",
    legal_form="",
    beneficiary_count=None,
    notes="",
    notify_deliveries=False,
    is_delivery_contact=False,
    is_active=True,
):
    legacy_projection = projection or AssociationRecipient(
        association_contact=association_contact,
    )
    legacy_projection.association_contact = association_contact
    legacy_projection.synced_contact = synced_contact
    legacy_projection.destination = recipient_organization.destination
    legacy_projection.structure_name = (structure_name or synced_contact.name or "").strip()
    legacy_projection.name = legacy_projection.structure_name or shipment_contact.contact.name
    legacy_projection.contact_title = (contact_title or "").strip()
    legacy_projection.contact_first_name = (contact_first_name or "").strip()
    legacy_projection.contact_last_name = (contact_last_name or "").strip()
    legacy_projection.emails = (
        emails or shipment_contact.contact.email or synced_contact.email or ""
    ).strip()
    legacy_projection.phones = (
        phones or shipment_contact.contact.phone or synced_contact.phone or ""
    ).strip()
    legacy_projection.address_line1 = (address_line1 or "").strip()
    legacy_projection.address_line2 = (address_line2 or "").strip()
    legacy_projection.postal_code = (postal_code or "").strip()
    legacy_projection.city = (city or "").strip()
    legacy_projection.country = (country or "France").strip()
    legacy_projection.legal_form = legal_form or synced_contact.legal_form or ""
    legacy_projection.beneficiary_count = (
        beneficiary_count if beneficiary_count is not None else synced_contact.beneficiary_count
    )
    legacy_projection.notes = (notes or "").strip()
    legacy_projection.notify_deliveries = bool(notify_deliveries)
    legacy_projection.is_delivery_contact = bool(is_delivery_contact)
    legacy_projection.is_active = bool(is_active)
    legacy_projection.save()
    return legacy_projection


def refresh_legacy_association_recipient_projections_for_runtime(
    *,
    recipient_organization,
    shipment_contact,
):
    organization = recipient_organization.organization
    address = organization.get_effective_address()
    projections = list(
        AssociationRecipient.objects.filter(
            synced_contact=organization,
            destination=recipient_organization.destination,
        ).select_related("association_contact")
    )
    refreshed = []
    for projection in projections:
        refreshed.append(
            refresh_legacy_association_recipient_projection(
                projection=projection,
                association_contact=projection.association_contact,
                synced_contact=organization,
                recipient_organization=recipient_organization,
                shipment_contact=shipment_contact,
                structure_name=organization.name,
                contact_title=shipment_contact.contact.title,
                contact_first_name=shipment_contact.contact.first_name,
                contact_last_name=shipment_contact.contact.last_name,
                emails=shipment_contact.contact.email or organization.email or "",
                phones=shipment_contact.contact.phone or organization.phone or "",
                address_line1=getattr(address, "address_line1", ""),
                address_line2=getattr(address, "address_line2", ""),
                postal_code=getattr(address, "postal_code", ""),
                city=getattr(address, "city", ""),
                country=getattr(address, "country", "France"),
                legal_form=organization.legal_form or "",
                beneficiary_count=organization.beneficiary_count,
                notes=organization.notes or "",
                notify_deliveries=projection.notify_deliveries,
                is_delivery_contact=projection.is_delivery_contact,
                is_active=projection.is_active,
            )
        )
    return refreshed
