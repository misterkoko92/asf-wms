import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from django.db import connection, transaction
from django.db.models import Count, ExpressionWrapper, F, IntegerField, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Contact, ContactAddress, ContactType
from wms.application.parties.use_cases import (
    update_recipient_shared_profile,
    update_runtime_recipient_shared_profile,
)
from wms.application.pilotage.pilotage_queries import build_scan_pilotage_payload
from wms.application.portal.dashboard_queries import (
    build_portal_dashboard_payload,
    build_recipient_scope_home_payload,
)
from wms.application.scan.dashboard_queries import build_scan_dashboard_payload
from wms.carton_status_events import set_carton_status
from wms.carton_view_helpers import build_cartons_ready_rows, get_carton_capacity_cm3
from wms.document_scan_queue import (
    DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
)
from wms.forms import ScanOutForm, ScanShipmentForm, ScanStockUpdateForm, ShipmentTrackingForm
from wms.models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    AssociationContactTitle,
    AssociationRecipient,
    Carton,
    CartonStatus,
    Destination,
    Document,
    DocumentType,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    MovementType,
    Order,
    OrderReviewStatus,
    PortalAccessGrant,
    PortalAccessRole,
    PrintTemplate,
    PrintTemplateVersion,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    ShipmentWorkflowProjection,
)
from wms.order_notifications import send_portal_order_notifications
from wms.portal_helpers import (
    build_destination_address,
    get_association_profile,
    get_contact_address,
)
from wms.portal_order_handlers import create_portal_order
from wms.portal_recipient_sync import sync_association_recipient_to_contact
from wms.print_layouts import DEFAULT_LAYOUTS, DOCUMENT_TEMPLATES
from wms.runtime_settings import get_runtime_config
from wms.scan_dashboard_destination_risk import build_destination_risk_snapshot
from wms.scan_dashboard_sla import (
    annotate_shipment_tracking_dates,
    build_sla_alert_rows,
    build_sla_rows,
    summarize_sla_alert_rows,
)
from wms.scan_product_helpers import resolve_product
from wms.scan_shipment_handlers import LOCKED_SHIPMENT_STATUSES
from wms.scan_shipment_helpers import resolve_shipment
from wms.services import (
    StockError,
    consume_stock,
    pack_carton,
    pack_carton_from_reserved,
    receive_stock,
)
from wms.shipment_form_helpers import build_shipment_form_payload
from wms.shipment_helpers import build_destination_label, parse_shipment_lines
from wms.shipment_party_snapshot import (
    apply_shipment_party_snapshot,
    build_shipment_party_snapshot_payload,
)
from wms.shipment_status import sync_shipment_ready_state
from wms.shipment_tracking_handlers import (
    TRACKING_TO_SHIPMENT_STATUS,
    allowed_tracking_statuses_for_shipment,
    validate_tracking_transition,
)
from wms.shipment_view_helpers import (
    build_shipment_document_links,
    build_shipments_ready_rows,
    build_shipments_tracking_rows,
)
from wms.stock_view_helpers import build_stock_context
from wms.upload_utils import ALLOWED_UPLOAD_EXTENSIONS
from wms.views_portal_account import _save_profile_updates
from wms.views_scan_shipments_support import (
    CLOSED_FILTER_EXCLUDE,
    _build_shipments_tracking_queryset,
    _normalize_closed_filter,
    _parse_planned_week,
    _shipment_can_be_closed,
    _stale_drafts_age_days,
    _stale_drafts_queryset,
)
from wms.workflow_blockage_queue import (
    WORKFLOW_BLOCKAGE_CLAIM_CLAIMED,
    build_workflow_blockage_rows,
    claim_workflow_blockage,
    release_workflow_blockage,
    summarize_workflow_blockage_rows,
    workflow_blockage_row_by_key,
)
from wms.workflow_observability import log_shipment_case_closed, log_workflow_event

from .permissions import IsAssociationProfileUser, IsPortalScopeUser, IsStaffUser
from .serializers import (
    UiPortalAccountUpdateSerializer,
    UiPortalOrderCreateSerializer,
    UiPortalRecipientMutationSerializer,
    UiPrintTemplateMutationSerializer,
    UiShipmentMutationSerializer,
    UiShipmentTrackingEventSerializer,
    UiStockOutSerializer,
    UiStockUpdateSerializer,
)
from .ui_api_errors import api_error, form_error_payload, serializer_field_errors


def _asciiize_dashboard_value(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    if isinstance(value, list):
        return [_asciiize_dashboard_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_asciiize_dashboard_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _asciiize_dashboard_value(item) for key, item in value.items()}
    return value


def _dashboard_filters_payload(dashboard_payload):
    return {
        "period": dashboard_payload["period"],
        "period_choices": [
            {"value": value, "label": _asciiize_dashboard_value(str(label))}
            for value, label in dashboard_payload["period_choices"]
        ],
        "destination": dashboard_payload["destination_id"],
        "destinations": [
            {"id": destination.id, "label": str(destination)}
            for destination in dashboard_payload["destinations"]
        ],
    }


def _dashboard_response_payload(dashboard_payload):
    return {
        "kpis": dashboard_payload["kpis"],
        "timeline": dashboard_payload["timeline"],
        "pending_actions": _asciiize_dashboard_value(dashboard_payload["pending_actions"]),
        "period_label": _asciiize_dashboard_value(dashboard_payload["period_label"]),
        "activity_cards": _asciiize_dashboard_value(dashboard_payload["activity_cards"]),
        "shipment_cards": _asciiize_dashboard_value(dashboard_payload["shipment_cards"]),
        "carton_cards": _asciiize_dashboard_value(dashboard_payload["carton_cards"]),
        "stock_cards": _asciiize_dashboard_value(dashboard_payload["stock_cards"]),
        "flow_cards": _asciiize_dashboard_value(dashboard_payload["flow_cards"]),
        "tracking_alert_hours": dashboard_payload["tracking_alert_hours"],
        "tracking_cards": _asciiize_dashboard_value(dashboard_payload["tracking_cards"]),
        "queue_processing_timeout_seconds": dashboard_payload["queue_processing_timeout_seconds"],
        "technical_cards": _asciiize_dashboard_value(dashboard_payload["technical_cards"]),
        "document_scan_processing_timeout_seconds": dashboard_payload[
            "document_scan_processing_timeout_seconds"
        ],
        "document_scan_cards": _asciiize_dashboard_value(dashboard_payload["document_scan_cards"]),
        "workflow_blockage_hours": dashboard_payload["workflow_blockage_hours"],
        "workflow_blockage_cards": _asciiize_dashboard_value(
            dashboard_payload["workflow_blockage_cards"]
        ),
        "workflow_blockage_summary_cards": _asciiize_dashboard_value(
            dashboard_payload["workflow_blockage_summary_cards"]
        ),
        "workflow_blockage_rows": _asciiize_dashboard_value(
            dashboard_payload["workflow_blockage_rows"]
        ),
        "destination_risk_summary_cards": _asciiize_dashboard_value(
            dashboard_payload["destination_risk_summary_cards"]
        ),
        "destination_risk_rows": _asciiize_dashboard_value(
            dashboard_payload["destination_risk_rows"]
        ),
        "sla_cards": _asciiize_dashboard_value(dashboard_payload["sla_cards"]),
        "sla_alert_summary_cards": _asciiize_dashboard_value(
            dashboard_payload["sla_alert_summary_cards"]
        ),
        "sla_alert_rows": _asciiize_dashboard_value(dashboard_payload["sla_alert_rows"]),
        "shipments_total": dashboard_payload["shipments_total"],
        "shipment_chart_rows": _asciiize_dashboard_value(dashboard_payload["shipment_chart_rows"]),
        "filters": _dashboard_filters_payload(dashboard_payload),
        "low_stock_threshold": dashboard_payload["low_stock_threshold"],
        "low_stock_rows": dashboard_payload["low_stock_rows"],
        "updated_at": timezone.now().isoformat(),
    }


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


def _dashboard_stock_snapshot(*, low_stock_threshold: int):
    lot_available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    product_available_expr = ExpressionWrapper(
        F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
        output_field=IntegerField(),
    )
    active_products = Product.objects.filter(is_active=True)
    available_lots = ProductLot.objects.filter(
        status=ProductLotStatus.AVAILABLE,
        quantity_on_hand__gt=0,
    )
    total_available_qty = available_lots.aggregate(total=Sum(lot_available_expr))["total"] or 0

    products_with_qty = active_products.annotate(
        available_qty=Coalesce(
            Sum(
                product_available_expr,
                filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
            ),
            0,
            output_field=IntegerField(),
        )
    )
    low_stock_qs = products_with_qty.filter(available_qty__lt=low_stock_threshold).order_by(
        "available_qty", "name"
    )
    return {
        "active_products_count": active_products.count(),
        "available_lots_count": available_lots.count(),
        "total_available_qty": total_available_qty,
        "low_stock_count": low_stock_qs.count(),
        "low_stock_rows": list(low_stock_qs.values("id", "sku", "name", "available_qty")[:10]),
    }


DASHBOARD_PERIOD_TODAY = "today"
DASHBOARD_PERIOD_7D = "7d"
DASHBOARD_PERIOD_30D = "30d"
DASHBOARD_PERIOD_WEEK = "week"
DASHBOARD_DEFAULT_PERIOD = DASHBOARD_PERIOD_WEEK
DASHBOARD_PERIOD_CHOICES = (
    (DASHBOARD_PERIOD_TODAY, "Aujourd hui"),
    (DASHBOARD_PERIOD_7D, "7 jours"),
    (DASHBOARD_PERIOD_30D, "30 jours"),
    (DASHBOARD_PERIOD_WEEK, "Semaine en cours"),
)
DASHBOARD_ACTION_OWNERS = ("magasin", "qualite", "admin", "portal")
DASHBOARD_ACTION_PRIORITIES = ("high", "medium", "low")
DASHBOARD_SHIPMENT_STATUS_ORDER = (
    ShipmentStatus.DRAFT,
    ShipmentStatus.PICKING,
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
)
DASHBOARD_SLA_SEGMENT_LABELS = {
    "planned_to_boarding": "Planifie -> OK mise a bord",
    "boarding_to_correspondent": "OK mise a bord -> Recu escale",
    "correspondent_to_delivery": "Recu escale -> Livre",
    "planned_to_delivery": "Planifie -> Livre",
}
DASHBOARD_SLA_ACTION_LABELS = {
    "planned_to_boarding": "Relancer mise a bord",
    "boarding_to_correspondent": "Relancer recu escale",
    "correspondent_to_delivery": "Relancer livraison",
}
DASHBOARD_WORKFLOW_BLOCKAGE_CATEGORY_LABELS = {
    "creation_expedition": "Creation expedition",
    "commande": "Commande",
    "suivi": "Suivi",
    "cloture": "Cloture",
    "queue": "Queue",
}
DASHBOARD_WORKFLOW_BLOCKAGE_KIND_LABELS = {
    "shipment_creation": "Debloquer creation expedition",
    "order_without_shipment": "Creer expedition",
    "shipment_dispute": "Resoudre litige",
    "shipment_sla_alert": "Traiter retard de suivi",
    "shipment_closure": "Clore dossier livre",
    "email_queue_failed": "Investiguer queue email en echec",
    "email_queue_stale": "Debloquer queue email",
    "document_scan_failed": "Investiguer queue scan doc en echec",
    "document_scan_stale": "Debloquer queue scan doc",
}
DASHBOARD_WORKFLOW_BLOCKAGE_CLAIM_STATE_LABELS = {
    "open": "A prendre",
    WORKFLOW_BLOCKAGE_CLAIM_CLAIMED: "Pris en charge",
}
DASHBOARD_WORKFLOW_PENDING_ACTION_TYPES = {
    "shipment_creation": "shipment_creation_blockage",
    "order_without_shipment": "order_without_shipment",
    "shipment_dispute": "shipment_dispute",
    "shipment_sla_alert": "shipment_sla_alert",
    "shipment_closure": "shipment_closure",
    "email_queue_failed": "workflow_queue_issue",
    "email_queue_stale": "workflow_queue_issue",
    "document_scan_failed": "workflow_queue_issue",
    "document_scan_stale": "workflow_queue_issue",
}


def _dashboard_period_start(period_key):
    now = timezone.now()
    tz = timezone.get_current_timezone()
    if period_key == DASHBOARD_PERIOD_TODAY:
        return timezone.make_aware(
            datetime.combine(timezone.localdate(), time.min),
            tz,
        )
    if period_key == DASHBOARD_PERIOD_7D:
        return now - timedelta(days=7)
    if period_key == DASHBOARD_PERIOD_30D:
        return now - timedelta(days=30)
    if period_key == DASHBOARD_PERIOD_WEEK:
        today = timezone.localdate()
        iso_year, iso_week, _ = today.isocalendar()
        week_start = date.fromisocalendar(iso_year, iso_week, 1)
        return timezone.make_aware(datetime.combine(week_start, time.min), tz)
    return now - timedelta(days=7)


def _normalize_dashboard_period(raw_value):
    value = (raw_value or "").strip().lower()
    allowed = {choice[0] for choice in DASHBOARD_PERIOD_CHOICES}
    if value in allowed:
        return value
    return DASHBOARD_DEFAULT_PERIOD


def _build_dashboard_shipment_chart_rows(status_count_map):
    shipments_total = sum(
        status_count_map.get(status, 0) for status in DASHBOARD_SHIPMENT_STATUS_ORDER
    )
    label_map = dict(ShipmentStatus.choices)
    rows = []
    for status in DASHBOARD_SHIPMENT_STATUS_ORDER:
        count = status_count_map.get(status, 0)
        percent = round((count / shipments_total) * 100, 1) if shipments_total else 0
        rows.append(
            {
                "status": status,
                "label": label_map.get(status, status),
                "count": count,
                "percent": percent,
            }
        )
    return rows, shipments_total


def _dashboard_positive_int(value, *, default: int) -> int:
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, int_value)


def _dashboard_age_hours(started_at):
    if started_at is None:
        return 0.0
    delta = timezone.now() - started_at
    return max(round(delta.total_seconds() / 3600, 1), 0.0)


def _build_dashboard_action(
    *,
    action_type: str,
    reference: str,
    label: str,
    priority: str,
    owner: str,
    url: str,
    started_at=None,
    context=None,
):
    if owner not in DASHBOARD_ACTION_OWNERS:
        raise ValueError(f"Unsupported dashboard action owner: {owner}")
    if priority not in DASHBOARD_ACTION_PRIORITIES:
        raise ValueError(f"Unsupported dashboard action priority: {priority}")
    item = {
        "type": action_type,
        "reference": reference,
        "label": label,
        "priority": priority,
        "owner": owner,
        "url": url,
        "age_hours": _dashboard_age_hours(started_at),
    }
    if context:
        item["context"] = context
    return item


def _dashboard_email_queue_snapshot(*, processing_timeout_seconds: int):
    queue_qs = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source="wms.email",
        event_type="send_email",
    )
    status_counts = {
        item["status"]: item["total"]
        for item in queue_qs.values("status").annotate(total=Count("id"))
    }
    stale_cutoff = timezone.now() - timedelta(seconds=processing_timeout_seconds)
    stale_processing_count = queue_qs.filter(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_cutoff,
    ).count()
    return {
        "pending_count": status_counts.get(IntegrationStatus.PENDING, 0),
        "processing_count": status_counts.get(IntegrationStatus.PROCESSING, 0),
        "failed_count": status_counts.get(IntegrationStatus.FAILED, 0),
        "stale_processing_count": stale_processing_count,
    }


def _dashboard_document_scan_timeout_seconds():
    return _dashboard_positive_int(
        getattr(
            settings,
            "DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS",
            DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
        ),
        default=DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    )


def _dashboard_document_scan_queue_snapshot(*, processing_timeout_seconds: int):
    queue_qs = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    )
    status_counts = {
        item["status"]: item["total"]
        for item in queue_qs.values("status").annotate(total=Count("id"))
    }
    stale_cutoff = timezone.now() - timedelta(seconds=processing_timeout_seconds)
    stale_processing_count = queue_qs.filter(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_cutoff,
    ).count()
    return {
        "pending_count": status_counts.get(IntegrationStatus.PENDING, 0),
        "processing_count": status_counts.get(IntegrationStatus.PROCESSING, 0),
        "failed_count": status_counts.get(IntegrationStatus.FAILED, 0),
        "stale_processing_count": stale_processing_count,
    }


def _dashboard_workflow_blockage_snapshot(
    shipments_scope,
    *,
    workflow_blockage_hours: int,
):
    cutoff = timezone.now() - timedelta(hours=workflow_blockage_hours)
    return {
        "stale_preparing_shipments_count": shipments_scope.filter(
            status__in=[ShipmentStatus.DRAFT, ShipmentStatus.PICKING],
            created_at__lt=cutoff,
            closed_at__isnull=True,
        ).count(),
        "stale_unplanned_orders_count": Order.objects.filter(
            review_status=OrderReviewStatus.APPROVED,
            shipment__isnull=True,
            created_at__lt=cutoff,
        ).count(),
        "open_delivered_cases_count": shipments_scope.filter(
            status=ShipmentStatus.DELIVERED,
            closed_at__isnull=True,
        ).count(),
        "open_disputed_cases_count": shipments_scope.filter(
            is_disputed=True,
            closed_at__isnull=True,
        ).count(),
    }


def _dashboard_workflow_blockage_rows(
    *,
    destination_id: str,
    workflow_blockage_hours: int,
    tracking_alert_hours: int,
    queue_processing_timeout_seconds: int,
    document_scan_timeout_seconds: int,
):
    shipments_qs = Shipment.objects.filter(archived_at__isnull=True)
    if destination_id:
        shipments_qs = shipments_qs.filter(destination_id=destination_id)
    shipments_with_tracking = annotate_shipment_tracking_dates(shipments_qs)
    base_rows = build_workflow_blockage_rows(
        shipments_scope=shipments_qs,
        shipments_with_tracking=shipments_with_tracking,
        workflow_blockage_hours=workflow_blockage_hours,
        tracking_alert_hours=tracking_alert_hours,
        email_queue_processing_timeout_seconds=queue_processing_timeout_seconds,
        document_scan_processing_timeout_seconds=document_scan_timeout_seconds,
    )
    rows = [
        {
            **row,
            "category_label": DASHBOARD_WORKFLOW_BLOCKAGE_CATEGORY_LABELS[row["category"]],
            "label": DASHBOARD_WORKFLOW_BLOCKAGE_KIND_LABELS.get(row["kind"], row["label"]),
            "claim_state_label": DASHBOARD_WORKFLOW_BLOCKAGE_CLAIM_STATE_LABELS[row["claim_state"]],
            "cta_label": "Ouvrir",
        }
        for row in base_rows
    ]
    return base_rows, rows


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


PORTAL_RECIPIENT_SELF = "self"
PORTAL_DEFAULT_COUNTRY = "France"


def _split_multi_values(value):
    raw = (value or "").replace("\n", ";").replace(",", ";")
    return [item.strip() for item in raw.split(";") if item.strip()]


def _validate_multi_emails(raw_value):
    values = _split_multi_values(raw_value)
    validator = EmailValidator()
    invalid_values = []
    for value in values:
        try:
            validator(value)
        except DjangoValidationError:
            invalid_values.append(value)
    return values, invalid_values


def _portal_order_destination_payload(*, profile, recipient_id, selected_destination):
    if recipient_id == PORTAL_RECIPIENT_SELF:
        address = get_contact_address(profile.contact)
        if not address:
            return None, "Adresse association manquante."
        return {
            "recipient_name": profile.contact.name,
            "recipient_contact": profile.contact,
            "destination_city": selected_destination.city
            if selected_destination
            else (address.city or ""),
            "destination_country": (
                selected_destination.country
                if selected_destination
                else (address.country or PORTAL_DEFAULT_COUNTRY)
            ),
            "destination_address": build_destination_address(
                line1=address.address_line1,
                line2=address.address_line2,
                postal_code=address.postal_code,
                city=address.city,
                country=address.country,
            ),
        }, ""

    recipient = (
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
            pk=recipient_id,
        )
        .select_related("destination")
        .first()
    )
    if recipient is None:
        return None, "Destinataire invalide."
    if selected_destination and recipient.destination_id not in {selected_destination.id, None}:
        return None, "Destinataire non disponible pour cette destination."

    recipient_contact = sync_association_recipient_to_contact(recipient)
    return {
        "recipient_name": recipient.get_display_name(),
        "recipient_contact": recipient_contact,
        "destination_city": (
            selected_destination.city
            if selected_destination
            else (recipient.city or (recipient.destination.city if recipient.destination else ""))
        ),
        "destination_country": (
            selected_destination.country
            if selected_destination
            else (
                recipient.country
                or (recipient.destination.country if recipient.destination else "")
                or PORTAL_DEFAULT_COUNTRY
            )
        ),
        "destination_address": build_destination_address(
            line1=recipient.address_line1,
            line2=recipient.address_line2,
            postal_code=recipient.postal_code,
            city=recipient.city or (recipient.destination.city if recipient.destination else ""),
            country=recipient.country
            or (recipient.destination.country if recipient.destination else "")
            or PORTAL_DEFAULT_COUNTRY,
        ),
    }, ""


def _portal_recipient_payload(validated_data, destination):
    title_value = (validated_data.get("contact_title") or "").strip()
    title_label = dict(AssociationContactTitle.choices).get(title_value, "")
    contact_display = " ".join(
        part
        for part in [
            str(title_label) if title_label else "",
            (validated_data.get("contact_first_name") or "").strip(),
            (validated_data.get("contact_last_name") or "").strip().upper(),
        ]
        if part
    ).strip()
    structure_name = (validated_data.get("structure_name") or "").strip()
    email_values = _split_multi_values(validated_data.get("emails", ""))
    phone_values = _split_multi_values(validated_data.get("phones", ""))
    return {
        "destination": destination,
        "name": structure_name or contact_display or "Destinataire",
        "structure_name": structure_name,
        "contact_title": title_value,
        "contact_last_name": (validated_data.get("contact_last_name") or "").strip(),
        "contact_first_name": (validated_data.get("contact_first_name") or "").strip(),
        "phones": "; ".join(phone_values),
        "emails": "; ".join(email_values),
        "email": email_values[0] if email_values else "",
        "phone": phone_values[0] if phone_values else "",
        "address_line1": (validated_data.get("address_line1") or "").strip(),
        "address_line2": (validated_data.get("address_line2") or "").strip(),
        "postal_code": (validated_data.get("postal_code") or "").strip(),
        "city": (validated_data.get("city") or "").strip(),
        "country": ((validated_data.get("country") or "").strip() or PORTAL_DEFAULT_COUNTRY),
        "notes": (validated_data.get("notes") or "").strip(),
        "notify_deliveries": bool(validated_data.get("notify_deliveries")),
        "is_delivery_contact": bool(validated_data.get("is_delivery_contact")),
    }


def _portal_recipient_row(recipient):
    return {
        "id": recipient.id,
        "display_name": recipient.get_display_name(),
        "destination_id": recipient.destination_id,
        "destination_label": str(recipient.destination) if recipient.destination_id else "",
        "structure_name": recipient.structure_name or "",
        "contact_title": recipient.contact_title or "",
        "contact_first_name": recipient.contact_first_name or "",
        "contact_last_name": recipient.contact_last_name or "",
        "phones": recipient.phones or recipient.phone or "",
        "emails": recipient.emails or recipient.email or "",
        "address_line1": recipient.address_line1,
        "address_line2": recipient.address_line2 or "",
        "postal_code": recipient.postal_code or "",
        "city": recipient.city or "",
        "country": recipient.country or PORTAL_DEFAULT_COUNTRY,
        "legal_form": recipient.legal_form or "",
        "beneficiary_count": recipient.beneficiary_count,
        "notes": recipient.notes or "",
        "notify_deliveries": recipient.notify_deliveries,
        "is_delivery_contact": recipient.is_delivery_contact,
        "is_active": recipient.is_active,
    }


def _portal_runtime_primary_recipient_contact(recipient_organization):
    return (
        ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
        )
        .select_related("contact")
        .order_by("id")
        .first()
    )


def _portal_runtime_recipient_row(recipient_organization):
    recipient_organization = (
        ShipmentRecipientOrganization.objects.filter(pk=recipient_organization.pk)
        .select_related("organization", "destination")
        .get()
    )
    organization = recipient_organization.organization
    address = organization.get_effective_address()
    shipment_recipient_contact = _portal_runtime_primary_recipient_contact(recipient_organization)
    contact = shipment_recipient_contact.contact if shipment_recipient_contact is not None else None
    return {
        "id": recipient_organization.id,
        "display_name": organization.name or "",
        "destination_id": recipient_organization.destination_id,
        "destination_label": str(recipient_organization.destination),
        "structure_name": organization.name or "",
        "contact_title": contact.title if contact is not None else "",
        "contact_first_name": contact.first_name if contact is not None else "",
        "contact_last_name": contact.last_name if contact is not None else "",
        "phones": contact.phone if contact is not None else "",
        "emails": contact.email if contact is not None else "",
        "address_line1": address.address_line1 if address else "",
        "address_line2": address.address_line2 if address else "",
        "postal_code": address.postal_code if address else "",
        "city": address.city if address else "",
        "country": (address.country if address else "") or PORTAL_DEFAULT_COUNTRY,
        "legal_form": organization.legal_form or "",
        "beneficiary_count": organization.beneficiary_count,
        "notes": organization.notes or "",
        "notify_deliveries": False,
        "is_delivery_contact": False,
        "is_active": recipient_organization.is_active,
    }


def _portal_shipper_contact_from_request(request):
    scope = getattr(request, "portal_scope", None)
    if (
        scope is not None
        and scope.role == PortalAccessRole.SHIPPER_ADMIN
        and scope.shipper is not None
    ):
        return scope.shipper.organization
    profile = get_association_profile(request.user)
    return profile.contact if profile is not None else None


def _portal_profile_from_request(request):
    scope = getattr(request, "portal_scope", None)
    if scope is not None and scope.association_profile is not None:
        return scope.association_profile
    return get_association_profile(request.user)


def _portal_recipient_scope_dashboard_payload(recipient_organization):
    payload = build_recipient_scope_home_payload(recipient_organization=recipient_organization)
    return {
        "mode": "recipient",
        "recipient": {
            "recipient_organization_id": payload["recipient_organization"].id,
            "structure_name": payload["recipient_structure_name"],
            "destination_label": payload["recipient_destination_label"],
            "legal_form_label": payload["recipient_legal_form_label"],
            "beneficiary_count": payload["recipient_beneficiary_count"],
            "address_lines": payload["recipient_address_lines"],
            "notes": payload["recipient_notes"],
            "contacts": payload["recipient_contact_rows"],
            "documents": payload["recipient_document_rows"],
            "preferences": payload["recipient_preference_rows"],
        },
    }


def _update_portal_runtime_recipient_from_payload(*, recipient_organization, payload):
    organization = recipient_organization.organization
    organization_updated_fields = []
    structure_name = (payload.get("structure_name") or "").strip()
    if organization.name != structure_name:
        organization.name = structure_name
        organization_updated_fields.append("name")
    legal_form = (payload.get("legal_form") or "").strip()
    if organization.legal_form != legal_form:
        organization.legal_form = legal_form
        organization_updated_fields.append("legal_form")
    beneficiary_count = payload.get("beneficiary_count")
    if organization.beneficiary_count != beneficiary_count:
        organization.beneficiary_count = beneficiary_count
        organization_updated_fields.append("beneficiary_count")
    notes = (payload.get("notes") or "").strip()
    if organization.notes != notes:
        organization.notes = notes
        organization_updated_fields.append("notes")
    if organization_updated_fields:
        organization.save(update_fields=organization_updated_fields)

    address = (
        organization.addresses.filter(is_default=True).first() or organization.addresses.first()
    )
    if address is None:
        address = ContactAddress(contact=organization, is_default=True)
    address.address_line1 = (payload.get("address_line1") or "").strip()
    address.address_line2 = (payload.get("address_line2") or "").strip()
    address.postal_code = (payload.get("postal_code") or "").strip()
    address.city = (payload.get("city") or "").strip()
    address.country = (payload.get("country") or "").strip() or PORTAL_DEFAULT_COUNTRY
    address.save()

    shipment_recipient_contact = _portal_runtime_primary_recipient_contact(recipient_organization)
    contact = shipment_recipient_contact.contact if shipment_recipient_contact is not None else None
    if contact is None:
        contact = Contact.objects.create(
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=True,
            name=structure_name or "Referent destinataire",
        )
        shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=contact,
            is_active=True,
        )

    contact_updated_fields = []
    for field_name, value in (
        ("title", (payload.get("contact_title") or "").strip()),
        ("first_name", (payload.get("contact_first_name") or "").strip()),
        ("last_name", (payload.get("contact_last_name") or "").strip()),
        (
            "email",
            _split_multi_values(payload.get("emails", ""))[0]
            if _split_multi_values(payload.get("emails", ""))
            else "",
        ),
        (
            "phone",
            _split_multi_values(payload.get("phones", ""))[0]
            if _split_multi_values(payload.get("phones", ""))
            else "",
        ),
    ):
        if getattr(contact, field_name) != value:
            setattr(contact, field_name, value)
            contact_updated_fields.append(field_name)
    contact_name = (
        " ".join(
            part
            for part in (
                (contact.first_name or "").strip(),
                (contact.last_name or "").strip(),
            )
            if part
        ).strip()
        or contact.name
    )
    if contact.name != contact_name:
        contact.name = contact_name
        contact_updated_fields.append("name")
    if contact.organization_id != organization.id:
        contact.organization = organization
        contact_updated_fields.append("organization")
    if contact_updated_fields:
        contact.save(update_fields=contact_updated_fields)

    allowed_shipper_contacts = [
        link.shipper.organization
        for link in recipient_organization.shipper_links.filter(
            is_active=True,
            shipper__is_active=True,
            shipper__organization__is_active=True,
        ).select_related("shipper__organization")
    ]
    return update_runtime_recipient_shared_profile(
        organization=organization,
        referent=contact,
        destination=recipient_organization.destination,
        allowed_shipper_contacts=allowed_shipper_contacts,
        is_correspondent=recipient_organization.is_correspondent,
        is_active=recipient_organization.is_active,
    )


def _portal_account_summary(profile):
    association = profile.contact
    address = get_contact_address(association)
    return {
        "association_name": association.name or "",
        "association_email": association.email or "",
        "association_phone": association.phone or "",
        "address_line1": address.address_line1 if address else "",
        "address_line2": address.address_line2 if address else "",
        "postal_code": address.postal_code if address else "",
        "city": address.city if address else "",
        "country": (address.country if address else "") or PORTAL_DEFAULT_COUNTRY,
        "notification_emails": profile.get_notification_emails(),
        "portal_contacts": [
            {
                "id": contact.id,
                "title": contact.title or "",
                "first_name": contact.first_name or "",
                "last_name": contact.last_name or "",
                "phone": contact.phone or "",
                "email": contact.email or "",
                "is_administrative": contact.is_administrative,
                "is_shipping": contact.is_shipping,
                "is_billing": contact.is_billing,
            }
            for contact in profile.portal_contacts.filter(is_active=True).order_by("position", "id")
        ],
    }


TEMPLATE_LABEL_MAP = dict(DOCUMENT_TEMPLATES)


def _superuser_required_error():
    return api_error(
        message="Acces reserve aux superusers.",
        code="superuser_required",
        http_status=status.HTTP_403_FORBIDDEN,
    )


def _shipment_document_row(document):
    filename = Path(document.file.name).name if document.file else ""
    return {
        "id": document.id,
        "doc_type": document.doc_type,
        "doc_type_label": document.get_doc_type_display(),
        "filename": filename,
        "url": document.file.url if document.file else "",
        "generated_at": document.generated_at.isoformat() if document.generated_at else None,
    }


def _template_updated_by(template):
    if template and template.updated_by:
        username = (template.updated_by.get_username() or "").strip()
        if username:
            return username
    return ""


def _template_versions_payload(template):
    if template is None:
        return []
    return [
        {
            "id": version.id,
            "version": version.version,
            "created_at": version.created_at.isoformat(),
            "created_by": version.created_by.get_username() if version.created_by else "",
        }
        for version in template.versions.select_related("created_by").order_by("-version")[:15]
    ]


def _template_preview_options(doc_type):
    shipments = []
    for shipment in (
        Shipment.objects.filter(archived_at__isnull=True)
        .select_related("destination")
        .order_by("reference", "id")[:30]
    ):
        destination = (
            shipment.destination.city
            if shipment.destination and shipment.destination.city
            else shipment.destination_address
        )
        label = shipment.reference or f"EXP-{shipment.id}"
        if destination:
            label = f"{label} - {destination}"
        shipments.append({"id": shipment.id, "label": label})

    products = []
    if doc_type in {"product_label", "product_qr"}:
        for product in Product.objects.order_by("name")[:30]:
            label = product.name
            if product.sku:
                label = f"{product.sku} - {label}"
            products.append({"id": product.id, "label": label})

    return {
        "shipments": sorted(shipments, key=lambda item: (item["label"] or "").lower()),
        "products": sorted(products, key=lambda item: (item["label"] or "").lower()),
    }


def _template_payload(doc_type, template):
    default_layout = DEFAULT_LAYOUTS.get(doc_type, {"blocks": []})
    layout = template.layout if template and template.layout else default_layout
    return {
        "doc_type": doc_type,
        "label": TEMPLATE_LABEL_MAP[doc_type],
        "has_override": bool(template and template.layout),
        "layout": layout,
        "updated_at": template.updated_at.isoformat() if template else None,
        "updated_by": _template_updated_by(template),
        "versions": _template_versions_payload(template),
        "preview_options": _template_preview_options(doc_type),
    }


def _save_print_template_layout(*, template, doc_type, layout_data, user):
    with transaction.atomic():
        if template is None:
            template = PrintTemplate.objects.create(
                doc_type=doc_type,
                layout=layout_data,
                updated_by=user,
            )
        else:
            template.layout = layout_data
            template.updated_by = user
            template.save(update_fields=["layout", "updated_by", "updated_at"])

        next_version = (
            template.versions.aggregate(max_version=Max("version"))["max_version"] or 0
        ) + 1
        PrintTemplateVersion.objects.create(
            template=template,
            version=next_version,
            layout=layout_data,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
    return template, next_version


class UiDashboardView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        dashboard_payload = build_scan_dashboard_payload(user=request.user, params=request.GET)
        return Response(_dashboard_response_payload(dashboard_payload))


class UiDashboardWorkflowBlockageClaimView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request):
        action = str(request.data.get("action") or "").strip().lower()
        blockage_key = str(request.data.get("blockage_key") or "").strip()
        destination_id = str(request.data.get("destination") or "").strip()
        if not blockage_key:
            return api_error("missing_blockage_key", "blockage_key is required.", status=400)
        if action not in {"claim", "release"}:
            return api_error("invalid_action", "action must be claim or release.", status=400)

        if action == "release":
            release_workflow_blockage(blockage_key=blockage_key)
            return Response(
                {
                    "ok": True,
                    "blockage_key": blockage_key,
                    "claim_state": "released",
                }
            )

        runtime = get_runtime_config()
        document_scan_timeout_seconds = _dashboard_document_scan_timeout_seconds()
        base_rows, _rows = _dashboard_workflow_blockage_rows(
            destination_id=destination_id,
            workflow_blockage_hours=runtime.workflow_blockage_hours,
            tracking_alert_hours=runtime.tracking_alert_hours,
            queue_processing_timeout_seconds=runtime.email_queue_processing_timeout_seconds,
            document_scan_timeout_seconds=document_scan_timeout_seconds,
        )
        row = workflow_blockage_row_by_key(base_rows, blockage_key)
        if row is None:
            return api_error("unknown_blockage", "Workflow blockage not found.", status=404)
        claim_workflow_blockage(row=row, user=request.user)
        return Response(
            {
                "ok": True,
                "blockage_key": blockage_key,
                "claim_state": "claimed",
            }
        )


class UiPilotageView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        payload = build_scan_pilotage_payload()
        payload["updated_at"] = timezone.now().isoformat()
        return Response(payload)


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
                "barcode": product.barcode or "",
                "name": product.name,
                "brand": product.brand or "",
                "category_id": product.category_id,
                "category_name": product.category.name if product.category else "",
                "location": str(product.default_location) if product.default_location_id else "",
                "stock_total": int(product.stock_total or 0),
                "last_movement_at": (
                    product.last_movement_at.isoformat() if product.last_movement_at else None
                ),
                "state": _stock_state(
                    int(product.stock_total or 0),
                    runtime.low_stock_threshold,
                ),
            }
            for product in products_qs
        ]
        categories = [
            {"id": category.id, "name": category.name} for category in context["categories"]
        ]
        warehouses = [
            {"id": warehouse.id, "name": warehouse.name} for warehouse in context["warehouses"]
        ]
        return Response(
            {
                "filters": {
                    "q": context["query"],
                    "category": context["category_id"],
                    "warehouse": context["warehouse_id"],
                    "sort": context["sort"],
                    "include_zero": context["include_zero"],
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


class UiCartonsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        carton_capacity_cm3 = get_carton_capacity_cm3()
        cartons_qs = (
            Carton.objects.filter(cartonitem__isnull=False)
            .select_related("shipment", "current_location")
            .prefetch_related("cartonitem_set__product_lot__product")
            .distinct()
            .order_by("-created_at")
        )
        carton_shipment_ids = {carton.id: carton.shipment_id for carton in cartons_qs}
        rows = build_cartons_ready_rows(cartons_qs, carton_capacity_cm3=carton_capacity_cm3)
        cartons = []
        for row in rows:
            shipment_id = carton_shipment_ids.get(row["id"])
            if shipment_id:
                packing_list_url = reverse(
                    "scan:scan_shipment_carton_document",
                    args=[shipment_id, row["id"]],
                )
            else:
                packing_list_url = reverse("scan:scan_carton_document", args=[row["id"]])
            cartons.append(
                {
                    "id": row["id"],
                    "code": row["code"],
                    "created_at": (row["created_at"].isoformat() if row["created_at"] else None),
                    "status_label": row["status_label"],
                    "status_value": row["status_value"],
                    "shipment_reference": row["shipment_reference"] or "",
                    "location": str(row["location"]) if row["location"] else "",
                    "weight_kg": row["weight_kg"],
                    "volume_percent": row["volume_percent"],
                    "packing_list": row["packing_list"],
                    "packing_list_url": packing_list_url,
                    "picking_url": row["picking_url"],
                }
            )
        return Response(
            {
                "meta": {
                    "total_cartons": len(cartons),
                    "carton_capacity_cm3": carton_capacity_cm3,
                },
                "cartons": cartons,
            }
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


class UiShipmentsReadyView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        shipments_qs = (
            Shipment.objects.filter(archived_at__isnull=True)
            .select_related(
                "destination",
                "shipper_contact_ref__organization",
                "recipient_contact_ref__organization",
            )
            .annotate(
                carton_count=Count("carton", distinct=True),
                ready_count=Count(
                    "carton",
                    filter=Q(carton__status__in=[CartonStatus.LABELED, CartonStatus.SHIPPED]),
                    distinct=True,
                ),
            )
            .order_by("-created_at")
        )
        shipments = build_shipments_ready_rows(shipments_qs)
        items = []
        for row in shipments:
            shipment_id = row["id"]
            tracking_url = (
                f"{reverse('scan:scan_shipment_track', args=[row['tracking_token']])}"
                "?return_to=shipments_ready"
            )
            items.append(
                {
                    "id": shipment_id,
                    "reference": row["reference"],
                    "carton_count": row["carton_count"],
                    "destination_iata": row["destination_iata"] or "",
                    "shipper_name": row["shipper_name"] or "",
                    "recipient_name": row["recipient_name"] or "",
                    "created_at": (row["created_at"].isoformat() if row["created_at"] else None),
                    "ready_at": row["ready_at"].isoformat() if row["ready_at"] else None,
                    "status_label": row["status_label"] or "",
                    "can_edit": bool(row["can_edit"]),
                    "documents": {
                        "shipment_note_url": reverse(
                            "scan:scan_shipment_document",
                            args=[shipment_id, "shipment_note"],
                        ),
                        "packing_list_shipment_url": reverse(
                            "scan:scan_shipment_document",
                            args=[shipment_id, "packing_list_shipment"],
                        ),
                        "donation_certificate_url": reverse(
                            "scan:scan_shipment_document",
                            args=[shipment_id, "donation_certificate"],
                        ),
                        "labels_url": reverse(
                            "scan:scan_shipment_labels",
                            args=[shipment_id],
                        ),
                    },
                    "actions": {
                        "tracking_url": tracking_url,
                        "edit_url": (
                            reverse("scan:scan_shipment_edit", args=[shipment_id])
                            if row["can_edit"]
                            else ""
                        ),
                    },
                }
            )

        return Response(
            {
                "meta": {
                    "total_shipments": len(items),
                    "stale_draft_count": _stale_drafts_queryset().count(),
                    "stale_draft_days": _stale_drafts_age_days(),
                },
                "shipments": items,
            }
        )


class UiShipmentsReadyArchiveView(APIView):
    permission_classes = [IsStaffUser]

    def post(self, request):
        archived_count = _stale_drafts_queryset().update(archived_at=timezone.now())
        if archived_count:
            message = f"{archived_count} brouillon(s) temporaire(s) archives."
        else:
            message = "Aucun brouillon temporaire ancien a archiver."
        return Response(
            {
                "ok": True,
                "message": message,
                "archived_count": archived_count,
                "stale_draft_count": _stale_drafts_queryset().count(),
            }
        )


class UiShipmentsTrackingView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        planned_week_value, week_start, week_end = _parse_planned_week(
            request.GET.get("planned_week")
        )
        closed_filter = _normalize_closed_filter(request.GET.get("closed"))
        warning = ""

        shipments_qs = _build_shipments_tracking_queryset()
        if closed_filter == CLOSED_FILTER_EXCLUDE:
            shipments_qs = shipments_qs.filter(closed_at__isnull=True)
        if planned_week_value and week_start and week_end:
            shipments_qs = shipments_qs.filter(
                planned_at__date__gte=week_start,
                planned_at__date__lt=week_end,
            )
        elif planned_week_value and week_start is None:
            warning = "Format semaine invalide. Utilisez AAAA-Wss ou AAAA-ss."

        items = []
        for row in build_shipments_tracking_rows(shipments_qs):
            closed_by = row["closed_by"]
            tracking_url = (
                f"{reverse('scan:scan_shipment_track', args=[row['tracking_token']])}"
                "?return_to=shipments_tracking"
            )
            items.append(
                {
                    "id": row["id"],
                    "reference": row["reference"],
                    "carton_count": row["carton_count"],
                    "shipper_name": row["shipper_name"],
                    "recipient_name": row["recipient_name"],
                    "planned_at": (row["planned_at"].isoformat() if row["planned_at"] else None),
                    "boarding_ok_at": (
                        row["boarding_ok_at"].isoformat() if row["boarding_ok_at"] else None
                    ),
                    "shipped_at": (row["shipped_at"].isoformat() if row["shipped_at"] else None),
                    "received_correspondent_at": (
                        row["received_correspondent_at"].isoformat()
                        if row["received_correspondent_at"]
                        else None
                    ),
                    "delivered_at": (
                        row["delivered_at"].isoformat() if row["delivered_at"] else None
                    ),
                    "is_disputed": bool(row["is_disputed"]),
                    "is_closed": bool(row["is_closed"]),
                    "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
                    "closed_by_username": getattr(closed_by, "username", ""),
                    "can_close": bool(row["can_close"]),
                    "actions": {
                        "tracking_url": tracking_url,
                    },
                }
            )

        return Response(
            {
                "meta": {
                    "total_shipments": len(items),
                },
                "filters": {
                    "planned_week": planned_week_value,
                    "closed": closed_filter,
                },
                "close_inactive_message": "Il reste des etapes a valider, verifier avant de clore",
                "warnings": [warning] if warning else [],
                "shipments": items,
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
                party_payload = build_shipment_party_snapshot_payload(
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    correspondent_contact=correspondent_contact,
                    shipper_name=shipper_contact.name,
                    recipient_name=recipient_contact.name,
                    correspondent_name=correspondent_contact.name,
                )
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
                    **party_payload,
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
                apply_shipment_party_snapshot(
                    shipment,
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    correspondent_contact=correspondent_contact,
                    shipper_name=shipper_contact.name,
                    recipient_name=recipient_contact.name,
                    correspondent_name=correspondent_contact.name,
                )
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
                        "party_snapshot",
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
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True), pk=shipment_id
        )
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


class UiShipmentDocumentsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, shipment_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True).prefetch_related("carton_set"),
            pk=shipment_id,
        )
        documents, carton_docs, additional_docs = build_shipment_document_links(
            shipment,
            public=False,
        )
        labels = [
            {
                "carton_id": carton.id,
                "carton_code": carton.code,
                "url": reverse("scan:scan_shipment_label", args=[shipment.id, carton.id]),
            }
            for carton in shipment.carton_set.order_by("code")
        ]
        return Response(
            {
                "shipment": _shipment_payload(shipment),
                "documents": documents,
                "carton_documents": carton_docs,
                "additional_documents": [
                    _shipment_document_row(document) for document in additional_docs
                ],
                "labels": {
                    "all_url": reverse("scan:scan_shipment_labels", args=[shipment.id]),
                    "items": labels,
                },
            }
        )

    def post(self, request, shipment_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True),
            pk=shipment_id,
        )
        uploaded = request.FILES.get("document_file")
        if uploaded is None:
            return api_error(
                message="Fichier requis.",
                code="document_file_required",
                field_errors={"document_file": ["Fichier requis."]},
            )

        extension = Path(uploaded.name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            return api_error(
                message="Format de fichier non autorise.",
                code="document_file_invalid_extension",
                field_errors={"document_file": ["Format de fichier non autorise."]},
            )

        document = Document.objects.create(
            shipment=shipment,
            doc_type=DocumentType.ADDITIONAL,
            file=uploaded,
        )
        log_workflow_event(
            "ui_shipment_document_uploaded",
            shipment=shipment,
            user=request.user if request.user.is_authenticated else None,
            document_id=document.id,
            doc_type=document.doc_type,
            filename=Path(document.file.name).name if document.file else "",
        )
        return Response(
            {
                "ok": True,
                "message": "Document ajoute.",
                "document": _shipment_document_row(document),
            },
            status=status.HTTP_201_CREATED,
        )


class UiShipmentDocumentDetailView(APIView):
    permission_classes = [IsStaffUser]

    def delete(self, request, shipment_id, document_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True),
            pk=shipment_id,
        )
        document = get_object_or_404(
            Document.objects.filter(
                shipment=shipment,
                doc_type=DocumentType.ADDITIONAL,
            ),
            pk=document_id,
        )
        filename = Path(document.file.name).name if document.file else ""
        if document.file:
            document.file.delete(save=False)
        document.delete()
        log_workflow_event(
            "ui_shipment_document_deleted",
            shipment=shipment,
            user=request.user if request.user.is_authenticated else None,
            document_id=document_id,
            doc_type=DocumentType.ADDITIONAL,
            filename=filename,
        )
        return Response(
            {
                "ok": True,
                "message": "Document supprime.",
                "document_id": document_id,
            }
        )


class UiShipmentLabelsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, shipment_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True).prefetch_related("carton_set"),
            pk=shipment_id,
        )
        labels = [
            {
                "carton_id": carton.id,
                "carton_code": carton.code,
                "url": reverse("scan:scan_shipment_label", args=[shipment.id, carton.id]),
            }
            for carton in shipment.carton_set.order_by("code")
        ]
        return Response(
            {
                "shipment": _shipment_payload(shipment),
                "all_url": reverse("scan:scan_shipment_labels", args=[shipment.id]),
                "labels": labels,
            }
        )


class UiShipmentLabelDetailView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, shipment_id, carton_id):
        shipment = get_object_or_404(
            Shipment.objects.filter(archived_at__isnull=True).prefetch_related("carton_set"),
            pk=shipment_id,
        )
        carton = shipment.carton_set.filter(pk=carton_id).first()
        if carton is None:
            return api_error(
                message="Carton introuvable pour cette expedition.",
                code="carton_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "shipment": _shipment_payload(shipment),
                "carton_id": carton.id,
                "carton_code": carton.code,
                "url": reverse("scan:scan_shipment_label", args=[shipment.id, carton.id]),
            }
        )


class UiPrintTemplatesView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        if not request.user.is_superuser:
            return _superuser_required_error()
        template_map = {
            template.doc_type: template
            for template in PrintTemplate.objects.select_related("updated_by")
        }
        rows = []
        for doc_type, label in DOCUMENT_TEMPLATES:
            template = template_map.get(doc_type)
            rows.append(
                {
                    "doc_type": doc_type,
                    "label": label,
                    "has_override": bool(template and template.layout),
                    "updated_at": template.updated_at.isoformat() if template else None,
                    "updated_by": _template_updated_by(template),
                }
            )
        return Response({"templates": rows})


class UiPrintTemplateDetailView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, doc_type):
        if not request.user.is_superuser:
            return _superuser_required_error()
        if doc_type not in TEMPLATE_LABEL_MAP:
            return api_error(
                message="Template introuvable.",
                code="template_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        template = (
            PrintTemplate.objects.filter(doc_type=doc_type).select_related("updated_by").first()
        )
        return Response(_template_payload(doc_type, template))

    def patch(self, request, doc_type):
        if not request.user.is_superuser:
            return _superuser_required_error()
        if doc_type not in TEMPLATE_LABEL_MAP:
            return api_error(
                message="Template introuvable.",
                code="template_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UiPrintTemplateMutationSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation template invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        action = payload.get("action", "save")
        layout_data = payload.get("layout", {})
        template = PrintTemplate.objects.filter(doc_type=doc_type).first()
        previous_layout = template.layout if template and template.layout else {}
        if previous_layout == layout_data:
            return Response(
                {
                    "ok": True,
                    "message": "Aucun changement detecte.",
                    "changed": False,
                    "template": _template_payload(doc_type, template),
                }
            )

        template, version = _save_print_template_layout(
            template=template,
            doc_type=doc_type,
            layout_data=layout_data,
            user=request.user,
        )
        template = PrintTemplate.objects.filter(pk=template.id).select_related("updated_by").first()
        return Response(
            {
                "ok": True,
                "message": "Template enregistre." if action == "save" else "Template reinitialise.",
                "changed": True,
                "version": version,
                "template": _template_payload(doc_type, template),
            }
        )


class UiPortalOrdersView(APIView):
    permission_classes = [IsAssociationProfileUser]

    def post(self, request):
        profile = get_association_profile(request.user)
        serializer = UiPortalOrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation commande invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        destination = Destination.objects.filter(
            pk=payload["destination_id"],
            is_active=True,
        ).first()
        if destination is None:
            return api_error(
                message="Destination invalide.",
                code="destination_invalid",
                field_errors={"destination_id": ["Destination invalide."]},
            )

        recipient_raw = (payload.get("recipient_id") or "").strip()
        if not recipient_raw:
            return api_error(
                message="Destinataire requis.",
                code="recipient_required",
                field_errors={"recipient_id": ["Destinataire requis."]},
            )
        recipient_id = recipient_raw
        if recipient_raw != PORTAL_RECIPIENT_SELF:
            try:
                recipient_id = int(recipient_raw)
            except (TypeError, ValueError):
                return api_error(
                    message="Destinataire invalide.",
                    code="recipient_invalid",
                    field_errors={"recipient_id": ["Destinataire invalide."]},
                )

        destination_payload, destination_error = _portal_order_destination_payload(
            profile=profile,
            recipient_id=recipient_id,
            selected_destination=destination,
        )
        if destination_error:
            return api_error(
                message=destination_error,
                code="destination_resolution_failed",
                non_field_errors=[destination_error],
            )

        requested_lines = payload["lines"]
        product_ids = {line["product_id"] for line in requested_lines}
        products = Product.objects.filter(is_active=True, id__in=product_ids)
        products_by_id = {product.id: product for product in products}
        missing_product_ids = sorted(product_ids - set(products_by_id))
        if missing_product_ids:
            return api_error(
                message="Produit introuvable.",
                code="product_not_found",
                field_errors={"lines": [f"Produit(s) introuvable(s): {missing_product_ids}"]},
            )

        quantity_by_product_id = {}
        for line in requested_lines:
            product_id = line["product_id"]
            quantity_by_product_id[product_id] = (
                quantity_by_product_id.get(product_id, 0) + line["quantity"]
            )
        line_items = [
            (products_by_id[product_id], quantity)
            for product_id, quantity in quantity_by_product_id.items()
        ]

        try:
            order = create_portal_order(
                user=request.user,
                profile=profile,
                recipient_name=destination_payload["recipient_name"],
                recipient_contact=destination_payload["recipient_contact"],
                destination_address=destination_payload["destination_address"],
                destination_city=destination_payload["destination_city"],
                destination_country=destination_payload["destination_country"],
                notes=payload.get("notes", ""),
                line_items=line_items,
            )
            send_portal_order_notifications(
                request,
                profile=profile,
                order=order,
            )
        except StockError as exc:
            return api_error(
                message=str(exc),
                code="portal_order_create_failed",
                non_field_errors=[str(exc)],
            )
        log_workflow_event(
            "ui_portal_order_created",
            shipment=order.shipment if order.shipment_id else None,
            user=request.user if request.user.is_authenticated else None,
            order_id=order.id,
            order_reference=order.reference or f"CMD-{order.id}",
            association_contact_id=profile.contact_id,
            line_count=len(requested_lines),
        )

        return Response(
            {
                "ok": True,
                "message": "Commande envoyee.",
                "order": {
                    "id": order.id,
                    "reference": order.reference or f"CMD-{order.id}",
                    "review_status": order.review_status,
                    "review_status_label": order.get_review_status_display(),
                    "shipment_id": order.shipment_id,
                    "shipment_reference": order.shipment.reference if order.shipment_id else "",
                    "created_at": order.created_at.isoformat(),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class UiPortalRecipientsView(APIView):
    permission_classes = [IsPortalScopeUser]

    def get(self, request):
        scope = request.portal_scope
        if (
            scope.role == PortalAccessRole.RECIPIENT_ADMIN
            and scope.recipient_organization is not None
        ):
            recipient = _portal_runtime_recipient_row(scope.recipient_organization)
            return Response(
                {
                    "mode": "recipient",
                    "recipients": [recipient],
                    "destinations": [
                        {
                            "id": scope.recipient_organization.destination_id,
                            "label": str(scope.recipient_organization.destination),
                        }
                    ],
                }
            )

        association_contact = _portal_shipper_contact_from_request(request)
        if association_contact is None:
            return api_error(
                message="Acces portail expediteur indisponible.",
                code="shipper_scope_required",
                http_status=status.HTTP_403_FORBIDDEN,
            )
        recipients = (
            AssociationRecipient.objects.filter(
                association_contact=association_contact,
                is_active=True,
            )
            .select_related("destination")
            .order_by("structure_name", "name", "contact_last_name", "contact_first_name")
        )
        destinations = Destination.objects.filter(is_active=True).order_by(
            "city", "country", "iata_code"
        )
        return Response(
            {
                "recipients": [_portal_recipient_row(recipient) for recipient in recipients],
                "destinations": [
                    {"id": destination.id, "label": str(destination)}
                    for destination in destinations
                ],
            }
        )

    def post(self, request):
        scope = request.portal_scope
        if scope.role != PortalAccessRole.SHIPPER_ADMIN:
            return api_error(
                message="Creation reservee au scope expediteur.",
                code="shipper_scope_required",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        association_contact = _portal_shipper_contact_from_request(request)
        if association_contact is None:
            return api_error(
                message="Acces portail expediteur indisponible.",
                code="shipper_scope_required",
                http_status=status.HTTP_403_FORBIDDEN,
            )
        serializer = UiPortalRecipientMutationSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation destinataire invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        destination = Destination.objects.filter(
            pk=payload["destination_id"], is_active=True
        ).first()
        if destination is None:
            return api_error(
                message="Escale de livraison requise.",
                code="destination_required",
                field_errors={"destination_id": ["Escale de livraison requise."]},
            )
        if payload.get("contact_title") and payload["contact_title"] not in dict(
            AssociationContactTitle.choices
        ):
            return api_error(
                message="Titre de contact invalide.",
                code="contact_title_invalid",
                field_errors={"contact_title": ["Titre de contact invalide."]},
            )

        email_values, invalid_values = _validate_multi_emails(payload.get("emails", ""))
        if invalid_values:
            return api_error(
                message="Emails invalides.",
                code="emails_invalid",
                field_errors={"emails": [f"Emails invalides: {', '.join(invalid_values)}."]},
            )
        if payload.get("notify_deliveries") and not email_values:
            return api_error(
                message="Ajoutez au moins un email pour activer l'alerte de livraison.",
                code="notify_email_required",
                field_errors={
                    "emails": ["Ajoutez au moins un email pour activer l'alerte de livraison."]
                },
            )

        result = update_recipient_shared_profile(
            association_contact=association_contact,
            destination=destination,
            structure_name=(payload.get("structure_name") or "").strip(),
            contact_title=(payload.get("contact_title") or "").strip(),
            contact_last_name=(payload.get("contact_last_name") or "").strip(),
            contact_first_name=(payload.get("contact_first_name") or "").strip(),
            phones=(payload.get("phones") or "").strip(),
            emails=(payload.get("emails") or "").strip(),
            address_line1=(payload.get("address_line1") or "").strip(),
            address_line2=(payload.get("address_line2") or "").strip(),
            postal_code=(payload.get("postal_code") or "").strip(),
            city=(payload.get("city") or "").strip(),
            country=((payload.get("country") or "").strip() or PORTAL_DEFAULT_COUNTRY),
            legal_form=(payload.get("legal_form") or "").strip(),
            beneficiary_count=payload.get("beneficiary_count"),
            notes=(payload.get("notes") or "").strip(),
            notify_deliveries=bool(payload.get("notify_deliveries")),
            is_delivery_contact=bool(payload.get("is_delivery_contact")),
            persist_projection=True,
        )
        recipient = result.legacy_projection
        log_workflow_event(
            "ui_portal_recipient_created",
            user=request.user if request.user.is_authenticated else None,
            recipient_id=recipient.id,
            association_contact_id=association_contact.id,
            destination_id=recipient.destination_id,
        )
        return Response(
            {
                "ok": True,
                "message": "Destinataire ajoute.",
                "recipient": _portal_recipient_row(recipient),
            },
            status=status.HTTP_201_CREATED,
        )


class UiPortalRecipientDetailView(APIView):
    permission_classes = [IsPortalScopeUser]

    def patch(self, request, recipient_id):
        serializer = UiPortalRecipientMutationSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation destinataire invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        destination = Destination.objects.filter(
            pk=payload["destination_id"], is_active=True
        ).first()
        if destination is None:
            return api_error(
                message="Escale de livraison requise.",
                code="destination_required",
                field_errors={"destination_id": ["Escale de livraison requise."]},
            )
        if payload.get("contact_title") and payload["contact_title"] not in dict(
            AssociationContactTitle.choices
        ):
            return api_error(
                message="Titre de contact invalide.",
                code="contact_title_invalid",
                field_errors={"contact_title": ["Titre de contact invalide."]},
            )

        email_values, invalid_values = _validate_multi_emails(payload.get("emails", ""))
        if invalid_values:
            return api_error(
                message="Emails invalides.",
                code="emails_invalid",
                field_errors={"emails": [f"Emails invalides: {', '.join(invalid_values)}."]},
            )
        if payload.get("notify_deliveries") and not email_values:
            return api_error(
                message="Ajoutez au moins un email pour activer l'alerte de livraison.",
                code="notify_email_required",
                field_errors={
                    "emails": ["Ajoutez au moins un email pour activer l'alerte de livraison."]
                },
            )

        scope = request.portal_scope
        if (
            scope.role == PortalAccessRole.RECIPIENT_ADMIN
            and scope.recipient_organization is not None
        ):
            if scope.recipient_organization.id != recipient_id:
                return api_error(
                    message="Destinataire introuvable.",
                    code="recipient_not_found",
                    http_status=status.HTTP_404_NOT_FOUND,
                )
            result = _update_portal_runtime_recipient_from_payload(
                recipient_organization=scope.recipient_organization,
                payload=payload,
            )
            recipient_row = _portal_runtime_recipient_row(result.recipient_organization)
            log_workflow_event(
                "ui_portal_recipient_updated",
                user=request.user if request.user.is_authenticated else None,
                recipient_id=result.recipient_organization.id,
                destination_id=result.recipient_organization.destination_id,
            )
            return Response(
                {
                    "ok": True,
                    "message": "Destinataire modifie.",
                    "recipient": recipient_row,
                }
            )

        association_contact = _portal_shipper_contact_from_request(request)
        if association_contact is None:
            return api_error(
                message="Acces portail expediteur indisponible.",
                code="shipper_scope_required",
                http_status=status.HTTP_403_FORBIDDEN,
            )
        recipient = (
            AssociationRecipient.objects.filter(
                association_contact=association_contact,
                is_active=True,
                pk=recipient_id,
            )
            .select_related("destination")
            .first()
        )
        if recipient is None:
            return api_error(
                message="Destinataire introuvable.",
                code="recipient_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        runtime_recipient_organization = None
        if recipient.synced_contact_id and recipient.destination_id:
            runtime_recipient_organization = ShipmentRecipientOrganization.objects.filter(
                organization=recipient.synced_contact,
                destination=recipient.destination,
                is_active=True,
            ).first()
        if (
            runtime_recipient_organization is not None
            and PortalAccessGrant.objects.filter(
                recipient_organization=runtime_recipient_organization,
                role=PortalAccessRole.RECIPIENT_ADMIN,
                is_active=True,
            ).exists()
        ):
            return api_error(
                message="Destinataire en lecture seule cote expediteur.",
                code="recipient_read_only",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        result = update_recipient_shared_profile(
            association_contact=association_contact,
            destination=destination,
            structure_name=(payload.get("structure_name") or "").strip(),
            contact_title=(payload.get("contact_title") or "").strip(),
            contact_last_name=(payload.get("contact_last_name") or "").strip(),
            contact_first_name=(payload.get("contact_first_name") or "").strip(),
            phones=(payload.get("phones") or "").strip(),
            emails=(payload.get("emails") or "").strip(),
            address_line1=(payload.get("address_line1") or "").strip(),
            address_line2=(payload.get("address_line2") or "").strip(),
            postal_code=(payload.get("postal_code") or "").strip(),
            city=(payload.get("city") or "").strip(),
            country=((payload.get("country") or "").strip() or PORTAL_DEFAULT_COUNTRY),
            legal_form=(payload.get("legal_form") or "").strip(),
            beneficiary_count=payload.get("beneficiary_count"),
            notes=(payload.get("notes") or "").strip(),
            notify_deliveries=bool(payload.get("notify_deliveries")),
            is_delivery_contact=bool(payload.get("is_delivery_contact")),
            persist_projection=True,
            legacy_projection=recipient,
        )
        recipient = result.legacy_projection
        log_workflow_event(
            "ui_portal_recipient_updated",
            user=request.user if request.user.is_authenticated else None,
            recipient_id=recipient.id,
            association_contact_id=association_contact.id,
            destination_id=recipient.destination_id,
        )
        return Response(
            {
                "ok": True,
                "message": "Destinataire modifie.",
                "recipient": _portal_recipient_row(recipient),
            }
        )


class UiPortalAccountView(APIView):
    permission_classes = [IsAssociationProfileUser]

    def get(self, request):
        profile = get_association_profile(request.user)
        return Response(_portal_account_summary(profile))

    def patch(self, request):
        profile = get_association_profile(request.user)
        serializer = UiPortalAccountUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                message="Validation compte invalide.",
                code="validation_error",
                field_errors=serializer_field_errors(serializer),
            )

        payload = serializer.validated_data
        contact_rows = []
        contact_errors = []
        for index, contact in enumerate(payload["contacts"]):
            row = {
                "index": index,
                "title": contact.get("title", ""),
                "last_name": contact.get("last_name", ""),
                "first_name": contact.get("first_name", ""),
                "phone": contact.get("phone", ""),
                "email": contact.get("email", ""),
                "is_administrative": bool(contact.get("is_administrative")),
                "is_shipping": bool(contact.get("is_shipping")),
                "is_billing": bool(contact.get("is_billing")),
            }
            if not (row["is_administrative"] or row["is_shipping"] or row["is_billing"]):
                contact_errors.append(f"Ligne {index + 1}: cochez au moins un type.")
            contact_rows.append(row)
        if contact_errors:
            return api_error(
                message="Validation contacts invalide.",
                code="contact_rows_invalid",
                non_field_errors=contact_errors,
            )

        form_data = {
            "association_name": payload.get("association_name", ""),
            "association_email": payload.get("association_email", ""),
            "association_phone": payload.get("association_phone", ""),
            "address_line1": payload.get("address_line1", ""),
            "address_line2": payload.get("address_line2", ""),
            "postal_code": payload.get("postal_code", ""),
            "city": payload.get("city", ""),
            "country": payload.get("country", PORTAL_DEFAULT_COUNTRY) or PORTAL_DEFAULT_COUNTRY,
        }
        _save_profile_updates(
            request=request,
            profile=profile,
            form_data=form_data,
            contact_rows=contact_rows,
        )
        profile.refresh_from_db()
        log_workflow_event(
            "ui_portal_account_updated",
            user=request.user if request.user.is_authenticated else None,
            association_contact_id=profile.contact_id,
            contact_count=len(contact_rows),
        )
        return Response(
            {
                "ok": True,
                "message": "Compte mis a jour.",
                "account": _portal_account_summary(profile),
            }
        )


class UiPortalDashboardView(APIView):
    permission_classes = [IsPortalScopeUser]

    def get(self, request):
        scope = request.portal_scope
        if (
            scope.role == PortalAccessRole.RECIPIENT_ADMIN
            and scope.recipient_organization is not None
        ):
            return Response(_portal_recipient_scope_dashboard_payload(scope.recipient_organization))

        profile = _portal_profile_from_request(request)
        if profile is None:
            return api_error(
                message="Acces portail expediteur indisponible.",
                code="shipper_scope_required",
                http_status=status.HTTP_403_FORBIDDEN,
            )
        dashboard_payload = build_portal_dashboard_payload(profile=profile)
        return Response(
            {
                "mode": "shipper",
                "kpis": dashboard_payload["dashboard_kpis"],
                "orders": dashboard_payload["order_rows"],
            }
        )
