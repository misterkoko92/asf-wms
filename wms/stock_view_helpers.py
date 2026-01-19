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


def build_stock_context(request):
    query = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    warehouse_id = (request.GET.get("warehouse") or "").strip()
    sort = (request.GET.get("sort") or "name").strip()

    products = Product.objects.filter(is_active=True).select_related("category")
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)

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
        stock_lots.values("product_id")
        .annotate(total=Sum(available_expr))
        .values("total")
    )

    movements = StockMovement.objects.filter(product_id=OuterRef("pk"))
    if warehouse_id:
        movements = movements.filter(
            Q(to_location__warehouse_id=warehouse_id)
            | Q(from_location__warehouse_id=warehouse_id)
        )
    last_movement_subquery = (
        movements.values("product_id")
        .annotate(last=Max("created_at"))
        .values("last")
    )

    products = products.annotate(
        stock_total=Coalesce(
            Subquery(stock_total_subquery, output_field=IntegerField()),
            0,
        ),
        last_movement_at=Subquery(
            last_movement_subquery, output_field=DateTimeField()
        ),
    ).filter(stock_total__gt=0)

    sort_map = {
        "name": "name",
        "sku": "sku",
        "qty_desc": "-stock_total",
        "qty_asc": "stock_total",
        "category": "category__name",
    }
    products = products.order_by(sort_map.get(sort, "name"), "name")

    categories = ProductCategory.objects.all().order_by("name")
    warehouses = Warehouse.objects.all().order_by("name")

    return {
        "active": "stock",
        "products": products,
        "categories": categories,
        "warehouses": warehouses,
        "query": query,
        "category_id": category_id,
        "warehouse_id": warehouse_id,
        "sort": sort,
    }
