from __future__ import annotations

from dataclasses import dataclass

from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)

MISSING_VALIDATED_SHIPPER = "missing_validated_shipper"
MISSING_ADMIN_CONTACT = "missing_admin_contact"
MISSING_PREPARATION_CONTACT = "missing_preparation_contact"
MISSING_VALIDATED_RECIPIENT = "missing_validated_recipient"


@dataclass(frozen=True)
class ReadinessRequirement:
    code: str
    label: str


@dataclass(frozen=True)
class ShipperReadiness:
    is_ready: bool
    missing_requirements: list[ReadinessRequirement]

    @property
    def missing_codes(self) -> list[str]:
        return [requirement.code for requirement in self.missing_requirements]


READINESS_LABELS = {
    MISSING_VALIDATED_SHIPPER: "Compte expediteur non valide",
    MISSING_ADMIN_CONTACT: "Contact administratif incomplet",
    MISSING_PREPARATION_CONTACT: "Contact preparation/logistique incomplet",
    MISSING_VALIDATED_RECIPIENT: "Aucun destinataire valide lie a votre structure",
}


def _has_value(value) -> bool:
    return bool(str(value or "").strip())


def _portal_contact_is_complete(contact: AssociationPortalContact) -> bool:
    return all(
        [
            _has_value(contact.title),
            _has_value(contact.last_name),
            _has_value(contact.first_name),
            _has_value(contact.email),
            _has_value(contact.phone),
        ]
    )


def _has_complete_contact(profile: AssociationProfile, *, role_field: str) -> bool:
    contacts = profile.portal_contacts.filter(is_active=True, **{role_field: True})
    return any(_portal_contact_is_complete(contact) for contact in contacts)


def _get_validated_shipper(profile: AssociationProfile) -> ShipmentShipper | None:
    return (
        ShipmentShipper.objects.filter(
            organization=profile.contact,
            is_active=True,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        .select_related("organization")
        .first()
    )


def _has_validated_linked_recipient(shipper: ShipmentShipper) -> bool:
    return ShipmentShipperRecipientLink.objects.filter(
        shipper=shipper,
        is_active=True,
        recipient_organization__is_active=True,
        recipient_organization__validation_status=ShipmentValidationStatus.VALIDATED,
        recipient_organization__organization__is_active=True,
        recipient_organization__destination__is_active=True,
    ).exists()


def _requirement(code: str) -> ReadinessRequirement:
    return ReadinessRequirement(code=code, label=READINESS_LABELS[code])


def build_shipper_readiness(profile: AssociationProfile) -> ShipperReadiness:
    missing_codes = []

    shipper = _get_validated_shipper(profile)
    if shipper is None:
        missing_codes.append(MISSING_VALIDATED_SHIPPER)

    if not _has_complete_contact(profile, role_field="is_administrative"):
        missing_codes.append(MISSING_ADMIN_CONTACT)

    if not _has_complete_contact(profile, role_field="is_shipping"):
        missing_codes.append(MISSING_PREPARATION_CONTACT)

    if shipper is None or not _has_validated_linked_recipient(shipper):
        missing_codes.append(MISSING_VALIDATED_RECIPIENT)

    missing_requirements = [_requirement(code) for code in missing_codes]
    return ShipperReadiness(
        is_ready=not missing_requirements,
        missing_requirements=missing_requirements,
    )
