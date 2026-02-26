from decimal import ROUND_HALF_UP
from pathlib import Path
import unicodedata

from django.db import transaction
from django.core.files import File

from .import_services_categories import build_category_path
from .import_services_common import _row_is_empty
from .import_services_locations import get_or_create_location
from .import_services_tags import build_product_tags
from .import_utils import get_value, parse_bool, parse_decimal, parse_int, parse_str
from .services import StockError, adjust_stock, receive_stock
from .text_utils import normalize_title, normalize_upper
from .models import Product, ProductLot, RackColor


QUANTITY_MODE_MOVEMENT = "movement"
QUANTITY_MODE_OVERWRITE = "overwrite"
DEFAULT_QUANTITY_MODE = QUANTITY_MODE_MOVEMENT
VALID_QUANTITY_MODES = {QUANTITY_MODE_MOVEMENT, QUANTITY_MODE_OVERWRITE}
IMPORT_TEMP_LOCATION_VALUE = "TEMP"


def normalize_quantity_mode(value):
    mode = (parse_str(value) or "").lower()
    if mode in VALID_QUANTITY_MODES:
        return mode
    return DEFAULT_QUANTITY_MODE


def _normalize_match_value(value):
    text = parse_str(value)
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return "".join(char.lower() for char in ascii_value if char.isalnum())


def _find_sku_matches_ignoring_case_and_special_chars(sku):
    normalized_sku = _normalize_match_value(sku)
    if not normalized_sku:
        return []
    queryset = Product.objects.exclude(sku="").only("id", "sku", "name", "brand")
    return [
        product
        for product in queryset
        if _normalize_match_value(product.sku) == normalized_sku
    ]


def _find_name_brand_matches_ignoring_case_and_special_chars(name, brand):
    normalized_name = _normalize_match_value(name)
    normalized_brand = _normalize_match_value(brand)
    if not normalized_name or not normalized_brand:
        return []
    queryset = (
        Product.objects.exclude(name="")
        .exclude(brand="")
        .only("id", "sku", "name", "brand")
    )
    return [
        product
        for product in queryset
        if _normalize_match_value(product.name) == normalized_name
        and _normalize_match_value(product.brand) == normalized_brand
    ]


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
        matches = _find_sku_matches_ignoring_case_and_special_chars(sku)
        if matches:
            return matches, "sku"
    if name and brand:
        matches = list(
            Product.objects.filter(name__iexact=name, brand__iexact=brand)
        )
        if matches:
            return matches, "name_brand"
        matches = _find_name_brand_matches_ignoring_case_and_special_chars(
            name,
            brand,
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


def _overwrite_product_quantity(*, product, quantity, location, user=None):
    lots = list(
        ProductLot.objects.filter(product=product)
        .select_related("location")
        .order_by("id")
    )
    for lot in lots:
        removable = max(0, lot.quantity_on_hand - lot.quantity_reserved)
        if removable <= 0:
            continue
        adjust_stock(
            user=user,
            lot=lot,
            delta=-removable,
            reason_code="import_overwrite",
            reason_notes="Import produits: ecrasement du stock.",
        )

    current_total = sum(
        ProductLot.objects.filter(product=product).values_list("quantity_on_hand", flat=True)
    )
    if current_total > quantity:
        raise ValueError(
            "Ecrasement impossible: stock reserve superieur a la quantite importee."
        )
    delta = quantity - current_total
    if delta <= 0:
        return
    receive_stock(
        user=user,
        product=product,
        quantity=delta,
        location=location,
    )


def _resolve_stock_location_for_import(*, product, location):
    if location is not None:
        return location
    if product.default_location is not None:
        return product.default_location
    temp_location = get_or_create_location(
        IMPORT_TEMP_LOCATION_VALUE,
        IMPORT_TEMP_LOCATION_VALUE,
        IMPORT_TEMP_LOCATION_VALUE,
        IMPORT_TEMP_LOCATION_VALUE,
    )
    if temp_location is None:
        return None
    if product.default_location_id != temp_location.id:
        product.default_location = temp_location
        if product.pk:
            product.save(update_fields=["default_location"])
    return temp_location


def _apply_quantity(*, product, quantity, location, user=None, quantity_mode=DEFAULT_QUANTITY_MODE):
    if quantity is None:
        return
    if quantity <= 0:
        raise ValueError("Quantité invalide.")
    stock_location = _resolve_stock_location_for_import(
        product=product,
        location=location,
    )
    if stock_location is None:
        raise ValueError("Emplacement requis pour la quantité.")
    quantity_mode = normalize_quantity_mode(quantity_mode)
    try:
        if quantity_mode == QUANTITY_MODE_OVERWRITE:
            with transaction.atomic():
                _overwrite_product_quantity(
                    product=product,
                    quantity=quantity,
                    location=stock_location,
                    user=user,
                )
            return
        receive_stock(
            user=user,
            product=product,
            quantity=quantity,
            location=stock_location,
        )
    except StockError as exc:
        raise ValueError(str(exc)) from exc


def _parse_product_name(row):
    name = parse_str(get_value(row, "name", "nom", "nom_produit", "produit"))
    if not name:
        raise ValueError("Nom produit requis.")
    return normalize_title(name)


def _parse_product_sku(row):
    return parse_str(get_value(row, "sku"))


def _parse_product_brand(row):
    brand = parse_str(get_value(row, "brand", "marque"))
    if brand:
        return normalize_upper(brand)
    return None


def _parse_product_category(row):
    category_parts = [
        parse_str(get_value(row, "category_l1", "categorie_l1", "category_1", "categorie_1")),
        parse_str(get_value(row, "category_l2", "categorie_l2", "category_2", "categorie_2")),
        parse_str(get_value(row, "category_l3", "categorie_l3", "category_3", "categorie_3")),
        parse_str(get_value(row, "category_l4", "categorie_l4", "category_4", "categorie_4")),
    ]
    category_provided = any(category_parts)
    category = build_category_path([part for part in category_parts if part])
    return category_provided, category


def _parse_product_tags(row):
    tags_raw = parse_str(get_value(row, "tags", "etiquettes", "etiquette"))
    tags_provided = tags_raw is not None
    tags = build_product_tags(tags_raw) if tags_raw else []
    return tags_provided, tags


def _apply_rack_color(default_location, row):
    rack_color = parse_str(get_value(row, "rack_color", "couleur_rack", "color_rack"))
    if rack_color and default_location is not None:
        RackColor.objects.update_or_create(
            warehouse=default_location.warehouse,
            zone=default_location.zone,
            defaults={"color": rack_color},
        )


def _parse_default_location(row):
    warehouse_name = parse_str(get_value(row, "warehouse", "entrepot"))
    zone = parse_str(get_value(row, "zone", "rack"))
    aisle = parse_str(get_value(row, "aisle", "etagere"))
    shelf = parse_str(get_value(row, "shelf", "bac", "emplacement"))
    default_location = get_or_create_location(warehouse_name, zone, aisle, shelf)
    _apply_rack_color(default_location, row)
    return default_location is not None, default_location


def _parse_volume_and_dimensions(row):
    length_cm = parse_decimal(get_value(row, "length_cm", "longueur_cm"))
    width_cm = parse_decimal(get_value(row, "width_cm", "largeur_cm"))
    height_cm = parse_decimal(get_value(row, "height_cm", "hauteur_cm"))
    volume_cm3 = parse_int(get_value(row, "volume_cm3", "volume_cm3"))
    if volume_cm3 is None:
        volume_cm3 = compute_volume(length_cm, width_cm, height_cm)
    return {
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "volume_cm3": volume_cm3,
    }


def _parse_product_values(row, *, base_dir):
    location_provided, default_location = _parse_default_location(row)
    category_provided, category = _parse_product_category(row)
    tags_provided, tags = _parse_product_tags(row)
    values = {
        "name": _parse_product_name(row),
        "sku": _parse_product_sku(row),
        "brand": _parse_product_brand(row),
        "ean": parse_str(get_value(row, "ean")),
        "barcode": parse_str(get_value(row, "barcode", "code_barre", "codebarre")),
        "color": parse_str(get_value(row, "color", "couleur")),
        "notes": parse_str(get_value(row, "notes", "note")),
        "quantity": parse_int(get_value(row, "quantity", "quantite", "stock", "qty")),
        "pu_ht": parse_decimal(get_value(row, "pu_ht", "price_ht", "unit_price_ht")),
        "tva": parse_decimal(get_value(row, "tva", "vat")),
        "category": category,
        "category_provided": category_provided,
        "tags": tags,
        "tags_provided": tags_provided,
        "default_location": default_location,
        "location_provided": location_provided,
        "photo_path": resolve_photo_path(
            get_value(row, "photo", "image", "photo_path", "image_path"),
            base_dir,
        ),
        "weight_g": parse_int(get_value(row, "weight_g", "poids_g")),
        "storage_conditions": parse_str(
            get_value(row, "storage_conditions", "conditions_stockage")
        ),
        "perishable": parse_bool(get_value(row, "perishable", "perissable")),
        "quarantine_default": parse_bool(
            get_value(row, "quarantine_default", "quarantaine_defaut")
        ),
    }
    values.update(_parse_volume_and_dimensions(row))
    return values


def _build_create_updates(values):
    updates = {}
    if values["category"] is not None:
        updates["category"] = values["category"]
    for field in ("ean", "barcode", "brand", "color", "pu_ht", "tva"):
        if values[field] is not None:
            updates[field] = values[field]
    if values["location_provided"]:
        updates["default_location"] = values["default_location"]
    for field in (
        "length_cm",
        "width_cm",
        "height_cm",
        "weight_g",
        "volume_cm3",
        "storage_conditions",
        "perishable",
        "quarantine_default",
        "notes",
    ):
        if values[field] is not None:
            updates[field] = values[field]
    return updates


def _build_update_fields(values):
    updates = {"name": values["name"]}
    if values["category_provided"]:
        updates["category"] = values["category"]
    for field in ("ean", "barcode", "brand", "color", "pu_ht", "tva"):
        if values[field] is not None:
            updates[field] = values[field]
    if values["location_provided"]:
        updates["default_location"] = values["default_location"]
    for field in (
        "length_cm",
        "width_cm",
        "height_cm",
        "weight_g",
        "volume_cm3",
        "storage_conditions",
        "perishable",
        "quarantine_default",
        "notes",
    ):
        if values[field] is not None:
            updates[field] = values[field]
    return updates


def _apply_product_updates(product, updates):
    if not updates:
        return
    for field, value in updates.items():
        setattr(product, field, value)
    product.save(update_fields=list(updates.keys()))


def import_product_row(
    row,
    *,
    user=None,
    existing_product=None,
    base_dir: Path | None = None,
    quantity_mode: str = DEFAULT_QUANTITY_MODE,
):
    name = _parse_product_name(row)
    sku = _parse_product_sku(row)
    if existing_product is None and sku and Product.objects.filter(sku__iexact=sku).exists():
        raise ValueError("SKU déjà utilisé.")
    values = _parse_product_values(row, base_dir=base_dir)
    values["name"] = name
    values["sku"] = sku

    warnings = []
    if existing_product is None:
        product = Product(sku=values["sku"] or "", name=values["name"])
        for field, value in _build_create_updates(values).items():
            setattr(product, field, value)
        attach_photo(product, values["photo_path"])
        product.save()
        if values["tags_provided"]:
            product.tags.set(values["tags"])
        _apply_quantity(
            product=product,
            quantity=values["quantity"],
            location=values["default_location"] if values["location_provided"] else None,
            user=user,
            quantity_mode=quantity_mode,
        )
        return product, True, warnings

    updates = _build_update_fields(values)
    photo_updated = attach_photo(existing_product, values["photo_path"])
    if photo_updated:
        updates["photo"] = existing_product.photo

    _apply_product_updates(existing_product, updates)
    if values["tags_provided"]:
        existing_product.tags.set(values["tags"])
    _apply_quantity(
        product=existing_product,
        quantity=values["quantity"],
        location=values["default_location"] if values["location_provided"] else None,
        user=user,
        quantity_mode=quantity_mode,
    )
    return existing_product, False, warnings


def import_products_rows(
    rows,
    *,
    user=None,
    decisions=None,
    base_dir: Path | None = None,
    start_index: int = 2,
    quantity_mode: str = DEFAULT_QUANTITY_MODE,
    collect_stats: bool = False,
):
    created = 0
    updated = 0
    errors = []
    warnings = []
    impacted_product_ids = set()
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
                    f"Ligne {index}: SKU {sku} déjà utilisé, SKU auto-généré."
                )
        try:
            product, was_created, row_warnings = import_product_row(
                row,
                user=user,
                existing_product=existing_product,
                base_dir=base_dir,
                quantity_mode=quantity_mode,
            )
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
            continue
        if collect_stats:
            impacted_product_ids.add(product.id)
        warnings.extend(row_warnings)
        if was_created:
            created += 1
        else:
            updated += 1
    if collect_stats:
        return (
            created,
            updated,
            errors,
            warnings,
            {"distinct_products": len(impacted_product_ids)},
        )
    return created, updated, errors, warnings


def import_products_single(row, user=None):
    product, _, _ = import_product_row(row, user=user)
    return product
