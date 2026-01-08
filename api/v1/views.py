from django.conf import settings
from django.db.models import Count, F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from wms.domain.dto import PackCartonInput, ReceiveStockInput
from wms.domain.orders import prepare_order, reserve_stock_for_order
from wms.domain.stock import StockError, pack_carton_from_input, receive_stock_from_input
from wms.models import (
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Order,
    Product,
    ProductLotStatus,
    Shipment,
)

from .serializers import (
    IntegrationDestinationSerializer,
    IntegrationEventSerializer,
    IntegrationEventStatusSerializer,
    IntegrationShipmentSerializer,
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


class IntegrationPermission(IsAuthenticated):
    def has_permission(self, request, view):
        api_key = getattr(settings, "INTEGRATION_API_KEY", "").strip()
        request_key = request.headers.get("X-ASF-Integration-Key", "").strip()
        if api_key and request_key == api_key:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IntegrationShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationShipmentSerializer
    permission_classes = [IntegrationPermission]

    def get_queryset(self):
        queryset = (
            Shipment.objects.select_related("destination")
            .annotate(carton_count=Count("carton"))
            .all()
        )
        status_value = (self.request.query_params.get("status") or "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        destination = (self.request.query_params.get("destination") or "").strip()
        if destination:
            queryset = queryset.filter(
                Q(destination__iata_code__iexact=destination)
                | Q(destination__city__icontains=destination)
            )
        since = (self.request.query_params.get("since") or "").strip()
        if since:
            try:
                since_dt = timezone.datetime.fromisoformat(since)
                if timezone.is_naive(since_dt):
                    since_dt = timezone.make_aware(since_dt)
                queryset = queryset.filter(created_at__gte=since_dt)
            except ValueError:
                pass
        return queryset.order_by("-created_at")


class IntegrationDestinationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationDestinationSerializer
    permission_classes = [IntegrationPermission]

    def get_queryset(self):
        queryset = Destination.objects.select_related("correspondent_contact").all()
        active_only = (self.request.query_params.get("active") or "").strip()
        if active_only:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("city")


class IntegrationEventViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = IntegrationEventSerializer
    permission_classes = [IntegrationPermission]
    queryset = IntegrationEvent.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        direction = (self.request.query_params.get("direction") or "").strip()
        if direction:
            queryset = queryset.filter(direction=direction)
        status_value = (self.request.query_params.get("status") or "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        source = (self.request.query_params.get("source") or "").strip()
        if source:
            queryset = queryset.filter(source=source)
        event_type = (self.request.query_params.get("event_type") or "").strip()
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return queryset

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return IntegrationEventStatusSerializer
        return IntegrationEventSerializer

    def perform_create(self, serializer):
        source = (serializer.validated_data.get("source") or "").strip()
        if not source:
            source = (self.request.headers.get("X-ASF-Source") or "").strip()
        if not source:
            raise ValidationError({"source": "source is required"})
        target = (serializer.validated_data.get("target") or "").strip()
        if not target:
            target = (self.request.headers.get("X-ASF-Target") or "").strip()
        serializer.save(
            source=source,
            target=target,
            direction=IntegrationDirection.INBOUND,
            status=IntegrationStatus.PENDING,
        )

    def perform_update(self, serializer):
        status_value = serializer.validated_data.get("status")
        processed_at = serializer.validated_data.get("processed_at")
        if status_value == IntegrationStatus.PROCESSED and processed_at is None:
            serializer.save(processed_at=timezone.now())
        else:
            serializer.save()
