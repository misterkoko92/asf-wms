import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_http_methods

from contacts.models import Contact

from .carton_handlers import handle_carton_status_update
from .carton_view_helpers import (
    build_carton_ready_row,
    build_cartons_ready_rows,
    get_carton_capacity_cm3,
)
from .emailing import send_or_enqueue_email_safe
from .forms import (
    ScanPackForm,
    ScanPackUnknownProductForm,
    ScanPrepareKitsForm,
    ScanShipmentForm,
    ShipmentTrackingAccessRecoveryForm,
    ShipmentTrackingForm,
    ShipmentTrackingGatewayForm,
    ShipmentTrackingPendingAccountForm,
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
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    Shipment,
    ShipmentDisputeOwner,
    ShipmentDisputeReason,
    ShipmentDisputeStatus,
    ShipmentRecipientOrganization,
    ShipmentStatus,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingIdentityStatus,
    VolunteerAccountRequest,
    VolunteerAccountRequestStatus,
    VolunteerProfile,
)
from .order_helpers import resolve_linked_order_for_shipment
from .pack_handlers import (
    build_pack_defaults,
    create_preparateur_unknown_product_from_pack,
    handle_pack_post,
)
from .preparateur_orders import (
    build_preparateur_selected_order_summary,
    get_preparateur_selected_order,
)
from .prepare_kits_helpers import (
    _parse_carton_ids,
    build_prepare_kits_page_context,
    build_prepare_kits_picking_context,
    prepare_kits,
)
from .recipient_product_preferences import score_recipient_carton_compatibilities
from .runtime_settings import is_shipment_track_legacy_enabled
from .scan_helpers import (
    build_carton_formats,
    build_location_data,
    build_pack_line_values,
    build_packing_result,
    build_product_options,
    build_shipment_line_values,
    parse_int,
)
from .scan_permissions import user_is_preparateur
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
from .shipment_tracking_access import (
    build_tracking_actor_snapshot_from_grant,
    default_tracking_escale_for_shipment,
    resolve_active_tracking_access_grant,
    resolve_shipment_contact_for_role,
    resolve_tracking_identifier_from_grant,
    tracking_allowed_statuses_for_role,
    tracking_grant_matches_shipment,
)
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
    _normalize_destination_filter,
    _normalize_return_to,
    _return_to_url,
    _return_to_view_name,
    _shipment_can_be_closed,
    _stale_drafts_age_days,
    _stale_drafts_queryset,
    build_shipments_tracking_filter_state,
    build_shipments_tracking_list_context,
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
    compatibility_by_carton_id = score_recipient_carton_compatibilities(
        recipient_organizations=recipient_organizations.values(),
        cartons=cartons_by_id.values(),
        as_of=as_of,
    )
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
                compatibility = compatibility_by_carton_id.get(carton_object.id, {}).get(
                    recipient_organization_id
                )
                if compatibility is None:
                    continue
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
        destination_label = getattr(destination, "iata_code", "") if destination is not None else ""
        if not destination_label and destination is not None:
            destination_label = str(destination)
        if not destination_label:
            destination_label = shipment.destination_country or ""
        shipper_label = (shipment.shipper_name or "").strip()
        label = shipment.reference
        if destination_label:
            label = f"{label} - {destination_label}"
        if shipper_label:
            label = f"{label} - {shipper_label}"
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


def _build_pack_state_from_post(post_data):
    line_count = parse_int(post_data.get("line_count")) or 1
    line_count = max(1, line_count)
    carton_format_id = (post_data.get("carton_format_id") or "").strip() or "custom"
    return {
        "carton_format_id": carton_format_id,
        "carton_custom": {
            "length_cm": post_data.get("carton_length_cm", ""),
            "width_cm": post_data.get("carton_width_cm", ""),
            "height_cm": post_data.get("carton_height_cm", ""),
            "max_weight_g": post_data.get("carton_max_weight_g", ""),
        },
        "line_count": line_count,
        "line_values": build_pack_line_values(line_count, post_data),
        "line_errors": {},
        "missing_defaults": [],
        "confirm_defaults": bool(post_data.get("confirm_defaults")),
    }


def _build_preparateur_pack_extra_context(
    request,
    *,
    unknown_product_form=None,
    unknown_product_modal_open=False,
):
    if not user_is_preparateur(request.user):
        return {}
    selected_order = get_preparateur_selected_order(request)
    return {
        "selected_order_summary": build_preparateur_selected_order_summary(selected_order),
        "location_data": build_location_data(),
        "unknown_product_form": unknown_product_form or ScanPackUnknownProductForm(),
        "unknown_product_modal_open": unknown_product_modal_open,
    }


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


def _build_shipment_order_workflow_summary(shipment):
    order = resolve_linked_order_for_shipment(shipment)
    if order is None:
        return None
    try:
        inbound_delivery = order.inbound_delivery
    except AttributeError:
        inbound_delivery = None
    except type(order).inbound_delivery.RelatedObjectDoesNotExist:
        inbound_delivery = None
    if inbound_delivery is None:
        return {
            "reference_label": order.reference or f"CMD-{order.id}",
            "declared_carton_count": 0,
            "unassigned_shipper_carton_count": 0,
            "has_inbound_delivery": False,
        }
    receipt = getattr(inbound_delivery, "receipt", None)
    shipper_cartons = list(receipt.shipper_cartons.all()) if receipt is not None else []
    return {
        "reference_label": order.reference or f"CMD-{order.id}",
        "receipt_reference": getattr(receipt, "reference", ""),
        "declared_carton_count": int(getattr(inbound_delivery, "declared_carton_count", 0) or 0),
        "unassigned_shipper_carton_count": sum(
            1 for carton in shipper_cartons if not getattr(carton, "shipment_id", None)
        ),
        "has_inbound_delivery": True,
    }


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
    order_workflow_summary = _build_shipment_order_workflow_summary(shipment)
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
        "order_workflow_summary": order_workflow_summary,
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


def _normalize_tracking_role(source) -> str:
    value = (source or "").strip()
    if value in set(ShipmentTrackingAccessRole.values):
        return value
    return ""


def _build_volunteer_actor_context(request, *, role, identifier):
    profile = getattr(getattr(request, "user", None), "volunteer_profile", None)
    if profile is None:
        return None
    volunteer_identifier = str(getattr(profile, "volunteer_id", "") or "").strip()
    if identifier and volunteer_identifier != identifier:
        return None
    email = str(getattr(request.user, "email", "") or "").strip()
    identity_status = (
        ShipmentTrackingIdentityStatus.VERIFIED
        if getattr(profile, "is_active", False)
        else ShipmentTrackingIdentityStatus.PENDING
    )
    snapshot = {
        "role": role,
        "identifier": volunteer_identifier,
        "email": email,
        "identity_status": identity_status,
        "auth_source": "volunteer",
        "volunteer_profile_id": profile.id,
    }
    return {
        "role": role,
        "identifier": volunteer_identifier,
        "email": email,
        "identity_status": identity_status,
        "auth_source": "volunteer",
        "snapshot": snapshot,
        "is_staff": False,
    }


def _resolve_tracking_actor_context(request, *, shipment, role, identifier):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if user.is_staff:
        return {
            "role": role,
            "identifier": identifier,
            "email": str(getattr(user, "email", "") or "").strip(),
            "identity_status": ShipmentTrackingIdentityStatus.VERIFIED,
            "auth_source": "staff",
            "snapshot": {
                "role": role,
                "identifier": identifier,
                "email": str(getattr(user, "email", "") or "").strip(),
                "identity_status": ShipmentTrackingIdentityStatus.VERIFIED,
                "auth_source": "staff",
            },
            "is_staff": True,
        }

    active_grant = resolve_active_tracking_access_grant(request)
    if active_grant is not None:
        active_role = role or active_grant.role
        active_identifier = identifier or resolve_tracking_identifier_from_grant(active_grant)
        if tracking_grant_matches_shipment(
            grant=active_grant,
            shipment=shipment,
            role=active_role,
            identifier=active_identifier,
        ):
            snapshot = build_tracking_actor_snapshot_from_grant(active_grant)
            return {
                "role": active_role,
                "identifier": active_identifier,
                "email": str(getattr(active_grant.user, "email", "") or "").strip(),
                "identity_status": active_grant.identity_status,
                "auth_source": "qr_restricted",
                "snapshot": snapshot,
                "grant": active_grant,
                "is_staff": False,
            }

    if role == ShipmentTrackingAccessRole.VOLUNTEER:
        return _build_volunteer_actor_context(request, role=role, identifier=identifier)
    return None


def _build_tracking_next_url(*, shipment, role, identifier):
    query = urlencode({"role": role, "identifier": identifier})
    return f"{reverse('scan:scan_shipment_track', args=[shipment.tracking_token])}?{query}"


def _build_tracking_login_url(*, shipment, role, identifier):
    next_url = _build_tracking_next_url(
        shipment=shipment,
        role=role,
        identifier=identifier,
    )
    query = urlencode(
        {
            "next": next_url,
            "role": role,
            "identifier": identifier,
        }
    )
    return f"{reverse('scan:scan_shipment_tracking_access_login')}?{query}"


def _build_tracking_set_password_url(request, *, user, grant, next_url):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"next": next_url, "grant": grant.id})
    return request.build_absolute_uri(
        reverse("scan:scan_shipment_tracking_access_set_password", args=[uid, token]) + f"?{query}"
    )


def _get_or_create_tracking_pending_user(*, email, role, identifier, first_name="", last_name=""):
    user_model = get_user_model()
    user = user_model.objects.filter(email__iexact=email).first()
    if user is None:
        username = f"qr-{role}-{identifier or email}".lower()[:150]
        user = user_model.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
    else:
        updates = []
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updates.append("first_name")
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updates.append("last_name")
        if not user.is_active:
            user.is_active = True
            updates.append("is_active")
        if updates:
            user.save(update_fields=updates)
    return user


def _assign_pending_contact_to_shipment(*, shipment, role, contact):
    update_fields = []
    if role == ShipmentTrackingAccessRole.SHIPPER:
        shipment.shipper_contact_ref = contact
        shipment.shipper_name = contact.name
        update_fields.extend(["shipper_contact_ref", "shipper_name"])
    elif role == ShipmentTrackingAccessRole.RECIPIENT:
        shipment.recipient_contact_ref = contact
        shipment.recipient_name = contact.name
        update_fields.extend(["recipient_contact_ref", "recipient_name"])
    elif role == ShipmentTrackingAccessRole.CORRESPONDENT:
        shipment.correspondent_contact_ref = contact
        shipment.correspondent_name = contact.name
        update_fields.extend(["correspondent_contact_ref", "correspondent_name"])
    if update_fields:
        shipment.save(update_fields=update_fields)


def _send_pending_tracking_access_email(*, request, shipment, grant):
    identifier = resolve_tracking_identifier_from_grant(grant)
    next_url = _build_tracking_next_url(
        shipment=shipment,
        role=grant.role,
        identifier=identifier,
    )
    set_password_url = _build_tracking_set_password_url(
        request,
        user=grant.user,
        grant=grant,
        next_url=next_url,
    )
    login_url = request.build_absolute_uri(
        reverse("scan:scan_shipment_tracking_access_login")
        + f"?{urlencode({'next': next_url, 'role': grant.role})}"
    )
    tracking_url = request.build_absolute_uri(
        reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
    )
    message = render_to_string(
        "emails/shipment_tracking_pending_created.txt",
        {
            "shipment": shipment,
            "grant": grant,
            "identifier": identifier,
            "role_label": grant.get_role_display(),
            "login_url": login_url,
            "set_password_url": set_password_url,
            "tracking_url": tracking_url,
        },
    )
    send_or_enqueue_email_safe(
        subject=_("ASF WMS - Accès suivi expédition créé"),
        message=message,
        recipient=[grant.user.email],
    )


def _sync_pending_volunteer_account_request(*, form, email):
    request_row = VolunteerAccountRequest.objects.filter(
        email__iexact=email,
        status=VolunteerAccountRequestStatus.PENDING,
    ).first()
    values = {
        "first_name": str(form.cleaned_data.get("first_name") or "").strip(),
        "last_name": str(form.cleaned_data.get("last_name") or "").strip(),
        "email": email,
        "status": VolunteerAccountRequestStatus.PENDING,
    }
    if request_row is None:
        return VolunteerAccountRequest.objects.create(**values)
    update_fields = []
    for field_name, value in values.items():
        if getattr(request_row, field_name) != value:
            setattr(request_row, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        request_row.save(update_fields=update_fields)
    return request_row


def _sync_pending_public_account_request(*, form, shipment, role, contact, email):
    account_type = (
        PublicAccountRequestType.SHIPPER
        if role == ShipmentTrackingAccessRole.SHIPPER
        else PublicAccountRequestType.RECIPIENT
    )
    request_row = PublicAccountRequest.objects.filter(
        contact=contact,
        account_type=account_type,
        requested_account_type=role,
        status=PublicAccountRequestStatus.PENDING,
    ).first()
    values = {
        "contact": contact,
        "account_type": account_type,
        "requested_account_type": role,
        "status": PublicAccountRequestStatus.PENDING,
        "association_name": str(form.cleaned_data.get("structure_name") or "").strip(),
        "email": email,
        "address_line1": str(form.cleaned_data.get("address_line1") or "").strip(),
        "postal_code": str(form.cleaned_data.get("postal_code") or "").strip(),
        "city": str(form.cleaned_data.get("city") or "").strip(),
        "country": str(form.cleaned_data.get("country") or "").strip() or "France",
        "destination": shipment.destination
        if role
        in {
            ShipmentTrackingAccessRole.RECIPIENT,
            ShipmentTrackingAccessRole.CORRESPONDENT,
        }
        else None,
    }
    if request_row is None:
        return PublicAccountRequest.objects.create(**values)
    update_fields = []
    for field_name, value in values.items():
        if getattr(request_row, field_name) != value:
            setattr(request_row, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        request_row.save(update_fields=update_fields)
    return request_row


def _create_pending_tracking_access(request, *, shipment, form):
    role = form.cleaned_data["role"]
    email = str(form.cleaned_data["email"] or "").strip().lower()
    with transaction.atomic():
        if role == ShipmentTrackingAccessRole.VOLUNTEER:
            user = _get_or_create_tracking_pending_user(
                email=email,
                role=role,
                identifier=email,
                first_name=str(form.cleaned_data.get("first_name") or "").strip(),
                last_name=str(form.cleaned_data.get("last_name") or "").strip(),
            )
            profile, _created = VolunteerProfile.objects.get_or_create(user=user)
            profile.short_name = str(form.cleaned_data.get("first_name") or "").strip()[:30]
            profile.is_active = False
            profile.must_change_password = True
            profile.save()
            _sync_pending_volunteer_account_request(form=form, email=email)
            grant, _created = ShipmentTrackingAccessGrant.objects.get_or_create(
                user=user,
                role=role,
                volunteer_profile=profile,
                defaults={"identity_status": ShipmentTrackingIdentityStatus.PENDING},
            )
        else:
            contact = resolve_shipment_contact_for_role(shipment=shipment, role=role)
            if contact is None:
                contact = Contact.objects.create(
                    name=str(form.cleaned_data.get("structure_name") or "").strip(),
                    email=email,
                    is_active=False,
                )
            else:
                contact.name = (
                    str(form.cleaned_data.get("structure_name") or "").strip() or contact.name
                )
                contact.email = email or contact.email
                contact.is_active = False
                contact.save(update_fields=["name", "email", "is_active"])
            _assign_pending_contact_to_shipment(shipment=shipment, role=role, contact=contact)
            user = _get_or_create_tracking_pending_user(
                email=email,
                role=role,
                identifier=getattr(contact, "asf_id", "") or email,
            )
            grant, _created = ShipmentTrackingAccessGrant.objects.get_or_create(
                user=user,
                role=role,
                contact=contact,
                defaults={"identity_status": ShipmentTrackingIdentityStatus.PENDING},
            )
            _sync_pending_public_account_request(
                form=form,
                shipment=shipment,
                role=role,
                contact=contact,
                email=email,
            )

        if grant.identity_status != ShipmentTrackingIdentityStatus.PENDING:
            grant.identity_status = ShipmentTrackingIdentityStatus.PENDING
            grant.save(update_fields=["identity_status"])

    _send_pending_tracking_access_email(request=request, shipment=shipment, grant=grant)
    return grant


def _render_shipment_tracking(
    request,
    *,
    shipment,
    tracking_url,
    form,
    can_update_tracking,
    back_to_url,
    return_to,
    access_required=False,
    gateway_form=None,
    recovery_form=None,
    pending_form=None,
    selected_role="",
    selected_identifier="",
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
            "access_required": access_required,
            "gateway_form": gateway_form,
            "recovery_form": recovery_form,
            "pending_form": pending_form,
            "selected_role": selected_role,
            "selected_identifier": selected_identifier,
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
        if user_is_preparateur(request.user):
            raise PermissionDenied

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
    if user_is_preparateur(request.user):
        cartons_qs = cartons_qs.exclude(status=CartonStatus.SHIPPED)
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
    filter_state = build_shipments_tracking_filter_state(
        request.POST if request.method == "POST" else request.GET
    )

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
                planned_week_value=filter_state["planned_week_value"],
                closed_filter=filter_state["closed_filter"],
                dispute_filter=filter_state["dispute_filter"],
                destination_value=(
                    str(filter_state["selected_destination"].id)
                    if filter_state["selected_destination"]
                    else filter_state["destination_filter_value"]
                ),
                query=filter_state["query"],
            )
        )

    list_context = build_shipments_tracking_list_context(request)
    if list_context["planned_week_invalid"]:
        messages.warning(
            request,
            _("Format semaine invalide. Utilisez AAAA-Wss ou AAAA-ss."),
        )

    return render(
        request,
        TEMPLATE_SHIPMENTS_TRACKING,
        {
            "active": ACTIVE_SHIPMENTS_TRACKING,
            **list_context,
            "close_inactive_message": _("Il reste des étapes à valider, vérifier avant de clore"),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_pack(request):
    form_initial = {}
    selected_order = (
        get_preparateur_selected_order(request) if user_is_preparateur(request.user) else None
    )
    if request.method == "GET":
        shipment_reference = (request.GET.get("shipment_reference") or "").strip()
        if (
            not shipment_reference
            and selected_order is not None
            and selected_order.shipment_id
            and selected_order.shipment
            and selected_order.shipment.reference
        ):
            shipment_reference = selected_order.shipment.reference
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
        action = (request.POST.get("action") or "").strip()
        if user_is_preparateur(request.user) and action == "create_unknown_product":
            unknown_product_form = ScanPackUnknownProductForm(request.POST)
            pack_state = _build_pack_state_from_post(request.POST)
            if unknown_product_form.is_valid():
                product = create_preparateur_unknown_product_from_pack(
                    request=request,
                    form=unknown_product_form,
                )
                line_index = int(unknown_product_form.cleaned_data["line_index"] or 0)
                if 1 <= line_index <= len(pack_state["line_values"]):
                    pack_state["line_values"][line_index - 1]["product_code"] = product.sku
                product_options = build_product_options(include_kits=True)
                unknown_product_form = ScanPackUnknownProductForm()
                messages.success(
                    request,
                    _("Produit %(sku)s créé et stock initial ajouté.") % {"sku": product.sku},
                )
                unknown_product_modal_open = False
            else:
                unknown_product_modal_open = True
            return _render_pack_page(
                request,
                form=form,
                product_options=product_options,
                carton_formats=carton_formats,
                carton_format_id=pack_state["carton_format_id"],
                carton_custom=pack_state["carton_custom"],
                line_count=pack_state["line_count"],
                line_values=pack_state["line_values"],
                line_errors=pack_state["line_errors"],
                packing_result=packing_result,
                missing_defaults=pack_state["missing_defaults"],
                confirm_defaults=pack_state["confirm_defaults"],
                extra_context=_build_preparateur_pack_extra_context(
                    request,
                    unknown_product_form=unknown_product_form,
                    unknown_product_modal_open=unknown_product_modal_open,
                ),
            )
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
        extra_context=_build_preparateur_pack_extra_context(request),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_preparateur_last_carton(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_cartons_ready")
    carton = Carton.objects.filter(prepared_by=request.user).order_by("-created_at", "-id").first()
    if carton is None:
        messages.info(request, _("Aucun colis préparé récemment."))
        return redirect("scan:scan_pack")
    return redirect("scan:scan_carton_edit", carton_id=carton.id)


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
            "use_local_helper": False,
        },
        {
            "label": _("Picking"),
            "url": carton_summary["picking_url"],
            "use_local_helper": True,
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
    initial = {}
    if request.method != "POST":
        shipper_contact_id = (request.GET.get("shipper_contact") or "").strip()
        recipient_contact_id = (request.GET.get("recipient_contact") or "").strip()
        if destination_id:
            initial["destination"] = destination_id
        if shipper_contact_id:
            initial["shipper_contact"] = shipper_contact_id
        if recipient_contact_id:
            initial["recipient_contact"] = recipient_contact_id
        try:
            carton_count = max(int((request.GET.get("carton_count") or "0").strip() or "0"), 0)
        except ValueError:
            carton_count = 0
        if carton_count:
            initial["carton_count"] = carton_count
    form = ScanShipmentForm(request.POST or None, destination_id=destination_id, initial=initial)
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
        form_initial = getattr(form, "initial", {})
        carton_count = int(initial.get("carton_count", form_initial.get("carton_count", 0)) or 0)
        if request.GET:
            line_values = build_shipment_line_values(carton_count, request.GET)
        else:
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
    related_order = resolve_linked_order_for_shipment(shipment)
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
    action = (request.POST.get("action") or "").strip() if request.method == "POST" else ""
    return_to = _normalize_return_to(source.get("return_to"))
    selected_role = _normalize_tracking_role(source.get("role") or request.GET.get("role"))
    selected_identifier = (source.get("identifier") or request.GET.get("identifier") or "").strip()
    actor_context = _resolve_tracking_actor_context(
        request,
        shipment=shipment,
        role=selected_role,
        identifier=selected_identifier,
    )
    if actor_context is not None:
        selected_role = actor_context.get("role", selected_role)
        selected_identifier = actor_context.get("identifier", selected_identifier)
    if not selected_role:
        selected_role = ShipmentTrackingAccessRole.VOLUNTEER
    is_dispute_action = action in {"set_disputed", "resolve_dispute"}

    last_event = shipment.tracking_events.order_by("-created_at").first()
    allowed_statuses = allowed_tracking_statuses_for_shipment(shipment)
    if actor_context is not None and not actor_context.get("is_staff"):
        allowed_statuses = tracking_allowed_statuses_for_role(
            actor_context.get("role"),
            allowed_statuses,
        )
    next_status = next_tracking_status(last_event.status if last_event else None)
    if allowed_statuses and next_status not in allowed_statuses:
        next_status = allowed_statuses[0]
    can_update_tracking = actor_context is not None
    form = None
    if can_update_tracking or is_dispute_action:
        form = ShipmentTrackingForm(
            request.POST or None,
            initial_status=next_status,
            allowed_statuses=allowed_statuses,
            shipment=shipment,
            actor_role=selected_role,
        )
    gateway_form = ShipmentTrackingGatewayForm(
        request.POST if action == "gateway" else None,
        initial={
            "role": selected_role,
            "identifier": selected_identifier,
        },
        selected_role=selected_role,
    )
    default_escale = default_tracking_escale_for_shipment(shipment)
    recovery_form = ShipmentTrackingAccessRecoveryForm(
        request.POST if action == "recovery" else None,
        initial={
            "role": selected_role,
            "escale_code": default_escale,
        },
        selected_role=selected_role,
        shipment=shipment,
    )
    pending_form = ShipmentTrackingPendingAccountForm(
        request.POST if action == "create_pending_account" else None,
        initial={
            "role": selected_role,
            "escale_code": default_escale,
        },
        selected_role=selected_role,
    )
    return_to_list = (
        request.method == "POST"
        and request.user.is_authenticated
        and request.user.is_staff
        and (request.POST.get("return_to_list") or "").strip() == "1"
    )
    return_to_view = _return_to_view_name(return_to) if return_to_list else None
    if request.method == "POST" and action == "gateway":
        if gateway_form.is_valid():
            return redirect(
                _build_tracking_login_url(
                    shipment=shipment,
                    role=gateway_form.cleaned_data["role"],
                    identifier=gateway_form.cleaned_data["identifier"],
                )
            )
    elif request.method == "POST" and action == "create_pending_account":
        if pending_form.is_valid():
            grant = _create_pending_tracking_access(request, shipment=shipment, form=pending_form)
            identifier = resolve_tracking_identifier_from_grant(grant)
            messages.success(
                request,
                _(
                    "Compte créé en attente. Consultez votre email pour définir votre mot de passe puis connectez-vous pour poursuivre le scan."
                ),
            )
            return redirect(
                _build_tracking_login_url(
                    shipment=shipment,
                    role=grant.role,
                    identifier=identifier,
                )
            )
    elif (
        request.method == "POST" and (can_update_tracking or is_dispute_action) and form is not None
    ):
        response = handle_shipment_tracking_post(
            request,
            shipment=shipment,
            form=form,
            actor_context=actor_context,
            return_to_list=return_to_list,
            return_to_view=return_to_view,
            return_to_key=return_to,
        )
        if response:
            return response
    elif request.method == "POST" and not can_update_tracking:
        messages.error(request, _("Connectez-vous pour poursuivre le suivi."))

    return _render_shipment_tracking(
        request,
        shipment=shipment,
        tracking_url=shipment.get_tracking_url(request=request),
        form=form,
        can_update_tracking=can_update_tracking,
        back_to_url=_return_to_url(return_to),
        return_to=return_to,
        access_required=not can_update_tracking,
        gateway_form=gateway_form,
        recovery_form=recovery_form,
        pending_form=pending_form,
        selected_role=selected_role,
        selected_identifier=selected_identifier,
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
