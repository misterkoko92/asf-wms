import re

from django.contrib.auth import get_user_model
from django.db.models import Q

from contacts.models import Contact, ContactAddress, ContactTag, ContactType

from .contact_filters import TAG_CORRESPONDENT
from .import_utils import get_value, parse_bool, parse_int, parse_str, parse_tokens
from .services import receive_stock
from .models import (
    Destination,
    Location,
    Product,
    ProductCategory,
    ProductTag,
    RackColor,
    Warehouse,
)


def _row_is_empty(row):
    for value in row.values():
        if value is None:
            continue
        if str(value).strip():
            return False
    return True


def build_category_path(parts):
    parent = None
    for name in parts:
        if not name:
            continue
        category, _ = ProductCategory.objects.get_or_create(name=name, parent=parent)
        parent = category
    return parent


def build_product_tags(raw_value):
    names = parse_tokens(raw_value)
    tags = []
    for name in names:
        tag, _ = ProductTag.objects.get_or_create(name=name)
        tags.append(tag)
    return tags


def build_contact_tags(raw_value):
    names = parse_tokens(raw_value)
    tags = []
    for name in names:
        tag, _ = ContactTag.objects.get_or_create(name=name)
        tags.append(tag)
    return tags


DESTINATION_LABEL_RE = re.compile(
    r"^(?P<city>.+?)\s*\((?P<iata>[^)]+)\)\s*(?:-\s*(?P<country>.+))?$"
)


def _parse_destination_label(value):
    if value is None:
        return None, None, None
    text = str(value).strip()
    if not text:
        return None, None, None
    match = DESTINATION_LABEL_RE.match(text)
    if match:
        city = (match.group("city") or "").strip()
        iata = (match.group("iata") or "").strip()
        country = (match.group("country") or "").strip()
        return city or None, iata or None, country or None
    if " - " in text:
        parts = [part.strip() for part in text.split(" - ") if part.strip()]
        if len(parts) >= 2:
            return parts[0], None, parts[1]
    if re.fullmatch(r"[A-Za-z0-9]{2,10}", text):
        return None, text, None
    return text, None, None


def _generate_destination_code(base):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", base or "").upper()
    cleaned = cleaned[:10]
    if not cleaned:
        cleaned = "DEST"
    candidate = cleaned
    suffix = 1
    while Destination.objects.filter(iata_code__iexact=candidate).exists():
        suffix += 1
        trimmed = cleaned[: max(1, 10 - len(str(suffix)))]
        candidate = f"{trimmed}{suffix}"
    return candidate


def _tags_include_correspondent(tags):
    if not tags:
        return False
    tag_names = {tag.name.strip().lower() for tag in tags if tag.name}
    return any(name in tag_names for name in TAG_CORRESPONDENT)


def _select_default_correspondent():
    tag_query = Q()
    for name in TAG_CORRESPONDENT:
        tag_query |= Q(tags__name__iexact=name)
    correspondent = (
        Contact.objects.filter(is_active=True).filter(tag_query).distinct().first()
    )
    if correspondent:
        return correspondent
    tag, _ = ContactTag.objects.get_or_create(name=TAG_CORRESPONDENT[0])
    correspondent, _ = Contact.objects.get_or_create(
        name="Correspondant par defaut",
        contact_type=ContactType.ORGANIZATION,
        defaults={"notes": "cree a l'import destination"},
    )
    correspondent.tags.add(tag)
    return correspondent


def _get_or_create_destination(
    raw_value,
    *,
    contact=None,
    tags=None,
    fallback_city=None,
    fallback_country=None,
):
    if not raw_value:
        return None
    city, iata_code, country = _parse_destination_label(raw_value)
    destination = None
    if iata_code:
        destination = Destination.objects.filter(iata_code__iexact=iata_code).first()
    if destination is None and city:
        search_country = country or fallback_country
        query = Destination.objects.filter(city__iexact=city)
        if search_country:
            query = query.filter(country__iexact=search_country)
            destination = query.first()
        elif query.count() == 1:
            destination = query.first()
    if destination:
        return destination
    resolved_city = city or fallback_city or str(raw_value).strip()
    resolved_country = country or fallback_country or "France"
    existing = Destination.objects.filter(
        city__iexact=resolved_city, country__iexact=resolved_country
    ).first()
    if existing:
        return existing
    resolved_iata = iata_code or _generate_destination_code(resolved_city)
    if contact and _tags_include_correspondent(tags or contact.tags.all()):
        correspondent = contact
    else:
        correspondent = _select_default_correspondent()
    return Destination.objects.create(
        city=resolved_city,
        iata_code=resolved_iata,
        country=resolved_country,
        correspondent_contact=correspondent,
    )


def get_or_create_location(warehouse_name, zone, aisle, shelf):
    if not all([warehouse_name, zone, aisle, shelf]):
        return None
    warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
    location, _ = Location.objects.get_or_create(
        warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
    )
    return location


def import_locations(rows):
    created = 0
    updated = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            warehouse_name = parse_str(get_value(row, "warehouse", "entrepot"))
            zone = parse_str(get_value(row, "zone", "rack"))
            aisle = parse_str(get_value(row, "aisle", "etagere"))
            shelf = parse_str(get_value(row, "shelf", "bac"))
            notes = parse_str(get_value(row, "notes", "note"))
            rack_color = parse_str(get_value(row, "rack_color", "couleur_rack"))
            if not all([warehouse_name, zone, aisle, shelf]):
                raise ValueError("Champs requis: entrepot, rack, etagere, bac.")
            warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
            location, was_created = Location.objects.get_or_create(
                warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
            )
            if notes is not None and location.notes != notes:
                location.notes = notes
                location.save(update_fields=["notes"])
                updated += 1 if not was_created else 0
            if was_created:
                created += 1
            if rack_color:
                RackColor.objects.update_or_create(
                    warehouse=warehouse,
                    zone=zone,
                    defaults={"color": rack_color},
                )
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


def import_categories(rows):
    created = 0
    updated = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            path = parse_str(get_value(row, "path", "chemin"))
            if path:
                parts = [p.strip() for p in re.split(r"[>/]", path) if p.strip()]
                if not parts:
                    raise ValueError("Chemin categorie vide.")
                build_category_path(parts)
                created += 1
                continue
            name = parse_str(get_value(row, "name", "categorie", "category"))
            parent_name = parse_str(get_value(row, "parent", "parent_name"))
            if not name:
                raise ValueError("Nom categorie requis.")
            parent = None
            if parent_name:
                parent, _ = ProductCategory.objects.get_or_create(
                    name=parent_name, parent=None
                )
            ProductCategory.objects.get_or_create(name=name, parent=parent)
            created += 1
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


def import_warehouses(rows):
    created = 0
    updated = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            name = parse_str(get_value(row, "name", "warehouse", "entrepot"))
            code = parse_str(get_value(row, "code"))
            if not name:
                raise ValueError("Nom entrepot requis.")
            warehouse, was_created = Warehouse.objects.get_or_create(
                name=name, defaults={"code": code or ""}
            )
            if not was_created and code is not None and warehouse.code != code:
                warehouse.code = code
                warehouse.save(update_fields=["code"])
                updated += 1
            if was_created:
                created += 1
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


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
            destination_value = parse_str(
                get_value(row, "destination", "dest", "destination_name")
            )
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
                            "Ligne {}: tags fusionnes (ajoutes: {}).".format(
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
                    raise ValueError("Societe requise pour utiliser l'adresse.")
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
                            notes="cree a l'ajout de Contact",
                        )
                    contact.organization = organization
                    contact.save(update_fields=["organization"])

            if destination_value is not None:
                destination = _get_or_create_destination(
                    destination_value,
                    contact=contact,
                    tags=tags,
                    fallback_city=address_city,
                    fallback_country=address_country,
                )
                if destination and contact.destination_id != destination.id:
                    contact.destination = destination
                    contact.save(update_fields=["destination"])

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


def import_users(rows, default_password):
    created = 0
    updated = 0
    errors = []
    User = get_user_model()
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            username = parse_str(get_value(row, "username", "login"))
            if not username:
                raise ValueError("Username requis.")
            email = parse_str(get_value(row, "email"))
            first_name = parse_str(get_value(row, "first_name", "prenom"))
            last_name = parse_str(get_value(row, "last_name", "nom"))
            is_staff = parse_bool(get_value(row, "is_staff", "staff"))
            is_superuser = parse_bool(get_value(row, "is_superuser", "admin"))
            is_active = parse_bool(get_value(row, "is_active", "actif"))
            password = parse_str(get_value(row, "password", "mot_de_passe"))

            user, was_created = User.objects.get_or_create(username=username)
            updates = {}
            if email is not None:
                updates["email"] = email
            if first_name is not None:
                updates["first_name"] = first_name
            if last_name is not None:
                updates["last_name"] = last_name
            if is_staff is not None:
                updates["is_staff"] = is_staff
            if is_superuser is not None:
                updates["is_superuser"] = is_superuser
            if is_active is not None:
                updates["is_active"] = is_active
            if updates:
                for field, value in updates.items():
                    setattr(user, field, value)
                user.save(update_fields=list(updates.keys()))
                updated += 1 if not was_created else 0
            if was_created:
                created += 1
            if password:
                user.set_password(password)
                user.save(update_fields=["password"])
            elif was_created:
                if not default_password:
                    raise ValueError(
                        "Mot de passe requis (colonne password ou IMPORT_DEFAULT_PASSWORD)."
                    )
                user.set_password(default_password)
                user.save(update_fields=["password"])
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


def import_products_single(row, user=None):
    name = parse_str(get_value(row, "name", "nom", "nom_produit", "produit"))
    if not name:
        raise ValueError("Nom produit requis.")
    sku = parse_str(get_value(row, "sku"))
    if sku and Product.objects.filter(sku=sku).exists():
        raise ValueError("SKU deja utilise.")
    brand = parse_str(get_value(row, "brand", "marque"))
    barcode = parse_str(get_value(row, "barcode", "code_barre", "codebarre"))
    color = parse_str(get_value(row, "color", "couleur"))
    notes = parse_str(get_value(row, "notes", "note"))
    quantity = parse_int(get_value(row, "quantity", "quantite", "stock"))

    category_parts = [
        parse_str(get_value(row, "category_l1", "categorie_l1")),
        parse_str(get_value(row, "category_l2", "categorie_l2")),
        parse_str(get_value(row, "category_l3", "categorie_l3")),
        parse_str(get_value(row, "category_l4", "categorie_l4")),
    ]
    category = build_category_path([p for p in category_parts if p])
    tags = build_product_tags(get_value(row, "tags", "etiquettes", "etiquette"))

    warehouse_name = parse_str(get_value(row, "warehouse", "entrepot"))
    zone = parse_str(get_value(row, "zone", "rack"))
    aisle = parse_str(get_value(row, "aisle", "etagere"))
    shelf = parse_str(get_value(row, "shelf", "bac"))
    location = get_or_create_location(warehouse_name, zone, aisle, shelf)
    rack_color = parse_str(get_value(row, "rack_color", "couleur_rack"))
    if rack_color and location:
        RackColor.objects.update_or_create(
            warehouse=location.warehouse,
            zone=location.zone,
            defaults={"color": rack_color},
        )

    product = Product.objects.create(
        sku=sku or "",
        name=name,
        brand=brand or "",
        barcode=barcode or "",
        color=color or "",
        category=category,
        default_location=location,
        notes=notes or "",
    )
    if tags:
        product.tags.set(tags)
    if quantity is not None:
        if quantity <= 0:
            raise ValueError("Quantite invalide.")
        stock_location = location or product.default_location
        if stock_location is None:
            raise ValueError("Emplacement requis pour la quantite.")
        receive_stock(
            user=user,
            product=product,
            quantity=quantity,
            location=stock_location,
        )
    return product
