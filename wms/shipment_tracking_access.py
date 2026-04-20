from __future__ import annotations

from django.db.models import Q

from .models import (
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingAuthSource,
    ShipmentTrackingIdentityStatus,
    ShipmentTrackingProofMode,
    ShipmentTrackingStatus,
)

DEFAULT_TRACKING_ESCALE_CODE = "CDG"
TRACKING_CONTACT_ROLES = {
    ShipmentTrackingAccessRole.SHIPPER,
    ShipmentTrackingAccessRole.RECIPIENT,
    ShipmentTrackingAccessRole.CORRESPONDENT,
}
TRACKING_DOWNSTREAM_RECEIPT_STATUSES = {
    ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
    ShipmentTrackingStatus.RECEIVED_RECIPIENT,
}
TRACKING_PENDING_ACCOUNT_FIELDS_BY_ROLE = {
    ShipmentTrackingAccessRole.VOLUNTEER: {
        "role",
        "email",
        "first_name",
        "last_name",
    },
    ShipmentTrackingAccessRole.SHIPPER: {
        "role",
        "email",
        "structure_name",
        "address_line1",
        "postal_code",
        "city",
        "country",
    },
    ShipmentTrackingAccessRole.RECIPIENT: {
        "role",
        "email",
        "structure_name",
        "address_line1",
        "postal_code",
        "city",
        "country",
        "escale_code",
    },
    ShipmentTrackingAccessRole.CORRESPONDENT: {
        "role",
        "email",
        "structure_name",
        "address_line1",
        "postal_code",
        "city",
        "country",
        "escale_code",
    },
}


def resolve_tracking_identifier_from_grant(grant: ShipmentTrackingAccessGrant) -> str:
    if getattr(grant, "contact_id", None):
        return str(getattr(grant.contact, "asf_id", "") or "").strip()
    if getattr(grant, "volunteer_profile_id", None):
        volunteer_id = getattr(grant.volunteer_profile, "volunteer_id", None)
        return str(volunteer_id) if volunteer_id is not None else ""
    return ""


def build_tracking_actor_snapshot_from_grant(
    grant: ShipmentTrackingAccessGrant,
) -> dict[str, object]:
    identifier = resolve_tracking_identifier_from_grant(grant)
    user = getattr(grant, "user", None)
    email = str(getattr(user, "email", "") or "").strip()
    destination = getattr(grant, "destination", None)
    return {
        "role": grant.role or "",
        "identifier": identifier,
        "email": email,
        "identity_status": grant.identity_status or ShipmentTrackingIdentityStatus.VERIFIED,
        "auth_source": ShipmentTrackingAuthSource.QR_RESTRICTED,
        "contact_id": grant.contact_id,
        "volunteer_profile_id": grant.volunteer_profile_id,
        "destination_id": getattr(destination, "id", None),
        "destination_iata_code": str(getattr(destination, "iata_code", "") or "").strip(),
    }


def tracking_identifier_label_for_role(role: str) -> str:
    if role == ShipmentTrackingAccessRole.VOLUNTEER:
        return "ID bénévole"
    if role in TRACKING_CONTACT_ROLES:
        return "ID ASF"
    return "Identifiant"


def shipment_has_boarding_ok(shipment) -> bool:
    if shipment is None:
        return False
    if getattr(shipment, "status", "") in {"shipped", "received_correspondent", "delivered"}:
        return True
    tracking_events = getattr(shipment, "tracking_events", None)
    if tracking_events is None:
        return False
    return tracking_events.filter(status=ShipmentTrackingStatus.BOARDING_OK).exists()


def default_tracking_escale_for_shipment(shipment) -> str:
    if not shipment_has_boarding_ok(shipment):
        return DEFAULT_TRACKING_ESCALE_CODE
    destination = getattr(shipment, "destination", None)
    destination_iata = str(getattr(destination, "iata_code", "") or "").strip().upper()
    return destination_iata or DEFAULT_TRACKING_ESCALE_CODE


def tracking_status_requires_proof(status: str) -> bool:
    return status in TRACKING_DOWNSTREAM_RECEIPT_STATUSES


def tracking_pending_account_fields_for_role(role: str) -> set[str]:
    return TRACKING_PENDING_ACCOUNT_FIELDS_BY_ROLE.get(role, {"role", "email"})


def tracking_requires_structure_details(role: str) -> bool:
    return role in TRACKING_CONTACT_ROLES


def resolve_tracking_proof_mode(*, proof_no_photo: bool, proof_file) -> str:
    if proof_no_photo:
        return ShipmentTrackingProofMode.MANUAL
    if proof_file:
        return ShipmentTrackingProofMode.PHOTO
    return ""


def find_active_tracking_access_grant(
    *,
    user,
    role: str,
    contact=None,
    volunteer_profile=None,
    destination=None,
):
    if user is None:
        return None
    queryset = ShipmentTrackingAccessGrant.objects.filter(
        user=user,
        role=role,
        is_active=True,
    ).select_related("contact", "volunteer_profile", "destination", "user")
    if contact is not None:
        queryset = queryset.filter(contact=contact)
    if volunteer_profile is not None:
        queryset = queryset.filter(volunteer_profile=volunteer_profile)
    if destination is not None:
        queryset = queryset.filter(
            Q(destination=destination) | Q(destination__isnull=True)
        ).order_by("-destination_id", "id")
    return queryset.first()
