import re
from decimal import Decimal

from .models import Product
from .product_display import build_product_display
from .text_utils import normalize_upper

BRAND_GROUP_MIN_ROWS = 3
_TOKEN_SPLIT_RE = re.compile(r"\s+")
_TRIMMED_NAME_RE_TEMPLATE = r"^\s*{token}(?:[\s\-:/|]+)?"


def _normalize_lookup_token(value):
    return "".join(char for char in normalize_upper(value or "") if char.isalnum())


def _normalize_ean(value):
    return _normalize_lookup_token(value)


def _row_key(row):
    if row.get("row_key"):
        return str(row["row_key"])
    return f"row-{row.get('index')}"


def _leading_name_token(value):
    text = str(value or "").strip()
    if not text:
        return ""
    first_part = _TOKEN_SPLIT_RE.split(text, maxsplit=1)[0]
    return _normalize_lookup_token(first_part)


def _trim_brand_prefix(name, token):
    if not name or not token:
        return name
    pattern = re.compile(_TRIMMED_NAME_RE_TEMPLATE.format(token=re.escape(token)), re.IGNORECASE)
    trimmed = pattern.sub("", str(name)).strip()
    return trimmed or str(name).strip()


def _format_tva_display(value):
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{(value * Decimal('100')).normalize()} %"


def _build_ean_index(products):
    ean_index = {}
    for product in products:
        normalized_ean = _normalize_ean(product.ean)
        if not normalized_ean:
            continue
        ean_index.setdefault(normalized_ean, []).append(product)
    return ean_index


def _category_consensus(reference_products):
    displays = [build_product_display(product) for product in reference_products]
    category_ids = {product.category_id for product in reference_products if product.category_id}
    category_paths = {
        (
            display["category_l1"],
            display["category_l2"],
            display["category_l3"],
            display["category_l4"],
        )
        for display in displays
        if any(
            (
                display["category_l1"],
                display["category_l2"],
                display["category_l3"],
                display["category_l4"],
            )
        )
    }
    if len(category_paths) != 1 or len(category_ids) != 1:
        return None
    category_path = next(iter(category_paths))
    return {
        "field_name": "category",
        "proposed_value": " > ".join(part for part in category_path if part),
        "model_value_id": next(iter(category_ids)),
        "per_row_update": {
            "category_l1": category_path[0],
            "category_l2": category_path[1],
            "category_l3": category_path[2],
            "category_l4": category_path[3],
        },
    }


def _tva_consensus(reference_products):
    tva_values = {product.tva for product in reference_products if product.tva is not None}
    if len(tva_values) != 1:
        return None
    value = next(iter(tva_values))
    return {
        "field_name": "tva",
        "proposed_value": _format_tva_display(value),
        "raw_value": str(value),
        "per_row_update": {"tva": str(value)},
    }


def _location_consensus(reference_products):
    displays = [build_product_display(product) for product in reference_products]
    location_ids = {
        product.default_location_id for product in reference_products if product.default_location_id
    }
    locations = {
        (
            display["warehouse"],
            display["zone"],
            display["aisle"],
            display["shelf"],
        )
        for display in displays
        if any((display["warehouse"], display["zone"], display["aisle"], display["shelf"]))
    }
    if len(locations) != 1 or len(location_ids) != 1:
        return None
    location = next(iter(locations))
    return {
        "field_name": "location",
        "proposed_value": " / ".join(part for part in location if part),
        "model_value_id": next(iter(location_ids)),
        "per_row_update": {
            "warehouse": location[0],
            "zone": location[1],
            "aisle": location[2],
            "shelf": location[3],
        },
    }


def _build_brand_group_suggestions(rows, products):
    known_brands = {
        _normalize_lookup_token(product.brand)
        for product in products
        if _normalize_lookup_token(product.brand)
    }
    groups = {}
    for row in rows:
        if str(row.get("brand") or "").strip():
            continue
        token = _leading_name_token(row.get("name"))
        if not token:
            continue
        groups.setdefault(token, []).append(row)

    suggestions = []
    for token, grouped_rows in sorted(groups.items()):
        if len(grouped_rows) < BRAND_GROUP_MIN_ROWS:
            continue
        row_keys = [_row_key(row) for row in grouped_rows]
        source = "Base + Batch" if token in known_brands else "Batch"
        confidence = "Forte" if source == "Base + Batch" else "Moyenne"
        brand_updates = {}
        for row in grouped_rows:
            update = {"brand": token}
            trimmed_name = _trim_brand_prefix(row.get("name"), token)
            if trimmed_name and trimmed_name != str(row.get("name") or "").strip():
                update["name"] = trimmed_name
            brand_updates[_row_key(row)] = update
        suggestions.append(
            {
                "id": f"brand:{token}",
                "field_name": "brand",
                "proposed_value": token,
                "confidence": confidence,
                "source": source,
                "row_keys": row_keys,
                "per_row_updates": brand_updates,
            }
        )

        if source != "Base + Batch":
            continue
        brand_products = [
            product for product in products if _normalize_lookup_token(product.brand) == token
        ]
        for consensus_builder in (_category_consensus, _tva_consensus, _location_consensus):
            consensus = consensus_builder(brand_products)
            if consensus is None:
                continue
            suggestions.append(
                {
                    "id": f"{consensus['field_name']}:{token}",
                    "field_name": consensus["field_name"],
                    "proposed_value": consensus["proposed_value"],
                    "model_value_id": consensus.get("model_value_id"),
                    "raw_value": consensus.get("raw_value"),
                    "confidence": "Forte",
                    "source": "Base + Batch",
                    "row_keys": row_keys,
                    "per_row_updates": {
                        row_key: dict(consensus["per_row_update"]) for row_key in row_keys
                    },
                }
            )
    return suggestions


def build_listing_assisted_suggestions(*, rows, products=None):
    products = list(
        products
        if products is not None
        else Product.objects.select_related(
            "category", "default_location", "default_location__warehouse"
        )
    )
    ean_index = _build_ean_index(products)
    auto_matches = {}
    for row in rows:
        normalized_ean = _normalize_ean(row.get("ean"))
        if not normalized_ean:
            continue
        matches = ean_index.get(normalized_ean, [])
        if len(matches) != 1:
            continue
        product = matches[0]
        auto_matches[_row_key(row)] = {
            "product_id": product.id,
            "match_type": "ean",
            "product": product,
        }

    return {
        "auto_matches": auto_matches,
        "line_suggestions": {},
        "group_suggestions": _build_brand_group_suggestions(rows, products),
    }
