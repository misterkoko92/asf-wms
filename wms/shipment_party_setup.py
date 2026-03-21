from __future__ import annotations

from contacts.models import Contact, ContactType

from .models import (
    ShipmentAuthorizedRecipientContact,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)

PRIORITY_SHIPPER_NAME = "Aviation Sans Frontieres"
DEFAULT_SHIPPER_CONTACT_FIRST_NAME = "Referent"
DEFAULT_SHIPPER_CONTACT_LAST_NAME = "Portail"


def _normalized_text(value) -> str:
    return str(value or "").strip()


def _casefold(value) -> str:
    return _normalized_text(value).casefold()


def _portal_contact_for_organization(organization: Contact):
    profile = organization.association_profiles.select_related("user").order_by("id").first()
    if profile is None:
        return None
    return profile.portal_contacts.filter(is_active=True).order_by("position", "id").first()


def ensure_shipment_shipper_default_contact(organization: Contact) -> Contact:
    existing = (
        organization.members.filter(
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if existing is not None:
        return existing

    portal_contact = _portal_contact_for_organization(organization)
    first_name = _normalized_text(getattr(portal_contact, "first_name", "")) or (
        DEFAULT_SHIPPER_CONTACT_FIRST_NAME
    )
    last_name = _normalized_text(getattr(portal_contact, "last_name", "")) or (
        DEFAULT_SHIPPER_CONTACT_LAST_NAME
    )
    email = _normalized_text(getattr(portal_contact, "email", "")) or _normalized_text(
        organization.email
    )
    phone = _normalized_text(getattr(portal_contact, "phone", "")) or _normalized_text(
        organization.phone
    )

    return Contact.objects.create(
        contact_type=ContactType.PERSON,
        organization=organization,
        title=_normalized_text(getattr(portal_contact, "title", "")),
        first_name=first_name[:120],
        last_name=last_name[:120],
        name=f"{first_name} {last_name}".strip()[:200],
        email=email[:254],
        phone=phone[:40],
        use_organization_address=True,
        is_active=True,
    )


def ensure_shipment_shipper(
    organization: Contact,
    *,
    validation_status: str = ShipmentValidationStatus.VALIDATED,
) -> ShipmentShipper:
    default_contact = ensure_shipment_shipper_default_contact(organization)
    shipper, created = ShipmentShipper.objects.get_or_create(
        organization=organization,
        defaults={
            "default_contact": default_contact,
            "validation_status": validation_status,
            "can_send_to_all": _casefold(organization.name) == _casefold(PRIORITY_SHIPPER_NAME),
            "is_active": True,
        },
    )
    if created:
        return shipper

    updated_fields = []
    if shipper.default_contact_id != default_contact.id:
        shipper.default_contact = default_contact
        updated_fields.append("default_contact")
    if shipper.validation_status != validation_status:
        shipper.validation_status = validation_status
        updated_fields.append("validation_status")
    target_can_send_to_all = _casefold(organization.name) == _casefold(PRIORITY_SHIPPER_NAME)
    if shipper.can_send_to_all != target_can_send_to_all:
        shipper.can_send_to_all = target_can_send_to_all
        updated_fields.append("can_send_to_all")
    if not shipper.is_active:
        shipper.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        shipper.save(update_fields=updated_fields)
    return shipper


def ensure_shipment_recipient_link(
    *,
    shipper: ShipmentShipper,
    recipient_organization,
) -> ShipmentShipperRecipientLink:
    link, created = ShipmentShipperRecipientLink.objects.get_or_create(
        shipper=shipper,
        recipient_organization=recipient_organization,
        defaults={"is_active": True},
    )
    if not created and not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active"])
    return link


def ensure_authorized_recipient_contact(
    *,
    link: ShipmentShipperRecipientLink,
    recipient_contact,
    is_active: bool,
    set_as_default: bool,
) -> ShipmentAuthorizedRecipientContact:
    authorized, _created = ShipmentAuthorizedRecipientContact.objects.get_or_create(
        link=link,
        recipient_contact=recipient_contact,
        defaults={
            "is_active": bool(is_active),
            "is_default": False,
        },
    )
    updated_fields = []
    if authorized.is_active != bool(is_active):
        authorized.is_active = bool(is_active)
        updated_fields.append("is_active")

    should_be_default = False
    if is_active:
        if set_as_default:
            should_be_default = True
        else:
            has_other_default = (
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=link,
                    is_active=True,
                    is_default=True,
                )
                .exclude(pk=authorized.pk)
                .exists()
            )
            if authorized.is_default or not has_other_default:
                should_be_default = True

    if should_be_default:
        ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_default=True,
        ).exclude(pk=authorized.pk).update(is_default=False)
    if authorized.is_default != should_be_default:
        authorized.is_default = should_be_default
        updated_fields.append("is_default")
    if updated_fields:
        authorized.save(update_fields=updated_fields)

    has_active_authorization = ShipmentAuthorizedRecipientContact.objects.filter(
        link=link,
        is_active=True,
    ).exists()
    if has_active_authorization and not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active"])
    elif not has_active_authorization and link.is_active:
        link.is_active = False
        link.save(update_fields=["is_active"])

    return authorized
