from decimal import Decimal

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


class ProductAccessPermission(IsAuthenticated):
    def has_permission(self, request, view):
        api_key = getattr(settings, "INTEGRATION_API_KEY", "").strip()
        request_key = request.headers.get("X-ASF-Integration-Key", "").strip()
        if api_key and request_key == api_key:
            return True
        return bool(request.user and request.user.is_authenticated)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [ProductAccessPermission]

    def get_queryset(self):
        def parse_bool(value):
            if value is None:
                return None
            text = str(value).strip().lower()
            if text in {"1", "true", "yes", "y", "oui"}:
                return True
            if text in {"0", "false", "no", "n", "non"}:
                return False
            return None

        def parse_int(value):
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def parse_decimal(value):
            if value is None:
                return None
            try:
                return Decimal(str(value).replace(",", "."))
            except (TypeError, ValueError, ArithmeticError):
                return None

        queryset = Product.objects.all()
        active_param = parse_bool(self.request.query_params.get("is_active"))
        if active_param is None:
            queryset = queryset.filter(is_active=True)
        else:
            queryset = queryset.filter(is_active=active_param)

        query = (self.request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(sku__icontains=query)
                | Q(barcode__icontains=query)
                | Q(brand__icontains=query)
            )

        name = (self.request.query_params.get("name") or "").strip()
        if name:
            queryset = queryset.filter(name__icontains=name)

        brand = (self.request.query_params.get("brand") or "").strip()
        if brand:
            queryset = queryset.filter(brand__icontains=brand)

        sku = (self.request.query_params.get("sku") or "").strip()
        if sku:
            queryset = queryset.filter(sku__icontains=sku)

        barcode = (self.request.query_params.get("barcode") or "").strip()
        if barcode:
            queryset = queryset.filter(barcode__icontains=barcode)

        ean = (self.request.query_params.get("ean") or "").strip()
        if ean:
            queryset = queryset.filter(ean__icontains=ean)

        color = (self.request.query_params.get("color") or "").strip()
        if color:
            queryset = queryset.filter(color__icontains=color)

        category_name = (self.request.query_params.get("category") or "").strip()
        if category_name:
            queryset = queryset.filter(category__name__icontains=category_name)

        category_id = parse_int(self.request.query_params.get("category_id"))
        if category_id is not None:
            queryset = queryset.filter(category_id=category_id)

        tag_name = (self.request.query_params.get("tag") or "").strip()
        if tag_name:
            queryset = queryset.filter(tags__name__icontains=tag_name)

        tag_id = parse_int(self.request.query_params.get("tag_id"))
        if tag_id is not None:
            queryset = queryset.filter(tags__id=tag_id)

        storage_conditions = (self.request.query_params.get("storage_conditions") or "").strip()
        if storage_conditions:
            queryset = queryset.filter(storage_conditions__icontains=storage_conditions)

        notes = (self.request.query_params.get("notes") or "").strip()
        if notes:
            queryset = queryset.filter(notes__icontains=notes)

        perishable = parse_bool(self.request.query_params.get("perishable"))
        if perishable is not None:
            queryset = queryset.filter(perishable=perishable)

        quarantine_default = parse_bool(self.request.query_params.get("quarantine_default"))
        if quarantine_default is not None:
            queryset = queryset.filter(quarantine_default=quarantine_default)

        default_location_id = parse_int(self.request.query_params.get("default_location_id"))
        if default_location_id is not None:
            queryset = queryset.filter(default_location_id=default_location_id)

        pu_ht = parse_decimal(self.request.query_params.get("pu_ht"))
        if pu_ht is not None:
            queryset = queryset.filter(pu_ht=pu_ht)

        tva = parse_decimal(self.request.query_params.get("tva"))
        if tva is not None:
            queryset = queryset.filter(tva=tva)

        pu_ttc = parse_decimal(self.request.query_params.get("pu_ttc"))
        if pu_ttc is not None:
            queryset = queryset.filter(pu_ttc=pu_ttc)

        weight_g = parse_int(self.request.query_params.get("weight_g"))
        if weight_g is not None:
            queryset = queryset.filter(weight_g=weight_g)

        volume_cm3 = parse_int(self.request.query_params.get("volume_cm3"))
        if volume_cm3 is not None:
            queryset = queryset.filter(volume_cm3=volume_cm3)

        length_cm = parse_decimal(self.request.query_params.get("length_cm"))
        if length_cm is not None:
            queryset = queryset.filter(length_cm=length_cm)

        width_cm = parse_decimal(self.request.query_params.get("width_cm"))
        if width_cm is not None:
            queryset = queryset.filter(width_cm=width_cm)

        height_cm = parse_decimal(self.request.query_params.get("height_cm"))
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

        available_stock = parse_int(self.request.query_params.get("available_stock"))
        if available_stock is not None:
            queryset = queryset.filter(available_stock=available_stock)

        return queryset.order_by("name")
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
