from django.db import connection, transaction
from django.db.models import F, IntegerField, Q, Sum, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from wms.carton_status_events import set_carton_status
from wms.forms import ScanOutForm, ScanShipmentForm, ScanStockUpdateForm, ShipmentTrackingForm
from wms.models import (
    Carton,
    CartonStatus,
    MovementType,
    Order,
    OrderReviewStatus,
    Product,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
)
from wms.portal_helpers import get_association_profile
from wms.runtime_settings import get_runtime_config
from wms.scan_shipment_handlers import LOCKED_SHIPMENT_STATUSES
from wms.scan_shipment_helpers import resolve_shipment
from wms.scan_product_helpers import resolve_product
from wms.services import StockError, consume_stock, pack_carton, pack_carton_from_reserved, receive_stock
from wms.shipment_helpers import build_destination_label, parse_shipment_lines
from wms.shipment_form_helpers import build_shipment_form_payload
from wms.shipment_status import sync_shipment_ready_state
from wms.shipment_tracking_handlers import (
    TRACKING_TO_SHIPMENT_STATUS,
    allowed_tracking_statuses_for_shipment,
    validate_tracking_transition,
)
from wms.stock_view_helpers import build_stock_context
from wms.views_scan_shipments_support import (
    _build_shipments_tracking_queryset,
    _shipment_can_be_closed,
)
from wms.workflow_observability import log_shipment_case_closed

from .permissions import IsAssociationProfileUser, IsStaffUser
from .serializers import (
    UiShipmentMutationSerializer,
    UiShipmentTrackingEventSerializer,
    UiStockOutSerializer,
    UiStockUpdateSerializer,
)
from .ui_api_errors import api_error, form_error_payload, serializer_field_errors


def _stock_state(quantity: int, low_stock_threshold: int) -> str:
    critical_threshold = max(1, low_stock_threshold // 2)
    if quantity <= 0:
        return "empty"
    if quantity < critical_threshold:
        return "critical"
    if quantity < low_stock_threshold:
        return "low"
    return "ok"


def _build_low_stock_rows(*, low_stock_threshold: int, limit: int = 5):
    available_qty_expr = ExpressionWrapper(
        F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
        output_field=IntegerField(),
    )
    queryset = (
        Product.objects.filter(is_active=True)
        .annotate(
            available_qty=Coalesce(
                Sum(
                    available_qty_expr,
                    filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
                ),
                0,
                output_field=IntegerField(),
            )
        )
        .filter(available_qty__lt=low_stock_threshold)
        .order_by("available_qty", "name")
    )
    return list(queryset.values("id", "sku", "name", "available_qty")[:limit])


def _shipment_payload(shipment):
    return {
        "id": shipment.id,
        "reference": shipment.reference,
        "status": shipment.status,
        "status_label": shipment.get_status_display(),
        "tracking_token": str(shipment.tracking_token),
        "is_disputed": shipment.is_disputed,
        "closed_at": shipment.closed_at.isoformat() if shipment.closed_at else None,
    }


def _shipment_form_data(validated_data, line_count):
    destination = str(validated_data["destination"])
    return {
        "destination": destination,
        "shipper_contact": str(validated_data["shipper_contact"]),
        "recipient_contact": str(validated_data["recipient_contact"]),
        "correspondent_contact": str(validated_data["correspondent_contact"]),
        "carton_count": str(line_count),
    }, destination


def _line_data_from_payload(lines):
    data = {}
    for index, line in enumerate(lines, start=1):
        prefix = f"line_{index}_"
        carton_id = line.get("carton_id")
        quantity = line.get("quantity")
        data[prefix + "carton_id"] = str(carton_id) if carton_id else ""
        data[prefix + "product_code"] = (line.get("product_code") or "").strip()
        data[prefix + "quantity"] = str(quantity) if quantity is not None else ""
    return data


def _allowed_carton_ids(*, shipment=None):
    _products, available_cartons, _destinations, _shipper, _recipient, _correspondent = (
        build_shipment_form_payload()
    )
    ids = {str(carton["id"]) for carton in available_cartons}
    if shipment is not None:
        ids.update(str(carton_id) for carton_id in shipment.carton_set.values_list("id", flat=True))
    return ids


class UiDashboardView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        runtime = get_runtime_config()
        low_stock_threshold = runtime.low_stock_threshold

        destination_id = (request.GET.get("destination") or "").strip()
        shipments_qs = Shipment.objects.filter(archived_at__isnull=True)
        if destination_id:
            shipments_qs = shipments_qs.filter(destination_id=destination_id)

        open_shipments_qs = shipments_qs.filter(closed_at__isnull=True)
        disputed_qs = open_shipments_qs.filter(is_disputed=True)
        delayed_qs = open_shipments_qs.filter(
            status__in=[
                ShipmentStatus.PICKING,
                ShipmentStatus.PACKED,
                ShipmentStatus.PLANNED,
                ShipmentStatus.SHIPPED,
                ShipmentStatus.RECEIVED_CORRESPONDENT,
            ]
        )

        kpis = {
            "open_shipments": open_shipments_qs.count(),
            "stock_alerts": len(
                _build_low_stock_rows(
                    low_stock_threshold=low_stock_threshold,
                    limit=20,
                )
            ),
            "open_disputes": disputed_qs.count(),
            "pending_orders": Order.objects.filter(
                review_status=OrderReviewStatus.PENDING
            ).count(),
            "shipments_delayed": delayed_qs.count(),
        }

        timeline_events = (
            ShipmentTrackingEvent.objects.select_related("shipment")
            .order_by("-created_at")[:8]
        )
        timeline = [
            {
                "id": event.id,
                "shipment_id": event.shipment_id,
                "reference": event.shipment.reference or f"EXP-{event.shipment_id}",
                "status": event.get_status_display(),
                "timestamp": event.created_at.isoformat(),
                "comments": event.comments or "",
            }
            for event in timeline_events
        ]

        pending_actions = []
        for row in _build_low_stock_rows(
            low_stock_threshold=low_stock_threshold,
            limit=3,
        ):
            pending_actions.append(
                {
                    "type": "stock_replenish",
                    "reference": row["sku"],
                    "label": f"Reappro {row['name']}",
                    "priority": "high",
                    "owner": "magasin",
                }
            )
        for shipment in disputed_qs.order_by("-created_at")[:3]:
            pending_actions.append(
                {
                    "type": "shipment_dispute",
                    "reference": shipment.reference or f"EXP-{shipment.id}",
                    "label": "Resoudre litige",
                    "priority": "high",
                    "owner": "qualite",
                }
            )
        for order in (
            Order.objects.filter(review_status=OrderReviewStatus.PENDING)
            .order_by("-created_at")[:3]
        ):
            pending_actions.append(
                {
                    "type": "order_review",
                    "reference": order.reference or f"CMD-{order.id}",
                    "label": "Valider commande",
                    "priority": "medium",
                    "owner": "admin",
                }
            )

        return Response(
            {
                "kpis": kpis,
                "timeline": timeline,
                "pending_actions": pending_actions[:10],
                "filters": {"destination": destination_id},
                "updated_at": timezone.now().isoformat(),
            }
        )


class UiStockView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        runtime = get_runtime_config()
        context = build_stock_context(request)
        products_qs = context["products"].select_related(
            "category",
            "default_location__warehouse",
        )
        products = [
            {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "brand": product.brand or "",
                "category_id": product.category_id,
                "category_name": product.category.name if product.category else "",
                "location": str(product.default_location)
                if product.default_location_id
                else "",
                "stock_total": int(product.stock_total or 0),
                "last_movement_at": (
                    product.last_movement_at.isoformat()
                    if product.last_movement_at
                    else None
                ),
                "state": _stock_state(
                    int(product.stock_total or 0),
                    runtime.low_stock_threshold,
                ),
            }
            for product in products_qs
        ]
        categories = [
            {"id": category.id, "name": category.name}
            for category in context["categories"]
        ]
        warehouses = [
            {"id": warehouse.id, "name": warehouse.name}
            for warehouse in context["warehouses"]
        ]
        return Response(
            {
                "filters": {
                    "q": context["query"],
                    "category": context["category_id"],
                    "warehouse": context["warehouse_id"],
                    "sort": context["sort"],
                },
                "meta": {
                    "total_products": len(products),
                    "low_stock_threshold": runtime.low_stock_threshold,
                },
                "products": products,
                "categories": categories,
                "warehouses": warehouses,
            }
        )


class UiStockUpdateView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request):
        serializer = UiStockUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation stock invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )
        validated = serializer.validated_data
        form = ScanStockUpdateForm(
            {
                "product_code": validated["product_code"],
                "quantity": validated["quantity"],
                "expires_on": validated["expires_on"],
                "lot_code": validated.get("lot_code", ""),
                "donor_contact": validated.get("donor_contact_id") or "",
            }
        )
        if not form.is_valid():
            field_errors, non_field_errors = form_error_payload(form)
            return api_error(
                message="Validation stock invalide.",
                code="validation_error",
                field_errors=field_errors,
                non_field_errors=non_field_errors,
            )
        product = getattr(form, "product", None)
        location = product.default_location if product else None
        if location is None:
            return api_error(
                message="Emplacement requis pour ce produit.",
                code="missing_default_location",
                non_field_errors=["Emplacement requis pour ce produit."],
            )
        donor_contact = form.cleaned_data.get("donor_contact")
        source_receipt = None
        try:
            if donor_contact:
                source_receipt = Receipt.objects.create(
                    receipt_type=ReceiptType.DONATION,
                    status=ReceiptStatus.RECEIVED,
                    source_contact=donor_contact,
                    received_on=timezone.localdate(),
                    warehouse=location.warehouse,
                    created_by=request.user,
                    notes="Auto MAJ stock (api/ui)",
                )
            lot = receive_stock(
                user=request.user,
                product=product,
                quantity=form.cleaned_data["quantity"],
                location=location,
                lot_code=form.cleaned_data["lot_code"] or "",
                received_on=timezone.localdate(),
                expires_on=form.cleaned_data["expires_on"],
                source_receipt=source_receipt,
            )
        except StockError as exc:
            return api_error(
                message=str(exc),
                code="stock_update_failed",
                non_field_errors=[str(exc)],
            )

        return Response(
            {
                "ok": True,
                "message": "Stock mis a jour.",
                "lot_id": lot.id,
                "product_id": lot.product_id,
                "quantity_on_hand": lot.quantity_on_hand,
                "location_id": lot.location_id,
                "receipt_id": source_receipt.id if source_receipt else None,
            },
            status=status.HTTP_201_CREATED,
        )


class UiStockOutView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request):
        serializer = UiStockOutSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation sortie stock invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )
        validated = serializer.validated_data
        form = ScanOutForm(
            {
                "product_code": validated["product_code"],
                "quantity": validated["quantity"],
                "shipment_reference": validated.get("shipment_reference", ""),
                "reason_code": validated.get("reason_code", ""),
                "reason_notes": validated.get("reason_notes", ""),
            }
        )
        if not form.is_valid():
            field_errors, non_field_errors = form_error_payload(form)
            return api_error(
                message="Validation sortie stock invalide.",
                code="validation_error",
                field_errors=field_errors,
                non_field_errors=non_field_errors,
            )

        product = resolve_product(form.cleaned_data["product_code"])
        if not product:
            return api_error(
                message="Produit introuvable.",
                code="product_not_found",
                field_errors={"product_code": ["Produit introuvable."]},
            )
        shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
        if form.cleaned_data["shipment_reference"] and not shipment:
            return api_error(
                message="Expedition introuvable.",
                code="shipment_not_found",
                field_errors={"shipment_reference": ["Expedition introuvable."]},
            )

        try:
            with transaction.atomic():
                consume_stock(
                    user=request.user,
                    product=product,
                    quantity=form.cleaned_data["quantity"],
                    movement_type=MovementType.OUT,
                    shipment=shipment,
                    reason_code=form.cleaned_data["reason_code"] or "scan_out",
                    reason_notes=form.cleaned_data["reason_notes"] or "",
                )
        except StockError as exc:
            return api_error(
                message=str(exc),
                code="stock_out_failed",
                non_field_errors=[str(exc)],
            )

        return Response(
            {
                "ok": True,
                "message": "Sortie stock enregistree.",
                "product_id": product.id,
                "shipment_id": shipment.id if shipment else None,
                "quantity": form.cleaned_data["quantity"],
            },
            status=status.HTTP_201_CREATED,
        )


class UiShipmentFormOptionsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        (
            product_options,
            available_cartons,
            destinations,
            shipper_contacts,
            recipient_contacts,
            correspondent_contacts,
        ) = build_shipment_form_payload()
        return Response(
            {
                "products": product_options,
                "available_cartons": available_cartons,
                "destinations": destinations,
                "shipper_contacts": shipper_contacts,
                "recipient_contacts": recipient_contacts,
                "correspondent_contacts": correspondent_contacts,
            }
        )


class UiShipmentCreateView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request):
        serializer = UiShipmentMutationSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation expedition invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        line_count = len(payload["lines"])
        form_data, destination_id = _shipment_form_data(payload, line_count)
        form = ScanShipmentForm(form_data, destination_id=destination_id)
        if not form.is_valid():
            field_errors, non_field_errors = form_error_payload(form)
            return api_error(
                message="Validation expedition invalide.",
                code="validation_error",
                field_errors=field_errors,
                non_field_errors=non_field_errors,
            )

        line_data = _line_data_from_payload(payload["lines"])
        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=line_count,
            data=line_data,
            allowed_carton_ids=_allowed_carton_ids(),
        )
        if line_errors:
            return api_error(
                message="Certaines lignes expedition sont invalides.",
                code="line_validation_error",
                field_errors={"lines": ["Certaines lignes expedition sont invalides."]},
                extra={
                    "line_values": line_values,
                    "line_errors": line_errors,
                },
            )

        try:
            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = form.cleaned_data["correspondent_contact"]
                shipment = Shipment.objects.create(
                    status=ShipmentStatus.DRAFT,
                    shipper_name=shipper_contact.name,
                    shipper_contact_ref=shipper_contact,
                    recipient_name=recipient_contact.name,
                    recipient_contact_ref=recipient_contact,
                    correspondent_name=correspondent_contact.name,
                    correspondent_contact_ref=correspondent_contact,
                    destination=destination,
                    destination_address=build_destination_label(destination),
                    destination_country=destination.country,
                    created_by=request.user,
                )
                for item in line_items:
                    carton_id = item.get("carton_id")
                    if carton_id:
                        carton_query = Carton.objects.filter(
                            id=carton_id,
                            status=CartonStatus.PACKED,
                            shipment__isnull=True,
                        )
                        if connection.features.has_select_for_update:
                            carton_query = carton_query.select_for_update()
                        carton = carton_query.first()
                        if carton is None:
                            raise StockError("Carton indisponible.")
                        carton.shipment = shipment
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            update_fields=["shipment"],
                            reason="shipment_create_assign",
                            user=getattr(request, "user", None),
                        )
                        continue
                    carton = pack_carton(
                        user=request.user,
                        product=item["product"],
                        quantity=item["quantity"],
                        carton=None,
                        carton_code=None,
                        shipment=shipment,
                    )
                    set_carton_status(
                        carton=carton,
                        new_status=CartonStatus.ASSIGNED,
                        reason="shipment_create_pack_assign",
                        user=getattr(request, "user", None),
                    )
            sync_shipment_ready_state(shipment)
        except StockError as exc:
            return api_error(
                message=str(exc),
                code="shipment_create_failed",
                non_field_errors=[str(exc)],
            )

        return Response(
            {
                "ok": True,
                "message": "Expedition creee.",
                "shipment": _shipment_payload(shipment),
                "line_count": line_count,
            },
            status=status.HTTP_201_CREATED,
        )


class UiShipmentUpdateView(APIView):
    permission_classes = [IsStaffUser]

    def patch(self, request, shipment_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True),
            pk=shipment_id,
        )
        if shipment.status in LOCKED_SHIPMENT_STATUSES:
            return api_error(
                message="Expedition verrouillee: modification impossible.",
                code="shipment_locked",
                http_status=status.HTTP_409_CONFLICT,
            )
        if shipment.is_disputed:
            return api_error(
                message="Expedition en litige: modification impossible.",
                code="shipment_disputed",
                http_status=status.HTTP_409_CONFLICT,
            )

        serializer = UiShipmentMutationSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation expedition invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        line_count = len(payload["lines"])
        form_data, destination_id = _shipment_form_data(payload, line_count)
        form = ScanShipmentForm(form_data, destination_id=destination_id)
        if not form.is_valid():
            field_errors, non_field_errors = form_error_payload(form)
            return api_error(
                message="Validation expedition invalide.",
                code="validation_error",
                field_errors=field_errors,
                non_field_errors=non_field_errors,
            )

        line_data = _line_data_from_payload(payload["lines"])
        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=line_count,
            data=line_data,
            allowed_carton_ids=_allowed_carton_ids(shipment=shipment),
        )
        if line_errors:
            return api_error(
                message="Certaines lignes expedition sont invalides.",
                code="line_validation_error",
                field_errors={"lines": ["Certaines lignes expedition sont invalides."]},
                extra={
                    "line_values": line_values,
                    "line_errors": line_errors,
                },
            )

        try:
            related_order = None
            try:
                related_order = shipment.order
            except Shipment.order.RelatedObjectDoesNotExist:
                related_order = None

            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = form.cleaned_data["correspondent_contact"]

                shipment.destination = destination
                shipment.shipper_name = shipper_contact.name
                shipment.shipper_contact_ref = shipper_contact
                shipment.recipient_name = recipient_contact.name
                shipment.recipient_contact_ref = recipient_contact
                shipment.correspondent_name = correspondent_contact.name
                shipment.correspondent_contact_ref = correspondent_contact
                shipment.destination_address = build_destination_label(destination)
                shipment.destination_country = destination.country
                shipment.save(
                    update_fields=[
                        "destination",
                        "shipper_name",
                        "shipper_contact_ref",
                        "recipient_name",
                        "recipient_contact_ref",
                        "correspondent_name",
                        "correspondent_contact_ref",
                        "destination_address",
                        "destination_country",
                    ]
                )

                order_lines_by_product = {}
                if related_order is not None:
                    order_lines_by_product = {
                        line.product_id: line
                        for line in related_order.lines.select_related("product").all()
                    }

                selected_carton_ids = {
                    item["carton_id"] for item in line_items if "carton_id" in item
                }
                cartons_to_remove = shipment.carton_set.exclude(id__in=selected_carton_ids)
                for carton in cartons_to_remove:
                    if carton.status == CartonStatus.SHIPPED:
                        raise StockError("Impossible de retirer un carton expedie.")
                    carton.shipment = None
                    if carton.status in {CartonStatus.ASSIGNED, CartonStatus.LABELED}:
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.PACKED,
                            update_fields=["shipment"],
                            reason="shipment_edit_unassign",
                            user=getattr(request, "user", None),
                        )
                    else:
                        carton.save(update_fields=["shipment"])

                for carton_id in selected_carton_ids:
                    carton_query = Carton.objects.filter(id=carton_id)
                    if connection.features.has_select_for_update:
                        carton_query = carton_query.select_for_update()
                    carton = carton_query.first()
                    if carton is None:
                        raise StockError("Carton introuvable.")
                    if carton.shipment_id and carton.shipment_id != shipment.id:
                        raise StockError("Carton indisponible.")
                    if carton.shipment_id != shipment.id and carton.status != CartonStatus.PACKED:
                        raise StockError("Carton indisponible.")
                    if carton.shipment_id != shipment.id:
                        carton.shipment = shipment
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            update_fields=["shipment"],
                            reason="shipment_edit_assign_existing",
                            user=getattr(request, "user", None),
                        )
                    elif carton.status == CartonStatus.PACKED:
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            reason="shipment_edit_reassign",
                            user=getattr(request, "user", None),
                        )

                for item in line_items:
                    if "product" not in item:
                        continue
                    if related_order is not None:
                        order_line = order_lines_by_product.get(item["product"].id)
                        if order_line is None:
                            raise StockError("Produit non present dans la commande liee.")
                        if item["quantity"] > order_line.remaining_quantity:
                            raise StockError(
                                f"{item['product'].name}: quantite demandee superieure au reliquat de la commande."
                            )
                        carton = pack_carton_from_reserved(
                            user=request.user,
                            line=order_line,
                            quantity=item["quantity"],
                            carton=None,
                            shipment=shipment,
                        )
                    else:
                        carton = pack_carton(
                            user=request.user,
                            product=item["product"],
                            quantity=item["quantity"],
                            carton=None,
                            carton_code=None,
                            shipment=shipment,
                        )
                    set_carton_status(
                        carton=carton,
                        new_status=CartonStatus.ASSIGNED,
                        reason="shipment_edit_pack_assign",
                        user=getattr(request, "user", None),
                    )
            sync_shipment_ready_state(shipment)
        except StockError as exc:
            return api_error(
                message=str(exc),
                code="shipment_update_failed",
                non_field_errors=[str(exc)],
            )

        return Response(
            {
                "ok": True,
                "message": "Expedition mise a jour.",
                "shipment": _shipment_payload(shipment),
                "line_count": line_count,
            }
        )


class UiShipmentTrackingEventCreateView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request, shipment_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True),
            pk=shipment_id,
        )
        if shipment.is_disputed:
            return api_error(
                message="Expedition en litige: resoudre avant de continuer le suivi.",
                code="shipment_disputed",
                http_status=status.HTTP_409_CONFLICT,
            )

        serializer = UiShipmentTrackingEventSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation suivi invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        allowed_statuses = allowed_tracking_statuses_for_shipment(shipment)
        form = ShipmentTrackingForm(
            serializer.validated_data,
            allowed_statuses=allowed_statuses,
        )
        if not form.is_valid():
            field_errors, non_field_errors = form_error_payload(form)
            return api_error(
                message="Validation suivi invalide.",
                code="validation_error",
                field_errors=field_errors,
                non_field_errors=non_field_errors,
            )

        status_value = form.cleaned_data["status"]
        transition_error = validate_tracking_transition(shipment, status_value)
        if transition_error:
            return api_error(
                message=transition_error,
                code="tracking_transition_invalid",
                field_errors={"status": [transition_error]},
            )

        tracking_event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=status_value,
            actor_name=form.cleaned_data["actor_name"],
            actor_structure=form.cleaned_data["actor_structure"],
            comments=form.cleaned_data["comments"] or "",
            created_by=request.user if request.user.is_authenticated else None,
        )

        target_status = TRACKING_TO_SHIPMENT_STATUS.get(status_value)
        if target_status and shipment.status != target_status:
            shipment.status = target_status
            update_fields = ["status"]
            if target_status == ShipmentStatus.PACKED and shipment.ready_at is None:
                shipment.ready_at = timezone.now()
                update_fields.append("ready_at")
            shipment.save(update_fields=update_fields)
            if target_status == ShipmentStatus.SHIPPED:
                for carton in shipment.carton_set.exclude(status=CartonStatus.SHIPPED):
                    set_carton_status(
                        carton=carton,
                        new_status=CartonStatus.SHIPPED,
                        reason="tracking_boarding_ok",
                        user=getattr(request, "user", None),
                    )

        return Response(
            {
                "ok": True,
                "message": "Suivi mis a jour.",
                "shipment": _shipment_payload(shipment),
                "tracking_event": {
                    "id": tracking_event.id,
                    "status": tracking_event.status,
                    "status_label": tracking_event.get_status_display(),
                    "created_at": tracking_event.created_at.isoformat(),
                    "comments": tracking_event.comments,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class UiShipmentCloseView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request, shipment_id):
        shipment = get_object_or_404(Shipment.objects.filter(archived_at__isnull=True), pk=shipment_id)
        if shipment.closed_at:
            return Response(
                {
                    "ok": True,
                    "message": "Dossier deja cloture.",
                    "shipment": _shipment_payload(shipment),
                }
            )
        tracking_row = _build_shipments_tracking_queryset().filter(pk=shipment_id).first()
        if tracking_row is None or not _shipment_can_be_closed(tracking_row):
            return api_error(
                message="Il reste des etapes a valider avant cloture.",
                code="shipment_close_blocked",
                http_status=status.HTTP_409_CONFLICT,
                non_field_errors=["Il reste des etapes a valider avant cloture."],
            )

        shipment.closed_at = timezone.now()
        shipment.closed_by = request.user if request.user.is_authenticated else None
        shipment.save(update_fields=["closed_at", "closed_by"])
        log_shipment_case_closed(
            shipment=shipment,
            user=request.user if request.user.is_authenticated else None,
        )
        return Response(
            {
                "ok": True,
                "message": "Dossier cloture.",
                "shipment": _shipment_payload(shipment),
            }
        )


class UiPortalDashboardView(APIView):
    permission_classes = [IsAssociationProfileUser]

    def get(self, request):
        profile = get_association_profile(request.user)
        orders_qs = (
            Order.objects.filter(association_contact=profile.contact)
            .select_related("shipment")
            .order_by("-created_at")
        )
        kpis = {
            "orders_total": orders_qs.count(),
            "orders_pending_review": orders_qs.filter(
                review_status=OrderReviewStatus.PENDING
            ).count(),
            "orders_changes_requested": orders_qs.filter(
                review_status=OrderReviewStatus.CHANGES_REQUESTED
            ).count(),
            "orders_with_shipment": orders_qs.filter(shipment__isnull=False).count(),
        }
        rows = [
            {
                "id": order.id,
                "reference": order.reference or f"CMD-{order.id}",
                "review_status": order.review_status,
                "review_status_label": order.get_review_status_display(),
                "shipment_id": order.shipment_id,
                "shipment_reference": (
                    order.shipment.reference if order.shipment_id else ""
                ),
                "requested_delivery_date": (
                    order.requested_delivery_date.isoformat()
                    if order.requested_delivery_date
                    else None
                ),
                "created_at": order.created_at.isoformat(),
            }
            for order in orders_qs[:12]
        ]
        return Response({"kpis": kpis, "orders": rows})
