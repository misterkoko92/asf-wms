from decimal import ROUND_HALF_UP
from pathlib import Path

from django.core.files import File

from .import_services_categories import build_category_path
from .import_services_common import _row_is_empty
from .import_services_locations import get_or_create_location
from .import_services_tags import build_product_tags
from .import_utils import get_value, parse_bool, parse_decimal, parse_int, parse_str
from .services import StockError, receive_stock
from .text_utils import normalize_title, normalize_upper
from .models import Product, RackColor

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


def import_products_single(row, user=None):
    product, _, _ = import_product_row(row, user=user)
    return product
