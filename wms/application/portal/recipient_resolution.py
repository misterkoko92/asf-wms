from wms.application.parties.use_cases import resolve_portal_recipient_party_contact
from wms.contact_labels import build_shipment_recipient_select_label
from wms.models import AssociationRecipient
from wms.portal_helpers import build_destination_address, get_contact_address
from wms.shipment_helpers import (
    shipment_link_for_recipient_contact,
    shipment_shipper_from_contact,
)

PORTAL_DEFAULT_COUNTRY = "France"
PORTAL_RECIPIENT_SELF = "self"


def _association_destination_payload(*, profile, selected_destination):
    address = get_contact_address(profile.contact)
    if not address:
        return None, "Adresse association manquante."
    return {
        "recipient_name": profile.contact.name,
        "recipient_contact": profile.contact,
        "destination_city": selected_destination.city
        if selected_destination
        else (address.city or ""),
        "destination_country": (
            selected_destination.country
            if selected_destination
            else (address.country or PORTAL_DEFAULT_COUNTRY)
        ),
        "destination_address": build_destination_address(
            line1=address.address_line1,
            line2=address.address_line2,
            postal_code=address.postal_code,
            city=address.city,
            country=address.country,
        ),
    }, ""


def resolve_portal_order_destination(*, profile, recipient_id, selected_destination):
    if recipient_id == PORTAL_RECIPIENT_SELF:
        return _association_destination_payload(
            profile=profile,
            selected_destination=selected_destination,
        )

    recipient = (
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
            pk=recipient_id,
        )
        .select_related("destination")
        .order_by("name")
        .first()
    )
    if recipient is None:
        return None, "Destinataire invalide."
    if selected_destination and recipient.destination_id not in {selected_destination.id, None}:
        return None, "Destinataire non disponible pour cette destination."

    recipient_contact = resolve_portal_recipient_party_contact(recipient)
    recipient_address = get_contact_address(recipient_contact) or get_contact_address(
        getattr(recipient, "synced_contact", None)
    )
    resolved_destination = selected_destination or recipient.destination
    destination_city = (
        (resolved_destination.city if resolved_destination else "")
        or recipient.city
        or (recipient_address.city if recipient_address else "")
    )
    destination_country = (
        (resolved_destination.country if resolved_destination else "")
        or recipient.country
        or (recipient_address.country if recipient_address else "")
        or PORTAL_DEFAULT_COUNTRY
    )
    address_city = (
        (recipient_address.city if recipient_address else "")
        or recipient.city
        or (resolved_destination.city if resolved_destination else "")
    )
    address_country = (
        (recipient_address.country if recipient_address else "")
        or recipient.country
        or (resolved_destination.country if resolved_destination else "")
        or PORTAL_DEFAULT_COUNTRY
    )
    recipient_name = (
        build_shipment_recipient_select_label(recipient_contact, destination=recipient.destination)
        if recipient_contact is not None
        else recipient.get_shipment_party_display_name()
    )

    return {
        "recipient_name": recipient_name,
        "recipient_contact": recipient_contact,
        "destination_city": destination_city,
        "destination_country": destination_country,
        "destination_address": build_destination_address(
            line1=(recipient_address.address_line1 if recipient_address else "")
            or recipient.address_line1,
            line2=(recipient_address.address_line2 if recipient_address else "")
            or recipient.address_line2,
            postal_code=(recipient_address.postal_code if recipient_address else "")
            or recipient.postal_code,
            city=address_city,
            country=address_country,
        ),
    }, ""


def build_allowed_destination_ids_by_recipient(*, profile, recipients, destinations):
    recipient_contact_by_id = {
        recipient.id: resolve_portal_recipient_party_contact(recipient) for recipient in recipients
    }
    allowed_destination_ids_by_recipient: dict[str, set[int]] = {
        str(recipient.id): set() for recipient in recipients
    }
    shipper = shipment_shipper_from_contact(profile.contact)
    if shipper is None:
        return {
            recipient_id: sorted(destination_ids)
            for recipient_id, destination_ids in allowed_destination_ids_by_recipient.items()
        }

    for destination in destinations:
        for recipient in recipients:
            if recipient.destination_id not in {destination.id, None}:
                continue
            recipient_contact = recipient_contact_by_id.get(recipient.id)
            if recipient_contact is None:
                continue
            if (
                shipment_link_for_recipient_contact(
                    shipper=shipper,
                    recipient_contact=recipient_contact,
                    destination=destination,
                )
                is not None
            ):
                allowed_destination_ids_by_recipient[str(recipient.id)].add(destination.id)

    return {
        recipient_id: sorted(destination_ids)
        for recipient_id, destination_ids in allowed_destination_ids_by_recipient.items()
    }
