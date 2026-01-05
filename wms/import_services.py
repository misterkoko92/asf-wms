import re

from django.contrib.auth import get_user_model

from contacts.models import Contact, ContactAddress, ContactTag, ContactType

from .import_utils import get_value, parse_bool, parse_str, parse_tokens
from .models import (
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
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            name = parse_str(get_value(row, "name", "nom"))
            if not name:
                raise ValueError("Nom contact requis.")
            raw_type = parse_str(get_value(row, "contact_type", "type"))
            contact_type = ContactType.ORGANIZATION
            if raw_type:
                normalized = raw_type.strip().lower()
                if normalized.startswith("p"):
                    contact_type = ContactType.PERSON
            email = parse_str(get_value(row, "email"))
            phone = parse_str(get_value(row, "phone", "telephone"))
            notes = parse_str(get_value(row, "notes", "note"))
            is_active = parse_bool(get_value(row, "is_active", "actif"))
            contact, was_created = Contact.objects.get_or_create(name=name)
            updates = {}
            if contact.contact_type != contact_type:
                updates["contact_type"] = contact_type
            if email is not None:
                updates["email"] = email
            if phone is not None:
                updates["phone"] = phone
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
            if tags:
                contact.tags.set(tags)

            address_line1 = parse_str(get_value(row, "address_line1", "adresse"))
            if address_line1:
                ContactAddress.objects.create(
                    contact=contact,
                    label=parse_str(get_value(row, "address_label", "label")) or "",
                    address_line1=address_line1,
                    address_line2=parse_str(get_value(row, "address_line2")) or "",
                    postal_code=parse_str(get_value(row, "postal_code", "code_postal"))
                    or "",
                    city=parse_str(get_value(row, "city", "ville")) or "",
                    region=parse_str(get_value(row, "region")) or "",
                    country=parse_str(get_value(row, "country", "pays")) or "France",
                    phone=parse_str(get_value(row, "address_phone")) or "",
                    email=parse_str(get_value(row, "address_email")) or "",
                    is_default=parse_bool(get_value(row, "address_is_default", "default"))
                    or False,
                    notes=parse_str(get_value(row, "address_notes")) or "",
                )
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


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
                user.set_password(default_password)
                user.save(update_fields=["password"])
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


def import_products_single(row):
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
    return product
