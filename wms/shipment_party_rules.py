from __future__ import annotations

from django.db.models import QuerySet

from contacts.models import Contact, ContactType

from .models import (
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from .shipment_party_registry import (
    eligible_recipient_organizations_for_shipper,
    eligible_shippers_for_stopover,
    stopover_correspondent_recipient_organization,
)

MESSAGE_DESTINATION_REQUIRED = "Escale requise."
MESSAGE_SHIPPER_REQUIRED = "Expediteur requis."
MESSAGE_SHIPPER_REVIEW_PENDING = "Expediteur en cours de revue ASF."
MESSAGE_SHIPPER_OUT_OF_SCOPE = "Expediteur non autorise pour cette escale."
MESSAGE_RECIPIENT_REQUIRED = "Destinataire requis."
MESSAGE_RECIPIENT_REVIEW_PENDING = "Destinataire en cours de revue ASF."
MESSAGE_RECIPIENT_BINDING_MISSING = "Destinataire non autorise pour cet expediteur et cette escale."


class ShipmentPartyResolutionError(Exception):
    pass


def normalize_party_contact_to_org(contact: Contact | None) -> Contact | None:
    if contact is None:
        return None
    if contact.contact_type == ContactType.PERSON and getattr(contact, "organization_id", None):
        return contact.organization
    return contact


def _active_contacts_for_ids(contact_ids) -> QuerySet[Contact]:
    normalized_ids = {contact_id for contact_id in contact_ids if contact_id}
    if not normalized_ids:
        return Contact.objects.none()
    return (
        Contact.objects.filter(pk__in=normalized_ids, is_active=True)
        .select_related("organization")
        .order_by("name", "id")
        .distinct()
    )


def _validated_active_shipper_queryset() -> QuerySet[ShipmentShipper]:
    return ShipmentShipper.objects.filter(
        is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
        organization__is_active=True,
    ).select_related("organization", "default_contact", "default_contact__organization")


def _validated_active_recipient_organization_queryset(
    *, destination=None
) -> QuerySet[ShipmentRecipientOrganization]:
    queryset = ShipmentRecipientOrganization.objects.filter(
        is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
        organization__is_active=True,
        destination__is_active=True,
    ).select_related("organization", "destination")
    if destination is not None:
        queryset = queryset.filter(destination=destination)
    return queryset


def _active_recipient_contact_queryset(*, destination=None) -> QuerySet[ShipmentRecipientContact]:
    queryset = ShipmentRecipientContact.objects.filter(
        is_active=True,
        contact__is_active=True,
        recipient_organization__is_active=True,
        recipient_organization__validation_status=ShipmentValidationStatus.VALIDATED,
        recipient_organization__organization__is_active=True,
        recipient_organization__destination__is_active=True,
    ).select_related("contact", "contact__organization", "recipient_organization")
    if destination is not None:
        queryset = queryset.filter(recipient_organization__destination=destination)
    return queryset


def active_shipper_contacts() -> QuerySet[Contact]:
    shippers = list(_validated_active_shipper_queryset())
    contact_ids = {shipper.organization_id for shipper in shippers}
    contact_ids.update(shipper.default_contact_id for shipper in shippers)
    return _active_contacts_for_ids(contact_ids)


def active_recipient_contacts() -> QuerySet[Contact]:
    recipient_organizations = _validated_active_recipient_organization_queryset()
    contact_ids = set(recipient_organizations.values_list("organization_id", flat=True))
    contact_ids.update(_active_recipient_contact_queryset().values_list("contact_id", flat=True))
    return _active_contacts_for_ids(contact_ids)


def recipient_contacts_for_destination(destination) -> QuerySet[Contact]:
    if destination is None or not destination.is_active:
        return Contact.objects.none()
    recipient_organizations = _validated_active_recipient_organization_queryset(
        destination=destination
    )
    contact_ids = set(recipient_organizations.values_list("organization_id", flat=True))
    contact_ids.update(
        _active_recipient_contact_queryset(destination=destination).values_list(
            "contact_id", flat=True
        )
    )
    return _active_contacts_for_ids(contact_ids)


def eligible_shipper_contacts_for_destination(destination):
    if destination is None or not destination.is_active:
        return Contact.objects.none()
    shippers = list(
        eligible_shippers_for_stopover(destination).select_related(
            "organization",
            "default_contact",
            "default_contact__organization",
        )
    )
    contact_ids = {shipper.organization_id for shipper in shippers}
    contact_ids.update(shipper.default_contact_id for shipper in shippers)
    return _active_contacts_for_ids(contact_ids)


def _shipment_shipper_record(shipper_org: Contact | None) -> ShipmentShipper | None:
    shipper_org = normalize_party_contact_to_org(shipper_org)
    if shipper_org is None:
        return None

    queryset = _validated_active_shipper_queryset()
    shipper = queryset.filter(default_contact=shipper_org).first()
    if shipper is not None:
        return shipper
    return queryset.filter(organization=shipper_org).first()


def _shipment_recipient_organization_record(
    *,
    recipient_org: Contact | None,
    destination,
) -> ShipmentRecipientOrganization | None:
    recipient_org = normalize_party_contact_to_org(recipient_org)
    if recipient_org is None or destination is None:
        return None

    return (
        ShipmentRecipientOrganization.objects.filter(
            organization=recipient_org,
            destination=destination,
            is_active=True,
            organization__is_active=True,
        )
        .select_related("organization", "destination")
        .order_by("id")
        .first()
    )


def eligible_recipient_contacts_for_shipper_destination(*, shipper_contact, destination):
    if destination is None or not destination.is_active:
        return Contact.objects.none()

    shipper = _shipment_shipper_record(shipper_contact)
    if shipper is None:
        return Contact.objects.none()

    recipient_organizations = eligible_recipient_organizations_for_shipper(
        shipper=shipper,
        destination=destination,
    )
    recipient_organization_ids = list(recipient_organizations.values_list("id", flat=True))
    if not recipient_organization_ids:
        return Contact.objects.none()

    contact_ids = set(recipient_organizations.values_list("organization_id", flat=True))
    contact_ids.update(
        ShipmentAuthorizedRecipientContact.objects.filter(
            link__shipper=shipper,
            link__recipient_organization_id__in=recipient_organization_ids,
            link__is_active=True,
            recipient_contact__is_active=True,
            recipient_contact__contact__is_active=True,
            recipient_contact__recipient_organization__is_active=True,
            recipient_contact__recipient_organization__validation_status=ShipmentValidationStatus.VALIDATED,
            recipient_contact__recipient_organization__destination=destination,
            is_active=True,
        ).values_list("recipient_contact__contact_id", flat=True)
    )
    return _active_contacts_for_ids(contact_ids)


def eligible_correspondent_contacts_for_destination(destination):
    if destination is None or not destination.is_active:
        return Contact.objects.none()

    recipient_organization = stopover_correspondent_recipient_organization(destination)
    if recipient_organization is None:
        return Contact.objects.none()

    contact_ids = {recipient_organization.organization_id}
    contact_ids.update(
        _active_recipient_contact_queryset(destination=destination)
        .filter(recipient_organization=recipient_organization)
        .values_list("contact_id", flat=True)
    )

    correspondent_contact = getattr(destination, "correspondent_contact", None)
    if correspondent_contact is not None and correspondent_contact.is_active:
        correspondent_org = normalize_party_contact_to_org(correspondent_contact)
        if (
            correspondent_org is not None
            and correspondent_org.id == recipient_organization.organization_id
        ):
            contact_ids.add(correspondent_contact.id)

    return _active_contacts_for_ids(contact_ids)


def resolve_shipper_for_operation(*, shipper_org, destination):
    if destination is None:
        raise ShipmentPartyResolutionError(MESSAGE_DESTINATION_REQUIRED)

    shipper_org = normalize_party_contact_to_org(shipper_org)
    if shipper_org is None:
        raise ShipmentPartyResolutionError(MESSAGE_SHIPPER_REQUIRED)

    shipper = _shipment_shipper_record(shipper_org)
    if shipper is None:
        raise ShipmentPartyResolutionError(MESSAGE_SHIPPER_REVIEW_PENDING)
    if not eligible_shippers_for_stopover(destination).filter(pk=shipper.pk).exists():
        raise ShipmentPartyResolutionError(MESSAGE_SHIPPER_OUT_OF_SCOPE)
    return shipper


def resolve_recipient_binding_for_operation(*, shipper_org, recipient_org, destination):
    if destination is None:
        raise ShipmentPartyResolutionError(MESSAGE_DESTINATION_REQUIRED)

    recipient_org = normalize_party_contact_to_org(recipient_org)
    if recipient_org is None:
        raise ShipmentPartyResolutionError(MESSAGE_RECIPIENT_REQUIRED)

    shipper = resolve_shipper_for_operation(
        shipper_org=shipper_org,
        destination=destination,
    )

    recipient_organization = _shipment_recipient_organization_record(
        recipient_org=recipient_org,
        destination=destination,
    )
    if recipient_organization is None:
        raise ShipmentPartyResolutionError(MESSAGE_RECIPIENT_BINDING_MISSING)
    if recipient_organization.validation_status != ShipmentValidationStatus.VALIDATED:
        raise ShipmentPartyResolutionError(MESSAGE_RECIPIENT_REVIEW_PENDING)

    if (
        not eligible_recipient_organizations_for_shipper(
            shipper=shipper,
            destination=destination,
        )
        .filter(pk=recipient_organization.pk)
        .exists()
    ):
        raise ShipmentPartyResolutionError(MESSAGE_RECIPIENT_BINDING_MISSING)

    return (
        ShipmentShipperRecipientLink.objects.filter(
            shipper=shipper,
            recipient_organization=recipient_organization,
            is_active=True,
        )
        .select_related("shipper", "recipient_organization")
        .order_by("id")
        .first()
        or recipient_organization
    )


def _contact_emails(contact: Contact | None) -> list[str]:
    if contact is None:
        return []
    emails: list[str] = []
    seen: set[str] = set()
    for value in (getattr(contact, "email", ""), getattr(contact, "email2", "")):
        normalized = str(value or "").strip()
        key = normalized.lower()
        if normalized and key not in seen:
            emails.append(normalized)
            seen.add(key)
    return emails


def build_party_contact_reference(contact: Contact | None, fallback_name: str = "") -> dict:
    if contact is None:
        return {
            "contact_id": None,
            "contact_name": str(fallback_name or "").strip(),
            "notification_emails": [],
        }

    return {
        "contact_id": contact.pk,
        "contact_name": contact.name,
        "contact_title": getattr(contact, "title", ""),
        "contact_first_name": getattr(contact, "first_name", ""),
        "contact_last_name": getattr(contact, "last_name", ""),
        "notification_emails": _contact_emails(contact),
        "phone": getattr(contact, "phone", ""),
        "phone2": getattr(contact, "phone2", ""),
    }
