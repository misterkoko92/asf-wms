import logging

from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_http_methods

from .carton_handlers import handle_carton_status_update
from .carton_view_helpers import (
    build_carton_ready_row,
    build_cartons_ready_rows,
    get_carton_capacity_cm3,
)
from .forms import (
    ScanPackForm,
    ScanPrepareKitsForm,
    ScanShipmentForm,
    ShipmentTrackingForm,
)
from .helper_install import build_helper_install_context, build_helper_installer_response
from .kits_view_helpers import build_kits_view_rows
from .local_document_helper import LOCAL_DOCUMENT_HELPER_ORIGIN
from .models import (
    Carton,
    CartonStatus,
    Destination,
    Document,
    DocumentType,
    Shipment,
    ShipmentDisputeOwner,
    ShipmentDisputeReason,
    ShipmentDisputeStatus,
    ShipmentRecipientOrganization,
    ShipmentStatus,
)
from .pack_handlers import build_pack_defaults, handle_pack_post
from .prepare_kits_helpers import (
    _parse_carton_ids,
    build_prepare_kits_page_context,
    build_prepare_kits_picking_context,
    prepare_kits,
)
from .recipient_product_preferences import score_recipient_carton_compatibility
from .runtime_settings import is_shipment_track_legacy_enabled
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
from .services import StockError
from .shipment_dossier_activity import record_shipment_dossier_activity
from .shipment_form_helpers import (
    build_carton_selection_data,
    build_shipment_edit_initial,
    build_shipment_edit_line_values,
    build_shipment_form_context,
    build_shipment_form_payload,
    build_shipment_order_line_values,
    build_shipment_order_product_options,
)
from .shipment_status import confirm_shipment_ready, shipment_can_be_confirmed_ready
from .shipment_tracking_handlers import (
    allowed_tracking_statuses_for_shipment,
    handle_shipment_tracking_post,
)
from .shipment_view_helpers import (
    build_carton_options,
    build_shipment_document_links,
    build_shipment_dossier_print_actions,
    build_shipments_ready_rows,
    build_shipments_tracking_rows,
    next_tracking_status,
)
from .status_presenters import present_shipment_status
from .view_permissions import (
    scan_staff_or_helper_installer_token_required,
    scan_staff_required,
)
from .view_utils import sorted_choices
from .views_scan_shipments_support import (
    ACTIVE_SHIPMENT,
    ACTIVE_SHIPMENTS_DOSSIERS,
    ACTIVE_SHIPMENTS_READY,
    ACTIVE_SHIPMENTS_TRACKING,
    ARCHIVE_STALE_DRAFTS_ACTION,
    CLOSE_SHIPMENT_ACTION,
    CLOSED_FILTER_EXCLUDE,
    CONFIRM_SHIPMENT_READY_ACTION,
    DISPUTE_FILTER_ALL,
    DISPUTE_FILTER_OPEN,
    DISPUTE_FILTER_OVERDUE,
    DISPUTE_FILTER_UNASSIGNED,
    RETURN_TO_SHIPMENTS_DOSSIERS,
    RETURN_TO_SHIPMENTS_TRACKING,
    _build_shipments_tracking_queryset,
    _build_shipments_tracking_redirect_url,
    _normalize_closed_filter,
    _normalize_destination_filter,
    _normalize_dispute_filter,
    _normalize_return_to,
    _parse_planned_week,
    _return_to_url,
    _return_to_view_name,
    _shipment_can_be_closed,
    _stale_drafts_age_days,
    _stale_drafts_queryset,
)
from .workflow_observability import log_shipment_case_closed

logger = logging.getLogger(__name__)

TEMPLATE_CARTONS_READY = "scan/cartons_ready.html"
TEMPLATE_KITS_VIEW = "scan/kits_view.html"
TEMPLATE_PREPARE_KITS = "scan/prepare_kits.html"
TEMPLATE_SHIPMENTS_READY = "scan/shipments_ready.html"
TEMPLATE_SHIPMENTS_TRACKING = "scan/shipments_tracking.html"
TEMPLATE_PACK = "scan/pack.html"
TEMPLATE_SHIPMENT_FORM = "scan/shipment_create.html"
TEMPLATE_SHIPMENT_DOSSIER = "scan/shipment_dossier.html"
TEMPLATE_SHIPMENT_TRACKING = "scan/shipment_tracking.html"
TEMPLATE_PICKING_LIST_KITS = "print/picking_list_kits.html"

ACTIVE_CARTONS_READY = "cartons_ready"
ACTIVE_KITS_VIEW = "kits_view"
ACTIVE_PREPARE_KITS = "prepare_kits"
ACTIVE_PACK = "pack"
LOCAL_DOCUMENT_HELPER_APP_LABEL = "asf-wms"
LOCAL_DOCUMENT_HELPER_INSTALL_ROUTE = "scan:scan_local_document_helper_installer"
EDITABLE_CARTON_ASSIGNMENT_SHIPMENT_STATUSES = (
    ShipmentStatus.DRAFT,
    ShipmentStatus.PICKING,
    ShipmentStatus.PACKED,
)

EDIT_BLOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}

DOSSIER_LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}


def _build_shipment_form_support(*, extra_carton_options=None, product_options=None):
    (
        product_options,
        available_cartons,
        destinations_json,
        shipper_contacts_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    ) = build_shipment_form_payload(product_options=product_options)
    cartons_json, allowed_carton_ids = build_carton_selection_data(
        available_cartons,
        extra_carton_options,
    )
    _annotate_carton_selection_compatibility(
        cartons_json=cartons_json,
        recipient_contacts_json=recipient_contacts_json,
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


def _annotate_carton_selection_compatibility(*, cartons_json, recipient_contacts_json):
    if not isinstance(cartons_json, list):
        return
    recipient_organization_ids = set()
    for recipient_contact in recipient_contacts_json or []:
        for recipient_organization_id in (
            recipient_contact.get("recipient_organization_ids_by_destination_id") or {}
        ).values():
            try:
                recipient_organization_ids.add(int(recipient_organization_id))
            except (TypeError, ValueError):
                continue

    recipient_organizations = {
        recipient_organization.id: recipient_organization
        for recipient_organization in ShipmentRecipientOrganization.objects.filter(
            id__in=recipient_organization_ids
        ).select_related("organization", "destination")
    }
    carton_ids = []
    for carton in cartons_json or []:
        if not isinstance(carton, dict):
            continue
        try:
            carton_ids.append(int(carton["id"]))
        except (KeyError, TypeError, ValueError):
            continue
    cartons_by_id = {
        carton.id: carton
        for carton in Carton.objects.filter(id__in=carton_ids).prefetch_related(
            "cartonitem_set__product_lot__product"
        )
    }
    as_of = timezone.now()
    for carton_row in cartons_json or []:
        if not isinstance(carton_row, dict):
            continue
        carton_object = cartons_by_id.get(carton_row.get("id"))
        compatibility_by_recipient_organization_id = {}
        if carton_object is not None:
            for (
                recipient_organization_id,
                recipient_organization,
            ) in recipient_organizations.items():
                compatibility = score_recipient_carton_compatibility(
                    recipient_organization=recipient_organization,
                    carton=carton_object,
                    as_of=as_of,
                )
                compatibility_by_recipient_organization_id[str(recipient_organization_id)] = {
                    "bucket": compatibility.bucket,
                    "score": compatibility.score,
                    "explanation": compatibility.explanation,
                }
        carton_row["compatibility_by_recipient_organization_id"] = (
            compatibility_by_recipient_organization_id
        )


def _build_local_document_helper_context(request):
    return {
        "helper_install": build_helper_install_context(
            install_url=reverse(LOCAL_DOCUMENT_HELPER_INSTALL_ROUTE),
            app_label=LOCAL_DOCUMENT_HELPER_APP_LABEL,
            request=request,
        ),
        "local_document_helper_origin": LOCAL_DOCUMENT_HELPER_ORIGIN,
    }


def _build_carton_assignment_shipment_options():
    shipments = (
        Shipment.objects.filter(
            status__in=EDITABLE_CARTON_ASSIGNMENT_SHIPMENT_STATUSES,
            is_disputed=False,
            archived_at__isnull=True,
        )
        .select_related("destination")
        .order_by("-reference", "-id")
    )
    options = []
    for shipment in shipments:
        destination = getattr(shipment, "destination", None)
        destination_label = str(destination) if destination is not None else ""
        if not destination_label:
            destination_label = shipment.destination_country or ""
        label = shipment.reference
        if destination_label:
            label = f"{label} - {destination_label}"
        options.append({"id": shipment.id, "label": label, "reference": shipment.reference})
    return options


def _render_pack_page(
    request,
    *,
    form,
    product_options,
    carton_formats,
    carton_format_id,
    carton_custom,
    line_count,
    line_values,
    line_errors,
    packing_result,
    missing_defaults,
    confirm_defaults,
    extra_context=None,
):
    context = {
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
        **_build_local_document_helper_context(request),
    }
    if extra_context:
        context.update(extra_context)
    return render(
        request,
        TEMPLATE_PACK,
        context,
    )


def _carton_is_editable(carton):
    if carton.status == CartonStatus.SHIPPED:
        return False
    shipment = getattr(carton, "shipment", None)
    if not shipment:
        return True
    if getattr(shipment, "is_disputed", False):
        return False
    return shipment.status not in EDIT_BLOCKED_SHIPMENT_STATUSES


def _build_carton_lock_notice(carton):
    if carton.status == CartonStatus.SHIPPED:
        return {
            "title": _("Colis verrouillé"),
            "body": _("Ce colis est déjà expédié et ne peut plus être modifié."),
            "tone": "warning",
        }
    shipment = getattr(carton, "shipment", None)
    if not shipment:
        return None
    if getattr(shipment, "is_disputed", False):
        return {
            "title": _("Colis verrouillé"),
            "body": _("Expédition en litige : modifications verrouillées."),
            "tone": "warning",
        }
    if shipment.status == ShipmentStatus.PLANNED:
        return {
            "title": _("Colis verrouillé"),
            "body": _("Expédition planifiée : modifications verrouillées."),
            "tone": "warning",
        }
    if shipment.status in EDIT_BLOCKED_SHIPMENT_STATUSES:
        return {
            "title": _("Colis verrouillé"),
            "body": _("Expédition verrouillée : modifications impossibles."),
            "tone": "warning",
        }
    return None


def _render_shipment_form(
    request,
    *,
    form,
    support,
    carton_count,
    line_values,
    line_errors,
    active,
    template_name=None,
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
    context.update(_build_local_document_helper_context(request))
    if extra_context:
        context.update(extra_context)
    return render(request, template_name or TEMPLATE_SHIPMENT_FORM, context)


def _build_receipt_allocation_summary(shipment):
    return list(
        shipment.receipt_allocations.select_related(
            "receipt__source_contact", "created_by"
        ).order_by(
            "receipt__received_on",
            "receipt__reference",
            "id",
        )
    )


def _build_tracking_page_data(shipment):
    documents, carton_docs, additional_docs = build_shipment_document_links(shipment, public=True)
    events = shipment.tracking_events.select_related("created_by").all()
    return documents, carton_docs, additional_docs, events


def _shipment_dossier_is_locked(shipment):
    return shipment.status in DOSSIER_LOCKED_SHIPMENT_STATUSES


def _shipment_dossier_can_edit(shipment):
    return not _shipment_dossier_is_locked(shipment) and not getattr(shipment, "is_disputed", False)


def _shipment_dossier_can_confirm_ready(shipment):
    if not _shipment_dossier_can_edit(shipment):
        return False
    return shipment_can_be_confirmed_ready(shipment)


def _shipment_dossier_extra_context(
    *,
    request,
    shipment,
    documents,
    carton_docs,
    receipt_allocations,
    can_edit,
    is_locked,
    edit_mode,
):
    return {
        "is_edit": True,
        "shipment": shipment,
        "tracking_url": shipment.get_tracking_url(request=request),
        "dossier_print_actions": build_shipment_dossier_print_actions(shipment),
        "documents": documents,
        "carton_docs": carton_docs,
        "receipt_allocations": receipt_allocations,
        "status_display": present_shipment_status(shipment),
        "is_locked": is_locked,
        "is_closed": bool(shipment.closed_at),
        "can_edit": can_edit,
        "can_confirm_ready": _shipment_dossier_can_confirm_ready(shipment),
        "can_close": _shipment_can_be_closed(shipment),
        "return_to": RETURN_TO_SHIPMENTS_DOSSIERS,
        "tracking_return_to": RETURN_TO_SHIPMENTS_DOSSIERS,
        "edit_mode": bool(edit_mode),
        "close_inactive_message": _("Il reste des étapes à valider, vérifier avant de clore"),
        "additional_document_count": documents.count(),
        "receipt_allocation_count": len(receipt_allocations),
        "carton_doc_count": len(carton_docs),
        "dossier_last_activity_at": getattr(shipment, "dossier_last_activity_at", None),
        "dossier_last_activity_label": getattr(shipment, "dossier_last_activity_label", ""),
    }


def _close_shipment_case(request, shipment):
    if shipment is None:
        messages.error(request, _("Expédition introuvable."))
        return
    if shipment.closed_at:
        messages.info(request, _("Dossier déjà clôturé."))
        return
    if not _shipment_can_be_closed(shipment):
        messages.warning(
            request,
            _("Il reste des étapes à valider, vérifier avant de clore."),
        )
        return

    shipment.closed_at = timezone.now()
    shipment.closed_by = request.user if request.user.is_authenticated else None
    shipment.save(update_fields=["closed_at", "closed_by"])
    record_shipment_dossier_activity(
        shipment=shipment,
        label="Dossier clôturé",
    )
    log_shipment_case_closed(
        shipment=shipment,
        user=request.user if request.user.is_authenticated else None,
    )
    messages.success(request, _("Dossier clôturé."))


def _confirm_shipment_ready(request, shipment):
    if shipment is None:
        messages.error(request, _("Expédition introuvable."))
        return
    if not _shipment_dossier_can_edit(shipment):
        messages.warning(request, _("Expédition verrouillée : confirmation impossible."))
        return
    try:
        confirm_shipment_ready(
            shipment=shipment,
            user=request.user if request.user.is_authenticated else None,
        )
    except StockError as exc:
        messages.error(request, str(exc))
        return

    record_shipment_dossier_activity(
        shipment=shipment,
        label="Expédition confirmée prête",
    )
    messages.success(request, _("Expédition confirmée prête."))


def _build_shipments_tracking_summary_cards(shipments):
    return [
        {
            "id": "open-disputes",
            "label": _("Litiges ouverts"),
            "value": sum(
                1
                for shipment in shipments
                if shipment.get("is_disputed") and not shipment.get("is_closed", False)
            ),
            "help": _("Dossiers en litige à traiter."),
            "url": f"{reverse('scan:scan_shipments_tracking')}?dispute=open",
            "tone": "danger",
        },
        {
            "id": "closable-cases",
            "label": _("Dossiers clôturables"),
            "value": sum(1 for shipment in shipments if shipment.get("can_close")),
            "help": _("Toutes étapes validées, clôture possible."),
            "url": reverse("scan:scan_shipments_tracking"),
            "tone": "success",
        },
        {
            "id": "waiting-stopover",
            "label": _("En attente escale"),
            "value": sum(
                1
                for shipment in shipments
                if shipment.get("status_value") == ShipmentStatus.SHIPPED
                and not shipment.get("is_closed", False)
            ),
            "help": _("Expédiées sans confirmation reçu escale."),
            "url": reverse("scan:scan_shipments_tracking"),
            "tone": "warn",
        },
        {
            "id": "waiting-delivery",
            "label": _("En attente livraison"),
            "value": sum(
                1
                for shipment in shipments
                if shipment.get("status_value") == ShipmentStatus.RECEIVED_CORRESPONDENT
                and not shipment.get("is_closed", False)
            ),
            "help": _("Reçu escale sans livraison confirmée."),
            "url": reverse("scan:scan_shipments_tracking"),
            "tone": "warn",
        },
    ]


def _format_datetime_local_value(value):
    if not value:
        return ""
    localized = timezone.localtime(value) if timezone.is_aware(value) else value
    return localized.strftime("%Y-%m-%dT%H:%M")


def _build_dispute_form_context(request, shipment):
    use_post_values = request.method == "POST" and (request.POST.get("action") or "").strip() in {
        "set_disputed",
        "resolve_dispute",
    }

    def _posted_or_current(field_name, current_value=""):
        if not use_post_values:
            return current_value
        posted_value = request.POST.get(field_name)
        if posted_value is None or posted_value == "":
            return current_value
        return posted_value

    reason_value = _posted_or_current("dispute_reason", shipment.dispute_reason or "")
    owner_value = _posted_or_current("dispute_owner", shipment.dispute_owner or "")
    status_value = _posted_or_current(
        "dispute_status",
        shipment.dispute_status or ShipmentDisputeStatus.OPEN.value,
    )
    due_at_value = _posted_or_current(
        "dispute_due_at",
        _format_datetime_local_value(getattr(shipment, "dispute_due_at", None)),
    )
    resolution_notes = _posted_or_current(
        "dispute_resolution_notes",
        shipment.dispute_resolution_notes or "",
    )

    return {
        "reason_value": reason_value,
        "owner_value": owner_value,
        "status_value": status_value,
        "due_at_value": due_at_value,
        "resolution_notes": resolution_notes,
        "reason_options": ShipmentDisputeReason.choices,
        "owner_options": ShipmentDisputeOwner.choices,
        "status_options": [
            ShipmentDisputeStatus.OPEN,
            ShipmentDisputeStatus.IN_PROGRESS,
            ShipmentDisputeStatus.WAITING_EXTERNAL,
        ],
    }


def _build_dispute_summary(shipment):
    has_dispute_data = any(
        [
            shipment.is_disputed,
            getattr(shipment, "dispute_reason", ""),
            getattr(shipment, "dispute_status", ""),
            getattr(shipment, "dispute_owner", ""),
            getattr(shipment, "dispute_resolution_notes", ""),
            getattr(shipment, "dispute_opened_at", None),
            getattr(shipment, "dispute_resolved_at", None),
        ]
    )
    if not has_dispute_data:
        return None
    opened_at = getattr(shipment, "dispute_opened_at", None) or getattr(
        shipment, "disputed_at", None
    )
    due_at = getattr(shipment, "dispute_due_at", None)
    return {
        "is_active": bool(shipment.is_disputed),
        "reason_label": shipment.get_dispute_reason_display() or _("Non renseigné"),
        "owner_label": shipment.get_dispute_owner_display() or _("Sans owner"),
        "status_label": shipment.get_dispute_status_display()
        or (ShipmentDisputeStatus.OPEN.label if shipment.is_disputed else ""),
        "due_at": due_at,
        "opened_at": opened_at,
        "resolved_at": getattr(shipment, "dispute_resolved_at", None),
        "resolution_notes": getattr(shipment, "dispute_resolution_notes", ""),
        "is_overdue": bool(shipment.is_disputed and due_at and due_at < timezone.now()),
    }


def _build_dispute_timeline(dispute_summary):
    if not dispute_summary:
        return []
    timeline = []
    if dispute_summary["opened_at"]:
        timeline.append(
            {
                "label": _("Litige ouvert"),
                "at": dispute_summary["opened_at"],
            }
        )
    if dispute_summary["due_at"]:
        timeline.append(
            {
                "label": _("Échéance"),
                "at": dispute_summary["due_at"],
            }
        )
    if dispute_summary["resolved_at"]:
        timeline.append(
            {
                "label": _("Litige résolu"),
                "at": dispute_summary["resolved_at"],
            }
        )
    return timeline


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
    is_staff_user = bool(request.user.is_authenticated and request.user.is_staff)
    dispute_summary = _build_dispute_summary(shipment)
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
            "can_manage_dispute": is_staff_user,
            "show_back_to_list": is_staff_user,
            "back_to_url": back_to_url,
            "return_to": return_to,
            "dispute_summary": dispute_summary,
            "dispute_timeline": _build_dispute_timeline(dispute_summary),
            "dispute_form": _build_dispute_form_context(request, shipment),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_cartons_ready(request):
    if request.method == "POST":
        bulk_document = (request.POST.get("bulk_document") or "").strip()
        selected_carton_ids = [
            value for value in request.POST.getlist("selected_carton_ids") if value
        ]
        if bulk_document and selected_carton_ids:
            carton_ids_value = ",".join(selected_carton_ids)
            if bulk_document == "picking":
                return redirect(
                    f"{reverse('scan:scan_cartons_picking')}?carton_ids={carton_ids_value}"
                )
            if bulk_document == "packing_lists":
                return redirect(
                    f"{reverse('scan:scan_cartons_view_bundle', args=['packing_lists'])}?carton_ids={carton_ids_value}"
                )

    response = handle_carton_status_update(request)
    if response:
        return response

    carton_capacity_cm3 = get_carton_capacity_cm3()
    shipment_reference_filter = (request.GET.get("shipment_reference") or "").strip()

    cartons_qs = (
        Carton.objects.filter(cartonitem__isnull=False)
        .select_related("shipment", "current_location", "preassigned_destination")
        .prefetch_related("cartonitem_set__product_lot__product", "status_events")
        .distinct()
        .order_by("-created_at")
    )
    if shipment_reference_filter:
        cartons_qs = cartons_qs.filter(shipment__reference__iexact=shipment_reference_filter)
    cartons = build_cartons_ready_rows(cartons_qs, carton_capacity_cm3=carton_capacity_cm3)

    return render(
        request,
        TEMPLATE_CARTONS_READY,
        {
            "active": ACTIVE_CARTONS_READY,
            "cartons": cartons,
            "editable_shipments": _build_carton_assignment_shipment_options(),
            "carton_status_choices": sorted_choices(
                [
                    (CartonStatus.DRAFT, CartonStatus.DRAFT.label),
                    (CartonStatus.PICKING, CartonStatus.PICKING.label),
                    (CartonStatus.PACKED, CartonStatus.PACKED.label),
                ]
            ),
            "shipment_reference_filter": shipment_reference_filter,
            **_build_local_document_helper_context(request),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_kits_view(request):
    return render(
        request,
        TEMPLATE_KITS_VIEW,
        {
            "active": ACTIVE_KITS_VIEW,
            "kits": build_kits_view_rows(),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_prepare_kits(request):
    selected_kit_id = (
        request.POST.get("kit_id") if request.method == "POST" else request.GET.get("kit_id")
    )
    form_initial = {}
    if request.method == "GET" and selected_kit_id:
        form_initial["kit_id"] = selected_kit_id
    form = ScanPrepareKitsForm(request.POST or None, initial=form_initial)

    prepared_carton_ids = None
    if request.method == "GET":
        prepared_carton_ids = request.session.pop("prepare_kits_results", None)
    elif form.is_valid():
        kit = form.cleaned_data["kit_id"]
        quantity = form.cleaned_data["quantity"]
        try:
            prepared_carton_ids = prepare_kits(
                user=request.user,
                kit=kit,
                quantity=quantity,
            )
        except StockError as exc:
            form.add_error(None, str(exc))
        else:
            request.session["prepare_kits_results"] = prepared_carton_ids
            messages.success(
                request,
                ngettext(
                    "%(quantity)s kit ajouté en préparation.",
                    "%(quantity)s kits ajoutés en préparation.",
                    quantity,
                )
                % {"quantity": quantity},
            )
            return redirect(f"{reverse('scan:scan_prepare_kits')}?kit_id={kit.id}")

    page_context = build_prepare_kits_page_context(
        selected_kit_id=selected_kit_id,
        prepared_carton_ids=prepared_carton_ids,
    )
    return render(
        request,
        TEMPLATE_PREPARE_KITS,
        {
            "active": ACTIVE_PREPARE_KITS,
            "form": form,
            **page_context,
            **_build_local_document_helper_context(request),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_prepare_kits_picking(request):
    carton_ids = _parse_carton_ids(request.GET.get("carton_ids"))
    context = build_prepare_kits_picking_context(carton_ids)
    if context is None:
        raise Http404(_("Aucun picking disponible."))
    return render(
        request,
        TEMPLATE_PICKING_LIST_KITS,
        context,
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
                    ngettext(
                        "%(count)s brouillon temporaire archivé.",
                        "%(count)s brouillons temporaires archivés.",
                        archived_count,
                    )
                    % {"count": archived_count},
                )
            else:
                messages.info(request, _("Aucun brouillon temporaire ancien à archiver."))
        return redirect("scan:scan_shipments_ready")

    search_query = (request.GET.get("q") or "").strip()
    shipments_qs = (
        Shipment.objects.filter(archived_at__isnull=True)
        .select_related(
            "destination",
            "shipper_contact_ref__organization",
            "recipient_contact_ref__organization",
        )
        .prefetch_related("carton_set__cartonitem_set__product_lot__product__category__parent")
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
    if search_query:
        shipments_qs = shipments_qs.filter(
            Q(reference__icontains=search_query)
            | Q(shipper_name__icontains=search_query)
            | Q(recipient_name__icontains=search_query)
            | Q(destination__city__icontains=search_query)
            | Q(destination__country__icontains=search_query)
            | Q(destination__iata_code__icontains=search_query)
        ).distinct()
    shipments = build_shipments_ready_rows(shipments_qs)
    stale_draft_count = _stale_drafts_queryset().count()

    return render(
        request,
        TEMPLATE_SHIPMENTS_READY,
        {
            "active": ACTIVE_SHIPMENTS_DOSSIERS,
            "shipments": shipments,
            "search_query": search_query,
            "stale_draft_count": stale_draft_count,
            "stale_draft_days": _stale_drafts_age_days(),
            **_build_local_document_helper_context(request),
        },
    )


@scan_staff_or_helper_installer_token_required(app_label=LOCAL_DOCUMENT_HELPER_APP_LABEL)
@require_http_methods(["GET"])
def scan_local_document_helper_installer(request):
    return build_helper_installer_response(
        request=request,
        app_label=LOCAL_DOCUMENT_HELPER_APP_LABEL,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_shipments_tracking(request):
    source = request.POST if request.method == "POST" else request.GET
    planned_week_value, week_start, week_end = _parse_planned_week(source.get("planned_week"))
    closed_filter = _normalize_closed_filter(source.get("closed"))
    dispute_filter = _normalize_dispute_filter(source.get("dispute"))
    destination_filter_value = _normalize_destination_filter(source.get("destination"))
    selected_destination = None
    if destination_filter_value:
        selected_destination = Destination.objects.filter(pk=destination_filter_value).first()

    if request.method == "POST":
        if (request.POST.get("action") or "").strip() == CLOSE_SHIPMENT_ACTION:
            shipment = (
                _build_shipments_tracking_queryset()
                .filter(pk=request.POST.get("shipment_id"))
                .first()
            )
            _close_shipment_case(request, shipment)
        return redirect(
            _build_shipments_tracking_redirect_url(
                planned_week_value=planned_week_value,
                closed_filter=closed_filter,
                dispute_filter=dispute_filter,
                destination_value=(
                    str(selected_destination.id)
                    if selected_destination
                    else destination_filter_value
                ),
            )
        )

    shipments_qs = _build_shipments_tracking_queryset()
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
    elif planned_week_value and week_start is None:
        messages.warning(
            request,
            _("Format semaine invalide. Utilisez AAAA-Wss ou AAAA-ss."),
        )

    shipments = build_shipments_tracking_rows(shipments_qs)
    summary_cards = _build_shipments_tracking_summary_cards(shipments)
    return render(
        request,
        TEMPLATE_SHIPMENTS_TRACKING,
        {
            "active": ACTIVE_SHIPMENTS_TRACKING,
            "shipments": shipments,
            "summary_cards": summary_cards,
            "planned_week_value": planned_week_value,
            "closed_filter": closed_filter,
            "dispute_filter": dispute_filter,
            "destination_filter_value": str(selected_destination.id)
            if selected_destination
            else "",
            "destination_filter_label": str(selected_destination) if selected_destination else "",
            "close_inactive_message": _("Il reste des étapes à valider, vérifier avant de clore"),
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
        response, pack_state = handle_pack_post(request, form=form, default_format=default_format)
        carton_format_id = pack_state["carton_format_id"]
        carton_custom = pack_state["carton_custom"]
        line_count = pack_state["line_count"]
        line_values = pack_state["line_values"]
        line_errors = pack_state["line_errors"]
        missing_defaults = pack_state.get("missing_defaults", [])
        confirm_defaults = pack_state.get("confirm_defaults", True)
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
        confirm_defaults = True
    return _render_pack_page(
        request,
        form=form,
        product_options=product_options,
        carton_formats=carton_formats,
        carton_format_id=carton_format_id,
        carton_custom=carton_custom,
        line_count=line_count,
        line_values=line_values,
        line_errors=line_errors,
        packing_result=packing_result,
        missing_defaults=missing_defaults,
        confirm_defaults=confirm_defaults,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_carton_edit(request, carton_id):
    editing_carton = get_object_or_404(
        Carton.objects.select_related(
            "shipment",
            "preassigned_destination",
            "current_location",
        ).prefetch_related("cartonitem_set__product_lot__product"),
        pk=carton_id,
    )
    carton_can_edit = _carton_is_editable(editing_carton)
    if request.method == "POST" and not carton_can_edit:
        messages.error(request, _("Impossible de modifier ce colis."))
        return redirect("scan:scan_cartons_ready")

    form_initial = {}
    if request.method == "GET":
        if editing_carton.shipment_id:
            form_initial["shipment_reference"] = editing_carton.shipment.reference
        elif editing_carton.preassigned_destination_id:
            form_initial["preassigned_destination"] = editing_carton.preassigned_destination
        if editing_carton.current_location_id:
            form_initial["current_location"] = editing_carton.current_location

    form = ScanPackForm(request.POST or None, initial=form_initial)
    packing_result = None
    if carton_can_edit:
        product_options = build_product_options(include_kits=True)
        carton_formats, default_format = build_carton_formats()
        line_errors = {}

        if request.method == "POST":
            response, pack_state = handle_pack_post(
                request,
                form=form,
                default_format=default_format,
                editing_carton=editing_carton,
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
            ) = build_pack_defaults(default_format, carton=editing_carton)
            missing_defaults = []
            confirm_defaults = False
    else:
        product_options = []
        carton_formats = []
        carton_custom = {
            "length_cm": editing_carton.length_cm or "",
            "width_cm": editing_carton.width_cm or "",
            "height_cm": editing_carton.height_cm or "",
            "max_weight_g": "",
        }
        carton_format_id = "custom"
        line_count = 0
        line_values = []
        line_errors = {}
        missing_defaults = []
        confirm_defaults = False

    carton_summary = build_carton_ready_row(
        editing_carton,
        carton_capacity_cm3=get_carton_capacity_cm3(),
    )
    carton_shipment_url = (
        reverse("scan:scan_shipment_edit", args=[editing_carton.shipment_id])
        if editing_carton.shipment_id
        else ""
    )
    carton_documents = [
        {
            "label": _("Liste de colisage"),
            "url": carton_summary["packing_list_url"],
        },
        {
            "label": _("Picking"),
            "url": carton_summary["picking_url"],
        },
    ]

    return _render_pack_page(
        request,
        form=form,
        product_options=product_options,
        carton_formats=carton_formats,
        carton_format_id=carton_format_id,
        carton_custom=carton_custom,
        line_count=line_count,
        line_values=line_values,
        line_errors=line_errors,
        packing_result=packing_result,
        missing_defaults=missing_defaults,
        confirm_defaults=confirm_defaults,
        extra_context={
            "active": ACTIVE_CARTONS_READY,
            "editing_carton": editing_carton,
            "carton_can_edit": carton_can_edit,
            "carton_edit_mode": request.method == "POST",
            "carton_summary": carton_summary,
            "carton_documents": carton_documents,
            "carton_shipment_url": carton_shipment_url,
            "carton_lock_notice": None
            if carton_can_edit
            else _build_carton_lock_notice(editing_carton),
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
        carton_count = form.initial.get("carton_count", 0) or 0
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
    shipment.ensure_qr_code(request=request)

    assigned_cartons_qs = shipment.carton_set.prefetch_related(
        "cartonitem_set__product_lot__product"
    ).order_by("code")
    assigned_cartons = list(assigned_cartons_qs)
    documents = Document.objects.filter(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL
    ).order_by("-generated_at")
    carton_docs = [{"id": carton.id, "code": carton.code} for carton in assigned_cartons]
    receipt_allocations = _build_receipt_allocation_summary(shipment)
    is_locked = _shipment_dossier_is_locked(shipment)
    can_edit = _shipment_dossier_can_edit(shipment)
    edit_mode = can_edit and (
        request.method == "POST" or (request.GET.get("mode") or "").strip() == "edit"
    )

    action = (request.POST.get("action") or "").strip()
    if request.method == "POST" and action == CLOSE_SHIPMENT_ACTION:
        _close_shipment_case(request, shipment)
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    if request.method == "POST" and action == CONFIRM_SHIPMENT_READY_ACTION:
        _confirm_shipment_ready(request, shipment)
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    if request.method == "POST" and not can_edit:
        if getattr(shipment, "is_disputed", False):
            messages.error(request, _("Expédition en litige: modification des colis impossible."))
        else:
            messages.error(request, _("Expédition verrouillée: modification des colis impossible."))
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    if not can_edit:
        return render(
            request,
            TEMPLATE_SHIPMENT_DOSSIER,
            {
                "active": ACTIVE_SHIPMENTS_DOSSIERS,
                **_build_local_document_helper_context(request),
                **_shipment_dossier_extra_context(
                    request=request,
                    shipment=shipment,
                    documents=documents,
                    carton_docs=carton_docs,
                    receipt_allocations=receipt_allocations,
                    can_edit=False,
                    is_locked=is_locked,
                    edit_mode=False,
                ),
            },
        )

    assigned_carton_options = build_carton_options(assigned_cartons)
    related_order = None
    try:
        related_order = shipment.order
    except Shipment.order.RelatedObjectDoesNotExist:
        related_order = None
    related_order_lines = []
    if related_order is not None:
        related_order_lines = list(
            related_order.lines.select_related("product").order_by("product__name")
        )
    order_line_values = []
    if not assigned_cartons:
        if related_order_lines:
            order_line_values = build_shipment_order_line_values(related_order_lines)
    order_product_options = None
    if related_order is not None:
        order_product_options = build_shipment_order_product_options(related_order_lines)

    initial = build_shipment_edit_initial(
        shipment,
        assigned_cartons,
        order_line_count=len(order_line_values),
    )
    destination_id = request.POST.get("destination") or initial["destination"]
    form = ScanShipmentForm(request.POST or None, destination_id=destination_id, initial=initial)
    support = _build_shipment_form_support(
        extra_carton_options=assigned_carton_options,
        product_options=order_product_options,
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

    return _render_shipment_form(
        request,
        form=form,
        support=support,
        carton_count=carton_count,
        line_values=line_values,
        line_errors=line_errors,
        active=ACTIVE_SHIPMENTS_DOSSIERS,
        template_name=TEMPLATE_SHIPMENT_DOSSIER,
        extra_context=_shipment_dossier_extra_context(
            request=request,
            shipment=shipment,
            documents=documents,
            carton_docs=carton_docs,
            receipt_allocations=receipt_allocations,
            can_edit=can_edit,
            is_locked=is_locked,
            edit_mode=edit_mode,
        ),
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
    if not is_shipment_track_legacy_enabled():
        raise Http404
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    logger.info(
        "Legacy shipment tracking endpoint used",
        extra={
            "shipment_reference": shipment.reference,
            "user_id": getattr(request.user, "id", None),
            "path": request.path,
        },
    )
    shipment.ensure_qr_code(request=request)
    response = _render_shipment_tracking(
        request,
        shipment=shipment,
        tracking_url="",
        form=None,
        can_update_tracking=False,
        back_to_url=_return_to_url(RETURN_TO_SHIPMENTS_TRACKING),
        return_to=RETURN_TO_SHIPMENTS_TRACKING,
    )
    response["X-ASF-Legacy-Endpoint"] = "shipment-track-by-reference; status=deprecated"
    response["X-ASF-Legacy-Sunset"] = "2026-06-30"
    return response
