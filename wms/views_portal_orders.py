from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DateTimeField, F, Max, Q, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .document_uploads import validate_document_upload
from .models import (
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    ProductCategory,
    OrderReviewStatus,
    ShipmentTrackingStatus,
)
from .order_helpers import (
    build_carton_format_data,
    build_ready_carton_rows,
    build_ready_carton_selection,
    build_order_line_estimates,
    build_order_line_items,
    build_order_product_rows,
    split_ready_rows_into_kits,
)
from .order_notifications import send_portal_order_notifications
from .portal_helpers import (
    build_destination_address,
    get_contact_address,
    get_default_carton_format,
)
from .portal_order_handlers import create_portal_order
from .portal_recipient_sync import sync_association_recipient_to_contact
from .scan_helpers import build_product_selection_data, parse_int as parse_int_safe
from .services import StockError
from .upload_utils import validate_upload
from .view_permissions import association_required
from .view_utils import sorted_choices

TEMPLATE_PORTAL_DASHBOARD = "portal/dashboard.html"
TEMPLATE_PORTAL_ORDER_CREATE = "portal/order_create.html"
TEMPLATE_PORTAL_ORDER_DETAIL = "portal/order_detail.html"

ACTION_UPLOAD_DOCUMENT = "upload_doc"
ACTION_UPLOAD_DOCUMENTS = "upload_docs"
RECIPIENT_SELF = "self"
DEFAULT_COUNTRY = "France"

ERROR_RECIPIENT_REQUIRED = "Destinataire requis."
ERROR_DESTINATION_REQUIRED = "Destination requise."
ERROR_DESTINATION_INVALID = "Destination invalide."
ERROR_RECIPIENT_UNAVAILABLE_FOR_DESTINATION = (
    "Destinataire non disponible pour cette destination."
)
ERROR_PRODUCT_REQUIRED = "Ajoutez au moins un produit."
ERROR_ASSOCIATION_ADDRESS_REQUIRED = "Adresse association manquante."
ERROR_RECIPIENT_INVALID = "Destinataire invalide."
ERROR_ORDER_UPLOAD_NOT_APPROVED = "Documents disponibles après validation de la commande."
ERROR_ORDER_NO_DOCUMENT_SELECTED = "Aucun fichier sélectionné."

MESSAGE_ORDER_SENT = "Commande envoyée."
MESSAGE_ORDER_DOCUMENT_ADDED = "Document ajouté."
MESSAGE_ORDER_DOCUMENTS_ADDED = "Documents ajoutés."


def _get_dashboard_orders(profile):
    return (
        Order.objects.filter(association_contact=profile.contact)
        .select_related("shipment__destination")
        .annotate(
            escale_label=Coalesce(
                "shipment__destination__city",
                "destination_city",
                Value(""),
            ),
            shipped_at=Coalesce(
                Max(
                    "shipment__tracking_events__created_at",
                    filter=Q(
                        shipment__tracking_events__status=ShipmentTrackingStatus.BOARDING_OK
                    ),
                ),
                F("shipment__created_at"),
                output_field=DateTimeField(),
            ),
            received_correspondent_at=Max(
                "shipment__tracking_events__created_at",
                filter=Q(
                    shipment__tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
                ),
            ),
            received_recipient_at=Max(
                "shipment__tracking_events__created_at",
                filter=Q(
                    shipment__tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT
                ),
            ),
        )
        .order_by("-created_at")
    )


def _get_active_recipients(profile):
    return list(
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
        ).select_related("destination").order_by(
            "structure_name",
            "name",
            "contact_last_name",
            "contact_first_name",
        )
    )


def _get_active_destinations():
    return list(
        Destination.objects.filter(is_active=True).order_by("city", "country", "iata_code")
    )


def _build_destination_options(destinations):
    return [
        {"id": str(destination.id), "label": str(destination)}
        for destination in destinations
    ]


def _build_recipient_options(profile, recipients):
    def _build_recipient_label(recipient):
        label = recipient.get_display_name()
        if recipient.destination:
            return f"{label} - {recipient.destination.city}"
        return label

    options = [
        {
            "id": RECIPIENT_SELF,
            "label": f"{profile.contact.name} (association)",
            "destination_id": "",
        },
        *[
            {
                "id": str(recipient.id),
                "label": _build_recipient_label(recipient),
                "destination_id": str(recipient.destination_id or ""),
            }
            for recipient in recipients
        ],
    ]
    return sorted(options, key=lambda item: str(item["label"] or "").lower())


def _filter_recipient_options(recipient_options, destination_id):
    selected_destination_id = (destination_id or "").strip()
    if not selected_destination_id:
        return [option for option in recipient_options if option["id"] == RECIPIENT_SELF]

    return [
        option
        for option in recipient_options
        if option["id"] == RECIPIENT_SELF
        or not option.get("destination_id")
        or option.get("destination_id") == selected_destination_id
    ]


def _build_order_create_defaults():
    return {"destination_id": "", "recipient_id": "", "notes": ""}


def _resolve_self_destination(profile, errors, *, selected_destination):
    address = get_contact_address(profile.contact)
    if not address:
        errors.append(ERROR_ASSOCIATION_ADDRESS_REQUIRED)
        return {
            "recipient_name": profile.contact.name,
            "recipient_contact": profile.contact,
            "destination_city": selected_destination.city if selected_destination else "",
            "destination_country": selected_destination.country
            if selected_destination
            else DEFAULT_COUNTRY,
            "destination_address": "",
        }

    destination_city = selected_destination.city if selected_destination else (address.city or "")
    destination_country = (
        selected_destination.country
        if selected_destination
        else (address.country or DEFAULT_COUNTRY)
    )
    return {
        "recipient_name": profile.contact.name,
        "recipient_contact": profile.contact,
        "destination_city": destination_city,
        "destination_country": destination_country,
        "destination_address": build_destination_address(
            line1=address.address_line1,
            line2=address.address_line2,
            postal_code=address.postal_code,
            city=address.city,
            country=address.country,
        ),
    }


def _resolve_recipient_destination(profile, recipient_id, errors, *, selected_destination):
    recipient = (
        AssociationRecipient.objects.filter(
            id=recipient_id,
            association_contact=profile.contact,
        )
        .select_related("destination")
        .order_by("name")
        .first()
    )
    if not recipient:
        errors.append(ERROR_RECIPIENT_INVALID)
        return {
            "recipient_name": "",
            "recipient_contact": None,
            "destination_city": "",
            "destination_country": DEFAULT_COUNTRY,
            "destination_address": "",
        }

    if selected_destination and recipient.destination_id not in {
        selected_destination.id,
        None,
    }:
        errors.append(ERROR_RECIPIENT_UNAVAILABLE_FOR_DESTINATION)
        return {
            "recipient_name": "",
            "recipient_contact": None,
            "destination_city": selected_destination.city,
            "destination_country": selected_destination.country or DEFAULT_COUNTRY,
            "destination_address": "",
        }

    recipient_contact = sync_association_recipient_to_contact(recipient)
    destination_city = (
        selected_destination.city
        if selected_destination
        else (recipient.city or (recipient.destination.city if recipient.destination else ""))
    )
    destination_country = (
        selected_destination.country
        if selected_destination
        else (
            recipient.country
            or (recipient.destination.country if recipient.destination else "")
            or DEFAULT_COUNTRY
        )
    )

    return {
        "recipient_name": recipient.get_display_name(),
        "recipient_contact": recipient_contact,
        "destination_city": destination_city,
        "destination_country": destination_country,
        "destination_address": build_destination_address(
            line1=recipient.address_line1,
            line2=recipient.address_line2,
            postal_code=recipient.postal_code,
            city=recipient.city or (recipient.destination.city if recipient.destination else ""),
            country=recipient.country
            or (recipient.destination.country if recipient.destination else "")
            or DEFAULT_COUNTRY,
        ),
    }


def _resolve_destination(profile, recipient_id, errors, *, selected_destination):
    if recipient_id == RECIPIENT_SELF:
        return _resolve_self_destination(
            profile,
            errors,
            selected_destination=selected_destination,
        )
    return _resolve_recipient_destination(
        profile,
        parse_int_safe(recipient_id),
        errors,
        selected_destination=selected_destination,
    )


def _build_order_create_context(
    *,
    destination_options,
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

    return {
        "destination_options": destination_options,
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
    }


def _get_portal_order_or_404(profile, order_id):
    return get_object_or_404(
        Order.objects.select_related("association_contact"),
        id=order_id,
        association_contact=profile.contact,
    )


def _handle_order_document_upload(request, order):
    if order.review_status != OrderReviewStatus.APPROVED:
        messages.error(request, ERROR_ORDER_UPLOAD_NOT_APPROVED)
        return redirect("portal:portal_order_detail", order_id=order.id)

    payload, error = validate_document_upload(
        request,
        doc_type_choices=OrderDocumentType.choices,
    )
    if error:
        messages.error(request, error)
        return redirect("portal:portal_order_detail", order_id=order.id)

    doc_type, uploaded = payload
    OrderDocument.objects.create(
        order=order,
        doc_type=doc_type,
        status=DocumentReviewStatus.PENDING,
        file=uploaded,
        uploaded_by=request.user,
    )
    messages.success(request, MESSAGE_ORDER_DOCUMENT_ADDED)
    return redirect("portal:portal_order_detail", order_id=order.id)


def _handle_order_document_uploads(request, order):
    if order.review_status != OrderReviewStatus.APPROVED:
        messages.error(request, ERROR_ORDER_UPLOAD_NOT_APPROVED)
        return redirect("portal:portal_order_detail", order_id=order.id)

    created = 0
    for doc_type, _label in OrderDocumentType.choices:
        uploaded = request.FILES.get(f"doc_file_{doc_type}")
        if not uploaded:
            continue
        validation_error = validate_upload(uploaded)
        if validation_error:
            messages.error(request, validation_error)
            continue
        OrderDocument.objects.create(
            order=order,
            doc_type=doc_type,
            status=DocumentReviewStatus.PENDING,
            file=uploaded,
            uploaded_by=request.user,
        )
        created += 1

    if not created:
        messages.error(request, ERROR_ORDER_NO_DOCUMENT_SELECTED)
    else:
        messages.success(request, MESSAGE_ORDER_DOCUMENTS_ADDED)
    return redirect("portal:portal_order_detail", order_id=order.id)


def _build_order_detail_context(order):
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
        "can_upload_docs": order.review_status == OrderReviewStatus.APPROVED,
    }


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET"])
def portal_dashboard(request):
    profile = request.association_profile
    orders = _get_dashboard_orders(profile)
    return render(request, TEMPLATE_PORTAL_DASHBOARD, {"orders": orders})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_order_create(request):
    profile = request.association_profile
    recipients = _get_active_recipients(profile)
    destinations = _get_active_destinations()
    destination_options = _build_destination_options(destinations)
    destination_by_id = {str(destination.id): destination for destination in destinations}
    recipient_options_all = _build_recipient_options(profile, recipients)

    product_options, product_by_id, available_by_id = build_product_selection_data()

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

        if not form_data["destination_id"]:
            errors.append(ERROR_DESTINATION_REQUIRED)
        else:
            selected_destination = destination_by_id.get(form_data["destination_id"])
            if selected_destination is None:
                errors.append(ERROR_DESTINATION_INVALID)

        recipient_options = _filter_recipient_options(
            recipient_options_all,
            form_data["destination_id"],
        )
        if not form_data["recipient_id"]:
            errors.append(ERROR_RECIPIENT_REQUIRED)
        elif form_data["recipient_id"] != RECIPIENT_SELF:
            allowed_recipient_ids = {option["id"] for option in recipient_options}
            if form_data["recipient_id"] not in allowed_recipient_ids:
                errors.append(ERROR_RECIPIENT_UNAVAILABLE_FOR_DESTINATION)

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
        if not line_items and not selected_ready_carton_ids and not selected_ready_kit_ids:
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
