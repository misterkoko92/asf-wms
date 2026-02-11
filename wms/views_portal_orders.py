from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .document_uploads import validate_document_upload
from .models import (
    AssociationRecipient,
    DocumentReviewStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderReviewStatus,
)
from .order_helpers import (
    build_carton_format_data,
    build_order_line_estimates,
    build_order_line_items,
    build_order_product_rows,
)
from .order_notifications import send_portal_order_notifications
from .portal_helpers import (
    build_destination_address,
    get_contact_address,
    get_default_carton_format,
)
from .portal_order_handlers import create_portal_order
from .scan_helpers import build_product_selection_data, parse_int as parse_int_safe
from .services import StockError
from .view_permissions import association_required
from .view_utils import sorted_choices

TEMPLATE_PORTAL_DASHBOARD = "portal/dashboard.html"
TEMPLATE_PORTAL_ORDER_CREATE = "portal/order_create.html"
TEMPLATE_PORTAL_ORDER_DETAIL = "portal/order_detail.html"

ACTION_UPLOAD_DOCUMENT = "upload_doc"
RECIPIENT_SELF = "self"
DEFAULT_COUNTRY = "France"

ERROR_RECIPIENT_REQUIRED = "Destinataire requis."
ERROR_PRODUCT_REQUIRED = "Ajoutez au moins un produit."
ERROR_ASSOCIATION_ADDRESS_REQUIRED = "Adresse association manquante."
ERROR_RECIPIENT_INVALID = "Destinataire invalide."
ERROR_ORDER_UPLOAD_NOT_APPROVED = "Documents disponibles après validation de la commande."

MESSAGE_ORDER_SENT = "Commande envoyée."
MESSAGE_ORDER_DOCUMENT_ADDED = "Document ajouté."


def _get_dashboard_orders(profile):
    return Order.objects.filter(association_contact=profile.contact).order_by("-created_at")[
        :50
    ]


def _get_active_recipients(profile):
    return list(
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
        ).order_by("name")
    )


def _build_recipient_options(profile, recipients):
    options = [
        {"id": RECIPIENT_SELF, "label": f"{profile.contact.name} (association)"},
        *[{"id": str(recipient.id), "label": recipient.name} for recipient in recipients],
    ]
    return sorted(options, key=lambda item: str(item["label"] or "").lower())


def _build_order_create_defaults():
    return {"recipient_id": RECIPIENT_SELF, "notes": ""}


def _resolve_self_destination(profile, errors):
    address = get_contact_address(profile.contact)
    if not address:
        errors.append(ERROR_ASSOCIATION_ADDRESS_REQUIRED)
        return {
            "recipient_name": profile.contact.name,
            "recipient_contact": profile.contact,
            "destination_city": "",
            "destination_country": DEFAULT_COUNTRY,
            "destination_address": "",
        }

    return {
        "recipient_name": profile.contact.name,
        "recipient_contact": profile.contact,
        "destination_city": address.city or "",
        "destination_country": address.country or DEFAULT_COUNTRY,
        "destination_address": build_destination_address(
            line1=address.address_line1,
            line2=address.address_line2,
            postal_code=address.postal_code,
            city=address.city,
            country=address.country,
        ),
    }


def _resolve_recipient_destination(profile, recipient_id, errors):
    recipient = (
        AssociationRecipient.objects.filter(
            id=recipient_id,
            association_contact=profile.contact,
        )
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

    return {
        "recipient_name": recipient.name,
        "recipient_contact": None,
        "destination_city": recipient.city or "",
        "destination_country": recipient.country or DEFAULT_COUNTRY,
        "destination_address": build_destination_address(
            line1=recipient.address_line1,
            line2=recipient.address_line2,
            postal_code=recipient.postal_code,
            city=recipient.city,
            country=recipient.country,
        ),
    }


def _resolve_destination(profile, recipient_id, errors):
    if recipient_id == RECIPIENT_SELF:
        return _resolve_self_destination(profile, errors)
    return _resolve_recipient_destination(
        profile,
        parse_int_safe(recipient_id),
        errors,
    )


def _build_order_create_context(
    *,
    recipient_options,
    form_data,
    product_options,
    product_by_id,
    line_quantities,
    errors,
    line_errors,
):
    carton_format = get_default_carton_format()
    carton_data = build_carton_format_data(carton_format)
    product_rows, total_estimated_cartons = build_order_product_rows(
        product_options,
        product_by_id,
        line_quantities,
        carton_format,
    )
    return {
        "recipient_options": recipient_options,
        "form_data": form_data,
        "products": product_rows,
        "product_data": product_options,
        "errors": errors,
        "line_errors": line_errors,
        "line_quantities": line_quantities,
        "total_estimated_cartons": total_estimated_cartons,
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
    recipient_options = _build_recipient_options(profile, recipients)

    product_options, product_by_id, available_by_id = build_product_selection_data()

    form_data = _build_order_create_defaults()
    errors = []
    line_errors = {}
    line_quantities = {}
    line_items = []

    if request.method == "POST":
        form_data["recipient_id"] = (request.POST.get("recipient_id") or "").strip()
        form_data["notes"] = (request.POST.get("notes") or "").strip()
        if not form_data["recipient_id"]:
            errors.append(ERROR_RECIPIENT_REQUIRED)
        line_items, line_quantities, line_errors = build_order_line_items(
            request.POST,
            product_options=product_options,
            product_by_id=product_by_id,
            available_by_id=available_by_id,
        )
        if not line_items:
            errors.append(ERROR_PRODUCT_REQUIRED)

        destination = _resolve_destination(profile, form_data["recipient_id"], errors)

        if not errors and not line_errors:
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

    return render(
        request,
        TEMPLATE_PORTAL_ORDER_CREATE,
        _build_order_create_context(
            recipient_options=recipient_options,
            form_data=form_data,
            product_options=product_options,
            product_by_id=product_by_id,
            line_quantities=line_quantities,
            errors=errors,
            line_errors=line_errors,
        ),
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_order_detail(request, order_id):
    profile = request.association_profile
    order = _get_portal_order_or_404(profile, order_id)

    if request.method == "POST" and request.POST.get("action") == ACTION_UPLOAD_DOCUMENT:
        return _handle_order_document_upload(request, order)

    return render(
        request,
        TEMPLATE_PORTAL_ORDER_DETAIL,
        _build_order_detail_context(order),
    )
