from django.db.models import F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from wms.domain.dto import PackCartonInput, ReceiveStockInput
from wms.domain.orders import prepare_order, reserve_stock_for_order
from wms.domain.stock import StockError, pack_carton_from_input, receive_stock_from_input
from wms.models import Order, Product, ProductLotStatus

from .serializers import (
    OrderSerializer,
    PackCartonSerializer,
    ProductSerializer,
    ReceiveStockSerializer,
)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)
        query = (self.request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(sku__icontains=query)
                | Q(barcode__icontains=query)
                | Q(brand__icontains=query)
            )
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
        ).order_by("name")
        return queryset


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    queryset = Order.objects.prefetch_related("lines__product").all().order_by("-created_at")

    @action(detail=True, methods=["post"])
    def reserve(self, request, pk=None):
        order = self.get_object()
        try:
            reserve_stock_for_order(order=order)
        except StockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        return Response({"order_id": order.id, "status": order.status})

    @action(detail=True, methods=["post"])
    def prepare(self, request, pk=None):
        order = self.get_object()
        try:
            prepare_order(user=request.user, order=order)
        except StockError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        return Response({"order_id": order.id, "status": order.status})


class ReceiveStockView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReceiveStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = ReceiveStockInput(**serializer.validated_data)
        try:
            lot = receive_stock_from_input(user=request.user, payload=payload)
        except (StockError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "lot_id": lot.id,
                "product_id": lot.product_id,
                "quantity": lot.quantity_on_hand,
                "location_id": lot.location_id,
            },
            status=status.HTTP_201_CREATED,
        )


class PackCartonView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PackCartonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = PackCartonInput(**serializer.validated_data)
        try:
            carton = pack_carton_from_input(user=request.user, payload=payload)
        except (StockError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "carton_id": carton.id,
                "carton_code": carton.code,
                "status": carton.status,
            },
            status=status.HTTP_201_CREATED,
        )
