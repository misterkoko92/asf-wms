from __future__ import annotations

from collections.abc import Iterable

from contacts.models import Contact

from .models import (
    Destination,
    DestinationCorrespondentDefault,
    DestinationCorrespondentOverride,
)


def resolve_correspondent_organizations(
    *,
    destination: Destination | None,
    shipper_org: Contact | None = None,
    recipient_org: Contact | None = None,
) -> list[Contact]:
    if destination is None:
        return []

    resolved_by_id: dict[int, Contact] = {}

    defaults = DestinationCorrespondentDefault.objects.filter(
        destination=destination,
        is_active=True,
    ).select_related("correspondent_org")
    for default in defaults:
        resolved_by_id.setdefault(default.correspondent_org_id, default.correspondent_org)

    overrides = DestinationCorrespondentOverride.objects.filter(
        destination=destination,
        is_active=True,
    ).select_related("correspondent_org", "shipper_org", "recipient_org")
    for override in overrides:
        if override.matches(shipper_org=shipper_org, recipient_org=recipient_org):
            resolved_by_id.setdefault(override.correspondent_org_id, override.correspondent_org)

    return list(resolved_by_id.values())


def build_coordination_message_for_correspondent(
    *,
    current_correspondent: Contact,
    all_correspondents: Iterable[Contact],
) -> str:
    other_correspondents = [
        org for org in all_correspondents if org.id and org.id != current_correspondent.id
    ]
    if not other_correspondents:
        return ""

    lines = [
        "D'autres correspondants sont impliques sur cette escale.",
        "Merci de vous coordonner directement avec :",
    ]
    for org in other_correspondents:
        email = (org.email or "").strip() or "email non renseigne"
        lines.append(f"- {org.name} ({email})")
    return "\n".join(lines)
