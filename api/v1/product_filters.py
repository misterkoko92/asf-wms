from django.db.models import F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from wms.models import ProductLotStatus

from .query_utils import parse_bool, parse_decimal, parse_int


def apply_product_filters(queryset, params):
    active_param = parse_bool(params.get("is_active"))
    if active_param is None:
        queryset = queryset.filter(is_active=True)
    else:
        queryset = queryset.filter(is_active=active_param)

    query = (params.get("q") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__icontains=query)
        )

    name = (params.get("name") or "").strip()
    if name:
        queryset = queryset.filter(name__icontains=name)

    brand = (params.get("brand") or "").strip()
    if brand:
        queryset = queryset.filter(brand__icontains=brand)

    sku = (params.get("sku") or "").strip()
    if sku:
        queryset = queryset.filter(sku__icontains=sku)

    barcode = (params.get("barcode") or "").strip()
    if barcode:
        queryset = queryset.filter(barcode__icontains=barcode)

    ean = (params.get("ean") or "").strip()
    if ean:
        queryset = queryset.filter(ean__icontains=ean)

    color = (params.get("color") or "").strip()
    if color:
        queryset = queryset.filter(color__icontains=color)

    category_name = (params.get("category") or "").strip()
    if category_name:
        queryset = queryset.filter(category__name__icontains=category_name)

    category_id = parse_int(params.get("category_id"))
    if category_id is not None:
        queryset = queryset.filter(category_id=category_id)

    tag_name = (params.get("tag") or "").strip()
    if tag_name:
        queryset = queryset.filter(tags__name__icontains=tag_name)

    tag_id = parse_int(params.get("tag_id"))
    if tag_id is not None:
        queryset = queryset.filter(tags__id=tag_id)

    storage_conditions = (params.get("storage_conditions") or "").strip()
    if storage_conditions:
        queryset = queryset.filter(storage_conditions__icontains=storage_conditions)

    notes = (params.get("notes") or "").strip()
    if notes:
        queryset = queryset.filter(notes__icontains=notes)

    perishable = parse_bool(params.get("perishable"))
    if perishable is not None:
        queryset = queryset.filter(perishable=perishable)

    quarantine_default = parse_bool(params.get("quarantine_default"))
    if quarantine_default is not None:
        queryset = queryset.filter(quarantine_default=quarantine_default)

    default_location_id = parse_int(params.get("default_location_id"))
    if default_location_id is not None:
        queryset = queryset.filter(default_location_id=default_location_id)

    pu_ht = parse_decimal(params.get("pu_ht"))
    if pu_ht is not None:
        queryset = queryset.filter(pu_ht=pu_ht)

    tva = parse_decimal(params.get("tva"))
    if tva is not None:
        queryset = queryset.filter(tva=tva)

    pu_ttc = parse_decimal(params.get("pu_ttc"))
    if pu_ttc is not None:
        queryset = queryset.filter(pu_ttc=pu_ttc)

    weight_g = parse_int(params.get("weight_g"))
    if weight_g is not None:
        queryset = queryset.filter(weight_g=weight_g)

    volume_cm3 = parse_int(params.get("volume_cm3"))
    if volume_cm3 is not None:
        queryset = queryset.filter(volume_cm3=volume_cm3)

    length_cm = parse_decimal(params.get("length_cm"))
    if length_cm is not None:
        queryset = queryset.filter(length_cm=length_cm)

    width_cm = parse_decimal(params.get("width_cm"))
    if width_cm is not None:
        queryset = queryset.filter(width_cm=width_cm)

    height_cm = parse_decimal(params.get("height_cm"))
    if height_cm is not None:
        queryset = queryset.filter(height_cm=height_cm)

    tag_filtered = bool(tag_name or tag_id)
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

    available_stock = parse_int(params.get("available_stock"))
    if available_stock is not None:
        queryset = queryset.filter(available_stock=available_stock)

    return queryset.order_by("name")
