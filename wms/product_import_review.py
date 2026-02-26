from django.db.models import F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from .import_services import DEFAULT_QUANTITY_MODE, normalize_quantity_mode
from .import_utils import get_value, parse_str
from .scan_helpers import parse_int
from .models import Product, ProductLotStatus


def row_is_empty(row):
    return all(not str(value or "").strip() for value in row.values())


def format_import_location(row):
    warehouse = parse_str(get_value(row, "warehouse", "entrepot"))
    zone = parse_str(get_value(row, "zone", "rack"))
    aisle = parse_str(get_value(row, "aisle", "etagere"))
    shelf = parse_str(get_value(row, "shelf", "bac", "emplacement"))
    if all([warehouse, zone, aisle, shelf]):
        return f"{warehouse} {zone}-{aisle}-{shelf}"
    return "-"


def summarize_import_row(row):
    quantity = parse_int(get_value(row, "quantity", "quantite", "stock", "qty"))
    return {
        "sku": parse_str(get_value(row, "sku")) or "",
        "name": parse_str(get_value(row, "name", "nom", "nom_produit", "produit")) or "",
        "brand": parse_str(get_value(row, "brand", "marque")) or "",
        "quantity": quantity if quantity is not None else "-",
        "location": format_import_location(row),
    }


def build_match_context(pending):
    if not pending:
        return None
    match_ids = {
        match_id
        for item in pending.get("matches", [])
        for match_id in item.get("match_ids", [])
    }
    if match_ids:
        available_expr = ExpressionWrapper(
            F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
            output_field=IntegerField(),
        )
        products = (
            Product.objects.filter(id__in=match_ids)
            .select_related("default_location")
            .annotate(
                available_stock=Coalesce(
                    Sum(
                        available_expr,
                        filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
                    ),
                    0,
                )
            )
        )
        products_by_id = {
            product.id: {
                "id": product.id,
                "sku": product.sku or "",
                "name": product.name,
                "brand": product.brand or "",
                "available_stock": int(product.available_stock or 0),
                "location": str(product.default_location) if product.default_location else "-",
            }
            for product in products
        }
    else:
        products_by_id = {}

    matches = []
    match_labels = {"sku": "SKU", "name_brand": "Nom + Marque"}
    for item in pending.get("matches", []):
        match_products = [
            products_by_id[match_id]
            for match_id in item.get("match_ids", [])
            if match_id in products_by_id
        ]
        matches.append(
            {
                "row_index": item.get("row_index"),
                "match_type": match_labels.get(item.get("match_type"), ""),
                "row": item.get("row_summary", {}),
                "products": match_products,
            }
        )
    return {
        "token": pending.get("token"),
        "matches": matches,
        "default_action": pending.get("default_action", "update"),
        "quantity_mode": normalize_quantity_mode(
            pending.get("quantity_mode", DEFAULT_QUANTITY_MODE)
        ),
    }
