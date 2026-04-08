from __future__ import annotations

from dataclasses import dataclass

from .models import (
    AssociationProfile,
    PortalAccessGrant,
    PortalAccessRole,
    ShipmentRecipientOrganization,
    ShipmentShipper,
)
from .portal_helpers import get_association_profile

ACTIVE_PORTAL_SCOPE_SESSION_KEY = "portal_active_scope"
PORTAL_SCOPE_SOURCE_GRANT = "grant"
PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION = "legacy_association_profile"


@dataclass(frozen=True)
class PortalScope:
    source: str
    role: str
    grant: PortalAccessGrant | None = None
    shipper: ShipmentShipper | None = None
    recipient_organization: ShipmentRecipientOrganization | None = None
    association_profile: AssociationProfile | None = None


def _scope_from_grant(grant: PortalAccessGrant) -> PortalScope:
    return PortalScope(
        source=PORTAL_SCOPE_SOURCE_GRANT,
        role=grant.role,
        grant=grant,
        shipper=grant.shipper,
        recipient_organization=grant.recipient_organization,
    )


def _scope_from_association_profile(profile: AssociationProfile) -> PortalScope:
    shipper = (
        ShipmentShipper.objects.filter(
            organization=profile.contact,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    return PortalScope(
        source=PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION,
        role=PortalAccessRole.SHIPPER_ADMIN,
        shipper=shipper,
        association_profile=profile,
    )


def list_user_portal_scopes(user) -> list[PortalScope]:
    if not user or not getattr(user, "is_authenticated", False):
        return []

    grants = list(
        PortalAccessGrant.objects.filter(user=user, is_active=True)
        .select_related(
            "shipper__organization",
            "recipient_organization__organization",
            "recipient_organization__destination",
        )
        .order_by("id")
    )
    if grants:
        return [_scope_from_grant(grant) for grant in grants]

    profile = get_association_profile(user)
    if profile is None:
        return []
    return [_scope_from_association_profile(profile)]


def activate_portal_scope(request, *, scope: PortalScope) -> None:
    if scope.grant is not None:
        request.session[ACTIVE_PORTAL_SCOPE_SESSION_KEY] = {
            "source": PORTAL_SCOPE_SOURCE_GRANT,
            "grant_id": scope.grant.id,
        }
    elif scope.association_profile is not None:
        request.session[ACTIVE_PORTAL_SCOPE_SESSION_KEY] = {
            "source": PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION,
            "association_profile_id": scope.association_profile.id,
        }
    else:
        request.session.pop(ACTIVE_PORTAL_SCOPE_SESSION_KEY, None)


def resolve_active_portal_scope(request) -> PortalScope | None:
    if not request or not getattr(request, "user", None):
        return None

    payload = request.session.get(ACTIVE_PORTAL_SCOPE_SESSION_KEY) or {}
    source = payload.get("source")

    if source == PORTAL_SCOPE_SOURCE_GRANT:
        grant_id = payload.get("grant_id")
        if not grant_id:
            return None
        grant = (
            PortalAccessGrant.objects.filter(
                id=grant_id,
                user=request.user,
                is_active=True,
            )
            .select_related(
                "shipper__organization",
                "recipient_organization__organization",
                "recipient_organization__destination",
            )
            .first()
        )
        if grant is None:
            return None
        return _scope_from_grant(grant)

    if source == PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION:
        profile = get_association_profile(request.user)
        if profile is None:
            return None
        expected_id = payload.get("association_profile_id")
        if expected_id and profile.id != expected_id:
            return None
        return _scope_from_association_profile(profile)

    scopes = list_user_portal_scopes(request.user)
    if len(scopes) == 1:
        return scopes[0]
    return None
