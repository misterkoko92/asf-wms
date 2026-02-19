from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction


def _normalize_destination_ids(destination_ids: Iterable[int | str | None]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for raw_value in destination_ids or []:
        try:
            value = int(raw_value) if raw_value is not None else 0
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    normalized.sort()
    return normalized


def contact_destination_ids(contact) -> list[int]:
    destination_ids = []
    destinations_relation = getattr(contact, "destinations", None)
    if destinations_relation is not None and hasattr(destinations_relation, "all"):
        destination_ids = _normalize_destination_ids(
            destination.id for destination in destinations_relation.all()
        )
    if destination_ids:
        return destination_ids
    legacy_destination_id = getattr(contact, "destination_id", None)
    return _normalize_destination_ids([legacy_destination_id])


def contact_primary_destination_id(contact):
    destination_ids = contact_destination_ids(contact)
    if len(destination_ids) == 1:
        return destination_ids[0]
    return None


def sync_contact_destination_scope(contact):
    if not getattr(contact, "pk", None):
        return []

    destination_ids = _normalize_destination_ids(
        contact.destinations.values_list("id", flat=True)
    )
    legacy_destination_id = getattr(contact, "destination_id", None)

    if not destination_ids and legacy_destination_id:
        destination_ids = [legacy_destination_id]
        contact.destinations.set(destination_ids)

    legacy_target = destination_ids[0] if len(destination_ids) == 1 else None
    if legacy_destination_id != legacy_target:
        contact.destination_id = legacy_target
        contact.save(update_fields=["destination"])

    return destination_ids


def set_contact_destination_scope(*, contact, destination_ids: Iterable[int | str | None]):
    if not getattr(contact, "pk", None):
        raise ValueError("Contact must be saved before assigning destination scope.")

    normalized_ids = _normalize_destination_ids(destination_ids)
    with transaction.atomic():
        contact.destinations.set(normalized_ids)
        legacy_target = normalized_ids[0] if len(normalized_ids) == 1 else None
        if contact.destination_id != legacy_target:
            contact.destination_id = legacy_target
            contact.save(update_fields=["destination"])
    return normalized_ids
