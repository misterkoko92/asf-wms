from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from contacts.models import Contact

from .admin_contacts_duplicate_detection import (
    find_similar_destinations,
    normalize_match_value,
)
from .models import Destination


def _resolve_correspondent_contact(value):
    if isinstance(value, Contact):
        return value
    if not value:
        return None
    return Contact.objects.filter(pk=value, is_active=True).first()


def _is_hard_destination_conflict(
    *, city: str, iata_code: str, country: str, exclude_id=None
) -> bool:
    normalized_city = normalize_match_value(city)
    normalized_country = normalize_match_value(country)
    normalized_iata = (iata_code or "").strip().upper()
    queryset = Destination.objects.filter(is_active=True)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    for destination in queryset.order_by("id"):
        if normalized_iata and destination.iata_code == normalized_iata:
            return True
        if (
            normalize_match_value(destination.city) == normalized_city
            and normalize_match_value(destination.country) == normalized_country
        ):
            return True
    return False


def build_destination_duplicate_candidates(cleaned_data, *, exclude_destination_id=None):
    return find_similar_destinations(
        city=cleaned_data.get("city", ""),
        iata_code=cleaned_data.get("iata_code", ""),
        country=cleaned_data.get("country", ""),
        exclude_destination_id=exclude_destination_id,
    )


def _apply_destination_fields(destination, *, data, overwrite: bool):
    updated_fields = []
    for field_name in ("city", "iata_code", "country"):
        incoming = (data.get(field_name) or "").strip()
        current = getattr(destination, field_name)
        if overwrite:
            if incoming and current != incoming:
                setattr(destination, field_name, incoming)
                updated_fields.append(field_name)
        elif not current and incoming:
            setattr(destination, field_name, incoming)
            updated_fields.append(field_name)

    correspondent_contact = _resolve_correspondent_contact(data.get("correspondent_contact_id"))
    if overwrite:
        if (
            correspondent_contact
            and destination.correspondent_contact_id != correspondent_contact.id
        ):
            destination.correspondent_contact = correspondent_contact
            updated_fields.append("correspondent_contact")
    elif destination.correspondent_contact_id is None and correspondent_contact is not None:
        destination.correspondent_contact = correspondent_contact
        updated_fields.append("correspondent_contact")

    is_active = bool(data.get("is_active"))
    if overwrite:
        if destination.is_active != is_active:
            destination.is_active = is_active
            updated_fields.append("is_active")
    elif is_active and not destination.is_active:
        destination.is_active = True
        updated_fields.append("is_active")

    if updated_fields:
        destination.save(update_fields=updated_fields)
    return destination


def save_destination_from_form(cleaned_data, *, editing_destination=None):
    correspondent_contact = _resolve_correspondent_contact(
        cleaned_data.get("correspondent_contact_id")
    )
    if correspondent_contact is None:
        raise ValidationError("Le correspondant de destination est obligatoire.")

    duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
    duplicate_target_id = cleaned_data.get("duplicate_target_id")

    with transaction.atomic():
        if duplicate_action in {"replace", "merge"}:
            target = Destination.objects.filter(pk=duplicate_target_id).first()
            if target is None:
                raise ValidationError("Destination cible introuvable.")
            return _apply_destination_fields(
                target,
                data=cleaned_data,
                overwrite=duplicate_action == "replace",
            )

        if duplicate_action == "duplicate":
            if _is_hard_destination_conflict(
                city=cleaned_data.get("city", ""),
                iata_code=cleaned_data.get("iata_code", ""),
                country=cleaned_data.get("country", ""),
                exclude_id=getattr(editing_destination, "id", None),
            ):
                raise ValidationError(
                    "Un conflit exact empêche la duplication de cette destination."
                )

        if editing_destination is not None:
            return _apply_destination_fields(editing_destination, data=cleaned_data, overwrite=True)

        if duplicate_action != "duplicate" and _is_hard_destination_conflict(
            city=cleaned_data.get("city", ""),
            iata_code=cleaned_data.get("iata_code", ""),
            country=cleaned_data.get("country", ""),
        ):
            raise ValidationError("Cette destination existe déjà.")

        return Destination.objects.create(
            city=(cleaned_data.get("city") or "").strip(),
            iata_code=(cleaned_data.get("iata_code") or "").strip().upper(),
            country=(cleaned_data.get("country") or "").strip(),
            correspondent_contact=correspondent_contact,
            is_active=bool(cleaned_data.get("is_active")),
        )
