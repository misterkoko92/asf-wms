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
ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY = "shipment_tracking_active_grant_id"
TRACKING_CONTACT_ROLES = {
    ShipmentTrackingAccessRole.SHIPPER,
    ShipmentTrackingAccessRole.RECIPIENT,
    ShipmentTrackingAccessRole.CORRESPONDENT,
}
TRACKING_DOWNSTREAM_RECEIPT_STATUSES = {
    ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
    ShipmentTrackingStatus.RECEIVED_RECIPIENT,
}
TRACKING_ALLOWED_STATUSES_BY_ROLE = {
    ShipmentTrackingAccessRole.VOLUNTEER: {
        ShipmentTrackingStatus.PLANNING_OK,
        ShipmentTrackingStatus.PLANNED,
        ShipmentTrackingStatus.MOVED_EXPORT,
        ShipmentTrackingStatus.BOARDING_OK,
    },
    ShipmentTrackingAccessRole.SHIPPER: {
        ShipmentTrackingStatus.PLANNING_OK,
        ShipmentTrackingStatus.PLANNED,
        ShipmentTrackingStatus.MOVED_EXPORT,
        ShipmentTrackingStatus.BOARDING_OK,
    },
    ShipmentTrackingAccessRole.CORRESPONDENT: {
        ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
    },
    ShipmentTrackingAccessRole.RECIPIENT: {
        ShipmentTrackingStatus.RECEIVED_RECIPIENT,
    },
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


def normalize_tracking_identifier(raw_value) -> str:
    return str(raw_value or "").strip()


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


def tracking_allowed_statuses_for_role(role: str, statuses) -> list[str]:
    status_values = list(statuses or [])
    if not role:
        return status_values
    allowed = TRACKING_ALLOWED_STATUSES_BY_ROLE.get(role)
    if allowed is None:
        return []
    return [status for status in status_values if status in allowed]


def tracking_role_allows_status(role: str, status: str) -> bool:
    if not role:
        return True
    allowed = TRACKING_ALLOWED_STATUSES_BY_ROLE.get(role)
    if allowed is None:
        return False
    return status in allowed


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


def resolve_tracking_access_grant_by_identifier(*, role: str, identifier: str):
    normalized_identifier = normalize_tracking_identifier(identifier)
    if not normalized_identifier:
        return None
    queryset = ShipmentTrackingAccessGrant.objects.filter(
        role=role,
        is_active=True,
    ).select_related("contact", "volunteer_profile", "destination", "user")
    if role == ShipmentTrackingAccessRole.VOLUNTEER:
        try:
            volunteer_id = int(normalized_identifier)
        except (TypeError, ValueError):
            return None
        return queryset.filter(volunteer_profile__volunteer_id=volunteer_id).first()
    return queryset.filter(contact__asf_id__iexact=normalized_identifier).first()


def resolve_tracking_access_grant_by_email(*, role: str, email: str):
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None
    return (
        ShipmentTrackingAccessGrant.objects.filter(
            role=role,
            is_active=True,
            user__email__iexact=normalized_email,
        )
        .select_related("contact", "volunteer_profile", "destination", "user")
        .first()
    )


def activate_tracking_access_grant(request, *, grant: ShipmentTrackingAccessGrant | None) -> None:
    if grant is None:
        request.session.pop(ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY, None)
        return
    request.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = grant.id


def resolve_active_tracking_access_grant(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    grant_id = request.session.get(ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY)
    if not grant_id:
        return None
    return (
        ShipmentTrackingAccessGrant.objects.filter(
            id=grant_id,
            user=user,
            is_active=True,
        )
        .select_related("contact", "volunteer_profile", "destination", "user")
        .first()
    )


def resolve_shipment_contact_for_role(*, shipment, role: str):
    if shipment is None:
        return None
    if role == ShipmentTrackingAccessRole.SHIPPER:
        return getattr(shipment, "shipper_contact_ref", None)
    if role == ShipmentTrackingAccessRole.RECIPIENT:
        return getattr(shipment, "recipient_contact_ref", None)
    if role == ShipmentTrackingAccessRole.CORRESPONDENT:
        return getattr(shipment, "correspondent_contact_ref", None)
    return None


def tracking_grant_matches_shipment(*, grant, shipment, role: str, identifier: str = "") -> bool:
    if grant is None or grant.role != role:
        return False
    if identifier and resolve_tracking_identifier_from_grant(
        grant
    ) != normalize_tracking_identifier(identifier):
        return False
    if role == ShipmentTrackingAccessRole.VOLUNTEER:
        return bool(getattr(grant, "volunteer_profile_id", None))
    contact = resolve_shipment_contact_for_role(shipment=shipment, role=role)
    return bool(contact and getattr(grant, "contact_id", None) == contact.id)
