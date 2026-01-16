import re
from decimal import ROUND_HALF_UP
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.db.models import Q

from contacts.models import Contact, ContactAddress, ContactTag, ContactType

from .contact_filters import TAG_CORRESPONDENT
from .import_utils import (
    get_value,
    parse_bool,
    parse_decimal,
    parse_int,
    parse_str,
    parse_tokens,
)
from .text_utils import normalize_category_name, normalize_title, normalize_upper
from .services import StockError, receive_stock
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
        normalized = normalize_category_name(name, is_root=parent is None)
        category, _ = ProductCategory.objects.get_or_create(
            name=normalized, parent=parent
        )
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
    zone = normalize_upper(zone)
    aisle = normalize_upper(aisle)
    shelf = normalize_upper(shelf)
    location, _ = Location.objects.get_or_create(
        warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
    )
    return location


def extract_product_identity(row):
    sku = parse_str(get_value(row, "sku"))
    name = parse_str(get_value(row, "name", "nom", "nom_produit", "produit"))
    brand = parse_str(get_value(row, "brand", "marque"))
    if name:
        name = normalize_title(name)
    if brand:
        brand = normalize_upper(brand)
    return sku, name, brand


def find_product_matches(*, sku, name, brand):
    if sku:
        matches = list(Product.objects.filter(sku__iexact=sku))
        if matches:
            return matches, "sku"
    if name and brand:
        matches = list(
            Product.objects.filter(name__iexact=name, brand__iexact=brand)
        )
        if matches:
            return matches, "name_brand"
    return [], None


def resolve_photo_path(raw_value, base_dir: Path | None):
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    photo_path = Path(text).expanduser()
    if not photo_path.is_absolute():
        if base_dir is None:
            return None
        photo_path = base_dir / photo_path
    return photo_path


def attach_photo(product, photo_path: Path | None):
    if not photo_path:
        return False
    if not photo_path.exists():
        raise ValueError(f"Photo introuvable: {photo_path}")
    with photo_path.open("rb") as handle:
        product.photo.save(photo_path.name, File(handle), save=False)
    return True


def compute_volume(length_cm, width_cm, height_cm):
    if length_cm is None or width_cm is None or height_cm is None:
        return None
    volume = length_cm * width_cm * height_cm
    return int(volume.to_integral_value(rounding=ROUND_HALF_UP))


def _apply_quantity(*, product, quantity, location, user=None):
    if quantity is None:
        return
    if quantity <= 0:
        raise ValueError("Quantite invalide.")
    stock_location = location or product.default_location
    if stock_location is None:
        raise ValueError("Emplacement requis pour la quantite.")
    try:
        receive_stock(
            user=user,
            product=product,
            quantity=quantity,
            location=stock_location,
        )
    except StockError as exc:
        raise ValueError(str(exc)) from exc


def import_product_row(row, *, user=None, existing_product=None, base_dir: Path | None = None):
    name = parse_str(get_value(row, "name", "nom", "nom_produit", "produit"))
    if not name:
        raise ValueError("Nom produit requis.")
    name = normalize_title(name)
    sku = parse_str(get_value(row, "sku"))
    if existing_product is None and sku and Product.objects.filter(sku__iexact=sku).exists():
        raise ValueError("SKU deja utilise.")
    brand = parse_str(get_value(row, "brand", "marque"))
    if brand:
        brand = normalize_upper(brand)
    ean = parse_str(get_value(row, "ean"))
    barcode = parse_str(get_value(row, "barcode", "code_barre", "codebarre"))
    color = parse_str(get_value(row, "color", "couleur"))
    notes = parse_str(get_value(row, "notes", "note"))
    quantity = parse_int(get_value(row, "quantity", "quantite", "stock", "qty"))
    pu_ht = parse_decimal(get_value(row, "pu_ht", "price_ht", "unit_price_ht"))
    tva = parse_decimal(get_value(row, "tva", "vat"))

    category_parts = [
        parse_str(get_value(row, "category_l1", "categorie_l1", "category_1", "categorie_1")),
        parse_str(get_value(row, "category_l2", "categorie_l2", "category_2", "categorie_2")),
        parse_str(get_value(row, "category_l3", "categorie_l3", "category_3", "categorie_3")),
        parse_str(get_value(row, "category_l4", "categorie_l4", "category_4", "categorie_4")),
    ]
    category_provided = any(category_parts)
    category = build_category_path([p for p in category_parts if p])

    tags_raw = parse_str(get_value(row, "tags", "etiquettes", "etiquette"))
    tags_provided = tags_raw is not None
    tags = build_product_tags(tags_raw) if tags_raw else []

    warehouse_name = parse_str(get_value(row, "warehouse", "entrepot"))
    zone = parse_str(get_value(row, "zone", "rack"))
    aisle = parse_str(get_value(row, "aisle", "etagere"))
    shelf = parse_str(get_value(row, "shelf", "bac", "emplacement"))
    default_location = get_or_create_location(warehouse_name, zone, aisle, shelf)
    location_provided = default_location is not None
    rack_color = parse_str(get_value(row, "rack_color", "couleur_rack", "color_rack"))
    if rack_color and default_location is not None:
        RackColor.objects.update_or_create(
            warehouse=default_location.warehouse,
            zone=default_location.zone,
            defaults={"color": rack_color},
        )

    photo_path = resolve_photo_path(
        get_value(row, "photo", "image", "photo_path", "image_path"),
        base_dir,
    )
    length_cm = parse_decimal(get_value(row, "length_cm", "longueur_cm"))
    width_cm = parse_decimal(get_value(row, "width_cm", "largeur_cm"))
    height_cm = parse_decimal(get_value(row, "height_cm", "hauteur_cm"))
    weight_g = parse_int(get_value(row, "weight_g", "poids_g"))
    volume_cm3 = parse_int(get_value(row, "volume_cm3", "volume_cm3"))
    if volume_cm3 is None:
        volume_cm3 = compute_volume(length_cm, width_cm, height_cm)

    storage_conditions = parse_str(
        get_value(row, "storage_conditions", "conditions_stockage")
    )
    perishable = parse_bool(get_value(row, "perishable", "perissable"))
    quarantine_default = parse_bool(
        get_value(row, "quarantine_default", "quarantaine_defaut")
    )

    warnings = []
    if existing_product is None:
        product = Product(sku=sku or "", name=name)
        if category is not None:
            product.category = category
        if ean is not None:
            product.ean = ean
        if barcode is not None:
            product.barcode = barcode
        if brand is not None:
            product.brand = brand
        if color is not None:
            product.color = color
        if pu_ht is not None:
            product.pu_ht = pu_ht
        if tva is not None:
            product.tva = tva
        if location_provided:
            product.default_location = default_location
        if length_cm is not None:
            product.length_cm = length_cm
        if width_cm is not None:
            product.width_cm = width_cm
        if height_cm is not None:
            product.height_cm = height_cm
        if weight_g is not None:
            product.weight_g = weight_g
        if volume_cm3 is not None:
            product.volume_cm3 = volume_cm3
        if storage_conditions is not None:
            product.storage_conditions = storage_conditions
        if perishable is not None:
            product.perishable = perishable
        if quarantine_default is not None:
            product.quarantine_default = quarantine_default
        if notes is not None:
            product.notes = notes
        attach_photo(product, photo_path)
        product.save()
        if tags_provided:
            product.tags.set(tags)
        _apply_quantity(
            product=product,
            quantity=quantity,
            location=default_location if location_provided else None,
            user=user,
        )
        return product, True, warnings

    updates = {"name": name}
    if category_provided:
        updates["category"] = category
    if ean is not None:
        updates["ean"] = ean
    if barcode is not None:
        updates["barcode"] = barcode
    if brand is not None:
        updates["brand"] = brand
    if color is not None:
        updates["color"] = color
    if pu_ht is not None:
        updates["pu_ht"] = pu_ht
    if tva is not None:
        updates["tva"] = tva
    if location_provided:
        updates["default_location"] = default_location
    if length_cm is not None:
        updates["length_cm"] = length_cm
    if width_cm is not None:
        updates["width_cm"] = width_cm
    if height_cm is not None:
        updates["height_cm"] = height_cm
    if weight_g is not None:
        updates["weight_g"] = weight_g
    if volume_cm3 is not None:
        updates["volume_cm3"] = volume_cm3
    if storage_conditions is not None:
        updates["storage_conditions"] = storage_conditions
    if perishable is not None:
        updates["perishable"] = perishable
    if quarantine_default is not None:
        updates["quarantine_default"] = quarantine_default
    if notes is not None:
        updates["notes"] = notes

    photo_updated = attach_photo(existing_product, photo_path)
    if photo_updated:
        updates["photo"] = existing_product.photo

    if updates:
        for field, value in updates.items():
            setattr(existing_product, field, value)
        existing_product.save(update_fields=list(updates.keys()))
    if tags_provided:
        existing_product.tags.set(tags)
    _apply_quantity(
        product=existing_product,
        quantity=quantity,
        location=default_location if location_provided else None,
        user=user,
    )
    return existing_product, False, warnings


def import_products_rows(
    rows,
    *,
    user=None,
    decisions=None,
    base_dir: Path | None = None,
    start_index: int = 2,
):
    created = 0
    updated = 0
    errors = []
    warnings = []
    decisions = decisions or {}
    for index, row in enumerate(rows, start=start_index):
        if _row_is_empty(row):
            continue
        decision = decisions.get(index)
        existing_product = None
        if decision and decision.get("action") == "update":
            match_id = decision.get("product_id")
            existing_product = Product.objects.filter(pk=match_id).first()
            if existing_product is None:
                errors.append(f"Ligne {index}: produit cible introuvable.")
                continue
        if decision and decision.get("action") == "create":
            sku = parse_str(get_value(row, "sku"))
            if sku and Product.objects.filter(sku__iexact=sku).exists():
                row = dict(row)
                row["sku"] = ""
                warnings.append(
                    f"Ligne {index}: SKU {sku} deja utilise, SKU auto-genere."
                )
        try:
            product, was_created, row_warnings = import_product_row(
                row,
                user=user,
                existing_product=existing_product,
                base_dir=base_dir,
            )
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
            continue
        warnings.extend(row_warnings)
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated, errors, warnings


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
            zone = normalize_upper(zone)
            aisle = normalize_upper(aisle)
            shelf = normalize_upper(shelf)
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
            name = normalize_category_name(name, is_root=parent_name is None)
            parent = None
            if parent_name:
                parent_name = normalize_category_name(parent_name, is_root=True)
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
    product, _, _ = import_product_row(row, user=user)
    return product
