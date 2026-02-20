from django.db.models import Count
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
from wms.emailing import EMAIL_QUEUE_EVENT_TYPE, EMAIL_QUEUE_SOURCE
from wms.models import (
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Order,
    Product,
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
from .permissions import IntegrationKeyOrAuth, IntegrationKeyOrStaff
from .product_filters import apply_product_filters
from .integration_filters import (
    apply_integration_destination_filters,
    apply_integration_event_filters,
    apply_integration_shipment_filters,
)


class ProductAccessPermission(IntegrationKeyOrAuth):
    pass


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [ProductAccessPermission]

    def get_queryset(self):
        queryset = Product.objects.all()
        return apply_product_filters(queryset, self.request.query_params)


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


class IntegrationPermission(IntegrationKeyOrStaff):
    pass


class IntegrationShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationShipmentSerializer
    permission_classes = [IntegrationPermission]

    def get_queryset(self):
        queryset = (
            Shipment.objects.select_related("destination")
            .annotate(carton_count=Count("carton"))
            .all()
        )
        queryset = apply_integration_shipment_filters(
            queryset, self.request.query_params
        )
        return queryset.order_by("-created_at")


class IntegrationDestinationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationDestinationSerializer
    permission_classes = [IntegrationPermission]

    def get_queryset(self):
        queryset = Destination.objects.select_related("correspondent_contact").all()
        queryset = apply_integration_destination_filters(
            queryset, self.request.query_params
        )
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
        return apply_integration_event_filters(queryset, self.request.query_params)

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
        event = serializer.instance
        if (
            event.direction == IntegrationDirection.OUTBOUND
            and event.source == EMAIL_QUEUE_SOURCE
            and event.event_type == EMAIL_QUEUE_EVENT_TYPE
        ):
            raise ValidationError(
                {
                    "detail": (
                        "Outbound email queue events are read-only via this API."
                    )
                }
            )
        status_value = serializer.validated_data.get("status")
        processed_at = serializer.validated_data.get("processed_at")
        if status_value == IntegrationStatus.PROCESSED and processed_at is None:
            serializer.save(processed_at=timezone.now())
        else:
            serializer.save()
