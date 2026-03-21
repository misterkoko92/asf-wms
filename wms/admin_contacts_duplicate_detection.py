from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from contacts.models import Contact, ContactType

from .models import Destination


def normalize_match_value(value: str) -> str:
    raw_value = (value or "").strip()
    if not raw_value:
        return ""
    normalized = unicodedata.normalize("NFKD", raw_value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


def is_fuzzy_match(*, source: str, candidate: str, threshold: float = 0.88) -> bool:
    if not source or not candidate:
        return False
    if source == candidate:
        return True
    if source in candidate or candidate in source:
        return True
    return SequenceMatcher(None, source, candidate).ratio() >= threshold


def _append_unique(matches, item, *, limit: int):
    if item in matches:
        return
    matches.append(item)
    if len(matches) > limit:
        del matches[limit:]


def find_similar_destinations(
    *,
    city: str,
    iata_code: str,
    country: str,
    exclude_destination_id: int | None = None,
    limit: int = 5,
):
    normalized_city = normalize_match_value(city)
    normalized_country = normalize_match_value(country)
    normalized_iata = (iata_code or "").strip().upper()
    matches = []

    queryset = Destination.objects.filter(is_active=True).select_related("correspondent_contact")
    if exclude_destination_id:
        queryset = queryset.exclude(pk=exclude_destination_id)

    for destination in queryset.order_by("city", "iata_code", "id"):
        if normalized_iata and destination.iata_code == normalized_iata:
            _append_unique(matches, destination, limit=limit)
            continue

        candidate_city = normalize_match_value(destination.city)
        candidate_country = normalize_match_value(destination.country)
        if normalized_city and normalized_country:
            if candidate_city == normalized_city and candidate_country == normalized_country:
                _append_unique(matches, destination, limit=limit)
                continue
            if candidate_country == normalized_country and is_fuzzy_match(
                source=normalized_city,
                candidate=candidate_city,
            ):
                _append_unique(matches, destination, limit=limit)
    return matches[:limit]


def find_similar_contacts(
    *,
    business_type: str,
    entity_type: str,
    organization_name: str = "",
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
    asf_id: str = "",
    exclude_contact_id: int | None = None,
    limit: int = 5,
):
    del business_type
    normalized_asf_id = (asf_id or "").strip()
    normalized_org = normalize_match_value(organization_name)
    normalized_first = normalize_match_value(first_name)
    normalized_last = normalize_match_value(last_name)
    normalized_email = (email or "").strip().casefold()
    normalized_phone = normalize_match_value(phone)
    normalized_person = normalize_match_value(
        " ".join(part for part in (first_name, last_name) if part)
    )

    queryset = Contact.objects.filter(is_active=True).select_related("organization")
    if exclude_contact_id:
        queryset = queryset.exclude(pk=exclude_contact_id)

    if normalized_asf_id:
        exact_matches = list(
            queryset.filter(asf_id=normalized_asf_id).order_by("name", "id")[:limit]
        )
        if exact_matches:
            return exact_matches

    matches = []
    desired_entity_type = entity_type or ContactType.ORGANIZATION
    if desired_entity_type == ContactType.ORGANIZATION:
        queryset = queryset.filter(contact_type=ContactType.ORGANIZATION)
        for contact in queryset.order_by("name", "id"):
            candidate_org = normalize_match_value(contact.name)
            if normalized_org and is_fuzzy_match(source=normalized_org, candidate=candidate_org):
                _append_unique(matches, contact, limit=limit)
                continue
            if normalized_email and (contact.email or "").strip().casefold() == normalized_email:
                _append_unique(matches, contact, limit=limit)
                continue
            if normalized_phone and normalize_match_value(contact.phone) == normalized_phone:
                _append_unique(matches, contact, limit=limit)
        return matches[:limit]

    queryset = queryset.filter(contact_type=ContactType.PERSON)
    for contact in queryset.order_by("name", "id"):
        candidate_person = normalize_match_value(
            " ".join(part for part in (contact.first_name, contact.last_name) if part)
            or contact.name
        )
        candidate_org = normalize_match_value(getattr(contact.organization, "name", ""))
        person_match = normalized_person and is_fuzzy_match(
            source=normalized_person,
            candidate=candidate_person,
        )
        organization_match = not normalized_org or (
            candidate_org and is_fuzzy_match(source=normalized_org, candidate=candidate_org)
        )
        if person_match and organization_match:
            _append_unique(matches, contact, limit=limit)
            continue
        if normalized_email and (contact.email or "").strip().casefold() == normalized_email:
            _append_unique(matches, contact, limit=limit)
            continue
        if normalized_phone and normalize_match_value(contact.phone) == normalized_phone:
            _append_unique(matches, contact, limit=limit)
            continue
        if (
            normalized_first
            and normalized_last
            and normalize_match_value(contact.first_name) == normalized_first
            and normalize_match_value(contact.last_name) == normalized_last
            and organization_match
        ):
            _append_unique(matches, contact, limit=limit)
    return matches[:limit]
