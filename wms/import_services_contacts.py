import re

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from contacts.rules import ensure_default_shipper_for_recipient
from contacts.tagging import TAG_SHIPPER

from .import_services_common import _row_is_empty
from .import_services_destinations import _get_or_create_destination
from .import_services_tags import build_contact_tags
from .import_utils import get_value, parse_bool, parse_str


DESTINATION_KEYS = ("destination", "dest", "destination_name")
DESTINATIONS_KEYS = ("destinations", "destination_scope", "destinations_scope")
LINKED_SHIPPERS_KEYS = ("linked_shippers", "expediteurs_lies", "expediteurs_lie")


def _row_has_any_key(row, *keys):
    return any(key in row for key in keys)


def _parse_multi_values(value):
    if value is None:
        return []
    parts = [
        token.strip()
        for token in re.split(r"[|\n]", str(value))
    ]
    return [part for part in parts if part]


def _resolve_destinations_for_row(
    *,
    row,
    contact,
    tags,
    fallback_city,
    fallback_country,
):
    if not _row_has_any_key(row, *DESTINATION_KEYS, *DESTINATIONS_KEYS):
        return None

    tokens = []
    for key in (*DESTINATIONS_KEYS, *DESTINATION_KEYS):
        if key not in row:
            continue
        tokens.extend(_parse_multi_values(row.get(key)))
    if not tokens:
        return []

    destinations = []
    seen = set()
    for token in tokens:
        destination = _get_or_create_destination(
            token,
            contact=contact,
            tags=tags,
            fallback_city=fallback_city,
            fallback_country=fallback_country,
        )
        if destination and destination.pk not in seen:
            seen.add(destination.pk)
            destinations.append(destination)
    return destinations


def _resolve_linked_shippers_for_row(*, row, warnings, index):
    if not _row_has_any_key(row, *LINKED_SHIPPERS_KEYS):
        return None

    names = []
    for key in LINKED_SHIPPERS_KEYS:
        if key not in row:
            continue
        names.extend(_parse_multi_values(row.get(key)))
    if not names:
        return []

    canonical_shipper_tag_name = TAG_SHIPPER[0]
    shipper_tag, _ = ContactTag.objects.get_or_create(name=canonical_shipper_tag_name)
    linked_contacts = []
    seen = set()
    for name in names:
        linked_shipper = Contact.objects.filter(name__iexact=name).first()
        if not linked_shipper:
            linked_shipper = Contact.objects.create(
                name=name,
                contact_type=ContactType.ORGANIZATION,
                notes="créé automatiquement depuis linked_shippers",
            )
            warnings.append(
                f"Ligne {index}: expéditeur lié créé automatiquement ({name})."
            )
        if not linked_shipper.tags.filter(pk=shipper_tag.pk).exists():
            linked_shipper.tags.add(shipper_tag)
        if linked_shipper.pk not in seen:
            seen.add(linked_shipper.pk)
            linked_contacts.append(linked_shipper)
    return linked_contacts


def import_contacts(rows):
    created = 0
    updated = 0
    errors = []
    warnings = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            raw_type = parse_str(get_value(row, "contact_type", "type"))
            contact_type = ContactType.ORGANIZATION
            if raw_type:
                normalized = raw_type.strip().lower()
                if normalized.startswith(("p", "indiv", "pers")):
                    contact_type = ContactType.PERSON
                elif normalized.startswith(("o", "soc", "org")):
                    contact_type = ContactType.ORGANIZATION

            name = parse_str(get_value(row, "name", "nom", "raison_sociale"))
            first_name = parse_str(get_value(row, "first_name", "prenom", "prénom"))
            last_name = parse_str(get_value(row, "last_name", "nom_personne", "nom_famille"))
            title = parse_str(get_value(row, "title", "titre"))
            role = parse_str(get_value(row, "role", "fonction"))
            email = parse_str(get_value(row, "email", "mail"))
            email2 = parse_str(get_value(row, "email2", "mail2"))
            phone = parse_str(get_value(row, "phone", "telephone", "tel"))
            phone2 = parse_str(get_value(row, "phone2", "telephone2", "tel2"))
            notes = parse_str(get_value(row, "notes", "note"))
            is_active = parse_bool(get_value(row, "is_active", "actif"))
            use_org_address = parse_bool(
                get_value(row, "use_organization_address", "adresse_societe")
            )
            siret = parse_str(get_value(row, "siret"))
            vat_number = parse_str(get_value(row, "vat_number", "tva", "vat"))
            legal_registration_number = parse_str(
                get_value(row, "legal_registration_number", "numero_enregistrement_legal")
            )
            asf_id = parse_str(get_value(row, "asf_id", "id_asf"))
            address_city = parse_str(get_value(row, "city", "ville"))
            address_country = parse_str(get_value(row, "country", "pays"))

            if contact_type == ContactType.PERSON and not last_name and name and first_name:
                last_name = name
                name = None
            if contact_type == ContactType.ORGANIZATION and not name and last_name:
                name = last_name
            if contact_type == ContactType.ORGANIZATION and not name:
                name = parse_str(get_value(row, "societe", "company", "organisation"))

            if not name and contact_type == ContactType.ORGANIZATION:
                raise ValueError("Nom contact requis.")
            if contact_type == ContactType.PERSON and not (name or first_name or last_name):
                raise ValueError("Nom ou prenom requis pour un individu.")

            contact_lookup = name or " ".join(
                part for part in [first_name, last_name] if part
            ).strip()
            if not contact_lookup:
                raise ValueError("Nom contact requis.")
            contact = (
                Contact.objects.filter(name__iexact=contact_lookup, contact_type=contact_type)
                .first()
            )
            was_created = False
            if not contact:
                contact = Contact.objects.create(
                    name=contact_lookup,
                    contact_type=contact_type,
                )
                was_created = True
            updates = {}
            if contact.contact_type != contact_type:
                updates["contact_type"] = contact_type
            if title is not None:
                updates["title"] = title
            if first_name is not None:
                updates["first_name"] = first_name
            if last_name is not None:
                updates["last_name"] = last_name
            if name is not None:
                updates["name"] = name
            if role is not None:
                updates["role"] = role
            if email is not None:
                updates["email"] = email
            if email2 is not None:
                updates["email2"] = email2
            if phone is not None:
                updates["phone"] = phone
            if phone2 is not None:
                updates["phone2"] = phone2
            if use_org_address is not None:
                updates["use_organization_address"] = use_org_address
            if siret is not None:
                updates["siret"] = siret
            if vat_number is not None:
                updates["vat_number"] = vat_number
            if legal_registration_number is not None:
                updates["legal_registration_number"] = legal_registration_number
            if asf_id is not None and not contact.asf_id:
                updates["asf_id"] = asf_id
            if notes is not None:
                updates["notes"] = notes
            if is_active is not None:
                updates["is_active"] = is_active
            if updates:
                for field, value in updates.items():
                    setattr(contact, field, value)
                contact.save(update_fields=list(updates.keys()))
                updated += 1 if not was_created else 0
            if was_created:
                created += 1

            tags = build_contact_tags(get_value(row, "tags", "etiquettes"))
            if (
                contact.contact_type == ContactType.ORGANIZATION
                and not tags
                and not contact.tags.exists()
            ):
                raise ValueError("Tag requis pour une societe.")
            if tags:
                if was_created:
                    contact.tags.set(tags)
                else:
                    existing_tag_names = set(
                        contact.tags.values_list("name", flat=True)
                    )
                    new_tags = [tag for tag in tags if tag.name not in existing_tag_names]
                    if new_tags:
                        contact.tags.add(*new_tags)
                        warnings.append(
                            "Ligne {}: tags fusionnés (ajoutés: {}).".format(
                                index, ", ".join(sorted(tag.name for tag in new_tags))
                            )
                        )
                    else:
                        contact.tags.add(*tags)

            if contact_type == ContactType.PERSON:
                organization_name = parse_str(
                    get_value(row, "organization", "societe", "company", "organisation")
                )
                if use_org_address and not (organization_name or contact.organization):
                    raise ValueError("Société requise pour utiliser l'adresse.")
                if organization_name:
                    organization = (
                        Contact.objects.filter(
                            name__iexact=organization_name,
                            contact_type=ContactType.ORGANIZATION,
                        ).first()
                    )
                    if not organization:
                        organization = Contact.objects.create(
                            name=organization_name,
                            contact_type=ContactType.ORGANIZATION,
                            notes="créé à l'ajout de Contact",
                        )
                    contact.organization = organization
                    contact.save(update_fields=["organization"])

            destinations = _resolve_destinations_for_row(
                row=row,
                contact=contact,
                tags=tags,
                fallback_city=address_city,
                fallback_country=address_country,
            )
            if destinations is not None:
                contact.destinations.set(destinations)
                legacy_destination = destinations[0] if len(destinations) == 1 else None
                legacy_destination_id = legacy_destination.id if legacy_destination else None
                if contact.destination_id != legacy_destination_id:
                    contact.destination = legacy_destination
                    contact.save(update_fields=["destination"])

            linked_shippers = _resolve_linked_shippers_for_row(
                row=row,
                warnings=warnings,
                index=index,
            )
            if linked_shippers is not None:
                contact.linked_shippers.set(linked_shippers)
            ensure_default_shipper_for_recipient(
                contact,
                tags=tags if tags else None,
            )

            address_line1 = parse_str(get_value(row, "address_line1", "adresse"))
            if address_line1 and not contact.use_organization_address:
                address_label = parse_str(get_value(row, "address_label", "label")) or ""
                address_line2 = parse_str(get_value(row, "address_line2")) or ""
                postal_code = (
                    parse_str(get_value(row, "postal_code", "code_postal")) or ""
                )
                city = parse_str(get_value(row, "city", "ville")) or ""
                region = parse_str(get_value(row, "region")) or ""
                country = parse_str(get_value(row, "country", "pays")) or "France"
                phone = parse_str(get_value(row, "address_phone")) or ""
                email = parse_str(get_value(row, "address_email")) or ""
                is_default = parse_bool(
                    get_value(row, "address_is_default", "default")
                )
                notes = parse_str(get_value(row, "address_notes")) or ""
                existing_address = ContactAddress.objects.filter(
                    contact=contact,
                    address_line1__iexact=address_line1,
                    address_line2__iexact=address_line2,
                    postal_code__iexact=postal_code,
                    city__iexact=city,
                    country__iexact=country,
                ).first()
                if existing_address:
                    updates = {}
                    if address_label and existing_address.label != address_label:
                        updates["label"] = address_label
                    if region and existing_address.region != region:
                        updates["region"] = region
                    if phone and existing_address.phone != phone:
                        updates["phone"] = phone
                    if email and existing_address.email != email:
                        updates["email"] = email
                    if notes and existing_address.notes != notes:
                        updates["notes"] = notes
                    if is_default is not None and existing_address.is_default != is_default:
                        updates["is_default"] = is_default
                    if updates:
                        for field, value in updates.items():
                            setattr(existing_address, field, value)
                        existing_address.save(update_fields=list(updates.keys()))
                else:
                    ContactAddress.objects.create(
                        contact=contact,
                        label=address_label,
                        address_line1=address_line1,
                        address_line2=address_line2,
                        postal_code=postal_code,
                        city=city,
                        region=region,
                        country=country,
                        phone=phone,
                        email=email,
                        is_default=is_default or False,
                        notes=notes,
                    )
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors, warnings
