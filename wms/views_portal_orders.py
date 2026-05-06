from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date, parse_time
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .application.portal.dashboard_queries import (
    build_portal_dashboard_payload,
    build_recipient_scope_home_payload,
    decorate_portal_dashboard_order,
)
from .application.portal.order_use_cases import submit_portal_order
from .application.portal.recipient_resolution import (
    PORTAL_RECIPIENT_SELF,
    build_allowed_destination_ids_by_recipient,
    resolve_portal_order_destination,
)
from .document_scan import DocumentScanStatus
from .document_scan_queue import queue_document_scan
from .document_uploads import validate_document_upload
from .models import (
    AssociationPickupAddress,
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderInboundArrivalMode,
    OrderReviewStatus,
    PortalAccessRole,
    ProductCategory,
)
from .order_helpers import (
    build_carton_format_data,
    build_order_line_estimates,
    build_order_line_items,
    build_order_product_rows,
    build_ready_carton_rows,
    build_ready_carton_selection,
    split_ready_rows_into_kits,
)
from .order_notifications import send_portal_order_notifications
from .portal_helpers import (
    get_association_profile,
    get_default_carton_format,
)
from .scan_helpers import build_product_selection_data
from .scan_helpers import parse_int as parse_int_safe
from .services import StockError
from .shipment_helpers import (
    shipment_link_for_recipient_contact,
    shipment_shipper_from_contact,
)
from .upload_utils import validate_upload
from .view_permissions import (
    association_required,
    portal_scope_required,
    require_association_profile,
)
from .view_utils import sorted_choices

TEMPLATE_PORTAL_DASHBOARD = "portal/dashboard.html"
TEMPLATE_PORTAL_RECIPIENT_SCOPE_HOME = "portal/recipient_scope_home.html"
TEMPLATE_PORTAL_ORDER_CREATE = "portal/order_create.html"
TEMPLATE_PORTAL_ORDER_DETAIL = "portal/order_detail.html"

ACTION_UPLOAD_DOCUMENT = "upload_doc"
ACTION_UPLOAD_DOCUMENTS = "upload_docs"
DEFAULT_COUNTRY = "France"

ERROR_RECIPIENT_REQUIRED = _("Destinataire requis.")
ERROR_DESTINATION_REQUIRED = _("Destination requise.")
ERROR_DESTINATION_INVALID = _("Destination invalide.")
ERROR_RECIPIENT_UNAVAILABLE_FOR_DESTINATION = _(
    "Destinataire non disponible pour cette destination."
)
ERROR_PRODUCT_REQUIRED = _("Ajoutez au moins un produit.")
ERROR_ASSOCIATION_ADDRESS_REQUIRED = _("Adresse association manquante.")
ERROR_RECIPIENT_INVALID = _("Destinataire invalide.")
ERROR_ORDER_NO_DOCUMENT_SELECTED = _("Aucun fichier sélectionné.")
ERROR_INBOUND_CARTON_COUNT_REQUIRED = _("Nombre de colis expéditeur requis.")
ERROR_INBOUND_PALLET_COUNT_REQUIRED = _("Nombre de palettes requis pour l'enlèvement.")
ERROR_INBOUND_OUT_OF_FORMAT_INVALID = _("Nombre de hors format invalide.")
ERROR_INBOUND_ARRIVAL_MODE_REQUIRED = _("Mode d'arrivée des colis expéditeur requis.")
ERROR_INBOUND_GUIDELINES_CONFIRMATION_REQUIRED = _(
    "Certifiez que les colis respectent les consignes ASF."
)
ERROR_PICKUP_PHONE_REQUIRED = _("Au moins un numéro de téléphone est requis pour l'enlèvement.")
ERROR_PICKUP_CONTACT_REQUIRED = _("Contact d'enlèvement requis.")
ERROR_PICKUP_ADDRESS_REQUIRED = _("Adresse d'enlèvement requise.")
ERROR_PICKUP_POSTAL_CODE_REQUIRED = _("Code postal d'enlèvement requis.")
ERROR_PICKUP_CITY_REQUIRED = _("Ville d'enlèvement requise.")
ERROR_PICKUP_COUNTRY_REQUIRED = _("Pays d'enlèvement requis.")
ERROR_PICKUP_AVAILABLE_FROM_REQUIRED = _("Date de mise à disposition des palettes requise.")
ERROR_PICKUP_SLOT_1_REQUIRED = _("Premier créneau d'ouverture requis.")
ERROR_PICKUP_SLOT_2_REQUIRED = _("Deuxième créneau d'ouverture requis si interruption en journée.")
ERROR_PICKUP_ACCESS_CONSTRAINTS_REQUIRED = _(
    "Renseignez une contrainte d'accès ou cochez Aucune contrainte d'accès."
)
ERROR_PICKUP_CONFIRMATION_REQUIRED = _(
    "Confirmez avoir toutes les informations nécessaires à l'enlèvement."
)

MESSAGE_ORDER_SENT = _("Commande envoyée.")
MESSAGE_ORDER_DOCUMENT_ADDED = _("Document ajouté.")
MESSAGE_ORDER_DOCUMENTS_ADDED = _("Documents ajoutés.")

PICKUP_OPEN_WEEKDAY_CHOICES = [
    ("monday", _("Lundi")),
    ("tuesday", _("Mardi")),
    ("wednesday", _("Mercredi")),
    ("thursday", _("Jeudi")),
    ("friday", _("Vendredi")),
    ("saturday", _("Samedi")),
    ("sunday", _("Dimanche")),
]
PICKUP_OPEN_WEEKDAY_VALUES = {value for value, _label in PICKUP_OPEN_WEEKDAY_CHOICES}


def _get_active_recipients(profile):
    return list(
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
        )
        .select_related("destination")
        .order_by(
            "structure_name",
            "name",
            "contact_last_name",
            "contact_first_name",
        )
    )


def _get_active_destinations():
    return list(Destination.objects.filter(is_active=True).order_by("city", "country", "iata_code"))


def _sorted_option_dicts(options, *, order="asc"):
    return sorted(
        options,
        key=lambda item: str(item.get("label") or "").lower(),
        reverse=order == "desc",
    )


def _build_destination_options(destinations):
    return _sorted_option_dicts(
        [{"id": str(destination.id), "label": str(destination)} for destination in destinations]
    )


def _split_destination_options_by_availability(destination_options, *, available_destination_ids):
    available_ids = {str(destination_id) for destination_id in available_destination_ids}
    available_options = []
    disabled_options = []
    for option in destination_options:
        if str(option["id"]) in available_ids:
            available_options.append(option)
        else:
            disabled_options.append(option)
    return _sorted_option_dicts(available_options), _sorted_option_dicts(disabled_options)


def _build_portal_recipient_option_label(recipient):
    structure_name = (recipient.structure_name or recipient.name or "").strip()
    contact_display = recipient.get_contact_display_name()
    if (
        structure_name
        and contact_display
        and structure_name.casefold() != contact_display.casefold()
    ):
        label = f"{structure_name}, {contact_display}"
    else:
        label = structure_name or contact_display or recipient.get_display_name()
    if recipient.destination:
        return f"{label} - {recipient.destination.city}"
    return label


def _build_recipient_options(
    recipients,
    *,
    allowed_destination_ids_by_recipient=None,
):
    options = [
        {
            "id": str(recipient.id),
            "label": _build_portal_recipient_option_label(recipient),
            "destination_id": str(recipient.destination_id or ""),
            "allowed_destination_ids": (
                allowed_destination_ids_by_recipient.get(str(recipient.id))
                if allowed_destination_ids_by_recipient is not None
                else None
            ),
        }
        for recipient in recipients
    ]
    return _sorted_option_dicts(options)


def _filter_recipient_options(recipient_options, destination_id, *, allowed_recipient_ids=None):
    selected_destination_id = (destination_id or "").strip()
    if not selected_destination_id:
        return []

    filtered_options = [
        option
        for option in recipient_options
        if option.get("destination_id") == selected_destination_id
    ]
    if allowed_recipient_ids is None:
        return filtered_options
    return [option for option in filtered_options if option["id"] in allowed_recipient_ids]


def _allowed_recipient_option_ids(*, selected_destination, allowed_destination_ids_by_recipient):
    if selected_destination is None or allowed_destination_ids_by_recipient is None:
        return None
    selected_destination_id = selected_destination.id
    return {
        recipient_id
        for recipient_id, destination_ids in allowed_destination_ids_by_recipient.items()
        if selected_destination_id in destination_ids
    }


def _allowed_destination_ids_by_recipient(profile, recipients, destinations):
    return build_allowed_destination_ids_by_recipient(
        profile=profile,
        recipients=recipients,
        destinations=destinations,
    )


def _available_destination_ids(allowed_destination_ids_by_recipient):
    return sorted(
        {
            destination_id
            for destination_ids in allowed_destination_ids_by_recipient.values()
            for destination_id in destination_ids
        }
    )


def _build_order_create_defaults():
    return {
        "destination_id": "",
        "recipient_id": "",
        "notes": "",
        "has_shipper_inbound": False,
        "wants_stock_completion": False,
        "arrival_mode": "",
        "declared_carton_count": "",
        "declared_pallet_count": "",
        "declared_out_of_format_count": "0",
        "parcel_guidelines_confirmed": False,
        "pickup_address_book_entry_id": "",
        "save_pickup_address": False,
        "pickup_company_name": "",
        "pickup_contact_name": "",
        "pickup_contact_phone": "",
        "pickup_contact_phone_2": "",
        "pickup_address_line1": "",
        "pickup_address_line2": "",
        "pickup_postal_code": "",
        "pickup_city": "",
        "pickup_country": DEFAULT_COUNTRY,
        "pickup_available_from_date": "",
        "pickup_requested_for_date": "",
        "pickup_open_weekdays": [],
        "pickup_opening_slot_1_start": "",
        "pickup_opening_slot_1_end": "",
        "pickup_has_midday_break": False,
        "pickup_opening_slot_2_start": "",
        "pickup_opening_slot_2_end": "",
        "pickup_has_no_access_constraints": False,
        "pickup_access_constraints_details": "",
        "tail_lift_required": True,
        "pallet_truck_required": True,
        "pickup_information_confirmed": False,
    }


def _is_checked(raw_value):
    return str(raw_value or "").strip().lower() in {"1", "true", "on", "yes"}


def _normalize_form_bool(form_data, key, raw_value):
    form_data[key] = _is_checked(raw_value)
    return form_data[key]


def _format_optional_time(value):
    if value is None:
        return ""
    return value.strftime("%H:%M")


def _normalize_pickup_open_weekdays(raw_values):
    weekdays = []
    seen = set()
    for raw_value in raw_values or []:
        value = str(raw_value or "").strip()
        if value not in PICKUP_OPEN_WEEKDAY_VALUES or value in seen:
            continue
        seen.add(value)
        weekdays.append(value)
    return weekdays


def _build_pickup_address_option(entry):
    label_parts = [
        entry.label,
        entry.pickup_company_name,
        entry.pickup_address_line1,
        entry.pickup_city,
    ]
    label = " - ".join(part.strip() for part in label_parts if (part or "").strip())
    if not label:
        label = f"Adresse enlèvement #{entry.id}"
    return {
        "id": str(entry.id),
        "label": label,
        "pickup_company_name": entry.pickup_company_name or "",
        "pickup_contact_name": entry.pickup_contact_name or "",
        "pickup_contact_phone": entry.pickup_contact_phone or "",
        "pickup_contact_phone_2": entry.pickup_contact_phone_2 or "",
        "pickup_address_line1": entry.pickup_address_line1 or "",
        "pickup_address_line2": entry.pickup_address_line2 or "",
        "pickup_postal_code": entry.pickup_postal_code or "",
        "pickup_city": entry.pickup_city or "",
        "pickup_country": entry.pickup_country or DEFAULT_COUNTRY,
        "pickup_open_weekdays": list(entry.pickup_open_weekdays or []),
        "pickup_opening_slot_1_start": _format_optional_time(entry.pickup_opening_slot_1_start),
        "pickup_opening_slot_1_end": _format_optional_time(entry.pickup_opening_slot_1_end),
        "pickup_has_midday_break": bool(entry.pickup_has_midday_break),
        "pickup_opening_slot_2_start": _format_optional_time(entry.pickup_opening_slot_2_start),
        "pickup_opening_slot_2_end": _format_optional_time(entry.pickup_opening_slot_2_end),
        "pickup_has_no_access_constraints": bool(entry.pickup_has_no_access_constraints),
        "pickup_access_constraints_details": entry.pickup_access_constraints_details or "",
        "tail_lift_required": bool(entry.tail_lift_required),
        "pallet_truck_required": bool(entry.pallet_truck_required),
    }


def _build_pickup_address_options(profile):
    entries = AssociationPickupAddress.objects.filter(association_contact=profile.contact).order_by(
        "-is_default",
        "-last_used_at",
        "-times_used",
        "label",
        "id",
    )
    return [_build_pickup_address_option(entry) for entry in entries]


def _resolve_pickup_address_entry(profile, raw_entry_id):
    entry_id = parse_int_safe(raw_entry_id)
    if not entry_id:
        return None
    return AssociationPickupAddress.objects.filter(
        id=entry_id,
        association_contact=profile.contact,
    ).first()


def _apply_pickup_address_entry_to_form_data(form_data, *, entry, post_data):
    if entry is None:
        return

    for field_name in (
        "pickup_company_name",
        "pickup_contact_name",
        "pickup_contact_phone",
        "pickup_contact_phone_2",
        "pickup_address_line1",
        "pickup_address_line2",
        "pickup_postal_code",
        "pickup_city",
        "pickup_country",
        "pickup_opening_slot_1_start",
        "pickup_opening_slot_1_end",
        "pickup_opening_slot_2_start",
        "pickup_opening_slot_2_end",
        "pickup_access_constraints_details",
    ):
        if form_data.get(field_name):
            continue
        value = _build_pickup_address_option(entry).get(field_name)
        if value is not None:
            form_data[field_name] = value

    if not form_data.get("pickup_open_weekdays"):
        form_data["pickup_open_weekdays"] = list(entry.pickup_open_weekdays or [])

    for field_name in (
        "pickup_has_midday_break",
        "pickup_has_no_access_constraints",
        "tail_lift_required",
        "pallet_truck_required",
    ):
        if field_name in post_data:
            continue
        form_data[field_name] = getattr(entry, field_name)


def _validate_shipper_inbound(form_data, errors):
    if not form_data["has_shipper_inbound"]:
        return None

    carton_count = parse_int_safe(form_data["declared_carton_count"])
    if carton_count is None or carton_count <= 0:
        errors.append(ERROR_INBOUND_CARTON_COUNT_REQUIRED)
        carton_count = None

    out_of_format_count = parse_int_safe(form_data["declared_out_of_format_count"])
    if out_of_format_count is None or out_of_format_count < 0:
        errors.append(ERROR_INBOUND_OUT_OF_FORMAT_INVALID)
        out_of_format_count = 0

    if not form_data["parcel_guidelines_confirmed"]:
        errors.append(ERROR_INBOUND_GUIDELINES_CONFIRMATION_REQUIRED)

    arrival_mode = (form_data["arrival_mode"] or "").strip()
    allowed_modes = {choice[0] for choice in OrderInboundArrivalMode.choices}
    if arrival_mode not in allowed_modes:
        errors.append(ERROR_INBOUND_ARRIVAL_MODE_REQUIRED)

    payload = {
        "arrival_mode": arrival_mode,
        "declared_carton_count": carton_count or 0,
        "declared_pallet_count": 0,
        "declared_out_of_format_count": out_of_format_count or 0,
        "parcel_guidelines_confirmed": form_data["parcel_guidelines_confirmed"],
        "pickup_address_book_entry": form_data.get("pickup_address_book_entry"),
        "save_pickup_address": bool(form_data.get("save_pickup_address")),
        "notes": "",
    }

    if arrival_mode != OrderInboundArrivalMode.PICKUP_REQUESTED:
        return payload

    pallet_count = parse_int_safe(form_data["declared_pallet_count"])
    if pallet_count is None or pallet_count <= 0:
        errors.append(ERROR_INBOUND_PALLET_COUNT_REQUIRED)
        pallet_count = None

    if not form_data["pickup_contact_name"].strip():
        errors.append(ERROR_PICKUP_CONTACT_REQUIRED)
    if not (
        form_data["pickup_contact_phone"].strip() or form_data["pickup_contact_phone_2"].strip()
    ):
        errors.append(ERROR_PICKUP_PHONE_REQUIRED)
    if not form_data["pickup_address_line1"].strip():
        errors.append(ERROR_PICKUP_ADDRESS_REQUIRED)
    if not form_data["pickup_postal_code"].strip():
        errors.append(ERROR_PICKUP_POSTAL_CODE_REQUIRED)
    if not form_data["pickup_city"].strip():
        errors.append(ERROR_PICKUP_CITY_REQUIRED)
    if not form_data["pickup_country"].strip():
        errors.append(ERROR_PICKUP_COUNTRY_REQUIRED)

    pickup_available_from_date = None
    if not form_data["pickup_available_from_date"].strip():
        errors.append(ERROR_PICKUP_AVAILABLE_FROM_REQUIRED)
    else:
        pickup_available_from_date = parse_date(form_data["pickup_available_from_date"])
        if pickup_available_from_date is None:
            errors.append(ERROR_PICKUP_AVAILABLE_FROM_REQUIRED)

    pickup_requested_for_date = None
    if form_data["pickup_requested_for_date"].strip():
        pickup_requested_for_date = parse_date(form_data["pickup_requested_for_date"])

    pickup_slot_1_start = parse_time(form_data["pickup_opening_slot_1_start"])
    pickup_slot_1_end = parse_time(form_data["pickup_opening_slot_1_end"])
    if pickup_slot_1_start is None or pickup_slot_1_end is None:
        errors.append(ERROR_PICKUP_SLOT_1_REQUIRED)

    pickup_slot_2_start = None
    pickup_slot_2_end = None
    if form_data["pickup_has_midday_break"]:
        pickup_slot_2_start = parse_time(form_data["pickup_opening_slot_2_start"])
        pickup_slot_2_end = parse_time(form_data["pickup_opening_slot_2_end"])
        if pickup_slot_2_start is None or pickup_slot_2_end is None:
            errors.append(ERROR_PICKUP_SLOT_2_REQUIRED)

    if (
        not form_data["pickup_has_no_access_constraints"]
        and not form_data["pickup_access_constraints_details"].strip()
    ):
        errors.append(ERROR_PICKUP_ACCESS_CONSTRAINTS_REQUIRED)

    if not form_data["pickup_information_confirmed"]:
        errors.append(ERROR_PICKUP_CONFIRMATION_REQUIRED)

    payload.update(
        {
            "pickup_company_name": form_data["pickup_company_name"].strip(),
            "declared_pallet_count": pallet_count or 0,
            "pickup_contact_name": form_data["pickup_contact_name"].strip(),
            "pickup_contact_phone": form_data["pickup_contact_phone"].strip(),
            "pickup_contact_phone_2": form_data["pickup_contact_phone_2"].strip(),
            "pickup_address_line1": form_data["pickup_address_line1"].strip(),
            "pickup_address_line2": form_data["pickup_address_line2"].strip(),
            "pickup_postal_code": form_data["pickup_postal_code"].strip(),
            "pickup_city": form_data["pickup_city"].strip(),
            "pickup_country": form_data["pickup_country"].strip() or DEFAULT_COUNTRY,
            "pickup_available_from_date": pickup_available_from_date,
            "pickup_requested_for_date": pickup_requested_for_date,
            "pickup_open_weekdays": _normalize_pickup_open_weekdays(
                form_data.get("pickup_open_weekdays") or []
            ),
            "pickup_opening_slot_1_start": pickup_slot_1_start,
            "pickup_opening_slot_1_end": pickup_slot_1_end,
            "pickup_has_midday_break": form_data["pickup_has_midday_break"],
            "pickup_opening_slot_2_start": pickup_slot_2_start,
            "pickup_opening_slot_2_end": pickup_slot_2_end,
            "pickup_has_no_access_constraints": form_data["pickup_has_no_access_constraints"],
            "pickup_access_constraints_details": form_data[
                "pickup_access_constraints_details"
            ].strip(),
            "tail_lift_required": form_data["tail_lift_required"],
            "pallet_truck_required": form_data["pallet_truck_required"],
            "pickup_information_confirmed": form_data["pickup_information_confirmed"],
        }
    )
    return payload


def _resolve_destination(profile, recipient_id, errors, *, selected_destination):
    resolved_recipient_id = recipient_id
    if recipient_id != PORTAL_RECIPIENT_SELF:
        resolved_recipient_id = parse_int_safe(recipient_id)
    destination_payload, error = resolve_portal_order_destination(
        profile=profile,
        recipient_id=resolved_recipient_id,
        selected_destination=selected_destination,
    )
    if not error:
        return destination_payload

    errors.append(error)
    return {
        "recipient_name": "",
        "recipient_contact": None,
        "destination_city": selected_destination.city if selected_destination else "",
        "destination_country": (
            (selected_destination.country or DEFAULT_COUNTRY)
            if selected_destination
            else DEFAULT_COUNTRY
        ),
        "destination_address": "",
    }


def _requires_recipient_binding(*, profile, recipient_contact) -> bool:
    return bool(recipient_contact and recipient_contact != profile.contact)


def _build_order_shipping_type_label(form_data):
    if not form_data.get("has_shipper_inbound"):
        return _("Stock ASF")

    arrival_mode = (form_data.get("arrival_mode") or "").strip()
    wants_stock = bool(form_data.get("wants_stock_completion"))
    if arrival_mode == OrderInboundArrivalMode.DROPOFF_WAREHOUSE:
        return _("Dépôt + Stock ASF") if wants_stock else _("Dépôt")
    if arrival_mode == OrderInboundArrivalMode.PICKUP_REQUESTED:
        return _("Enlèvement + Stock ASF") if wants_stock else _("Enlèvement")
    return _("À sélectionner")


def create_portal_order(
    *,
    user,
    profile,
    recipient_name,
    recipient_contact,
    destination_address,
    destination_city,
    destination_country,
    notes,
    line_items,
    ready_carton_ids=None,
    inbound_delivery_data=None,
):
    return submit_portal_order(
        user=user,
        profile=profile,
        destination_payload={
            "recipient_name": recipient_name,
            "recipient_contact": recipient_contact,
            "destination_address": destination_address,
            "destination_city": destination_city,
            "destination_country": destination_country,
        },
        notes=notes,
        line_items=line_items,
        ready_carton_ids=ready_carton_ids,
        inbound_delivery_data=inbound_delivery_data,
    )


def _build_order_create_context(
    *,
    destination_options,
    disabled_destination_options,
    recipient_options,
    recipient_options_all,
    form_data,
    product_options,
    product_by_id,
    line_quantities,
    errors,
    line_errors,
    ready_carton_rows,
    ready_kit_rows,
    total_selected_ready_cartons,
    pickup_address_options,
):
    carton_format = get_default_carton_format()
    carton_data = build_carton_format_data(carton_format)
    product_rows, total_estimated_cartons_to_prepare = build_order_product_rows(
        product_options,
        product_by_id,
        line_quantities,
        carton_format,
    )
    category_paths_by_row = {}
    for row in product_rows:
        row_id = row.get("id")
        if not row_id:
            continue
        row_key = f"unit:{row_id}"
        row["filter_row_key"] = row_key
        product = product_by_id.get(row_id)
        category = getattr(product, "category", None) if product is not None else None
        category_path = []
        while category is not None:
            category_path.append(str(category.id))
            category = category.parent
        category_path.reverse()
        category_paths_by_row[row_key] = [category_path] if category_path else []

    for row in ready_carton_rows:
        row_key = f"ready:{row['row_key']}"
        row["filter_row_key"] = row_key
        category_paths_by_row[row_key] = row.get("category_paths", [])

    for row in ready_kit_rows:
        row_key = f"kit:{row['row_key']}"
        row["filter_row_key"] = row_key
        category_paths_by_row[row_key] = row.get("category_paths", [])

    category_ids = sorted(
        {
            int(category_id)
            for paths in category_paths_by_row.values()
            for path in paths
            for category_id in path
            if str(category_id).isdigit()
        }
    )
    category_labels_by_id = {
        str(category.id): category.name
        for category in ProductCategory.objects.filter(id__in=category_ids)
    }
    category_filter_max_depth = max(
        [len(path) for paths in category_paths_by_row.values() for path in paths] or [0]
    )
    selected_destination_id = (form_data.get("destination_id") or "").strip()
    selected_recipient_id = (form_data.get("recipient_id") or "").strip()

    def _find_option_label(options, selected_id):
        for option in options:
            if str(option.get("id") or "") == selected_id:
                return option.get("label") or ""
        return ""

    route_ready = bool(selected_destination_id and selected_recipient_id)
    selected_destination_label = _find_option_label(
        [*destination_options, *disabled_destination_options],
        selected_destination_id,
    )
    selected_recipient_label = _find_option_label(
        recipient_options_all,
        selected_recipient_id,
    )

    return {
        "destination_options": destination_options,
        "disabled_destination_options": disabled_destination_options,
        "recipient_options": recipient_options,
        "recipient_options_all": recipient_options_all,
        "form_data": form_data,
        "products": product_rows,
        "product_data": product_options,
        "errors": errors,
        "line_errors": line_errors,
        "line_quantities": line_quantities,
        "ready_cartons": ready_carton_rows,
        "ready_kits": ready_kit_rows,
        "total_selected_ready_cartons": total_selected_ready_cartons,
        "total_estimated_cartons_to_prepare": total_estimated_cartons_to_prepare,
        "total_estimated_cartons": total_estimated_cartons_to_prepare,
        "category_paths_by_row": category_paths_by_row,
        "category_labels_by_id": category_labels_by_id,
        "category_filter_max_depth": category_filter_max_depth,
        "carton_format": carton_data,
        "pickup_address_options": pickup_address_options,
        "pickup_open_weekday_choices": PICKUP_OPEN_WEEKDAY_CHOICES,
        "route_ready": route_ready,
        "selected_destination_label": selected_destination_label,
        "selected_recipient_label": selected_recipient_label,
        "shipping_type_label": _build_order_shipping_type_label(form_data),
    }


def _get_portal_order_or_404(profile, order_id):
    return get_object_or_404(
        Order.objects.select_related("association_contact"),
        id=order_id,
        association_contact=profile.contact,
    )


def _handle_order_document_upload(request, order):
    payload, error = validate_document_upload(
        request,
        doc_type_choices=OrderDocumentType.choices,
    )
    if error:
        messages.error(request, error)
        return redirect("portal:portal_order_detail", order_id=order.id)

    doc_type, uploaded = payload
    document = OrderDocument.objects.create(
        order=order,
        doc_type=doc_type,
        status=DocumentReviewStatus.PENDING,
        file=uploaded,
        uploaded_by=request.user,
        scan_status=DocumentScanStatus.PENDING,
        scan_message="Scan antivirus en cours.",
    )
    queue_document_scan(document)
    messages.success(request, MESSAGE_ORDER_DOCUMENT_ADDED)
    return redirect("portal:portal_order_detail", order_id=order.id)


def _handle_order_document_uploads(request, order):
    created = 0
    for doc_type, _label in OrderDocumentType.choices:
        uploaded = request.FILES.get(f"doc_file_{doc_type}")
        if not uploaded:
            continue
        validation_error = validate_upload(uploaded)
        if validation_error:
            messages.error(request, validation_error)
            continue
        document = OrderDocument.objects.create(
            order=order,
            doc_type=doc_type,
            status=DocumentReviewStatus.PENDING,
            file=uploaded,
            uploaded_by=request.user,
            scan_status=DocumentScanStatus.PENDING,
            scan_message="Scan antivirus en cours.",
        )
        queue_document_scan(document)
        created += 1

    if not created:
        messages.error(request, ERROR_ORDER_NO_DOCUMENT_SELECTED)
    else:
        messages.success(request, MESSAGE_ORDER_DOCUMENTS_ADDED)
    return redirect("portal:portal_order_detail", order_id=order.id)


def _build_order_detail_context(order):
    decorate_portal_dashboard_order(order)
    carton_format = get_default_carton_format()
    line_rows, total_estimated_cartons = build_order_line_estimates(
        order.lines.select_related("product"),
        carton_format,
    )
    return {
        "order": order,
        "line_rows": line_rows,
        "total_estimated_cartons": total_estimated_cartons,
        "order_documents": order.documents.all(),
        "order_doc_types": sorted_choices(OrderDocumentType.choices),
        "can_upload_docs": True,
        "order_status_display": order.order_status_display,
        "review_status_display": order.review_status_display,
        "shipment_status_display": order.shipment_status_display,
    }


@login_required(login_url="portal:portal_login")
@portal_scope_required
@require_http_methods(["GET"])
def portal_dashboard(request):
    scope = request.portal_scope
    if scope.role == PortalAccessRole.RECIPIENT_ADMIN and scope.recipient_organization is not None:
        recipient_payload = build_recipient_scope_home_payload(
            recipient_organization=scope.recipient_organization
        )
        return render(request, TEMPLATE_PORTAL_RECIPIENT_SCOPE_HOME, recipient_payload)

    if scope.role != PortalAccessRole.SHIPPER_ADMIN:
        raise PermissionDenied

    association_profile_response = require_association_profile(request)
    if not hasattr(association_profile_response, "contact"):
        return association_profile_response
    profile = (
        association_profile_response
        or scope.association_profile
        or get_association_profile(request.user)
    )
    dashboard_payload = build_portal_dashboard_payload(profile=profile)
    return render(
        request,
        TEMPLATE_PORTAL_DASHBOARD,
        {
            "orders": dashboard_payload["orders"],
            "dashboard_kpis": dashboard_payload["dashboard_kpis"],
        },
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_order_create(request):
    profile = request.association_profile
    recipients = _get_active_recipients(profile)
    destinations = _get_active_destinations()
    destination_by_id = {str(destination.id): destination for destination in destinations}
    allowed_destination_ids_by_recipient = _allowed_destination_ids_by_recipient(
        profile,
        recipients,
        destinations,
    )
    destination_options_all = _build_destination_options(destinations)
    destination_options, disabled_destination_options = _split_destination_options_by_availability(
        destination_options_all,
        available_destination_ids=_available_destination_ids(allowed_destination_ids_by_recipient),
    )
    recipient_options_all = _build_recipient_options(
        recipients,
        allowed_destination_ids_by_recipient=allowed_destination_ids_by_recipient,
    )

    product_options, product_by_id, available_by_id = build_product_selection_data()
    pickup_address_options = _build_pickup_address_options(profile)

    form_data = _build_order_create_defaults()
    errors = []
    line_errors = {}
    line_quantities = {}
    line_items = []
    selected_destination = None
    selected_ready_carton_ids = []
    selected_ready_kit_ids = []
    ready_carton_quantities = {}
    ready_kit_quantities = {}
    ready_carton_line_errors = {}
    ready_kit_line_errors = {}
    total_selected_ready_cartons = 0
    ready_kit_rows = []
    all_ready_rows = build_ready_carton_rows()
    ready_carton_rows, ready_kit_rows = split_ready_rows_into_kits(all_ready_rows)

    if request.method == "POST":
        form_data["destination_id"] = (request.POST.get("destination_id") or "").strip()
        form_data["recipient_id"] = (request.POST.get("recipient_id") or "").strip()
        form_data["notes"] = (request.POST.get("notes") or "").strip()
        _normalize_form_bool(
            form_data, "has_shipper_inbound", request.POST.get("has_shipper_inbound")
        )
        _normalize_form_bool(
            form_data,
            "wants_stock_completion",
            request.POST.get("wants_stock_completion"),
        )
        form_data["arrival_mode"] = (request.POST.get("arrival_mode") or "").strip()
        form_data["declared_carton_count"] = (
            request.POST.get("declared_carton_count") or ""
        ).strip()
        form_data["declared_pallet_count"] = (
            request.POST.get("declared_pallet_count") or ""
        ).strip()
        form_data["declared_out_of_format_count"] = (
            request.POST.get("declared_out_of_format_count") or "0"
        ).strip()
        _normalize_form_bool(
            form_data,
            "parcel_guidelines_confirmed",
            request.POST.get("parcel_guidelines_confirmed"),
        )
        form_data["pickup_address_book_entry_id"] = (
            request.POST.get("pickup_address_book_entry_id") or ""
        ).strip()
        _normalize_form_bool(
            form_data,
            "save_pickup_address",
            request.POST.get("save_pickup_address"),
        )
        form_data["pickup_company_name"] = (request.POST.get("pickup_company_name") or "").strip()
        form_data["pickup_contact_name"] = (request.POST.get("pickup_contact_name") or "").strip()
        form_data["pickup_contact_phone"] = (request.POST.get("pickup_contact_phone") or "").strip()
        form_data["pickup_contact_phone_2"] = (
            request.POST.get("pickup_contact_phone_2") or ""
        ).strip()
        form_data["pickup_address_line1"] = (request.POST.get("pickup_address_line1") or "").strip()
        form_data["pickup_address_line2"] = (request.POST.get("pickup_address_line2") or "").strip()
        form_data["pickup_postal_code"] = (request.POST.get("pickup_postal_code") or "").strip()
        form_data["pickup_city"] = (request.POST.get("pickup_city") or "").strip()
        form_data["pickup_country"] = (
            request.POST.get("pickup_country") or DEFAULT_COUNTRY
        ).strip()
        form_data["pickup_available_from_date"] = (
            request.POST.get("pickup_available_from_date") or ""
        ).strip()
        form_data["pickup_requested_for_date"] = (
            request.POST.get("pickup_requested_for_date") or ""
        ).strip()
        form_data["pickup_open_weekdays"] = _normalize_pickup_open_weekdays(
            request.POST.getlist("pickup_open_weekdays")
        )
        form_data["pickup_opening_slot_1_start"] = (
            request.POST.get("pickup_opening_slot_1_start") or ""
        ).strip()
        form_data["pickup_opening_slot_1_end"] = (
            request.POST.get("pickup_opening_slot_1_end") or ""
        ).strip()
        _normalize_form_bool(
            form_data,
            "pickup_has_midday_break",
            request.POST.get("pickup_has_midday_break"),
        )
        form_data["pickup_opening_slot_2_start"] = (
            request.POST.get("pickup_opening_slot_2_start") or ""
        ).strip()
        form_data["pickup_opening_slot_2_end"] = (
            request.POST.get("pickup_opening_slot_2_end") or ""
        ).strip()
        _normalize_form_bool(
            form_data,
            "pickup_has_no_access_constraints",
            request.POST.get("pickup_has_no_access_constraints"),
        )
        form_data["pickup_access_constraints_details"] = (
            request.POST.get("pickup_access_constraints_details") or ""
        ).strip()
        _normalize_form_bool(
            form_data, "tail_lift_required", request.POST.get("tail_lift_required")
        )
        _normalize_form_bool(
            form_data,
            "pallet_truck_required",
            request.POST.get("pallet_truck_required"),
        )
        _normalize_form_bool(
            form_data,
            "pickup_information_confirmed",
            request.POST.get("pickup_information_confirmed"),
        )
        form_data["pickup_address_book_entry"] = _resolve_pickup_address_entry(
            profile,
            form_data["pickup_address_book_entry_id"],
        )
        if (
            form_data["has_shipper_inbound"]
            and form_data["arrival_mode"] == OrderInboundArrivalMode.PICKUP_REQUESTED
        ):
            _apply_pickup_address_entry_to_form_data(
                form_data,
                entry=form_data["pickup_address_book_entry"],
                post_data=request.POST,
            )

        if not form_data["destination_id"]:
            errors.append(ERROR_DESTINATION_REQUIRED)
        else:
            selected_destination = destination_by_id.get(form_data["destination_id"])
            if selected_destination is None:
                errors.append(ERROR_DESTINATION_INVALID)

        allowed_recipient_ids = _allowed_recipient_option_ids(
            selected_destination=selected_destination,
            allowed_destination_ids_by_recipient=allowed_destination_ids_by_recipient,
        )
        recipient_options = _filter_recipient_options(
            recipient_options_all,
            form_data["destination_id"],
            allowed_recipient_ids=allowed_recipient_ids,
        )
        if not form_data["recipient_id"]:
            errors.append(ERROR_RECIPIENT_REQUIRED)
        else:
            allowed_recipient_ids = {option["id"] for option in recipient_options}
            if form_data["recipient_id"] not in allowed_recipient_ids:
                errors.append(ERROR_RECIPIENT_UNAVAILABLE_FOR_DESTINATION)

        include_stock_selection = (
            not form_data["has_shipper_inbound"] or form_data["wants_stock_completion"]
        )
        if include_stock_selection:
            (
                selected_ready_carton_ids,
                ready_carton_quantities,
                ready_carton_line_errors,
                total_selected_ready_cartons,
            ) = build_ready_carton_selection(
                request.POST,
                ready_carton_rows=ready_carton_rows,
                field_prefix="ready_carton",
            )
            (
                selected_ready_kit_ids,
                ready_kit_quantities,
                ready_kit_line_errors,
                total_selected_ready_kits,
            ) = build_ready_carton_selection(
                request.POST,
                ready_carton_rows=ready_kit_rows,
                field_prefix="ready_kit",
            )
            total_selected_ready_cartons += total_selected_ready_kits

            all_ready_rows = build_ready_carton_rows(
                selected_quantities={
                    **ready_carton_quantities,
                    **ready_kit_quantities,
                },
                line_errors={
                    **ready_carton_line_errors,
                    **ready_kit_line_errors,
                },
            )
            ready_carton_rows, ready_kit_rows = split_ready_rows_into_kits(all_ready_rows)

            line_items, line_quantities, line_errors = build_order_line_items(
                request.POST,
                product_options=product_options,
                product_by_id=product_by_id,
                available_by_id=available_by_id,
            )
        inbound_delivery_data = _validate_shipper_inbound(form_data, errors)
        if (
            not line_items
            and not selected_ready_carton_ids
            and not selected_ready_kit_ids
            and not inbound_delivery_data
            and not form_data["has_shipper_inbound"]
        ):
            errors.append(ERROR_PRODUCT_REQUIRED)

        destination = _resolve_destination(
            profile,
            form_data["recipient_id"],
            errors,
            selected_destination=selected_destination,
        )

        if (
            not errors
            and not line_errors
            and not ready_carton_line_errors
            and not ready_kit_line_errors
        ):
            try:
                if _requires_recipient_binding(
                    profile=profile,
                    recipient_contact=destination["recipient_contact"],
                ):
                    shipper = shipment_shipper_from_contact(profile.contact)
                    if (
                        shipper is None
                        or shipment_link_for_recipient_contact(
                            shipper=shipper,
                            recipient_contact=destination["recipient_contact"],
                            destination=selected_destination,
                        )
                        is None
                    ):
                        errors.append(ERROR_RECIPIENT_UNAVAILABLE_FOR_DESTINATION)
            except StockError as exc:
                errors.append(str(exc))

        if (
            not errors
            and not line_errors
            and not ready_carton_line_errors
            and not ready_kit_line_errors
        ):
            try:
                order = create_portal_order(
                    user=request.user,
                    profile=profile,
                    recipient_name=destination["recipient_name"],
                    recipient_contact=destination["recipient_contact"],
                    destination_address=destination["destination_address"],
                    destination_city=destination["destination_city"],
                    destination_country=destination["destination_country"],
                    notes=form_data["notes"],
                    line_items=line_items,
                    ready_carton_ids=selected_ready_carton_ids + selected_ready_kit_ids,
                    inbound_delivery_data=inbound_delivery_data,
                )
            except StockError as exc:
                errors.append(str(exc))
            else:
                send_portal_order_notifications(
                    request,
                    profile=profile,
                    order=order,
                )
                messages.success(request, MESSAGE_ORDER_SENT)
                return redirect("portal:portal_order_detail", order_id=order.id)
    else:
        recipient_options = _filter_recipient_options(
            recipient_options_all,
            form_data["destination_id"],
        )

    return render(
        request,
        TEMPLATE_PORTAL_ORDER_CREATE,
        _build_order_create_context(
            destination_options=destination_options,
            disabled_destination_options=disabled_destination_options,
            recipient_options=recipient_options,
            recipient_options_all=recipient_options_all,
            form_data=form_data,
            product_options=product_options,
            product_by_id=product_by_id,
            line_quantities=line_quantities,
            errors=errors,
            line_errors=line_errors,
            ready_carton_rows=ready_carton_rows,
            ready_kit_rows=ready_kit_rows,
            total_selected_ready_cartons=total_selected_ready_cartons,
            pickup_address_options=pickup_address_options,
        ),
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_order_detail(request, order_id):
    profile = request.association_profile
    order = _get_portal_order_or_404(profile, order_id)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == ACTION_UPLOAD_DOCUMENT:
            return _handle_order_document_upload(request, order)
        if action == ACTION_UPLOAD_DOCUMENTS:
            return _handle_order_document_uploads(request, order)

    return render(
        request,
        TEMPLATE_PORTAL_ORDER_DETAIL,
        _build_order_detail_context(order),
    )
