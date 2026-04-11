from pathlib import Path

from .import_services import extract_product_identity, find_product_matches
from .import_utils import extract_tabular_data, normalize_header, parse_str
from .incomplete_product_suggestions import build_listing_assisted_suggestions
from .listing_row_classification import is_non_product_listing_row
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
    "prix_ht": "pu_ht",
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
    "qte": "quantity",
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
    ("perishable", "Périssable"),
    ("quarantine_default", "Quarantaine"),
    ("notes", "Notes"),
]

PALLET_LOCATION_FIELDS = [
    ("warehouse", "Entrepôt"),
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
    ("perishable", "Périssable"),
    ("quarantine_default", "Quarantaine par défaut"),
    ("quantity", "Quantité"),
]

LISTING_SUGGESTION_FIELD_LABELS = {
    "brand": "Marque",
    "category": "Catégorie",
    "tva": "TVA",
    "location": "Emplacement",
}

LISTING_REVIEW_OVERRIDE_FIELDS = [
    *(field for field, _label in PALLET_REVIEW_FIELDS),
    *(field for field, _label in PALLET_LOCATION_FIELDS),
    "quantity",
    "rack_color",
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


def normalize_listing_mapping(mapping):
    normalized = {}
    for raw_idx, field in (mapping or {}).items():
        try:
            idx = int(raw_idx)
        except (TypeError, ValueError):
            continue
        field_name = str(field or "").strip()
        if not field_name:
            continue
        normalized[idx] = field_name
    return normalized


def apply_listing_mapping(rows, mapping):
    normalized_mapping = normalize_listing_mapping(mapping)
    mapped_rows = []
    for row in rows:
        if _listing_row_empty(row) or is_non_product_listing_row(row):
            continue
        mapped = {}
        for idx, field in normalized_mapping.items():
            if idx < len(row):
                mapped[field] = row[idx]
        mapped_rows.append(mapped)
    return mapped_rows


def _clean_listing_value(value):
    return parse_str(value) or ""


def _normalize_review_overrides(review_overrides):
    normalized = {}
    for row_key, payload in (review_overrides or {}).items():
        row_key_value = _clean_listing_value(row_key)
        if not row_key_value:
            continue
        values = {}
        payload_values = (payload or {}).get("values") or {}
        for field_name in LISTING_REVIEW_OVERRIDE_FIELDS:
            if field_name not in payload_values:
                continue
            values[field_name] = _clean_listing_value(payload_values.get(field_name))
        normalized[row_key_value] = {
            "selection": _clean_listing_value((payload or {}).get("selection")) or "new",
            "values": values,
        }
    return normalized


def capture_listing_review_overrides_from_post(post_data, rows, mapping, *, start_index=2):
    overrides = {}
    for row_index, row in enumerate(apply_listing_mapping(rows, mapping), start=start_index):
        row_key = f"row-{row_index}"
        values = {}
        for field_name in LISTING_REVIEW_OVERRIDE_FIELDS:
            values[field_name] = _clean_listing_value(
                post_data.get(f"row_{row_index}_{field_name}", row.get(field_name))
            )
        overrides[row_key] = {
            "selection": _clean_listing_value(post_data.get(f"row_{row_index}_match")) or "new",
            "values": values,
        }
    return overrides


def apply_listing_group_suggestion_to_overrides(review_overrides, suggestion):
    normalized_overrides = _normalize_review_overrides(review_overrides)
    for row_key, updates in ((suggestion or {}).get("per_row_updates") or {}).items():
        row_override = normalized_overrides.setdefault(
            row_key,
            {
                "selection": "new",
                "values": {},
            },
        )
        if row_override.get("selection") != "new":
            continue
        values = row_override.setdefault("values", {})
        for field_name, proposed_value in (updates or {}).items():
            if field_name not in LISTING_REVIEW_OVERRIDE_FIELDS:
                continue
            normalized_value = _clean_listing_value(proposed_value)
            if field_name == "name":
                if normalized_value:
                    values[field_name] = normalized_value
                continue
            if not _clean_listing_value(values.get(field_name)) and normalized_value:
                values[field_name] = normalized_value
    review_overrides.clear()
    review_overrides.update(normalized_overrides)
    return review_overrides


def _format_category_value(values):
    return " > ".join(
        part
        for part in (
            values.get("category_l1"),
            values.get("category_l2"),
            values.get("category_l3"),
            values.get("category_l4"),
        )
        if part
    )


def _format_location_value(values):
    return " / ".join(
        part
        for part in (
            values.get("warehouse"),
            values.get("zone"),
            values.get("aisle"),
            values.get("shelf"),
        )
        if part
    )


def _group_suggestion_current_value(row, field_name):
    values = row.get("values") or {}
    if field_name == "brand":
        return values.get("brand") or "-"
    if field_name == "category":
        return _format_category_value(values) or "-"
    if field_name == "tva":
        return values.get("tva") or "-"
    if field_name == "location":
        return _format_location_value(values) or "-"
    return "-"


def _group_suggestion_linked_product(row):
    if row.get("default_match") == "new":
        return ""
    existing = row.get("existing") or {}
    sku = existing.get("sku") or ""
    name = existing.get("name") or ""
    if sku and name:
        return f"{sku} - {name}"
    return sku or name


def _enrich_group_suggestions(group_suggestions, review_rows):
    rows_by_key = {f"row-{row['index']}": row for row in review_rows}
    enriched = []
    for suggestion in group_suggestions:
        preview_rows = []
        for row_key in suggestion.get("row_keys") or []:
            row = rows_by_key.get(row_key)
            if row is None:
                continue
            preview_rows.append(
                {
                    "row_key": row_key,
                    "index": row["index"],
                    "ean": row["values"].get("ean", ""),
                    "name": row["values"].get("name", ""),
                    "current_value": _group_suggestion_current_value(
                        row, suggestion.get("field_name")
                    ),
                    "proposed_value": suggestion.get("proposed_value", ""),
                    "linked_product": _group_suggestion_linked_product(row),
                }
            )
        enriched.append(
            {
                **suggestion,
                "field_label": LISTING_SUGGESTION_FIELD_LABELS.get(
                    suggestion.get("field_name"), suggestion.get("field_name", "")
                ),
                "preview_rows": preview_rows,
            }
        )
    return enriched


def build_listing_extract_options(
    extension, sheet_name, header_row, pdf_mode, page_start, page_end, page_numbers=None
):
    options = {}
    if extension in {".xlsx", ".xls"}:
        if sheet_name:
            options["sheet_name"] = sheet_name
        options["header_row"] = header_row or 1
    if extension == ".pdf":
        if pdf_mode == "custom":
            options["pdf_pages"] = (page_start, page_end)
        elif pdf_mode == "detected" and page_numbers:
            options["pdf_pages"] = list(page_numbers)
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
        pdf_pages.get("pages"),
    )


def build_listing_review_state(rows, mapping, *, start_index=2, review_overrides=None):
    mapped_rows = apply_listing_mapping(rows, mapping)
    match_labels = {
        "barcode": "Barcode",
        "ean": "EAN",
        "sku": "SKU",
        "name_brand": "Nom + Marque",
        "name": "Nom",
    }
    normalized_review_overrides = _normalize_review_overrides(review_overrides)
    suggestion_rows = []
    for row_index, row in enumerate(mapped_rows, start=start_index):
        suggestion_row = dict(row)
        suggestion_row["index"] = row_index
        suggestion_row["row_key"] = f"row-{row_index}"
        suggestion_rows.append(suggestion_row)
    suggestion_state = build_listing_assisted_suggestions(rows=suggestion_rows)
    review = []
    for suggestion_row in suggestion_rows:
        row_index = suggestion_row["index"]
        row_key = suggestion_row["row_key"]
        row = suggestion_row
        values = {field: _clean_listing_value(row.get(field)) for field, _ in PALLET_REVIEW_FIELDS}
        for key, _ in PALLET_LOCATION_FIELDS:
            values[key] = _clean_listing_value(row.get(key))
        values["quantity"] = _clean_listing_value(row.get("quantity"))
        values["rack_color"] = _clean_listing_value(row.get("rack_color"))

        sku, name, brand = extract_product_identity(row)
        matches, match_type = find_product_matches(
            sku=sku,
            name=name,
            brand=brand,
            barcode=_clean_listing_value(row.get("barcode")),
            ean=_clean_listing_value(row.get("ean")),
        )
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
        default_match = "new"
        match_badge = ""
        auto_match = suggestion_state["auto_matches"].get(row_key)
        if auto_match:
            auto_match_value = f"product:{auto_match['product_id']}"
            if any(option["value"] == auto_match_value for option in match_options):
                default_match = auto_match_value
                match_badge = "Match auto EAN"

        if existing:
            for key, _ in PALLET_LOCATION_FIELDS:
                if not values.get(key):
                    values[key] = existing.get(key, "")

        row_override = normalized_review_overrides.get(row_key) or {}
        for field_name, override_value in (row_override.get("values") or {}).items():
            values[field_name] = _clean_listing_value(override_value)
        override_selection = row_override.get("selection")
        if override_selection and (
            override_selection == "new"
            or any(option["value"] == override_selection for option in match_options)
        ):
            default_match = override_selection
            if auto_match:
                auto_match_value = f"product:{auto_match['product_id']}"
                if override_selection != auto_match_value:
                    match_badge = ""

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
                "match_badge": match_badge,
                "line_suggestions": suggestion_state["line_suggestions"].get(row_key, []),
            }
        )
    return {
        "rows": review,
        "group_suggestions": _enrich_group_suggestions(
            suggestion_state["group_suggestions"], review
        ),
    }


def build_listing_review_rows(rows, mapping, *, start_index=2):
    return build_listing_review_state(rows, mapping, start_index=start_index)["rows"]


def build_listing_columns(headers, rows, mapping):
    normalized_mapping = normalize_listing_mapping(mapping)
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
                "mapped": normalized_mapping.get(idx, ""),
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
