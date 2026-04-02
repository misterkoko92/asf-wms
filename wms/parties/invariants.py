from __future__ import annotations

from wms.models import ShipmentRecipientOrganization


def recipient_organization_matches_destination(recipient_organization, destination) -> bool:
    if recipient_organization is None or destination is None:
        return False
    return recipient_organization.destination_id == getattr(destination, "id", None)


def organization_can_be_reused_for_destination(organization, destination) -> bool:
    if organization is None:
        return False
    existing = ShipmentRecipientOrganization.objects.filter(organization=organization).first()
    return existing is None or recipient_organization_matches_destination(existing, destination)


def recipient_organizations_share_destination(left, right) -> bool:
    if left is None or right is None:
        return False
    return left.destination_id == right.destination_id
