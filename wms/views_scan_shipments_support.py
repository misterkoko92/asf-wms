import re
from datetime import date, timedelta
from urllib.parse import urlencode

from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    Shipment,
    ShipmentStatus,
    ShipmentTrackingStatus,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
)
from .shipment_view_helpers import build_shipments_tracking_rows

ACTIVE_SHIPMENT = "shipment"
ACTIVE_SHIPMENTS_READY = "shipments_ready"
ACTIVE_SHIPMENTS_TRACKING = "shipments_tracking"

ARCHIVE_STALE_DRAFTS_ACTION = "archive_stale_drafts"
STALE_DRAFTS_AGE_DAYS = 30
CLOSE_SHIPMENT_ACTION = "close_shipment_case"
CLOSED_FILTER_EXCLUDE = "exclude"
CLOSED_FILTER_ALL = "all"
PLANNED_WEEK_RE = re.compile(r"^(?P<year>\d{4})-(?:W)?(?P<week>\d{2})$")
RETURN_TO_SHIPMENTS_READY = "shipments_ready"
RETURN_TO_SHIPMENTS_TRACKING = "shipments_tracking"
RETURN_TO_VIEW_NAMES = {
    RETURN_TO_SHIPMENTS_READY: "scan:scan_shipments_ready",
    RETURN_TO_SHIPMENTS_TRACKING: "scan:scan_shipments_tracking",
}


def _stale_drafts_cutoff():
    return timezone.now() - timedelta(days=STALE_DRAFTS_AGE_DAYS)


def _stale_drafts_queryset():
    return Shipment.objects.filter(
        archived_at__isnull=True,
        status=ShipmentStatus.DRAFT,
        reference__startswith=TEMP_SHIPMENT_REFERENCE_PREFIX,
        created_at__lt=_stale_drafts_cutoff(),
    )


def _normalize_closed_filter(raw_value):
    if (raw_value or "").strip() == CLOSED_FILTER_ALL:
        return CLOSED_FILTER_ALL
    return CLOSED_FILTER_EXCLUDE


def _parse_planned_week(raw_value):
    cleaned = (raw_value or "").strip()
    if not cleaned:
        return "", None, None
    match = PLANNED_WEEK_RE.match(cleaned)
    if not match:
        return cleaned, None, None
    year = int(match.group("year"))
    week = int(match.group("week"))
    try:
        start = date.fromisocalendar(year, week, 1)
    except ValueError:
        return f"{year:04d}-W{week:02d}", None, None
    return f"{year:04d}-W{week:02d}", start, start + timedelta(days=7)


def _normalize_return_to(raw_value):
    value = (raw_value or "").strip()
    if value in RETURN_TO_VIEW_NAMES:
        return value
    return RETURN_TO_SHIPMENTS_TRACKING


def _return_to_view_name(return_to):
    return RETURN_TO_VIEW_NAMES.get(
        return_to,
        RETURN_TO_VIEW_NAMES[RETURN_TO_SHIPMENTS_TRACKING],
    )


def _return_to_url(return_to):
    return reverse(_return_to_view_name(return_to))


def _build_shipments_tracking_queryset():
    return (
        Shipment.objects.filter(
            archived_at__isnull=True,
            status__in=[
                ShipmentStatus.PLANNED,
                ShipmentStatus.SHIPPED,
                ShipmentStatus.RECEIVED_CORRESPONDENT,
                ShipmentStatus.DELIVERED,
            ],
        )
        .select_related(
            "shipper_contact_ref__organization",
            "recipient_contact_ref__organization",
            "closed_by",
        )
        .annotate(
            carton_count=Count("carton", distinct=True),
            planned_at=Max(
                "tracking_events__created_at",
                filter=Q(tracking_events__status=ShipmentTrackingStatus.PLANNED),
            ),
            boarding_ok_at=Max(
                "tracking_events__created_at",
                filter=Q(tracking_events__status=ShipmentTrackingStatus.BOARDING_OK),
            ),
            shipped_tracking_at=Max(
                "tracking_events__created_at",
                filter=Q(tracking_events__status=ShipmentTrackingStatus.BOARDING_OK),
            ),
            received_correspondent_at=Max(
                "tracking_events__created_at",
                filter=Q(
                    tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
                ),
            ),
            delivered_at=Max(
                "tracking_events__created_at",
                filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT),
            ),
        )
        .order_by("-planned_at", "-created_at")
    )


def _build_shipments_tracking_redirect_url(*, planned_week_value, closed_filter):
    query_items = {}
    if planned_week_value:
        query_items["planned_week"] = planned_week_value
    if closed_filter == CLOSED_FILTER_ALL:
        query_items["closed"] = CLOSED_FILTER_ALL
    base_url = reverse("scan:scan_shipments_tracking")
    if not query_items:
        return base_url
    return f"{base_url}?{urlencode(query_items)}"


def _shipment_can_be_closed(shipment):
    rows = build_shipments_tracking_rows([shipment])
    if not rows:
        return False
    return bool(rows[0]["can_close"])
