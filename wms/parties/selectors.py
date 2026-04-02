from __future__ import annotations

from django.db.models import QuerySet

from contacts.models import Contact
from wms.models import (
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)


def validated_shippers() -> QuerySet[ShipmentShipper]:
    return ShipmentShipper.objects.filter(
        is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
        organization__is_active=True,
    )


def validated_active_recipient_organization_filters(*, prefix: str = "") -> dict[str, object]:
    return {
        f"{prefix}is_active": True,
        f"{prefix}validation_status": ShipmentValidationStatus.VALIDATED,
        f"{prefix}organization__is_active": True,
        f"{prefix}destination__is_active": True,
    }


def validated_recipient_organizations(
    *, destination=None
) -> QuerySet[ShipmentRecipientOrganization]:
    queryset = ShipmentRecipientOrganization.objects.filter(
        **validated_active_recipient_organization_filters()
    ).select_related("organization", "destination")
    if destination is not None:
        queryset = queryset.filter(destination=destination)
    return queryset


def validated_recipient_organizations_for_destination(
    destination,
) -> QuerySet[ShipmentRecipientOrganization]:
    if destination is None or not destination.is_active:
        return ShipmentRecipientOrganization.objects.none()
    return validated_recipient_organizations(destination=destination)


def active_recipient_contact_links(*, destination=None) -> QuerySet[ShipmentRecipientContact]:
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


def active_recipient_contacts_for_destination(*, destination) -> QuerySet[Contact]:
    if destination is None or not destination.is_active:
        return Contact.objects.none()
    return (
        Contact.objects.filter(
            pk__in=active_recipient_contact_links(destination=destination).values_list(
                "contact_id", flat=True
            ),
            is_active=True,
        )
        .select_related("organization")
        .order_by("last_name", "id")
        .distinct()
    )
