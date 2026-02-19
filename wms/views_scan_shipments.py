import re
from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .carton_handlers import handle_carton_status_update
from .carton_view_helpers import build_cartons_ready_rows, get_carton_capacity_cm3
from .forms import ScanPackForm, ScanShipmentForm, ShipmentTrackingForm
from .models import (

    Carton,
    CartonStatus,
    Document,
    DocumentType,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingStatus,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
)
from .pack_handlers import build_pack_defaults, handle_pack_post
from .scan_helpers import (
    build_carton_formats,
    build_packing_result,
    build_product_options,
    build_shipment_line_values,
)
from .scan_shipment_handlers import (
    handle_shipment_create_post,
    handle_shipment_edit_post,
)
from .shipment_form_helpers import (
    build_carton_selection_data,
    build_shipment_edit_initial,
    build_shipment_edit_line_values,
    build_shipment_form_context,
    build_shipment_form_payload,
    build_shipment_order_line_values,
)
from .shipment_tracking_handlers import (
    allowed_tracking_statuses_for_shipment,
    handle_shipment_tracking_post,
)
from .shipment_view_helpers import (
    build_carton_options,
    build_shipment_document_links,
    build_shipments_ready_rows,
    build_shipments_tracking_rows,
    next_tracking_status,
)
from .view_permissions import scan_staff_required
from .view_utils import sorted_choices

TEMPLATE_CARTONS_READY = "scan/cartons_ready.html"
TEMPLATE_SHIPMENTS_READY = "scan/shipments_ready.html"
TEMPLATE_SHIPMENTS_TRACKING = "scan/shipments_tracking.html"
TEMPLATE_PACK = "scan/pack.html"
TEMPLATE_SHIPMENT_FORM = "scan/shipment_create.html"
TEMPLATE_SHIPMENT_TRACKING = "scan/shipment_tracking.html"

ACTIVE_CARTONS_READY = "cartons_ready"
ACTIVE_SHIPMENTS_READY = "shipments_ready"
ACTIVE_SHIPMENTS_TRACKING = "shipments_tracking"
ACTIVE_PACK = "pack"
ACTIVE_SHIPMENT = "shipment"
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


def _build_shipment_form_support(*, extra_carton_options=None):
    (
        product_options,
        available_cartons,
        destinations_json,
        shipper_contacts_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    ) = build_shipment_form_payload()
    cartons_json, allowed_carton_ids = build_carton_selection_data(
        available_cartons,
        extra_carton_options,
    )
    return {
        "product_options": product_options,
        "cartons_json": cartons_json,
        "allowed_carton_ids": allowed_carton_ids,
        "destinations_json": destinations_json,
        "shipper_contacts_json": shipper_contacts_json,
        "recipient_contacts_json": recipient_contacts_json,
        "correspondent_contacts_json": correspondent_contacts_json,
    }


def _render_shipment_form(
    request,
    *,
    form,
    support,
    carton_count,
    line_values,
    line_errors,
    active,
    extra_context=None,
):
    context = build_shipment_form_context(
        form=form,
        product_options=support["product_options"],
        cartons_json=support["cartons_json"],
        carton_count=carton_count,
        line_values=line_values,
        line_errors=line_errors,
        destinations_json=support["destinations_json"],
        shipper_contacts_json=support["shipper_contacts_json"],
        recipient_contacts_json=support["recipient_contacts_json"],
        correspondent_contacts_json=support["correspondent_contacts_json"],
    )
    context["active"] = active
    if extra_context:
        context.update(extra_context)
    return render(request, TEMPLATE_SHIPMENT_FORM, context)


def _build_tracking_page_data(shipment):
    documents, carton_docs, additional_docs = build_shipment_document_links(
        shipment, public=True
    )
    events = shipment.tracking_events.select_related("created_by").all()
    return documents, carton_docs, additional_docs, events


def _render_shipment_tracking(
    request,
    *,
    shipment,
    tracking_url,
    form,
    can_update_tracking,
    back_to_url,
    return_to,
):
    documents, carton_docs, additional_docs, events = _build_tracking_page_data(shipment)
    return render(
        request,
        TEMPLATE_SHIPMENT_TRACKING,
        {
            "shipment": shipment,
            "active": ACTIVE_SHIPMENTS_READY,
            "tracking_url": tracking_url,
            "documents": documents,
            "carton_docs": carton_docs,
            "additional_docs": additional_docs,
            "events": events,
            "form": form,
            "can_update_tracking": can_update_tracking,
            "show_back_to_list": bool(
                request.user.is_authenticated and request.user.is_staff
            ),
            "back_to_url": back_to_url,
            "return_to": return_to,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_cartons_ready(request):
    response = handle_carton_status_update(request)
    if response:
        return response

    carton_capacity_cm3 = get_carton_capacity_cm3()

    cartons_qs = (
        Carton.objects.filter(cartonitem__isnull=False)
        .select_related("shipment", "current_location")
        .prefetch_related("cartonitem_set__product_lot__product")
        .distinct()
        .order_by("-created_at")
    )
    cartons = build_cartons_ready_rows(
        cartons_qs, carton_capacity_cm3=carton_capacity_cm3
    )

    return render(
        request,
        TEMPLATE_CARTONS_READY,
        {
            "active": ACTIVE_CARTONS_READY,
            "cartons": cartons,
            "carton_status_choices": sorted_choices(
                [
                    (CartonStatus.DRAFT, CartonStatus.DRAFT.label),
                    (CartonStatus.PICKING, CartonStatus.PICKING.label),
                    (CartonStatus.PACKED, CartonStatus.PACKED.label),
                ]
            ),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_shipments_ready(request):
    if request.method == "POST":
        if (request.POST.get("action") or "").strip() == ARCHIVE_STALE_DRAFTS_ACTION:
            archived_count = _stale_drafts_queryset().update(archived_at=timezone.now())
            if archived_count:
                messages.success(
                    request,
                    f"{archived_count} brouillon(s) temporaire(s) archivé(s).",
                )
            else:
                messages.info(request, "Aucun brouillon temporaire ancien à archiver.")
        return redirect("scan:scan_shipments_ready")

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
                filter=Q(
                    carton__status__in=[CartonStatus.LABELED, CartonStatus.SHIPPED]
                ),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )
    shipments = build_shipments_ready_rows(shipments_qs)
    stale_draft_count = _stale_drafts_queryset().count()

    return render(
        request,
        TEMPLATE_SHIPMENTS_READY,
        {
            "active": ACTIVE_SHIPMENTS_READY,
            "shipments": shipments,
            "stale_draft_count": stale_draft_count,
            "stale_draft_days": STALE_DRAFTS_AGE_DAYS,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_shipments_tracking(request):
    source = request.POST if request.method == "POST" else request.GET
    planned_week_value, week_start, week_end = _parse_planned_week(
        source.get("planned_week")
    )
    closed_filter = _normalize_closed_filter(source.get("closed"))

    if request.method == "POST":
        if (request.POST.get("action") or "").strip() == CLOSE_SHIPMENT_ACTION:
            shipment = _build_shipments_tracking_queryset().filter(
                pk=request.POST.get("shipment_id")
            ).first()
            if shipment is None:
                messages.error(request, "Expédition introuvable.")
            elif shipment.closed_at:
                messages.info(request, "Dossier déjà clôturé.")
            elif not _shipment_can_be_closed(shipment):
                messages.warning(
                    request,
                    "Il reste des étapes à valider, vérifier avant de clore.",
                )
            else:
                shipment.closed_at = timezone.now()
                shipment.closed_by = (
                    request.user if request.user.is_authenticated else None
                )
                shipment.save(update_fields=["closed_at", "closed_by"])
                messages.success(request, "Dossier clôturé.")
        return redirect(
            _build_shipments_tracking_redirect_url(
                planned_week_value=planned_week_value,
                closed_filter=closed_filter,
            )
        )

    shipments_qs = _build_shipments_tracking_queryset()
    if closed_filter == CLOSED_FILTER_EXCLUDE:
        shipments_qs = shipments_qs.filter(closed_at__isnull=True)
    if planned_week_value and week_start and week_end:
        shipments_qs = shipments_qs.filter(
            planned_at__date__gte=week_start,
            planned_at__date__lt=week_end,
        )
    elif planned_week_value and week_start is None:
        messages.warning(
            request,
            "Format semaine invalide. Utilisez AAAA-Wss ou AAAA-ss.",
        )

    shipments = build_shipments_tracking_rows(shipments_qs)
    return render(
        request,
        TEMPLATE_SHIPMENTS_TRACKING,
        {
            "active": ACTIVE_SHIPMENTS_TRACKING,
            "shipments": shipments,
            "planned_week_value": planned_week_value,
            "closed_filter": closed_filter,
            "close_inactive_message": "Il reste des étapes à valider, vérifier avant de clore",
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_pack(request):
    form_initial = {}
    if request.method == "GET":
        shipment_reference = (request.GET.get("shipment_reference") or "").strip()
        if shipment_reference:
            form_initial["shipment_reference"] = shipment_reference
    form = ScanPackForm(request.POST or None, initial=form_initial)
    product_options = build_product_options(include_kits=True)
    carton_formats, default_format = build_carton_formats()
    line_errors = {}
    packing_result = None

    packed_carton_ids = request.session.pop("pack_results", None)
    if packed_carton_ids:
        packing_result = build_packing_result(packed_carton_ids)

    if request.method == "POST":
        response, pack_state = handle_pack_post(
            request, form=form, default_format=default_format
        )
        carton_format_id = pack_state["carton_format_id"]
        carton_custom = pack_state["carton_custom"]
        line_count = pack_state["line_count"]
        line_values = pack_state["line_values"]
        line_errors = pack_state["line_errors"]
        missing_defaults = pack_state.get("missing_defaults", [])
        confirm_defaults = pack_state.get("confirm_defaults", False)
        if response:
            return response
    else:
        (
            carton_format_id,
            carton_custom,
            line_count,
            line_values,
        ) = build_pack_defaults(default_format)
        missing_defaults = []
        confirm_defaults = False
    return render(
        request,
        TEMPLATE_PACK,
        {
            "form": form,
            "active": ACTIVE_PACK,
            "products_json": product_options,
            "carton_formats": carton_formats,
            "carton_format_id": carton_format_id,
            "carton_custom": carton_custom,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
            "packing_result": packing_result,
            "missing_defaults": missing_defaults,
            "confirm_defaults": confirm_defaults,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_shipment_create(request):
    destination_id = request.POST.get("destination") or request.GET.get("destination")
    form = ScanShipmentForm(request.POST or None, destination_id=destination_id)
    support = _build_shipment_form_support()
    line_errors = {}
    line_values = []

    if request.method == "POST":
        response, carton_count, line_values, line_errors = handle_shipment_create_post(
            request,
            form=form,
            available_carton_ids=support["allowed_carton_ids"],
        )
        if response:
            return response
    else:
        carton_count = form.initial.get("carton_count", 1)
        line_values = build_shipment_line_values(carton_count)

    return _render_shipment_form(
        request,
        form=form,
        support=support,
        carton_count=carton_count,
        line_values=line_values,
        line_errors=line_errors,
        active=ACTIVE_SHIPMENT,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_shipment_edit(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related(
            "destination__correspondent_contact",
            "shipper_contact_ref",
            "recipient_contact_ref",
            "correspondent_contact_ref",
        ),
        pk=shipment_id,
        archived_at__isnull=True,
    )
    if shipment.status in {
        ShipmentStatus.PLANNED,
        ShipmentStatus.SHIPPED,
        ShipmentStatus.RECEIVED_CORRESPONDENT,
        ShipmentStatus.DELIVERED,
    }:
        messages.error(request, "Expédition non modifiable.")
        return redirect("scan:scan_shipments_ready")

    shipment.ensure_qr_code(request=request)

    assigned_cartons_qs = shipment.carton_set.prefetch_related(
        "cartonitem_set__product_lot__product"
    ).order_by("code")
    assigned_cartons = list(assigned_cartons_qs)
    assigned_carton_options = build_carton_options(assigned_cartons)
    order_line_values = []
    if not assigned_cartons:
        related_order = None
        try:
            related_order = shipment.order
        except Shipment.order.RelatedObjectDoesNotExist:
            related_order = None
        if related_order is not None:
            order_line_values = build_shipment_order_line_values(
                related_order.lines.select_related("product").order_by("product__name")
            )

    initial = build_shipment_edit_initial(
        shipment,
        assigned_cartons,
        order_line_count=len(order_line_values),
    )
    destination_id = request.POST.get("destination") or initial["destination"]
    form = ScanShipmentForm(
        request.POST or None, destination_id=destination_id, initial=initial
    )
    support = _build_shipment_form_support(
        extra_carton_options=assigned_carton_options
    )
    line_errors = {}
    line_values = []

    if request.method == "POST":
        response, carton_count, line_values, line_errors = handle_shipment_edit_post(
            request,
            form=form,
            shipment=shipment,
            allowed_carton_ids=support["allowed_carton_ids"],
        )
        if response:
            return response
    else:
        carton_count = initial["carton_count"]
        line_values = build_shipment_edit_line_values(
            assigned_cartons,
            carton_count,
            order_line_values=order_line_values,
        )

    documents = Document.objects.filter(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL
    ).order_by("-generated_at")
    carton_docs = [{"id": carton.id, "code": carton.code} for carton in assigned_cartons]

    return _render_shipment_form(
        request,
        form=form,
        support=support,
        carton_count=carton_count,
        line_values=line_values,
        line_errors=line_errors,
        active=ACTIVE_SHIPMENTS_READY,
        extra_context={
            "is_edit": True,
            "shipment": shipment,
            "tracking_url": shipment.get_tracking_url(request=request),
            "documents": documents,
            "carton_docs": carton_docs,
        },
    )


@require_http_methods(["GET", "POST"])
def scan_shipment_track(request, tracking_token):
    shipment = get_object_or_404(Shipment, tracking_token=tracking_token)
    shipment.ensure_qr_code(request=request)
    source = request.POST if request.method == "POST" else request.GET
    return_to = _normalize_return_to(source.get("return_to"))
    last_event = shipment.tracking_events.order_by("-created_at").first()
    allowed_statuses = allowed_tracking_statuses_for_shipment(shipment)
    next_status = next_tracking_status(last_event.status if last_event else None)
    if allowed_statuses and next_status not in allowed_statuses:
        next_status = allowed_statuses[0]
    form = ShipmentTrackingForm(
        request.POST or None,
        initial_status=next_status,
        allowed_statuses=allowed_statuses,
    )
    return_to_list = (
        request.method == "POST"
        and request.user.is_authenticated
        and request.user.is_staff
        and (request.POST.get("return_to_list") or "").strip() == "1"
    )
    return_to_view = _return_to_view_name(return_to) if return_to_list else None
    response = handle_shipment_tracking_post(
        request,
        shipment=shipment,
        form=form,
        return_to_list=return_to_list,
        return_to_view=return_to_view,
        return_to_key=return_to,
    )
    if response:
        return response
    return _render_shipment_tracking(
        request,
        shipment=shipment,
        tracking_url=shipment.get_tracking_url(request=request),
        form=form,
        can_update_tracking=True,
        back_to_url=_return_to_url(return_to),
        return_to=return_to,
    )


@require_http_methods(["GET"])
def scan_shipment_track_legacy(request, shipment_ref):
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    shipment.ensure_qr_code(request=request)
    return _render_shipment_tracking(
        request,
        shipment=shipment,
        tracking_url="",
        form=None,
        can_update_tracking=False,
        back_to_url=_return_to_url(RETURN_TO_SHIPMENTS_TRACKING),
        return_to=RETURN_TO_SHIPMENTS_TRACKING,
    )
