from __future__ import annotations

from django.db.models import Q

from .models import (
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAuthSource,
    ShipmentTrackingIdentityStatus,
)


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
