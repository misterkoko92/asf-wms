from django.shortcuts import render

from .models import RackColor
from .print_context import build_product_label_context, build_product_qr_label_context
from .print_layouts import DEFAULT_LAYOUTS
from .print_renderer import get_template_layout
from .print_utils import build_label_pages, extract_block_style


def _ordered_products(products):
    if hasattr(products, "select_related"):
        queryset = (
            products.select_related("default_location", "default_location__warehouse")
            .order_by("name", "id")
            .all()
        )
        return list(queryset)
    return sorted(
        list(products),
        key=lambda product: ((product.name or "").lower(), product.id or 0),
    )


def render_product_labels_response(request, products):
    products_list = _ordered_products(products)
    warehouse_ids = {
        product.default_location.warehouse_id
        for product in products_list
        if product.default_location_id
    }
    rack_color_map = {}
    if warehouse_ids:
        rack_colors = RackColor.objects.filter(warehouse_id__in=warehouse_ids)
        rack_color_map = {
            (rack_color.warehouse_id, rack_color.zone.lower()): rack_color.color
            for rack_color in rack_colors
        }

    layout_override = get_template_layout("product_label")
    layout = layout_override or DEFAULT_LAYOUTS.get("product_label", {"blocks": []})
    contexts = []
    for product in products_list:
        rack_color = None
        location = product.default_location
        if location:
            rack_color = rack_color_map.get((location.warehouse_id, location.zone.lower()))
        contexts.append(build_product_label_context(product, rack_color=rack_color))

    pages, page_style = build_label_pages(
        layout,
        contexts,
        block_type="product_label",
        labels_per_page=4,
    )
    return render(
        request,
        "print/product_labels.html",
        {"pages": pages, "page_style": page_style},
    )


def render_product_qr_labels_response(request, products):
    products_list = _ordered_products(products)
    for product in products_list:
        if not product.qr_code_image:
            product.generate_qr_code()
            product.save(update_fields=["qr_code_image"])

    layout_override = get_template_layout("product_qr")
    layout = layout_override or DEFAULT_LAYOUTS.get("product_qr", {"blocks": []})
    page_style = extract_block_style(layout, "product_qr_label")
    try:
        rows = int(page_style.get("page_rows") or 5)
        cols = int(page_style.get("page_columns") or 3)
    except (TypeError, ValueError):
        rows, cols = 5, 3
    labels_per_page = max(1, rows * cols)
    contexts = [build_product_qr_label_context(product) for product in products_list]
    pages, page_style = build_label_pages(
        layout,
        contexts,
        block_type="product_qr_label",
        labels_per_page=labels_per_page,
    )
    return render(
        request,
        "print/product_qr_labels.html",
        {"pages": pages, "page_style": page_style},
    )
