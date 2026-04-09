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

from .models import Product, ProductCategory, ProductLot, StockMovement, Warehouse

CATEGORY_FILTER_MAX_LEVELS = 4
STOCK_PAGE_SIZE = 100


def _parse_bool_query_param(value):
    return (value or "").strip().lower() in {"1", "true", "on", "yes", "oui"}


def _build_category_path_ids(category):
    path = []
    current = category
    visited_ids = set()
    while current is not None:
        current_id = getattr(current, "id", None)
        if current_id is None or current_id in visited_ids:
            break
        visited_ids.add(current_id)
        path.append(str(current_id))
        current = getattr(current, "parent", None)
    path.reverse()
    return path[-CATEGORY_FILTER_MAX_LEVELS:]


def _build_category_filter_context(*, selected_category_id):
    categories = list(
        ProductCategory.objects.select_related(
            "parent",
            "parent__parent",
            "parent__parent__parent",
        ).order_by("name", "id")
    )
    category_labels_by_id = {}
    category_paths_by_id = {}
    for category in categories:
        category_id = str(category.id)
        category_labels_by_id[category_id] = category.name
        category_paths_by_id[category_id] = _build_category_path_ids(category)

    selected_category_key = str(selected_category_id or "").strip()
    selected_category_path = category_paths_by_id.get(selected_category_key, [])
    descendant_category_ids = [
        int(category_id)
        for category_id, path in category_paths_by_id.items()
        if selected_category_path and path[: len(selected_category_path)] == selected_category_path
    ]
    category_filter_max_depth = min(
        max((len(path) for path in category_paths_by_id.values()), default=0),
        CATEGORY_FILTER_MAX_LEVELS,
    )
    return {
        "categories": categories,
        "category_labels_by_id": category_labels_by_id,
        "category_paths_by_id": category_paths_by_id,
        "category_filter_max_depth": category_filter_max_depth,
        "selected_category_path": selected_category_path,
        "descendant_category_ids": descendant_category_ids,
    }


def build_stock_context(request):
    query = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    warehouse_id = (request.GET.get("warehouse") or "").strip()
    sort = (request.GET.get("sort") or "name").strip()
    page_number = (request.GET.get("page") or "1").strip()
    include_zero = _parse_bool_query_param(request.GET.get("include_zero"))
    category_filter_context = _build_category_filter_context(selected_category_id=category_id)

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
