from django.db.models import F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from wms.models import ProductLotStatus

from .query_utils import parse_bool, parse_decimal, parse_int


TEXT_FILTERS = (
    ("name", "name__icontains"),
    ("brand", "brand__icontains"),
    ("sku", "sku__icontains"),
    ("barcode", "barcode__icontains"),
    ("ean", "ean__icontains"),
    ("color", "color__icontains"),
    ("category", "category__name__icontains"),
    ("tag", "tags__name__icontains"),
    ("storage_conditions", "storage_conditions__icontains"),
    ("notes", "notes__icontains"),
)

BOOL_FILTERS = (
    ("perishable", "perishable"),
    ("quarantine_default", "quarantine_default"),
)

INT_FILTERS = (
    ("category_id", "category_id"),
    ("tag_id", "tags__id"),
    ("default_location_id", "default_location_id"),
    ("weight_g", "weight_g"),
    ("volume_cm3", "volume_cm3"),
)

DECIMAL_FILTERS = (
    ("pu_ht", "pu_ht"),
    ("tva", "tva"),
    ("pu_ttc", "pu_ttc"),
    ("length_cm", "length_cm"),
    ("width_cm", "width_cm"),
    ("height_cm", "height_cm"),
)


def _normalized_param(params, key):
    return (params.get(key) or "").strip()


def apply_product_filters(queryset, params):
    active_param = parse_bool(params.get("is_active"))
    if active_param is None:
        queryset = queryset.filter(is_active=True)
    else:
        queryset = queryset.filter(is_active=active_param)

    query = _normalized_param(params, "q")
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__icontains=query)
        )

    text_values = {}
    for param, lookup in TEXT_FILTERS:
        value = _normalized_param(params, param)
        text_values[param] = value
        if value:
            queryset = queryset.filter(**{lookup: value})

    int_values = {}
    for param, lookup in INT_FILTERS:
        value = parse_int(params.get(param))
        int_values[param] = value
        if value is not None:
            queryset = queryset.filter(**{lookup: value})

    for param, lookup in BOOL_FILTERS:
        value = parse_bool(params.get(param))
        if value is not None:
            queryset = queryset.filter(**{lookup: value})

    for param, lookup in DECIMAL_FILTERS:
        value = parse_decimal(params.get(param))
        if value is not None:
            queryset = queryset.filter(**{lookup: value})

    tag_filtered = bool(text_values["tag"] or int_values["tag_id"])
    if tag_filtered:
        queryset = queryset.distinct()

    available_expr = ExpressionWrapper(
        F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
        output_field=IntegerField(),
    )
    queryset = queryset.annotate(
        available_stock=Coalesce(
            Sum(
                available_expr,
                filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
            ),
            0,
        )
    ).select_related("category").prefetch_related("tags")

    available_stock_value = parse_int(params.get("available_stock"))
    if available_stock_value is not None:
        queryset = queryset.filter(available_stock=available_stock_value)

    return queryset.order_by("name")
