import json
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from django.conf import settings

from .forms import (
    ScanOutForm,
    ScanPackForm,
    ScanReceiptAssociationForm,
    ScanStockUpdateForm,
    ScanShipmentForm,
    ShipmentTrackingForm,
)
from .models import (
    Carton,
    CartonStatus,
    Document,
    DocumentType,
    Destination,
    Location,
    Product,
    Receipt,
    ReceiptType,
    Order,
    OrderReviewStatus,
    OrderStatus,
    AssociationRecipient,
    AccountDocument,
    AccountDocumentType,
    DocumentReviewStatus,
    OrderDocument,
    OrderDocumentType,
    PublicOrderLink,
    PrintTemplate,
    PrintTemplateVersion,
    Shipment,
    ShipmentStatus,
    WmsChange,
)
from .print_context import (
    build_carton_document_context,
    build_label_context,
    build_product_label_context,
    build_preview_context,
    build_sample_label_context,
)
from .print_layouts import BLOCK_LIBRARY, DEFAULT_LAYOUTS, DOCUMENT_TEMPLATES
from .print_renderer import get_template_layout, layout_changed, render_layout_from_layout
from .print_utils import build_label_pages, extract_block_style
from .import_utils import (
    get_value,
    parse_bool,
    parse_decimal,
    parse_str,
)
from .scan_helpers import (
    build_carton_formats,
    build_location_data,
    build_packing_result,
    build_product_options,
    build_product_selection_data,
    build_shipment_line_values,
    parse_int as parse_int_safe,
)
from .scan_shipment_handlers import (
    handle_shipment_create_post,
    handle_shipment_edit_post,
)
from .portal_helpers import (
    build_destination_address,
    get_association_profile,
    get_contact_address,
    get_default_carton_format,
)
from .order_helpers import (
    build_carton_format_data,
    build_order_line_estimates,
    build_order_line_items,
    build_order_product_rows,
)
from .view_permissions import association_required, require_superuser as _require_superuser
from .shipment_document_handlers import (
    handle_shipment_document_delete,
    handle_shipment_document_upload,
)
from .shipment_form_helpers import (
    build_carton_selection_data,
    build_shipment_edit_initial,
    build_shipment_edit_line_values,
    build_shipment_form_context,
    build_shipment_form_payload,
)
from .shipment_view_helpers import (
    build_carton_options,
    build_shipment_document_links,
    build_shipments_ready_rows,
    next_tracking_status,
    render_carton_document,
    render_shipment_document,
    render_shipment_labels,
)
from .receipt_view_helpers import build_receipts_view_rows
from .receipt_handlers import (
    build_hors_format_lines,
    handle_receipt_action,
    handle_receipt_association_post,
)
from .receipt_scan_state import build_receipt_scan_state
from .receipt_pallet_state import (
    build_receive_pallet_context,
    build_receive_pallet_state,
)
from .stock_view_helpers import build_stock_context
from .order_scan_handlers import handle_order_action
from .order_view_handlers import handle_orders_view_action
from .order_view_helpers import build_orders_view_rows
from .order_scan_state import build_order_scan_state
from .pack_handlers import build_pack_defaults, handle_pack_post
from .stock_update_handlers import handle_stock_update_post
from .stock_out_handlers import handle_stock_out_post
from .shipment_tracking_handlers import handle_shipment_tracking_post
from .carton_handlers import handle_carton_status_update
from .carton_view_helpers import build_cartons_ready_rows, get_carton_capacity_cm3
from .account_request_handlers import handle_account_request_form
from .view_utils import sorted_choices
from .contact_payloads import build_shipper_contact_payload
from .exports import EXPORT_HANDLERS
from .scan_import_handlers import handle_scan_import_action, render_scan_import
from .document_uploads import validate_document_upload
from .public_order_handlers import (
    create_public_order,
    send_public_order_notifications,
)
from .order_notifications import send_portal_order_notifications
from .portal_order_handlers import create_portal_order
from .services import (
    StockError,
    prepare_order,
    receive_stock,
)


@require_http_methods(["GET", "POST"])
def portal_login(request):
    if request.user.is_authenticated:
        profile = get_association_profile(request.user)
        if profile:
            return redirect("portal:portal_dashboard")

    errors = []
    identifier = ""
    next_url = request.GET.get("next") or ""
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""
        next_url = (request.POST.get("next") or "").strip()
        if not identifier or not password:
            errors.append("Email et mot de passe requis.")
        else:
            user = get_user_model().objects.filter(email__iexact=identifier).first()
            username = user.username if user else identifier
            user = authenticate(request, username=username, password=password)
            if not user:
                errors.append("Identifiants invalides.")
            elif not user.is_active:
                errors.append("Compte inactif.")
            elif not get_association_profile(user):
                errors.append("Compte non active par ASF.")
            else:
                login(request, user)
                profile = get_association_profile(user)
                if profile and profile.must_change_password:
                    return redirect("portal:portal_change_password")
                return redirect(next_url or "portal:portal_dashboard")

    return render(
        request,
        "portal/login.html",
        {"errors": errors, "identifier": identifier, "next": next_url},
    )


@login_required(login_url="portal:portal_login")
def portal_logout(request):
    logout(request)
    return redirect("portal:portal_login")


@require_http_methods(["GET", "POST"])
def portal_set_password(request, uidb64, token):
    user = None
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_user_model().objects.filter(pk=uid).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "portal/set_password.html", {"invalid": True})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile = get_association_profile(user)
        if profile and profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        login(request, user)
        return redirect("portal:portal_dashboard")

    return render(request, "portal/set_password.html", {"form": form, "invalid": False})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_change_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        profile = request.association_profile
        if profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password"])
        messages.success(request, "Mot de passe mis a jour.")
        return redirect("portal:portal_dashboard")
    return render(request, "portal/change_password.html", {"form": form})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET"])
def portal_dashboard(request):
    profile = request.association_profile
    orders = (
        Order.objects.filter(association_contact=profile.contact)
        .order_by("-created_at")[:50]
    )
    return render(request, "portal/dashboard.html", {"orders": orders})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_order_create(request):
    profile = request.association_profile
    recipients = list(
        AssociationRecipient.objects.filter(
            association_contact=profile.contact, is_active=True
        ).order_by("name")
    )
    recipient_options = [
        {"id": "self", "label": f"{profile.contact.name} (association)"},
        *[{"id": str(rec.id), "label": rec.name} for rec in recipients],
    ]
    recipient_options = sorted(
        recipient_options, key=lambda item: str(item["label"] or "").lower()
    )

    product_options, product_by_id, available_by_id = build_product_selection_data()

    form_data = {"recipient_id": "self", "notes": ""}
    errors = []
    line_errors = {}
    line_quantities = {}
    line_items = []

    if request.method == "POST":
        form_data["recipient_id"] = (request.POST.get("recipient_id") or "").strip()
        form_data["notes"] = (request.POST.get("notes") or "").strip()
        if not form_data["recipient_id"]:
            errors.append("Destinataire requis.")
        line_items, line_quantities, line_errors = build_order_line_items(
            request.POST,
            product_options=product_options,
            product_by_id=product_by_id,
            available_by_id=available_by_id,
        )
        if not line_items:
            errors.append("Ajoutez au moins un produit.")

        recipient_name = ""
        destination_city = ""
        destination_country = "France"
        destination_address = ""
        recipient_contact = None

        if form_data["recipient_id"] == "self":
            recipient_contact = profile.contact
            recipient_name = profile.contact.name
            address = get_contact_address(profile.contact)
            if not address:
                errors.append("Adresse association manquante.")
            else:
                destination_address = build_destination_address(
                    line1=address.address_line1,
                    line2=address.address_line2,
                    postal_code=address.postal_code,
                    city=address.city,
                    country=address.country,
                )
                destination_city = address.city or ""
                destination_country = address.country or "France"
        else:
            recipient_id = parse_int_safe(form_data["recipient_id"])
            recipient = (
                AssociationRecipient.objects.filter(
                    id=recipient_id, association_contact=profile.contact
                )
                .order_by("name")
                .first()
            )
            if not recipient:
                errors.append("Destinataire invalide.")
            else:
                recipient_name = recipient.name
                destination_address = build_destination_address(
                    line1=recipient.address_line1,
                    line2=recipient.address_line2,
                    postal_code=recipient.postal_code,
                    city=recipient.city,
                    country=recipient.country,
                )
                destination_city = recipient.city or ""
                destination_country = recipient.country or "France"

        if not errors and not line_errors:
            try:
                order = create_portal_order(
                    user=request.user,
                    profile=profile,
                    recipient_name=recipient_name,
                    recipient_contact=recipient_contact,
                    destination_address=destination_address,
                    destination_city=destination_city,
                    destination_country=destination_country,
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
                messages.success(request, "Commande envoyee.")
                return redirect("portal:portal_order_detail", order_id=order.id)

    carton_format = get_default_carton_format()
    carton_data = build_carton_format_data(carton_format)
    product_rows, total_estimated_cartons = build_order_product_rows(
        product_options, product_by_id, line_quantities, carton_format
    )

    return render(
        request,
        "portal/order_create.html",
        {
            "recipient_options": recipient_options,
            "form_data": form_data,
            "products": product_rows,
            "product_data": product_options,
            "errors": errors,
            "line_errors": line_errors,
            "line_quantities": line_quantities,
            "total_estimated_cartons": total_estimated_cartons,
            "carton_format": carton_data,
        },
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_order_detail(request, order_id):
    profile = request.association_profile
    order = get_object_or_404(
        Order.objects.select_related("association_contact"),
        id=order_id,
        association_contact=profile.contact,
    )

    if request.method == "POST" and request.POST.get("action") == "upload_doc":
        if order.review_status != OrderReviewStatus.APPROVED:
            messages.error(
                request,
                "Documents disponibles apres validation de la commande.",
            )
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
        messages.success(request, "Document ajoute.")
        return redirect("portal:portal_order_detail", order_id=order.id)

    carton_format = get_default_carton_format()
    line_rows, total_estimated_cartons = build_order_line_estimates(
        order.lines.select_related("product"),
        carton_format,
    )

    return render(
        request,
        "portal/order_detail.html",
        {
            "order": order,
            "line_rows": line_rows,
            "total_estimated_cartons": total_estimated_cartons,
            "order_documents": order.documents.all(),
            "order_doc_types": sorted_choices(OrderDocumentType.choices),
            "can_upload_docs": order.review_status == OrderReviewStatus.APPROVED,
        },
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_recipients(request):
    profile = request.association_profile
    errors = []
    form_data = {
        "name": "",
        "email": "",
        "phone": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": "France",
        "notes": "",
    }

    if request.method == "POST" and request.POST.get("action") == "create_recipient":
        form_data.update(
            {
                "name": (request.POST.get("name") or "").strip(),
                "email": (request.POST.get("email") or "").strip(),
                "phone": (request.POST.get("phone") or "").strip(),
                "address_line1": (request.POST.get("address_line1") or "").strip(),
                "address_line2": (request.POST.get("address_line2") or "").strip(),
                "postal_code": (request.POST.get("postal_code") or "").strip(),
                "city": (request.POST.get("city") or "").strip(),
                "country": (request.POST.get("country") or "France").strip(),
                "notes": (request.POST.get("notes") or "").strip(),
            }
        )
        if not form_data["name"]:
            errors.append("Nom requis.")
        if not form_data["address_line1"]:
            errors.append("Adresse requise.")
        if not errors:
            AssociationRecipient.objects.create(
                association_contact=profile.contact,
                name=form_data["name"],
                email=form_data["email"],
                phone=form_data["phone"],
                address_line1=form_data["address_line1"],
                address_line2=form_data["address_line2"],
                postal_code=form_data["postal_code"],
                city=form_data["city"],
                country=form_data["country"] or "France",
                notes=form_data["notes"],
            )
            messages.success(request, "Destinataire ajoute.")
            return redirect("portal:portal_recipients")

    recipients = AssociationRecipient.objects.filter(
        association_contact=profile.contact, is_active=True
    ).order_by("name")
    return render(
        request,
        "portal/recipients.html",
        {"recipients": recipients, "errors": errors, "form_data": form_data},
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_account(request):
    profile = request.association_profile
    association = profile.contact
    address = get_contact_address(association)

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == "update_notifications":
            profile.notification_emails = (
                request.POST.get("notification_emails") or ""
            ).strip()
            profile.save(update_fields=["notification_emails"])
            messages.success(request, "Contacts mis a jour.")
            return redirect("portal:portal_account")
        if action == "upload_account_doc":
            payload, error = validate_document_upload(
                request,
                doc_type_choices=AccountDocumentType.choices,
            )
            if error:
                messages.error(request, error)
                return redirect("portal:portal_account")
            doc_type, uploaded = payload
            AccountDocument.objects.create(
                association_contact=association,
                doc_type=doc_type,
                status=DocumentReviewStatus.PENDING,
                file=uploaded,
                uploaded_by=request.user,
            )
            messages.success(request, "Document ajoute.")
            return redirect("portal:portal_account")

    account_documents = AccountDocument.objects.filter(
        association_contact=association
    ).order_by("-uploaded_at")
    return render(
        request,
        "portal/account.html",
        {
            "association": association,
            "address": address,
            "notification_emails": profile.notification_emails,
            "account_documents": account_documents,
            "account_doc_types": sorted_choices(AccountDocumentType.choices),
            "user": request.user,
        },
    )


@require_http_methods(["GET"])
def scan_public_order_summary(request, token, order_id):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    order = (
        Order.objects.select_related("recipient_contact")
        .prefetch_related("lines__product")
        .filter(id=order_id, public_link=link)
        .first()
    )
    if not order:
        raise Http404

    carton_format = get_default_carton_format()
    line_rows, total_cartons = build_order_line_estimates(
        order.lines.all(),
        carton_format,
        estimate_key="cartons_estimated",
    )

    return render(
        request,
        "print/order_summary.html",
        {
            "order": order,
            "line_rows": line_rows,
            "total_cartons": total_cartons,
            "carton_format": carton_format,
        },
    )


@require_http_methods(["GET", "POST"])
def scan_public_account_request(request, token):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    return handle_account_request_form(
        request,
        link=link,
        redirect_url=reverse("scan:scan_public_account_request", args=[token]),
    )


@require_http_methods(["GET", "POST"])
def portal_account_request(request):
    return handle_account_request_form(
        request,
        link=None,
        redirect_url=reverse("portal:portal_account_request"),
    )


@require_http_methods(["GET", "POST"])
def scan_public_order(request, token):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    product_options, product_by_id, available_by_id = build_product_selection_data()

    contact_payload = build_shipper_contact_payload()

    form_data = {
        "association_name": "",
        "association_email": "",
        "association_phone": "",
        "association_line1": "",
        "association_line2": "",
        "association_postal_code": "",
        "association_city": "",
        "association_country": "France",
        "association_notes": "",
        "association_contact_id": "",
    }
    errors = []
    line_errors = {}
    line_quantities = {}
    summary_url = None
    summary_order_id = parse_int_safe(request.GET.get("order"))
    if summary_order_id:
        summary_url = reverse(
            "scan:scan_public_order_summary", args=[token, summary_order_id]
        )

    if request.method == "POST":
        form_data.update(
            {
                "association_name": (request.POST.get("association_name") or "").strip(),
                "association_email": (request.POST.get("association_email") or "").strip(),
                "association_phone": (request.POST.get("association_phone") or "").strip(),
                "association_line1": (request.POST.get("association_line1") or "").strip(),
                "association_line2": (request.POST.get("association_line2") or "").strip(),
                "association_postal_code": (
                    request.POST.get("association_postal_code") or ""
                ).strip(),
                "association_city": (request.POST.get("association_city") or "").strip(),
                "association_country": (
                    request.POST.get("association_country") or "France"
                ).strip(),
                "association_notes": (request.POST.get("association_notes") or "").strip(),
                "association_contact_id": (
                    request.POST.get("association_contact_id") or ""
                ).strip(),
            }
        )
        if not form_data["association_name"]:
            errors.append("Nom de l'association requis.")
        if not form_data["association_line1"]:
            errors.append("Adresse requise.")

        line_items, line_quantities, line_errors = build_order_line_items(
            request.POST,
            product_options=product_options,
            product_by_id=product_by_id,
            available_by_id=available_by_id,
        )

        if not line_items:
            errors.append("Ajoutez au moins un produit.")

        if not errors and not line_errors:
            try:
                order, contact = create_public_order(
                    request=request,
                    link=link,
                    form_data=form_data,
                    line_items=line_items,
                )
            except StockError as exc:
                errors.append(str(exc))
            else:
                send_public_order_notifications(
                    request,
                    token=token,
                    order=order,
                    form_data=form_data,
                    contact=contact,
                )
                messages.success(
                    request,
                    "Commande envoyee. L'equipe ASF va la traiter rapidement.",
                )
                return redirect(
                    f"{reverse('scan:scan_public_order', args=[token])}?order={order.id}"
                )

    carton_format = get_default_carton_format()
    carton_data = build_carton_format_data(carton_format)

    return render(
        request,
        "scan/public_order.html",
        {
            "link": link,
            "products": product_options,
            "product_data": product_options,
            "contacts": contact_payload,
            "form_data": form_data,
            "errors": errors,
            "line_errors": line_errors,
            "line_quantities": line_quantities,
            "carton_format": carton_data,
            "summary_url": summary_url,
        },
    )


@login_required
def scan_stock(request):
    return render(request, "scan/stock.html", build_stock_context(request))


@login_required
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
        "scan/cartons_ready.html",
        {
            "active": "cartons_ready",
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


@login_required
@require_http_methods(["GET"])
def scan_shipments_ready(request):
    shipments_qs = (
        Shipment.objects.select_related("destination")
        .annotate(
            carton_count=Count("carton", distinct=True),
            ready_count=Count(
                "carton",
                filter=Q(
                    carton__status__in=[CartonStatus.PACKED, CartonStatus.SHIPPED]
                ),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )
    shipments = build_shipments_ready_rows(shipments_qs)

    return render(
        request,
        "scan/shipments_ready.html",
        {
            "active": "shipments_ready",
            "shipments": shipments,
        },
    )


@login_required
@require_http_methods(["GET"])
def scan_receipts_view(request):
    filter_value = (request.GET.get("type") or "all").strip().lower()
    receipts_qs = (
        Receipt.objects.select_related("source_contact", "carrier_contact")
        .prefetch_related("hors_format_items")
        .order_by("-received_on", "-created_at")
    )
    if filter_value == "pallet":
        receipts_qs = receipts_qs.filter(receipt_type=ReceiptType.PALLET)
    elif filter_value == "association":
        receipts_qs = receipts_qs.filter(receipt_type=ReceiptType.ASSOCIATION)
    else:
        filter_value = "all"
    receipts = build_receipts_view_rows(receipts_qs)

    return render(
        request,
        "scan/receipts_view.html",
        {
            "active": "receipts_view",
            "filter_value": filter_value,
            "receipts": receipts,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_stock_update(request):
    product_options = build_product_options()
    location_data = build_location_data()
    create_form = ScanStockUpdateForm(request.POST or None)
    if request.method == "POST":
        response = handle_stock_update_post(request, form=create_form)
        if response:
            return response
    return render(
        request,
        "scan/stock_update.html",
        {
            "active": "stock_update",
            "create_form": create_form,
            "products_json": product_options,
            "location_data": location_data,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    receipt_state = build_receipt_scan_state(request, action=action)
    select_form = receipt_state["select_form"]
    create_form = receipt_state["create_form"]
    line_form = receipt_state["line_form"]
    selected_receipt = receipt_state["selected_receipt"]
    receipt_lines = receipt_state["receipt_lines"]
    pending_count = receipt_state["pending_count"]

    if request.method == "POST":
        response, handler_lines, handler_pending = handle_receipt_action(
            request,
            action=action,
            select_form=select_form,
            create_form=create_form,
            line_form=line_form,
            selected_receipt=selected_receipt,
        )
        if response:
            return response
        if handler_lines is not None:
            receipt_lines = handler_lines
            pending_count = handler_pending
    return render(
        request,
        "scan/receive.html",
        {
            "active": "receive",
            "products_json": product_options,
            "select_form": select_form,
            "create_form": create_form,
            "line_form": line_form,
            "selected_receipt": selected_receipt,
            "receipt_lines": receipt_lines,
            "pending_count": pending_count,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    action = request.POST.get("action", "")
    state = build_receive_pallet_state(request, action=action)
    if state["response"]:
        return state["response"]

    return render(
        request,
        "scan/receive_pallet.html",
        build_receive_pallet_context(state),
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_association(request):
    line_count, line_values = build_hors_format_lines(request)
    line_errors = {}
    create_form = ScanReceiptAssociationForm(request.POST or None)
    if request.method == "POST":
        response, line_errors = handle_receipt_association_post(
            request,
            create_form=create_form,
            line_values=line_values,
            line_count=line_count,
        )
        if response:
            return response

    return render(
        request,
        "scan/receive_association.html",
        {
            "active": "receive_association",
            "create_form": create_form,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_order(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    order_state = build_order_scan_state(request, action=action)
    select_form = order_state["select_form"]
    create_form = order_state["create_form"]
    line_form = order_state["line_form"]
    selected_order = order_state["selected_order"]
    order_lines = order_state["order_lines"]
    remaining_total = order_state["remaining_total"]

    if request.method == "POST":
        response, handler_lines, handler_remaining = handle_order_action(
            request,
            action=action,
            select_form=select_form,
            create_form=create_form,
            line_form=line_form,
            selected_order=selected_order,
        )
        if response:
            return response
        if handler_lines is not None:
            order_lines = handler_lines
            remaining_total = handler_remaining

    return render(
        request,
        "scan/order.html",
        {
            "active": "order",
            "products_json": product_options,
            "select_form": select_form,
            "create_form": create_form,
            "line_form": line_form,
            "selected_order": selected_order,
            "order_lines": order_lines,
            "remaining_total": remaining_total,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_orders_view(request):
    orders_qs = (
        Order.objects.select_related(
            "association_contact",
            "recipient_contact",
            "created_by",
            "shipment",
        )
        .prefetch_related("documents")
        .order_by("-created_at")
    )

    if request.method == "POST":
        response = handle_orders_view_action(request, orders_qs=orders_qs)
        if response:
            return response

    rows = build_orders_view_rows(orders_qs)

    return render(
        request,
        "scan/orders_view.html",
        {
            "active": "orders_view",
            "orders": rows,
            "review_status_choices": sorted_choices(OrderReviewStatus.choices),
            "approved_status": OrderReviewStatus.APPROVED,
            "rejected_status": OrderReviewStatus.REJECTED,
            "changes_status": OrderReviewStatus.CHANGES_REQUESTED,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_pack(request):
    form = ScanPackForm(request.POST or None)
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
        if response:
            return response
    else:
        (
            carton_format_id,
            carton_custom,
            line_count,
            line_values,
        ) = build_pack_defaults(default_format)
    return render(
        request,
        "scan/pack.html",
        {
            "form": form,
            "active": "pack",
            "products_json": product_options,
            "carton_formats": carton_formats,
            "carton_format_id": carton_format_id,
            "carton_custom": carton_custom,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
            "packing_result": packing_result,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_shipment_create(request):
    destination_id = request.POST.get("destination") or request.GET.get("destination")
    form = ScanShipmentForm(request.POST or None, destination_id=destination_id)
    (
        product_options,
        available_cartons,
        destinations_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    ) = build_shipment_form_payload()
    cartons_json, available_carton_ids = build_carton_selection_data(available_cartons)
    line_errors = {}
    line_values = []

    if request.method == "POST":
        response, carton_count, line_values, line_errors = handle_shipment_create_post(
            request,
            form=form,
            available_carton_ids=available_carton_ids,
        )
        if response:
            return response
    else:
        carton_count = form.initial.get("carton_count", 1)
        line_values = build_shipment_line_values(carton_count)

    context = build_shipment_form_context(
        form=form,
        product_options=product_options,
        cartons_json=cartons_json,
        carton_count=carton_count,
        line_values=line_values,
        line_errors=line_errors,
        destinations_json=destinations_json,
        recipient_contacts_json=recipient_contacts_json,
        correspondent_contacts_json=correspondent_contacts_json,
    )
    context["active"] = "shipment"
    return render(request, "scan/shipment_create.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def scan_shipment_edit(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination__correspondent_contact"),
        pk=shipment_id,
    )
    if shipment.status in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}:
        messages.error(request, "Expedition non modifiable.")
        return redirect("scan:scan_shipments_ready")

    shipment.ensure_qr_code(request=request)

    assigned_cartons_qs = shipment.carton_set.prefetch_related(
        "cartonitem_set__product_lot__product"
    ).order_by("code")
    assigned_cartons = list(assigned_cartons_qs)
    assigned_carton_options = build_carton_options(assigned_cartons)

    initial = build_shipment_edit_initial(shipment, assigned_cartons)
    destination_id = request.POST.get("destination") or initial["destination"]
    form = ScanShipmentForm(
        request.POST or None, destination_id=destination_id, initial=initial
    )
    (
        product_options,
        available_cartons,
        destinations_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    ) = build_shipment_form_payload()
    cartons_json, allowed_carton_ids = build_carton_selection_data(
        available_cartons, assigned_carton_options
    )
    line_errors = {}
    line_values = []

    if request.method == "POST":
        response, carton_count, line_values, line_errors = handle_shipment_edit_post(
            request,
            form=form,
            shipment=shipment,
            allowed_carton_ids=allowed_carton_ids,
        )
        if response:
            return response
    else:
        carton_count = initial["carton_count"]
        line_values = build_shipment_edit_line_values(assigned_cartons, carton_count)

    documents = Document.objects.filter(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL
    ).order_by("-generated_at")
    carton_docs = [{"id": carton.id, "code": carton.code} for carton in assigned_cartons]

    context = build_shipment_form_context(
        form=form,
        product_options=product_options,
        cartons_json=cartons_json,
        carton_count=carton_count,
        line_values=line_values,
        line_errors=line_errors,
        destinations_json=destinations_json,
        recipient_contacts_json=recipient_contacts_json,
        correspondent_contacts_json=correspondent_contacts_json,
    )
    context.update(
        {
            "active": "shipments_ready",
            "is_edit": True,
            "shipment": shipment,
            "tracking_url": shipment.get_tracking_url(request=request),
            "documents": documents,
            "carton_docs": carton_docs,
        }
    )
    return render(request, "scan/shipment_create.html", context)


@require_http_methods(["GET", "POST"])
def scan_shipment_track(request, shipment_ref):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    shipment.ensure_qr_code(request=request)
    documents, carton_docs, additional_docs = build_shipment_document_links(
        shipment, public=True
    )
    last_event = shipment.tracking_events.order_by("-created_at").first()
    next_status = next_tracking_status(last_event.status if last_event else None)
    form = ShipmentTrackingForm(request.POST or None, initial_status=next_status)
    response = handle_shipment_tracking_post(request, shipment=shipment, form=form)
    if response:
        return response
    events = shipment.tracking_events.select_related("created_by").all()
    tracking_url = shipment.get_tracking_url(request=request)
    return render(
        request,
        "scan/shipment_tracking.html",
        {
            "shipment": shipment,
            "active": "shipments_ready",
            "tracking_url": tracking_url,
            "documents": documents,
            "carton_docs": carton_docs,
            "additional_docs": additional_docs,
            "events": events,
            "form": form,
        },
    )


@login_required
@require_http_methods(["GET"])
def scan_shipment_document(request, shipment_id, doc_type):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    return render_shipment_document(request, shipment, doc_type)


@require_http_methods(["GET"])
def scan_shipment_document_public(request, shipment_ref, doc_type):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    return render_shipment_document(request, shipment, doc_type)


@login_required
@require_http_methods(["GET"])
def scan_shipment_carton_document(request, shipment_id, carton_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return render_carton_document(request, shipment, carton)


@require_http_methods(["GET"])
def scan_shipment_carton_document_public(request, shipment_ref, carton_id):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return render_carton_document(request, shipment, carton)


@login_required
@require_http_methods(["GET"])
def scan_carton_document(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.select_related("shipment"),
        pk=carton_id,
    )
    if carton.shipment_id:
        shipment = carton.shipment
        context = build_carton_document_context(shipment, carton)
    else:
        item_rows = []
        weight_total_g = 0
        for item in carton.cartonitem_set.select_related(
            "product_lot", "product_lot__product"
        ):
            product = item.product_lot.product
            if product.weight_g:
                weight_total_g += product.weight_g * item.quantity
            item_rows.append(
                {
                    "product": item.product_lot.product.name,
                    "lot": item.product_lot.lot_code or "N/A",
                    "quantity": item.quantity,
                    "expires_on": item.product_lot.expires_on,
                }
            )
        context = {
            "document_date": timezone.localdate(),
            "shipment_ref": "-",
            "carton_code": carton.code,
            "item_rows": item_rows,
            "carton_weight_kg": weight_total_g / 1000 if weight_total_g else None,
            "hide_footer": True,
        }
    layout_override = get_template_layout("packing_list_carton")
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, "print/dynamic_document.html", {"blocks": blocks})
    return render(request, "print/liste_colisage_carton.html", context)


@login_required
@require_http_methods(["GET"])
def scan_shipment_labels(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), pk=shipment_id
    )
    return render_shipment_labels(request, shipment)


@require_http_methods(["GET"])
def scan_shipment_labels_public(request, shipment_ref):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), reference=shipment_ref
    )
    return render_shipment_labels(request, shipment)


@login_required
@require_http_methods(["GET"])
def scan_shipment_label(request, shipment_id, carton_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), pk=shipment_id
    )
    shipment.ensure_qr_code(request=request)
    cartons = list(shipment.carton_set.order_by("code"))
    total = len(cartons)
    position = None
    for index, carton in enumerate(cartons, start=1):
        if carton.id == carton_id:
            position = index
            break
    if position is None:
        raise Http404("Carton not found for shipment")
    label_context = build_label_context(shipment, position=position, total=total)
    qr_url = label_context.get("label_qr_url") or ""
    labels = [
        {
            "city": label_context["label_city"],
            "iata": label_context["label_iata"],
            "shipment_ref": label_context["label_shipment_ref"],
            "position": label_context["label_position"],
            "total": label_context["label_total"],
            "qr_url": qr_url,
            "carton_id": carton_id,
        }
    ]
    layout_override = get_template_layout("shipment_label")
    if layout_override:
        label_context["label_qr_url"] = qr_url
        blocks = render_layout_from_layout(layout_override, label_context)
        return render(
            request, "print/dynamic_labels.html", {"labels": [{"blocks": blocks}]}
        )
    return render(request, "print/etiquette_expedition.html", {"labels": labels})


@login_required
@require_http_methods(["GET"])
def scan_print_templates(request):
    _require_superuser(request)
    template_map = {
        template.doc_type: template
        for template in PrintTemplate.objects.select_related("updated_by")
    }
    items = []
    for doc_type, label in DOCUMENT_TEMPLATES:
        template = template_map.get(doc_type)
        items.append(
            {
                "doc_type": doc_type,
                "label": label,
                "has_override": bool(template and template.layout),
                "updated_at": template.updated_at if template else None,
                "updated_by": template.updated_by if template else None,
            }
        )
    return render(
        request,
        "scan/print_template_list.html",
        {
            "active": "print_templates",
            "shell_class": "scan-shell-wide",
            "templates": items,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_print_template_edit(request, doc_type):
    _require_superuser(request)
    doc_map = dict(DOCUMENT_TEMPLATES)
    if doc_type not in doc_map:
        raise Http404("Template not found")

    template = (
        PrintTemplate.objects.filter(doc_type=doc_type)
        .select_related("updated_by")
        .first()
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        layout_data = None

        if action == "restore":
            version_id = request.POST.get("version_id")
            if not version_id:
                messages.error(request, "Version requise.")
                return redirect("scan:scan_print_template_edit", doc_type=doc_type)
            version = get_object_or_404(
                PrintTemplateVersion, pk=version_id, template__doc_type=doc_type
            )
            layout_data = version.layout or {}
        elif action == "reset":
            if template is None:
                messages.info(request, "Ce modele est deja sur la version par defaut.")
                return redirect("scan:scan_print_template_edit", doc_type=doc_type)
            layout_data = {}
        else:
            layout_json = request.POST.get("layout_json") or ""
            try:
                layout_data = json.loads(layout_json) if layout_json else {}
            except json.JSONDecodeError:
                messages.error(request, "Le layout fourni est invalide.")
                return redirect("scan:scan_print_template_edit", doc_type=doc_type)

        previous_layout = template.layout if template else None
        if not layout_changed(previous_layout, layout_data):
            messages.info(request, "Aucun changement detecte.")
            return redirect("scan:scan_print_template_edit", doc_type=doc_type)

        with transaction.atomic():
            if template is None:
                template = PrintTemplate.objects.create(
                    doc_type=doc_type,
                    layout=layout_data,
                    updated_by=request.user,
                )
            else:
                template.layout = layout_data
                template.updated_by = request.user
                template.save(update_fields=["layout", "updated_by", "updated_at"])

            next_version = (
                template.versions.aggregate(max_version=Max("version"))["max_version"]
                or 0
            ) + 1
            PrintTemplateVersion.objects.create(
                template=template,
                version=next_version,
                layout=layout_data,
                created_by=request.user,
            )

        if action == "reset":
            messages.success(request, "Modele remis par defaut.")
        elif action == "restore":
            messages.success(request, "Version restauree.")
        else:
            messages.success(request, "Modele enregistre.")
        return redirect("scan:scan_print_template_edit", doc_type=doc_type)

    default_layout = DEFAULT_LAYOUTS.get(doc_type, {"blocks": []})
    layout = template.layout if template and template.layout else default_layout

    shipments = []
    for shipment in Shipment.objects.select_related("destination").order_by(
        "reference", "id"
    )[:30]:
        dest = (
            shipment.destination.city
            if shipment.destination and shipment.destination.city
            else shipment.destination_address
        )
        label = shipment.reference
        if dest:
            label = f"{label} - {dest}"
        shipments.append({"id": shipment.id, "label": label})
    shipments.sort(key=lambda item: str(item["label"] or "").lower())

    products = []
    if doc_type in {"product_label", "product_qr"}:
        for product in Product.objects.order_by("name")[:30]:
            label = product.name
            if product.sku:
                label = f"{product.sku} - {label}"
            products.append({"id": product.id, "label": label})
        products.sort(key=lambda item: str(item["label"] or "").lower())

    versions = []
    if template:
        versions = list(
            template.versions.select_related("created_by").order_by("-version")
        )

    return render(
        request,
        "scan/print_template_edit.html",
        {
            "active": "print_templates",
            "shell_class": "scan-shell-wide",
            "doc_type": doc_type,
            "doc_label": doc_map[doc_type],
            "template": template,
            "layout": layout,
            "block_library": BLOCK_LIBRARY,
            "shipments": shipments,
            "products": products,
            "versions": versions,
        },
    )


@login_required
@require_http_methods(["POST"])
def scan_print_template_preview(request):
    _require_superuser(request)
    doc_type = (request.POST.get("doc_type") or "").strip()
    if doc_type not in dict(DOCUMENT_TEMPLATES):
        raise Http404("Template not found")

    layout_json = request.POST.get("layout_json") or ""
    try:
        layout_data = json.loads(layout_json) if layout_json else {"blocks": []}
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    shipment_id = request.POST.get("shipment_id") or ""
    shipment = None
    if shipment_id.isdigit():
        shipment = (
            Shipment.objects.select_related("destination")
            .prefetch_related("carton_set")
            .filter(pk=int(shipment_id))
            .first()
        )

    if doc_type == "shipment_label":
        labels = []
        if shipment:
            cartons = list(shipment.carton_set.order_by("code")[:6])
            total = shipment.carton_set.count() or 1
            if not cartons:
                label_context = build_sample_label_context()
                blocks = render_layout_from_layout(layout_data, label_context)
                labels.append({"blocks": blocks})
            else:
                for index, _carton in enumerate(cartons, start=1):
                    label_context = build_label_context(
                        shipment, position=index, total=total
                    )
                    blocks = render_layout_from_layout(layout_data, label_context)
                    labels.append({"blocks": blocks})
        else:
            label_context = build_sample_label_context()
            blocks = render_layout_from_layout(layout_data, label_context)
            labels.append({"blocks": blocks})

        return render(request, "print/dynamic_labels.html", {"labels": labels})

    if doc_type == "product_label":
        product_id = request.POST.get("product_id") or ""
        product = None
        if product_id.isdigit():
            product = (
                Product.objects.select_related("default_location", "default_location__warehouse")
                .filter(pk=int(product_id))
                .first()
            )
        if product:
            base_context = build_product_label_context(product)
        else:
            base_context = build_preview_context(doc_type)
        contexts = [dict(base_context) for _ in range(4)]
        pages, page_style = build_label_pages(
            layout_data,
            contexts,
            block_type="product_label",
            labels_per_page=4,
        )
        return render(
            request,
            "print/product_labels.html",
            {"pages": pages, "page_style": page_style},
        )
    if doc_type == "product_qr":
        product_id = request.POST.get("product_id") or ""
        product = None
        if product_id.isdigit():
            product = (
                Product.objects.select_related("default_location", "default_location__warehouse")
                .filter(pk=int(product_id))
                .first()
            )
        if product:
            if not product.qr_code_image:
                product.generate_qr_code()
                product.save(update_fields=["qr_code_image"])
            base_context = build_preview_context(doc_type, product=product)
        else:
            base_context = build_preview_context(doc_type)
        page_style = extract_block_style(layout_data, "product_qr_label")
        try:
            rows = int(page_style.get("page_rows") or 5)
            cols = int(page_style.get("page_columns") or 3)
        except (TypeError, ValueError):
            rows, cols = 5, 3
        labels_per_page = max(1, rows * cols)
        contexts = [dict(base_context) for _ in range(labels_per_page)]
        pages, page_style = build_label_pages(
            layout_data,
            contexts,
            block_type="product_qr_label",
            labels_per_page=labels_per_page,
        )
        return render(
            request,
            "print/product_qr_labels.html",
            {"pages": pages, "page_style": page_style},
        )

    context = build_preview_context(doc_type, shipment=shipment)
    blocks = render_layout_from_layout(layout_data, context)
    return render(request, "print/dynamic_document.html", {"blocks": blocks})


@login_required
@require_http_methods(["GET", "POST"])
def scan_import(request):
    _require_superuser(request)
    export_target = (request.GET.get("export") or "").strip().lower()
    if export_target:
        handler = EXPORT_HANDLERS.get(export_target)
        if handler is None:
            raise Http404
        return handler()
    default_password = getattr(settings, "IMPORT_DEFAULT_PASSWORD", None)
    pending_import = request.session.get("product_import_pending")

    def clear_pending_import():
        pending = request.session.pop("product_import_pending", None)
        if pending and pending.get("temp_path"):
            Path(pending["temp_path"]).unlink(missing_ok=True)
    if request.method == "POST":
        response = handle_scan_import_action(
            request,
            default_password=default_password,
            clear_pending_import=clear_pending_import,
        )
        if response:
            return response

    return render_scan_import(request, pending_import)


@login_required
@require_http_methods(["POST"])
def scan_shipment_document_upload(request, shipment_id):
    return handle_shipment_document_upload(request, shipment_id=shipment_id)


@login_required
@require_http_methods(["POST"])
def scan_shipment_document_delete(request, shipment_id, document_id):
    return handle_shipment_document_delete(
        request, shipment_id=shipment_id, document_id=document_id
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_out(request):
    form = ScanOutForm(request.POST or None)
    product_options = build_product_options()
    if request.method == "POST":
        response = handle_stock_out_post(request, form=form)
        if response:
            return response
    return render(
        request,
        "scan/out.html",
        {"form": form, "active": "out", "products_json": product_options},
    )


@login_required
@require_http_methods(["GET"])
def scan_sync(request):
    state = WmsChange.get_state()
    return JsonResponse(
        {
            "version": state.version,
            "changed_at": state.last_changed_at.isoformat(),
        }
    )


@login_required
@require_http_methods(["GET"])
def scan_faq(request):
    return render(
        request,
        "scan/faq.html",
        {
            "active": "faq",
            "shell_class": "scan-shell-wide",
        },
    )


SERVICE_WORKER_JS = """const CACHE_NAME = 'wms-scan-v33';
const ASSETS = [
  '/static/scan/scan.css',
  '/static/scan/scan.js',
  '/static/scan/zxing.min.js',
  '/static/scan/manifest.json',
  '/static/scan/icon.svg'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
"""


def scan_service_worker(request):
    response = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/scan/"
    return response
