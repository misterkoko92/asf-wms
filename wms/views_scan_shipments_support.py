import re
from datetime import date, timedelta
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    Destination,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingStatus,
)
from .runtime_settings import get_runtime_config
from .scan_list_urls import build_scan_list_url
from .shipment_view_helpers import build_shipments_tracking_rows

ACTIVE_SHIPMENT = "shipment"
ACTIVE_SHIPMENTS_READY = "shipments_ready"
ACTIVE_SHIPMENTS_DOSSIERS = "shipments_dossiers"
ACTIVE_SHIPMENTS_TRACKING = "shipments_tracking"

ARCHIVE_STALE_DRAFTS_ACTION = "archive_stale_drafts"
CLOSE_SHIPMENT_ACTION = "close_shipment_case"
CONFIRM_SHIPMENT_READY_ACTION = "confirm_shipment_ready"
CLOSED_FILTER_EXCLUDE = "exclude"
CLOSED_FILTER_ALL = "all"
DISPUTE_FILTER_ALL = "all"
DISPUTE_FILTER_OPEN = "open"
DISPUTE_FILTER_OVERDUE = "overdue"
DISPUTE_FILTER_UNASSIGNED = "unassigned"
PLANNED_WEEK_RE = re.compile(r"^(?P<year>\d{4})-(?:W)?(?P<week>\d{2})$")
RETURN_TO_SHIPMENTS_READY = "shipments_ready"
RETURN_TO_SHIPMENTS_DOSSIERS = "shipments_dossiers"
RETURN_TO_SHIPMENTS_TRACKING = "shipments_tracking"
RETURN_TO_VIEW_NAMES = {
    RETURN_TO_SHIPMENTS_READY: "scan:scan_shipments_ready",
    RETURN_TO_SHIPMENTS_DOSSIERS: "scan:scan_shipments_ready",
    RETURN_TO_SHIPMENTS_TRACKING: "scan:scan_shipments_tracking",
}
SHIPMENTS_TRACKING_PAGE_SIZE = 100


def _stale_drafts_cutoff():
    return timezone.now() - timedelta(days=_stale_drafts_age_days())


def _stale_drafts_age_days():
    return get_runtime_config().stale_drafts_age_days


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


def _normalize_dispute_filter(raw_value):
    value = (raw_value or "").strip()
    if value in {
        DISPUTE_FILTER_OPEN,
        DISPUTE_FILTER_OVERDUE,
        DISPUTE_FILTER_UNASSIGNED,
    }:
        return value
    return DISPUTE_FILTER_ALL


def _normalize_destination_filter(raw_value):
    return (raw_value or "").strip()


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
                filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT),
            ),
            delivered_at=Max(
                "tracking_events__created_at",
                filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT),
            ),
        )
        .order_by("-planned_at", "-created_at")
    )


def _build_shipments_tracking_redirect_url(
    *,
    planned_week_value,
    closed_filter,
    dispute_filter=DISPUTE_FILTER_ALL,
    destination_value="",
    query="",
):
    query_items = {}
    if planned_week_value:
        query_items["planned_week"] = planned_week_value
    if closed_filter == CLOSED_FILTER_ALL:
        query_items["closed"] = CLOSED_FILTER_ALL
    if dispute_filter != DISPUTE_FILTER_ALL:
        query_items["dispute"] = dispute_filter
    if destination_value:
        query_items["destination"] = destination_value
    if query:
        query_items["q"] = query
    base_url = reverse("scan:scan_shipments_tracking")
    if not query_items:
        return base_url
    return f"{base_url}?{urlencode(query_items)}"


def build_shipments_tracking_filter_state(source):
    planned_week_value, week_start, week_end = _parse_planned_week(source.get("planned_week"))
    destination_filter_value = _normalize_destination_filter(source.get("destination"))
    return {
        "planned_week_value": planned_week_value,
        "week_start": week_start,
        "week_end": week_end,
        "closed_filter": _normalize_closed_filter(source.get("closed")),
        "dispute_filter": _normalize_dispute_filter(source.get("dispute")),
        "destination_filter_value": destination_filter_value,
        "query": (source.get("q") or "").strip(),
        "selected_destination": (
            Destination.objects.filter(pk=destination_filter_value).first()
            if destination_filter_value
            else None
        ),
    }


def _shipment_can_be_closed(shipment):
    tracking_shipment = shipment
    if getattr(shipment, "pk", None) and not hasattr(shipment, "carton_count"):
        tracking_shipment = _build_shipments_tracking_queryset().filter(pk=shipment.pk).first()
        if tracking_shipment is None:
            return False
    rows = build_shipments_tracking_rows([tracking_shipment])
    if not rows:
        return False
    return bool(rows[0]["can_close"])


def _apply_shipments_tracking_filters(shipments_qs, *, filter_state):
    selected_destination = filter_state["selected_destination"]
    closed_filter = filter_state["closed_filter"]
    dispute_filter = filter_state["dispute_filter"]
    planned_week_value = filter_state["planned_week_value"]
    week_start = filter_state["week_start"]
    week_end = filter_state["week_end"]

    if selected_destination:
        shipments_qs = shipments_qs.filter(destination=selected_destination)
    if closed_filter == CLOSED_FILTER_EXCLUDE:
        shipments_qs = shipments_qs.filter(closed_at__isnull=True)
    if dispute_filter == DISPUTE_FILTER_OPEN:
        shipments_qs = shipments_qs.filter(is_disputed=True)
    elif dispute_filter == DISPUTE_FILTER_OVERDUE:
        shipments_qs = shipments_qs.filter(
            is_disputed=True,
            dispute_due_at__lt=timezone.now(),
        )
    elif dispute_filter == DISPUTE_FILTER_UNASSIGNED:
        shipments_qs = shipments_qs.filter(is_disputed=True, dispute_owner="")
    if planned_week_value and week_start and week_end:
        shipments_qs = shipments_qs.filter(
            planned_at__date__gte=week_start,
            planned_at__date__lt=week_end,
        )
    return shipments_qs


def _apply_shipments_tracking_search(shipments_qs, query):
    if not query:
        return shipments_qs
    return shipments_qs.filter(
        Q(reference__icontains=query)
        | Q(shipper_name__icontains=query)
        | Q(recipient_name__icontains=query)
        | Q(shipper_contact_ref__name__icontains=query)
        | Q(recipient_contact_ref__name__icontains=query)
    )


def _build_shipments_tracking_summary_cards(shipments_qs, *, params):
    base_url = reverse("scan:scan_shipments_tracking")
    list_url = build_scan_list_url(base_url, params, reset_keys={"page"})
    return [
        {
            "id": "open-disputes",
            "label": "Litiges ouverts",
            "value": shipments_qs.filter(is_disputed=True, closed_at__isnull=True).count(),
            "help": "Dossiers en litige à traiter.",
            "url": build_scan_list_url(
                base_url,
                params,
                updates={"dispute": DISPUTE_FILTER_OPEN},
                reset_keys={"page"},
            ),
            "tone": "danger",
        },
        {
            "id": "closable-cases",
            "label": "Dossiers clôturables",
            "value": shipments_qs.filter(
                status=ShipmentStatus.DELIVERED,
                is_disputed=False,
                closed_at__isnull=True,
                planned_at__isnull=False,
                boarding_ok_at__isnull=False,
                received_correspondent_at__isnull=False,
                delivered_at__isnull=False,
            ).count(),
            "help": "Toutes étapes validées, clôture possible.",
            "url": list_url,
            "tone": "success",
        },
        {
            "id": "waiting-stopover",
            "label": "En attente escale",
            "value": shipments_qs.filter(
                status=ShipmentStatus.SHIPPED,
                closed_at__isnull=True,
            ).count(),
            "help": "Expédiées sans confirmation reçu escale.",
            "url": list_url,
            "tone": "warn",
        },
        {
            "id": "waiting-delivery",
            "label": "En attente livraison",
            "value": shipments_qs.filter(
                status=ShipmentStatus.RECEIVED_CORRESPONDENT,
                closed_at__isnull=True,
            ).count(),
            "help": "Reçu escale sans livraison confirmée.",
            "url": list_url,
            "tone": "warn",
        },
    ]


def build_shipments_tracking_list_context(request):
    filter_state = build_shipments_tracking_filter_state(request.GET)
    query = filter_state["query"]
    page_number = (request.GET.get("page") or "1").strip()

    shipments_qs = _build_shipments_tracking_queryset()
    shipments_qs = _apply_shipments_tracking_filters(
        shipments_qs,
        filter_state=filter_state,
    )
    shipments_qs = _apply_shipments_tracking_search(shipments_qs, query)

    paginator = Paginator(shipments_qs, SHIPMENTS_TRACKING_PAGE_SIZE)
    shipments_page = paginator.get_page(page_number)

    page_prev_url = None
    if shipments_page.has_previous():
        page_prev_url = build_scan_list_url(
            reverse("scan:scan_shipments_tracking"),
            request.GET,
            page=shipments_page.previous_page_number(),
        )

    page_next_url = None
    if shipments_page.has_next():
        page_next_url = build_scan_list_url(
            reverse("scan:scan_shipments_tracking"),
            request.GET,
            page=shipments_page.next_page_number(),
        )

    selected_destination = filter_state["selected_destination"]
    return {
        "shipments": build_shipments_tracking_rows(shipments_page.object_list),
        "summary_cards": _build_shipments_tracking_summary_cards(
            shipments_qs,
            params=request.GET,
        ),
        "total_count": paginator.count,
        "page_size": SHIPMENTS_TRACKING_PAGE_SIZE,
        "page_obj": shipments_page,
        "shipments_page": shipments_page,
        "page_prev_url": page_prev_url,
        "page_next_url": page_next_url,
        "reset_url": build_scan_list_url(
            reverse("scan:scan_shipments_tracking"),
            request.GET,
            reset_keys={"page", "planned_week", "closed", "dispute", "destination", "q"},
        ),
        "planned_week_value": filter_state["planned_week_value"],
        "planned_week_invalid": bool(
            filter_state["planned_week_value"] and filter_state["week_start"] is None
        ),
        "closed_filter": filter_state["closed_filter"],
        "dispute_filter": filter_state["dispute_filter"],
        "destination_filter_value": str(selected_destination.id) if selected_destination else "",
        "destination_filter_label": str(selected_destination) if selected_destination else "",
        "query": query,
    }
