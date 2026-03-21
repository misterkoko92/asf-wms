from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from contacts.models import Contact, ContactType

from .models import (
    Destination,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)
from .shipment_party_setup import (
    PRIORITY_SHIPPER_NAME,
    ensure_authorized_recipient_contact,
    ensure_shipment_recipient_link,
    ensure_shipment_shipper,
)

_DEFAULT_SHIPPER_BINDING_SYNC_ENABLED = ContextVar(
    "default_shipper_binding_sync_enabled",
    default=True,
)
DEFAULT_RECIPIENT_SHIPPER_NAME = PRIORITY_SHIPPER_NAME.upper()


def default_shipper_binding_sync_enabled() -> bool:
    return _DEFAULT_SHIPPER_BINDING_SYNC_ENABLED.get()


@contextmanager
def suppress_default_shipper_binding_sync():
    token = _DEFAULT_SHIPPER_BINDING_SYNC_ENABLED.set(False)
    try:
        yield
    finally:
        _DEFAULT_SHIPPER_BINDING_SYNC_ENABLED.reset(token)


def _resolve_default_shipper() -> ShipmentShipper | None:
    shipper = (
        ShipmentShipper.objects.filter(
            organization__is_active=True,
            organization__name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME,
        )
        .select_related("organization", "default_contact")
        .order_by("id")
        .first()
    )
    if shipper is not None:
        return ensure_shipment_shipper(
            shipper.organization,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )

    organization = Contact.objects.filter(
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
        name__iexact=DEFAULT_RECIPIENT_SHIPPER_NAME,
    ).first()
    if organization is None:
        return None
    return ensure_shipment_shipper(
        organization,
        validation_status=ShipmentValidationStatus.VALIDATED,
    )


def _active_recipient_organizations(*, destination_ids: list[int] | None = None):
    queryset = ShipmentRecipientOrganization.objects.filter(
        is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
        organization__is_active=True,
        destination__is_active=True,
    ).select_related("organization", "destination")
    if destination_ids is not None:
        queryset = queryset.filter(destination_id__in=destination_ids)
    return queryset.order_by("destination_id", "organization__name", "id")


def _default_recipient_contact(recipient_organization: ShipmentRecipientOrganization):
    return (
        ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
            contact__is_active=True,
        )
        .select_related("contact")
        .order_by("id")
        .first()
    )


def _ensure_default_shipper_links(
    *,
    shipper: ShipmentShipper,
    recipient_organizations,
) -> int:
    created = 0
    for recipient_organization in recipient_organizations:
        link_already_exists = shipper.recipient_links.filter(
            recipient_organization=recipient_organization
        ).exists()
        link = ensure_shipment_recipient_link(
            shipper=shipper,
            recipient_organization=recipient_organization,
        )
        if not link_already_exists:
            created += 1

        default_contact = _default_recipient_contact(recipient_organization)
        if default_contact is None:
            continue
        has_default = link.authorized_recipient_contacts.filter(
            is_active=True,
            is_default=True,
        ).exists()
        existing_authorization = link.authorized_recipient_contacts.filter(
            recipient_contact=default_contact
        ).first()
        ensure_authorized_recipient_contact(
            link=link,
            recipient_contact=default_contact,
            is_active=True,
            set_as_default=not has_default
            or bool(existing_authorization is not None and existing_authorization.is_default),
        )
    return created


def ensure_default_shipper_links_for_destination_id(destination_id: int) -> int:
    destination = Destination.objects.filter(pk=destination_id, is_active=True).only("id").first()
    if destination is None:
        return 0

    shipper = _resolve_default_shipper()
    if shipper is None:
        return 0
    return _ensure_default_shipper_links(
        shipper=shipper,
        recipient_organizations=_active_recipient_organizations(destination_ids=[destination.id]),
    )


def ensure_default_shipper_links_for_recipient_organization_id(
    recipient_organization_id: int,
) -> int:
    recipient_organization = (
        _active_recipient_organizations().filter(pk=recipient_organization_id).first()
    )
    if recipient_organization is None:
        return 0

    shipper = _resolve_default_shipper()
    if shipper is None:
        return 0
    return _ensure_default_shipper_links(
        shipper=shipper,
        recipient_organizations=[recipient_organization],
    )


def ensure_default_shipper_bindings_for_destination_id(destination_id: int) -> int:
    return ensure_default_shipper_links_for_destination_id(destination_id)


def ensure_default_shipper_bindings_for_recipient_assignment_id(role_assignment_id: int) -> int:
    return 0
