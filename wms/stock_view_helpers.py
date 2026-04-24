from django.core.paginator import Paginator
from django.db.models import (
    DateTimeField,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce

from .models import Product, ProductLot, StockMovement, Warehouse
from .product_category_filters import build_category_filter_context

STOCK_PAGE_SIZE = 100


def _parse_bool_query_param(value):
    return (value or "").strip().lower() in {"1", "true", "on", "yes", "oui"}


def build_stock_context(request):
    query = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    warehouse_id = (request.GET.get("warehouse") or "").strip()
    sort = (request.GET.get("sort") or "name").strip()
    page_number = (request.GET.get("page") or "1").strip()
    include_zero_param = request.GET.get("include_zero")
    include_zero = (
        True if include_zero_param is None else _parse_bool_query_param(include_zero_param)
    )
    category_filter_context = build_category_filter_context(selected_category_id=category_id)

    products = Product.objects.filter(is_active=True).select_related("category")
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__icontains=query)
        )
    if category_filter_context["descendant_category_ids"]:
        products = products.filter(
            category_id__in=category_filter_context["descendant_category_ids"]
        )

    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    stock_lots = ProductLot.objects.filter(
        product_id=OuterRef("pk"),
        quantity_on_hand__gt=0,
    )
    if warehouse_id:
        stock_lots = stock_lots.filter(location__warehouse_id=warehouse_id)
    stock_total_subquery = (
        stock_lots.values("product_id").annotate(total=Sum(available_expr)).values("total")
    )

    movements = StockMovement.objects.filter(product_id=OuterRef("pk"))
    if warehouse_id:
        movements = movements.filter(
            Q(to_location__warehouse_id=warehouse_id) | Q(from_location__warehouse_id=warehouse_id)
        )
    last_movement_subquery = (
        movements.values("product_id").annotate(last=Max("created_at")).values("last")
    )

    products = products.annotate(
        stock_total=Coalesce(
            Subquery(stock_total_subquery, output_field=IntegerField()),
            0,
        ),
        last_movement_at=Subquery(last_movement_subquery, output_field=DateTimeField()),
    )
    if not include_zero:
        products = products.filter(stock_total__gt=0)

    sort_map = {
        "name": "name",
        "sku": "sku",
        "qty_desc": "-stock_total",
        "qty_asc": "stock_total",
        "category": "category__name",
    }
    products = products.order_by(sort_map.get(sort, "name"), "name")
    paginator = Paginator(products, STOCK_PAGE_SIZE)
    products_page = paginator.get_page(page_number)

    warehouses = Warehouse.objects.all().order_by("name")

    def build_page_url(target_page):
        params = request.GET.copy()
        if target_page <= 1:
            params.pop("page", None)
        else:
            params["page"] = str(target_page)
        encoded = params.urlencode()
        return f"?{encoded}" if encoded else "?"

    return {
        "active": "stock",
        "products": products_page.object_list,
        "products_page": products_page,
        "products_total_count": paginator.count,
        "products_page_prev_url": (
            build_page_url(products_page.previous_page_number())
            if products_page.has_previous()
            else ""
        ),
        "products_page_next_url": (
            build_page_url(products_page.next_page_number()) if products_page.has_next() else ""
        ),
        "categories": category_filter_context["categories"],
        "category_labels_by_id": category_filter_context["category_labels_by_id"],
        "category_paths_by_id": category_filter_context["category_paths_by_id"],
        "category_filter_max_depth": category_filter_context["category_filter_max_depth"],
        "selected_category_path": category_filter_context["selected_category_path"],
        "warehouses": warehouses,
        "query": query,
        "category_id": category_id,
        "warehouse_id": warehouse_id,
        "sort": sort,
        "include_zero": include_zero,
    }
