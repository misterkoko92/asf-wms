from pathlib import Path

from .import_utils import extract_tabular_data, normalize_header, parse_str
from .import_services import extract_product_identity, find_product_matches
from .product_display import build_product_display


PALLET_LISTING_REQUIRED_FIELDS = {"name", "quantity"}

PALLET_LISTING_HEADER_MAP = {
    "nom": "name",
    "nom_produit": "name",
    "produit": "name",
    "designation": "name",
    "marque": "brand",
    "brand": "brand",
    "couleur": "color",
    "categorie_l1": "category_l1",
    "categorie_1": "category_l1",
    "category_l1": "category_l1",
    "category_1": "category_l1",
    "categorie_l2": "category_l2",
    "categorie_2": "category_l2",
    "category_l2": "category_l2",
    "category_2": "category_l2",
    "categorie_l3": "category_l3",
    "categorie_3": "category_l3",
    "category_l3": "category_l3",
    "category_3": "category_l3",
    "categorie_l4": "category_l4",
    "categorie_4": "category_l4",
    "category_l4": "category_l4",
    "category_4": "category_l4",
    "code_barre": "barcode",
    "barcode": "barcode",
    "ean": "ean",
    "code_ean": "ean",
    "tags": "tags",
    "etiquettes": "tags",
    "entrepot": "warehouse",
    "warehouse": "warehouse",
    "zone": "zone",
    "rack": "zone",
    "etagere": "aisle",
    "aisle": "aisle",
    "bac": "shelf",
    "shelf": "shelf",
    "couleur_rack": "rack_color",
    "rack_color": "rack_color",
    "notes": "notes",
    "longueur_cm": "length_cm",
    "length_cm": "length_cm",
    "largeur_cm": "width_cm",
    "width_cm": "width_cm",
    "hauteur_cm": "height_cm",
    "height_cm": "height_cm",
    "poids_g": "weight_g",
    "weight_g": "weight_g",
    "volume_cm3": "volume_cm3",
    "conditions_stockage": "storage_conditions",
    "storage_conditions": "storage_conditions",
    "perissable": "perishable",
    "perishable": "perishable",
    "quarantaine_defaut": "quarantine_default",
    "quarantine_default": "quarantine_default",
    "quantite": "quantity",
    "qty": "quantity",
    "stock": "quantity",
    "pu_ht": "pu_ht",
    "puht": "pu_ht",
    "price_ht": "pu_ht",
    "unit_price_ht": "pu_ht",
    "tva": "tva",
    "vat": "tva",
}

PALLET_REVIEW_FIELDS = [
    ("name", "Nom"),
    ("brand", "Marque"),
    ("color", "Couleur"),
    ("category_l1", "Cat L1"),
    ("category_l2", "Cat L2"),
    ("category_l3", "Cat L3"),
    ("category_l4", "Cat L4"),
    ("barcode", "Barcode"),
    ("ean", "EAN"),
    ("tags", "Tags"),
    ("pu_ht", "PU HT"),
    ("tva", "TVA"),
    ("length_cm", "L cm"),
    ("width_cm", "l cm"),
    ("height_cm", "h cm"),
    ("weight_g", "Poids g"),
    ("volume_cm3", "Volume"),
    ("storage_conditions", "Stockage"),
    ("perishable", "Perissable"),
    ("quarantine_default", "Quarantaine"),
    ("notes", "Notes"),
]

PALLET_LOCATION_FIELDS = [
    ("warehouse", "Entrepot"),
    ("zone", "Rack"),
    ("aisle", "Etagere"),
    ("shelf", "Bac"),
]

PALLET_LISTING_MAPPING_FIELDS = [
    ("name", "Nom produit"),
    ("brand", "Marque"),
    ("color", "Couleur"),
    ("category_l1", "Categorie L1"),
    ("category_l2", "Categorie L2"),
    ("category_l3", "Categorie L3"),
    ("category_l4", "Categorie L4"),
    ("barcode", "Barcode"),
    ("ean", "EAN"),
    ("pu_ht", "PU HT"),
    ("tva", "TVA"),
    ("tags", "Tags"),
    ("warehouse", "Entrepot"),
    ("zone", "Rack"),
    ("aisle", "Etagere"),
    ("shelf", "Bac"),
    ("rack_color", "Couleur rack"),
    ("notes", "Notes"),
    ("length_cm", "Longueur cm"),
    ("width_cm", "Largeur cm"),
    ("height_cm", "Hauteur cm"),
    ("weight_g", "Poids g"),
    ("volume_cm3", "Volume cm3"),
    ("storage_conditions", "Conditions stockage"),
    ("perishable", "Perissable"),
    ("quarantine_default", "Quarantaine par defaut"),
    ("quantity", "Quantite"),
]


def _listing_row_empty(row):
    return all(not str(value or "").strip() for value in row)


def build_listing_mapping_defaults(headers):
    mapping = {}
    for idx, header in enumerate(headers):
        normalized = normalize_header(header)
        mapped = PALLET_LISTING_HEADER_MAP.get(normalized)
        if mapped:
            mapping[idx] = mapped
    return mapping


def apply_listing_mapping(rows, mapping):
    mapped_rows = []
    for row in rows:
        if _listing_row_empty(row):
            continue
        mapped = {}
        for idx, field in mapping.items():
            if idx < len(row):
                mapped[field] = row[idx]
        mapped_rows.append(mapped)
    return mapped_rows


def _clean_listing_value(value):
    return parse_str(value) or ""


def build_listing_extract_options(
    extension, sheet_name, header_row, pdf_mode, page_start, page_end
):
    options = {}
    if extension in {".xlsx", ".xls"}:
        if sheet_name:
            options["sheet_name"] = sheet_name
        options["header_row"] = header_row or 1
    if extension == ".pdf" and pdf_mode == "custom":
        options["pdf_pages"] = (page_start, page_end)
    return options


def pending_listing_extract_options(pending_data):
    pdf_pages = pending_data.get("pdf_pages") or {}
    return build_listing_extract_options(
        pending_data.get("extension", ""),
        pending_data.get("sheet_name", ""),
        pending_data.get("header_row") or 1,
        pdf_pages.get("mode") or "all",
        pdf_pages.get("start"),
        pdf_pages.get("end"),
    )


def build_listing_review_rows(rows, mapping, *, start_index=2):
    mapped_rows = apply_listing_mapping(rows, mapping)
    match_labels = {"name_brand": "Nom + Marque"}
    review = []
    for row_index, row in enumerate(mapped_rows, start=start_index):
        values = {
            field: _clean_listing_value(row.get(field))
            for field, _ in PALLET_REVIEW_FIELDS
        }
        for key, _ in PALLET_LOCATION_FIELDS:
            values[key] = _clean_listing_value(row.get(key))
        values["quantity"] = _clean_listing_value(row.get("quantity"))
        values["rack_color"] = _clean_listing_value(row.get("rack_color"))

        _, name, brand = extract_product_identity(row)
        matches, match_type = find_product_matches(sku=None, name=name, brand=brand)
        match_options = []
        for product in matches:
            label = f"{product.sku} - {product.name}"
            if product.brand:
                label = f"{label} ({product.brand})"
            match_options.append(
                {
                    "id": product.id,
                    "value": f"product:{product.id}",
                    "label": label,
                    "data": build_product_display(product),
                }
            )
        existing = match_options[0]["data"] if match_options else None
        default_match = f"product:{match_options[0]['id']}" if match_options else "new"

        if existing:
            for key, _ in PALLET_LOCATION_FIELDS:
                if not values.get(key):
                    values[key] = existing.get(key, "")

        fields = []
        for field, label in PALLET_REVIEW_FIELDS:
            fields.append(
                {
                    "name": field,
                    "label": label,
                    "value": values.get(field, ""),
                    "existing": existing.get(field, "") if existing else "",
                }
            )
        locations = []
        for key, label in PALLET_LOCATION_FIELDS:
            locations.append(
                {
                    "name": key,
                    "label": label,
                    "value": values.get(key, ""),
                    "existing": existing.get(key, "") if existing else "",
                }
            )

        review.append(
            {
                "index": row_index,
                "values": values,
                "fields": fields,
                "locations": locations,
                "existing": existing,
                "match_type": match_labels.get(match_type, "-"),
                "match_options": match_options,
                "default_match": default_match,
            }
        )
    return review


def build_listing_columns(headers, rows, mapping):
    columns = []
    for idx, header in enumerate(headers):
        sample = ""
        for row in rows:
            if idx < len(row) and str(row[idx] or "").strip():
                sample = row[idx]
                break
        columns.append(
            {
                "index": idx,
                "name": header,
                "sample": sample,
                "mapped": mapping.get(idx, ""),
            }
        )
    return columns


def load_listing_table(pending_data):
    data = Path(pending_data["file_path"]).read_bytes()
    return extract_tabular_data(
        data,
        pending_data["extension"],
        **pending_listing_extract_options(pending_data),
    )
