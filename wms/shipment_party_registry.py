from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import (
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)


def _validated_active_shippers() -> QuerySet[ShipmentShipper]:
    return ShipmentShipper.objects.filter(
        is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
        organization__is_active=True,
    )


def _validated_active_recipient_organization_filters(*, prefix: str = "") -> dict[str, object]:
    return {
        f"{prefix}is_active": True,
        f"{prefix}validation_status": ShipmentValidationStatus.VALIDATED,
        f"{prefix}organization__is_active": True,
        f"{prefix}destination__is_active": True,
    }


def _validated_active_recipient_organizations(
    *, destination
) -> QuerySet[ShipmentRecipientOrganization]:
    return ShipmentRecipientOrganization.objects.filter(
        destination=destination,
        **_validated_active_recipient_organization_filters(),
    )


def eligible_shippers_for_stopover(destination) -> QuerySet[ShipmentShipper]:
    if destination is None or not destination.is_active:
        return ShipmentShipper.objects.none()

    return (
        _validated_active_shippers()
        .filter(
            Q(can_send_to_all=True)
            | Q(
                recipient_links__is_active=True,
                recipient_links__recipient_organization__destination=destination,
                **_validated_active_recipient_organization_filters(
                    prefix="recipient_links__recipient_organization__"
                ),
            )
        )
        .distinct()
    )


def eligible_recipient_organizations_for_shipper(
    *, shipper, destination
) -> QuerySet[ShipmentRecipientOrganization]:
    if shipper is None or destination is None or not destination.is_active:
        return ShipmentRecipientOrganization.objects.none()

    shipper_is_eligible = _validated_active_shippers().filter(pk=shipper.pk).exists()
    if not shipper_is_eligible:
        return ShipmentRecipientOrganization.objects.none()

    base_qs = _validated_active_recipient_organizations(destination=destination)
    if shipper.can_send_to_all:
        return base_qs

    return base_qs.filter(
        shipper_links__shipper=shipper,
        shipper_links__is_active=True,
    ).distinct()


def eligible_recipient_contacts_for_link(link) -> QuerySet[ShipmentRecipientContact]:
    if link is None or not link.is_active:
        return ShipmentRecipientContact.objects.none()

    return (
        ShipmentRecipientContact.objects.filter(
            authorized_links__link=link,
            authorized_links__is_active=True,
            is_active=True,
            contact__is_active=True,
            recipient_organization_id=link.recipient_organization_id,
            **_validated_active_recipient_organization_filters(prefix="recipient_organization__"),
        )
        .distinct()
        .order_by("contact__last_name", "id")
    )


def default_recipient_contact_for_link(link) -> ShipmentRecipientContact | None:
    if link is None or not link.is_active:
        return None

    authorized = (
        ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_default=True,
            is_active=True,
            recipient_contact__is_active=True,
            recipient_contact__contact__is_active=True,
            **_validated_active_recipient_organization_filters(
                prefix="recipient_contact__recipient_organization__"
            ),
        )
        .select_related("recipient_contact")
        .first()
    )
    return authorized.recipient_contact if authorized else None


def stopover_correspondent_recipient_organization(
    destination,
) -> ShipmentRecipientOrganization | None:
    if destination is None or not destination.is_active:
        return None

    return (
        ShipmentRecipientOrganization.objects.filter(
            destination=destination,
            is_correspondent=True,
            is_active=True,
            validation_status=ShipmentValidationStatus.VALIDATED,
            organization__is_active=True,
        )
        .order_by("id")
        .first()
    )
