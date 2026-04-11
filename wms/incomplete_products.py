from .forms import ScanIncompleteProductBulkUpdateForm, ScanIncompleteProductReceiptFilterForm
from .import_utils import parse_decimal
from .incomplete_product_suggestions import build_listing_assisted_suggestions
from .models import Location, Product, ProductCategory
from .product_display import build_product_display

INCOMPLETE_PRODUCT_SUGGESTION_FIELD_LABELS = {
    "brand": "Marque",
    "category": "Catégorie",
    "tva": "TVA",
    "location": "Emplacement",
}


def _normalize_product_ids(product_ids):
    normalized = []
    seen = set()
    for value in product_ids or []:
        try:
            product_id = int(value)
        except (TypeError, ValueError):
            continue
        if product_id in seen:
            continue
        seen.add(product_id)
        normalized.append(product_id)
    return normalized


def build_incomplete_products_queryset(*, receipt_id=None, product_ids=None):
    queryset = (
        Product.objects.filter(is_incomplete=True)
        .select_related(
            "category",
            "default_location",
            "default_location__warehouse",
        )
        .order_by("name", "id")
    )
    normalized_product_ids = _normalize_product_ids(product_ids)
    if product_ids is not None:
        if not normalized_product_ids:
            return queryset.none()
        queryset = queryset.filter(id__in=normalized_product_ids)
    if receipt_id:
        queryset = queryset.filter(productlot__source_receipt_id=receipt_id)
    return queryset.distinct()


def apply_incomplete_products_bulk_update(*, form, receipt_id=None, product_ids=None):
    queryset = build_incomplete_products_queryset(
        receipt_id=receipt_id,
        product_ids=product_ids,
    )
    products = list(queryset.filter(id__in=form.cleaned_data["selected_product_ids"]))
    field_name = form.cleaned_data["field_name"]
    value = form.cleaned_data["resolved_value"]
    for product in products:
        setattr(product, field_name, value)
        product.save(update_fields=[field_name])
    return len(products), field_name


def _incomplete_row_key(product):
    return f"product-{product.id}"


def _build_incomplete_suggestion_rows(products):
    rows = []
    displays = {}
    for product in products:
        display = build_product_display(product)
        row_key = _incomplete_row_key(product)
        rows.append(
            {
                "row_key": row_key,
                "index": product.id,
                "name": product.name or "",
                "brand": product.brand or "",
                "ean": product.ean or "",
                "category_l1": display["category_l1"],
                "category_l2": display["category_l2"],
                "category_l3": display["category_l3"],
                "category_l4": display["category_l4"],
                "tva": str(product.tva) if product.tva is not None else "",
                "warehouse": display["warehouse"],
                "zone": display["zone"],
                "aisle": display["aisle"],
                "shelf": display["shelf"],
            }
        )
        displays[row_key] = display
    return rows, displays


def _format_incomplete_current_value(product, display, field_name):
    if field_name == "brand":
        return product.brand or "-"
    if field_name == "category":
        return str(product.category) if product.category else "-"
    if field_name == "tva":
        return str(product.tva) if product.tva is not None else "-"
    if field_name == "location":
        return str(product.default_location) if product.default_location else "-"
    return "-"


def build_incomplete_product_suggestions(queryset):
    products = list(queryset)
    if not products:
        return []

    rows, displays = _build_incomplete_suggestion_rows(products)
    product_ids = [product.id for product in products]
    base_products = Product.objects.exclude(id__in=product_ids).filter(is_incomplete=False)
    suggestion_state = build_listing_assisted_suggestions(rows=rows, products=base_products)
    products_by_key = {_incomplete_row_key(product): product for product in products}
    suggestions = []
    for suggestion in suggestion_state["group_suggestions"]:
        preview_rows = []
        for row_key in suggestion.get("row_keys") or []:
            product = products_by_key.get(row_key)
            if product is None:
                continue
            preview_rows.append(
                {
                    "product_id": product.id,
                    "sku": product.sku or "-",
                    "ean": product.ean or "",
                    "name": product.name or "",
                    "current_value": _format_incomplete_current_value(
                        product,
                        displays.get(row_key) or {},
                        suggestion.get("field_name"),
                    ),
                    "proposed_value": suggestion.get("proposed_value", ""),
                }
            )
        suggestions.append(
            {
                **suggestion,
                "field_label": INCOMPLETE_PRODUCT_SUGGESTION_FIELD_LABELS.get(
                    suggestion.get("field_name"), suggestion.get("field_name", "")
                ),
                "preview_rows": preview_rows,
            }
        )
    return suggestions


def apply_incomplete_product_suggestion(*, queryset, suggestion):
    products = list(queryset)
    products_by_key = {_incomplete_row_key(product): product for product in products}
    field_name = (suggestion or {}).get("field_name")
    model_value_id = (suggestion or {}).get("model_value_id")
    raw_value = (suggestion or {}).get("raw_value")
    category = None
    location = None
    tva = None
    if field_name == "category" and model_value_id:
        category = ProductCategory.objects.filter(pk=model_value_id).first()
    elif field_name == "location" and model_value_id:
        location = Location.objects.filter(pk=model_value_id).first()
    elif field_name == "tva" and raw_value:
        tva = parse_decimal(raw_value)

    updated_count = 0
    for row_key, row_update in ((suggestion or {}).get("per_row_updates") or {}).items():
        product = products_by_key.get(row_key)
        if product is None:
            continue
        update_fields = []
        if field_name == "brand":
            proposed_brand = (row_update or {}).get("brand") or ""
            proposed_name = (row_update or {}).get("name") or ""
            if not product.brand and proposed_brand:
                product.brand = proposed_brand
                update_fields.append("brand")
            if proposed_name and proposed_name != product.name:
                product.name = proposed_name
                update_fields.append("name")
        elif field_name == "category":
            if product.category_id is None and category is not None:
                product.category = category
                update_fields.append("category")
        elif field_name == "location":
            if product.default_location_id is None and location is not None:
                product.default_location = location
                update_fields.append("default_location")
        elif field_name == "tva":
            if product.tva is None and tva is not None:
                product.tva = tva
                update_fields.append("tva")
        if update_fields:
            product.save(update_fields=update_fields)
            updated_count += 1
    return updated_count, field_name


def build_incomplete_products_bulk_form(*, queryset, data=None):
    if data is not None:
        return ScanIncompleteProductBulkUpdateForm(
            data,
            product_queryset=queryset,
        )
    return ScanIncompleteProductBulkUpdateForm(product_queryset=queryset)


def build_incomplete_products_context(
    *,
    queryset,
    action_url,
    edit_next_url,
    card_id,
    bulk_form=None,
    suggestions=None,
    show_receipt_filter=False,
    receipt_filter_form=None,
    receipt_id=None,
    embedded=False,
):
    products = list(queryset)
    return {
        "incomplete_products": products,
        "incomplete_bulk_form": bulk_form or build_incomplete_products_bulk_form(queryset=queryset),
        "incomplete_products_action_url": action_url,
        "incomplete_products_edit_next_url": edit_next_url,
        "incomplete_products_card_id": card_id,
        "incomplete_products_show_receipt_filter": show_receipt_filter,
        "incomplete_receipt_filter_form": receipt_filter_form
        or ScanIncompleteProductReceiptFilterForm(),
        "incomplete_products_receipt_id": receipt_id,
        "incomplete_product_suggestions": (
            suggestions
            if suggestions is not None
            else build_incomplete_product_suggestions(queryset)
        ),
        "incomplete_products_embedded": embedded,
    }
