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
    ShipmentWorkflowProjection,
)
from wms.workflow_projection import build_destination_workflow_projection_rows

from .integration_filters import (
    apply_integration_destination_filters,
    apply_integration_event_filters,
    apply_integration_shipment_filters,
)
from .permissions import IntegrationKeyOrAuth, IntegrationKeyOrStaff
from .product_filters import apply_product_filters
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


def _normalize_query_param(params, key):
    return (params.get(key) or "").strip()


def _parse_bool_query_param(raw_value):
    value = (raw_value or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_datetime_query_param(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = timezone.datetime.fromisoformat(value)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _apply_workflow_projection_filters(queryset, params):
    destination_id = _normalize_query_param(params, "destination_id")
    if destination_id:
        queryset = queryset.filter(destination_id=destination_id)
    shipment_status = _normalize_query_param(params, "shipment_status")
    if shipment_status:
        queryset = queryset.filter(shipment_status=shipment_status)
    current_segment = _normalize_query_param(params, "current_segment")
    if current_segment:
        queryset = queryset.filter(current_segment=current_segment)
    delay_state = _normalize_query_param(params, "delay_state")
    if delay_state:
        queryset = queryset.filter(delay_state=delay_state)
    has_open_dispute = _parse_bool_query_param(params.get("has_open_dispute"))
    if has_open_dispute is not None:
        queryset = queryset.filter(has_open_dispute=has_open_dispute)
    is_closed = _parse_bool_query_param(params.get("is_closed"))
    if is_closed is not None:
        queryset = queryset.filter(is_closed=is_closed)
    projected_since = _parse_datetime_query_param(params.get("projected_since"))
    if projected_since is not None:
        queryset = queryset.filter(projected_at__gte=projected_since)
    return queryset


class IntegrationShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationShipmentSerializer
    permission_classes = [IntegrationPermission]

    def get_queryset(self):
        queryset = (
            Shipment.objects.select_related("destination")
            .annotate(carton_count=Count("carton"))
            .all()
        )
        queryset = apply_integration_shipment_filters(queryset, self.request.query_params)
        return queryset.order_by("-created_at")


class IntegrationDestinationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationDestinationSerializer
    permission_classes = [IntegrationPermission]

    def get_queryset(self):
        queryset = Destination.objects.select_related("correspondent_contact").all()
        queryset = apply_integration_destination_filters(queryset, self.request.query_params)
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
                {"detail": ("Outbound email queue events are read-only via this API.")}
            )
        status_value = serializer.validated_data.get("status")
        processed_at = serializer.validated_data.get("processed_at")
        if status_value == IntegrationStatus.PROCESSED and processed_at is None:
            serializer.save(processed_at=timezone.now())
        else:
            serializer.save()


class WorkflowProjectionShipmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = ShipmentWorkflowProjection.objects.select_related(
            "shipment", "destination"
        ).all()
        queryset = _apply_workflow_projection_filters(queryset, request.query_params)
        rows = list(
            queryset.order_by("reference", "shipment_id").values(
                "shipment_id",
                "reference",
                "tracking_token",
                "destination_id",
                "destination_label",
                "shipment_status",
                "shipment_created_at",
                "planned_at",
                "boarding_ok_at",
                "received_correspondent_at",
                "delivered_at",
                "closed_at",
                "current_segment",
                "segment_started_at",
                "segment_age_hours",
                "is_closed",
                "lead_hours_planned_to_boarding",
                "lead_hours_boarding_to_correspondent",
                "lead_hours_correspondent_to_delivery",
                "lead_hours_delivery_to_close",
                "lead_hours_total_to_delivery",
                "has_open_dispute",
                "dispute_reason",
                "dispute_owner",
                "dispute_opened_at",
                "dispute_resolved_at",
                "dispute_resolution_hours",
                "delay_state",
                "current_delay_hours",
                "active_blockage_category",
                "projected_at",
            )
        )
        return Response(rows)


class WorkflowProjectionDestinationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = ShipmentWorkflowProjection.objects.select_related("destination").all()
        queryset = _apply_workflow_projection_filters(queryset, request.query_params)
        rows = build_destination_workflow_projection_rows(queryset)
        return Response(rows)
