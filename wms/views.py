import csv
import io
import json
import math
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.db import connection, transaction
from django.db.models import DateTimeField, F, IntegerField, Max, OuterRef, Q, Subquery, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.conf import settings

from contacts.models import Contact, ContactAddress, ContactTag, ContactType

from .forms import (
    ScanOutForm,
    ScanPackForm,
    ScanReceiptCreateForm,
    ScanReceiptAssociationForm,
    ScanReceiptLineForm,
    ScanReceiptPalletForm,
    ScanReceiptSelectForm,
    ScanStockUpdateForm,
    ScanOrderCreateForm,
    ScanOrderLineForm,
    ScanOrderSelectForm,
    ScanShipmentForm,
    ShipmentTrackingForm,
)
from .contact_filters import (
    TAG_CORRESPONDENT,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    contacts_with_tags,
)
from .models import (
    Carton,
    CartonFormat,
    CartonStatus,
    Document,
    DocumentType,
    MovementType,
    Destination,
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RackColor,
    Receipt,
    ReceiptHorsFormat,
    ReceiptStatus,
    ReceiptType,
    Order,
    OrderReviewStatus,
    OrderStatus,
    AssociationProfile,
    AssociationRecipient,
    AccountDocument,
    AccountDocumentType,
    DocumentReviewStatus,
    OrderDocument,
    OrderDocumentType,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicOrderLink,
    PrintTemplate,
    PrintTemplateVersion,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    StockMovement,
    Warehouse,
    WmsChange,
)
from .print_context import (
    build_carton_document_context,
    build_label_context,
    build_product_label_context,
    build_preview_context,
    build_sample_label_context,
    build_shipment_document_context,
)
from .print_layouts import BLOCK_LIBRARY, DEFAULT_LAYOUTS, DOCUMENT_TEMPLATES
from .print_renderer import get_template_layout, layout_changed, render_layout_from_layout
from .print_utils import build_label_pages, extract_block_style
from .import_utils import (
    decode_text,
    extract_tabular_data,
    get_value,
    iter_import_rows,
    list_excel_sheets,
    normalize_header,
    parse_bool,
    parse_decimal,
    parse_int,
    parse_str,
)
from .import_services import (
    import_categories,
    import_contacts,
    import_locations,
    extract_product_identity,
    find_product_matches,
    import_product_row,
    import_products_rows,
    import_users,
    import_warehouses,
)
from .scan_helpers import (
    build_available_cartons,
    build_carton_formats,
    build_location_data,
    build_pack_line_values,
    build_packing_bins,
    build_packing_result,
    build_product_options,
    build_shipment_line_values,
    get_carton_volume_cm3,
    get_product_volume_cm3,
    get_product_weight_g,
    parse_int,
    resolve_default_warehouse,
    resolve_carton_size,
    resolve_product,
    resolve_shipment,
)
from .services import (
    StockError,
    consume_stock,
    create_shipment_for_order,
    pack_carton,
    prepare_order,
    receive_receipt_line,
    receive_stock,
    reserve_stock_for_order,
)
from .emailing import get_admin_emails, send_email_safe


def _compute_shipment_progress(shipment):
    cartons = shipment.carton_set.all()
    total = cartons.count()
    ready = cartons.filter(
        status__in=[CartonStatus.PACKED, CartonStatus.SHIPPED]
    ).count()
    if total == 0 or ready == 0:
        return total, ready, ShipmentStatus.DRAFT, "DRAFT"
    if ready < total:
        return total, ready, ShipmentStatus.PICKING, f"PARTIEL ({ready}/{total})"
    return total, ready, ShipmentStatus.PACKED, "READY"


def _sync_shipment_ready_state(shipment):
    if shipment.status in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED}:
        return
    total, ready, new_status, _ = _compute_shipment_progress(shipment)
    was_packed = shipment.status == ShipmentStatus.PACKED
    updates = {}
    if shipment.status != new_status:
        updates["status"] = new_status
    if new_status == ShipmentStatus.PACKED:
        if not was_packed or shipment.ready_at is None:
            updates["ready_at"] = timezone.now()
    elif shipment.ready_at is not None:
        updates["ready_at"] = None
    if updates:
        shipment.status = updates.get("status", shipment.status)
        shipment.ready_at = updates.get("ready_at", shipment.ready_at)
        shipment.save(update_fields=list(updates))


def _require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def _resolve_contact_by_name(tag, name):
    if not name:
        return None
    return contacts_with_tags(tag).filter(name__iexact=name).first()


def _sorted_choices(choices):
    return sorted(choices, key=lambda choice: str(choice[1] or "").lower())


def _build_carton_options(cartons):
    options = []
    for carton in cartons:
        weight_total = 0
        for item in carton.cartonitem_set.all():
            product_weight = item.product_lot.product.weight_g or 0
            weight_total += product_weight * item.quantity
        options.append(
            {
                "id": carton.id,
                "code": carton.code,
                "weight_g": weight_total,
            }
        )
    return options


def _build_destination_label(destination):
    if not destination:
        return ""
    return str(destination)


def _build_shipment_contact_payload():
    destinations = Destination.objects.filter(is_active=True).select_related(
        "correspondent_contact"
    )
    recipient_contacts = (
        contacts_with_tags(TAG_RECIPIENT)
        .filter(contact_type=ContactType.ORGANIZATION)
        .select_related("destination")
        .prefetch_related("addresses")
    )
    correspondent_contacts = contacts_with_tags(TAG_CORRESPONDENT).select_related(
        "destination"
    )

    destinations_json = [
        {
            "id": destination.id,
            "country": destination.country,
            "correspondent_contact_id": destination.correspondent_contact_id,
        }
        for destination in destinations
    ]
    recipient_contacts_json = []
    for contact in recipient_contacts:
        address_source = (
            contact.get_effective_addresses()
            if hasattr(contact, "get_effective_addresses")
            else contact.addresses.all()
        )
        countries = {address.country for address in address_source if address.country}
        recipient_contacts_json.append(
            {
                "id": contact.id,
                "name": contact.name,
                "countries": sorted(countries),
                "destination_id": contact.destination_id,
            }
        )
    correspondent_contacts_json = [
        {"id": contact.id, "name": contact.name, "destination_id": contact.destination_id}
        for contact in correspondent_contacts
    ]
    return destinations_json, recipient_contacts_json, correspondent_contacts_json


def _build_shipment_document_links(shipment, *, public=False):
    doc_route = (
        "scan:scan_shipment_document_public"
        if public
        else "scan:scan_shipment_document"
    )
    carton_route = (
        "scan:scan_shipment_carton_document_public"
        if public
        else "scan:scan_shipment_carton_document"
    )
    label_route = (
        "scan:scan_shipment_labels_public"
        if public
        else "scan:scan_shipment_labels"
    )
    doc_args = (
        lambda doc_type: [shipment.reference, doc_type]
        if public
        else [shipment.id, doc_type]
    )
    carton_args = (
        lambda carton_id: [shipment.reference, carton_id]
        if public
        else [shipment.id, carton_id]
    )
    documents = [
        {
            "label": "Bon d'expedition",
            "url": reverse(doc_route, args=doc_args("shipment_note")),
        },
        {
            "label": "Liste colisage (lot)",
            "url": reverse(doc_route, args=doc_args("packing_list_shipment")),
        },
        {
            "label": "Attestation donation",
            "url": reverse(doc_route, args=doc_args("donation_certificate")),
        },
        {
            "label": "Attestation aide humanitaire",
            "url": reverse(doc_route, args=doc_args("humanitarian_certificate")),
        },
        {
            "label": "Attestation douane",
            "url": reverse(doc_route, args=doc_args("customs")),
        },
        {
            "label": "Etiquettes colis",
            "url": reverse(
                label_route, args=[shipment.reference if public else shipment.id]
            ),
        },
    ]
    carton_docs = [
        {
            "label": carton.code,
            "url": reverse(carton_route, args=carton_args(carton.id)),
        }
        for carton in shipment.carton_set.all().order_by("code")
    ]
    additional_docs = Document.objects.filter(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL
    ).order_by("-generated_at")
    return documents, carton_docs, additional_docs


def _next_tracking_status(last_status):
    choices = [choice[0] for choice in ShipmentTrackingStatus.choices]
    if not choices:
        return None
    if not last_status or last_status not in choices:
        return choices[0]
    index = choices.index(last_status)
    if index + 1 < len(choices):
        return choices[index + 1]
    return last_status


def _parse_shipment_lines(*, carton_count, data, allowed_carton_ids):
    line_values = build_shipment_line_values(carton_count, data)
    line_errors = {}
    line_items = []
    for index in range(1, carton_count + 1):
        prefix = f"line_{index}_"
        carton_id = (data.get(prefix + "carton_id") or "").strip()
        product_code = (data.get(prefix + "product_code") or "").strip()
        quantity_raw = (data.get(prefix + "quantity") or "").strip()
        errors = []

        if carton_id and (product_code or quantity_raw):
            errors.append("Choisissez un carton OU creez un colis depuis un produit.")
        elif carton_id:
            if carton_id not in allowed_carton_ids:
                errors.append("Carton indisponible.")
            else:
                line_items.append({"carton_id": int(carton_id)})
        elif product_code or quantity_raw:
            if not product_code:
                errors.append("Produit requis.")
            quantity = None
            if not quantity_raw:
                errors.append("Quantite requise.")
            else:
                quantity = parse_int(quantity_raw)
                if quantity is None or quantity <= 0:
                    errors.append("Quantite invalide.")
            product = resolve_product(product_code) if product_code else None
            if product_code and not product:
                errors.append("Produit introuvable.")
            if not errors and product and quantity:
                line_items.append({"product": product, "quantity": quantity})
        else:
            errors.append("Renseignez un carton ou un produit.")

        if errors:
            line_errors[str(index)] = errors
    return line_values, line_items, line_errors


def _build_destination_address(*, line1, line2, postal_code, city, country):
    parts = [line1, line2]
    city_line = " ".join(part for part in [postal_code, city] if part)
    if city_line:
        parts.append(city_line)
    if country:
        parts.append(country)
    return "\n".join(part for part in parts if part)


def _get_contact_address(contact):
    if not contact:
        return None
    if hasattr(contact, "get_effective_address"):
        return contact.get_effective_address()
    return contact.addresses.filter(is_default=True).first() or contact.addresses.first()


def _get_default_carton_format():
    return (
        CartonFormat.objects.filter(is_default=True).first()
        or CartonFormat.objects.order_by("name").first()
    )


def _build_public_base_url(request):
    base = settings.SITE_BASE_URL
    if base:
        return base.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _send_email_safe(*, subject, message, recipient):
    return send_email_safe(subject=subject, message=message, recipient=recipient)


def _get_admin_emails():
    return get_admin_emails()


def _validate_upload(file_obj):
    suffix = Path(file_obj.name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return f"Format non autorise: {file_obj.name}"
    max_size = PORTAL_MAX_FILE_SIZE_MB * 1024 * 1024
    if file_obj.size > max_size:
        return f"Fichier trop volumineux: {file_obj.name}"
    return None


def _get_association_profile(user):
    if not user or not user.is_authenticated:
        return None
    return (
        AssociationProfile.objects.select_related("contact")
        .filter(user=user)
        .first()
    )


def _build_order_creator_info(order):
    contact = None
    if order.created_by:
        profile = _get_association_profile(order.created_by)
        if profile:
            contact = profile.contact
    if not contact:
        contact = order.association_contact or order.recipient_contact

    name = "-"
    phone = ""
    email = ""
    if contact:
        name = contact.name
        phone = contact.phone or ""
        email = contact.email or ""
        address = _get_contact_address(contact)
        if address:
            phone = phone or address.phone or ""
            email = email or address.email or ""
    if order.created_by and name == "-":
        name = (
            order.created_by.get_full_name()
            or order.created_by.username
            or order.created_by.email
            or "-"
        )
    if order.created_by and not email:
        email = order.created_by.email or ""
    return {"name": name, "phone": phone, "email": email}


def _attach_order_documents_to_shipment(order, shipment):
    if not order or not shipment:
        return
    wanted_types = {
        OrderDocumentType.DONATION_ATTESTATION,
        OrderDocumentType.HUMANITARIAN_ATTESTATION,
    }
    existing_files = set(
        Document.objects.filter(
            shipment=shipment, doc_type=DocumentType.ADDITIONAL
        ).values_list("file", flat=True)
    )
    for doc in order.documents.filter(doc_type__in=wanted_types):
        if not doc.file:
            continue
        if doc.file.name in existing_files:
            continue
        Document.objects.create(
            shipment=shipment,
            doc_type=DocumentType.ADDITIONAL,
            file=doc.file,
        )


def association_required(view):
    def wrapped(request, *args, **kwargs):
        profile = _get_association_profile(request.user)
        if not profile:
            raise PermissionDenied
        if profile.must_change_password:
            change_url = reverse("portal:portal_change_password")
            if request.path != change_url:
                return redirect(change_url)
        request.association_profile = profile
        return view(request, *args, **kwargs)

    return wrapped


def _estimate_cartons_for_line(*, product, quantity, carton_format):
    if not carton_format:
        return None
    weight_g = get_product_weight_g(product)
    volume = get_product_volume_cm3(product)
    carton_volume = get_carton_volume_cm3(
        {
            "length_cm": carton_format.length_cm,
            "width_cm": carton_format.width_cm,
            "height_cm": carton_format.height_cm,
        }
    )
    max_by_volume = None
    if volume and volume > 0 and carton_volume and carton_volume > 0:
        max_by_volume = int(carton_volume // volume)
        max_by_volume = max(1, max_by_volume)
    max_by_weight = None
    if weight_g and weight_g > 0 and carton_format.max_weight_g:
        max_by_weight = int(carton_format.max_weight_g // weight_g)
        max_by_weight = max(1, max_by_weight)
    if max_by_volume and max_by_weight:
        max_units = min(max_by_volume, max_by_weight)
    else:
        max_units = max_by_volume or max_by_weight
    if not max_units:
        return None
    return int(math.ceil(quantity / max_units))


@require_http_methods(["GET", "POST"])
def portal_login(request):
    if request.user.is_authenticated:
        profile = _get_association_profile(request.user)
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
            elif not _get_association_profile(user):
                errors.append("Compte non active par ASF.")
            else:
                login(request, user)
                profile = _get_association_profile(user)
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
        profile = _get_association_profile(user)
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

    product_options = build_product_options()
    product_ids = [item["id"] for item in product_options if item.get("id")]
    products = Product.objects.filter(id__in=product_ids, is_active=True)
    product_by_id = {product.id: product for product in products}
    available_by_id = {
        item["id"]: int(item.get("available_stock") or 0) for item in product_options
    }

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

        for item in product_options:
            product_id = item.get("id")
            if not product_id:
                continue
            raw_qty = (request.POST.get(f"product_{product_id}_qty") or "").strip()
            if raw_qty:
                line_quantities[str(product_id)] = raw_qty
            if not raw_qty:
                continue
            quantity = parse_int(raw_qty)
            if quantity is None or quantity <= 0:
                line_errors[str(product_id)] = "Quantite invalide."
                continue
            available = available_by_id.get(product_id, 0)
            if quantity > available:
                line_errors[str(product_id)] = "Stock insuffisant."
                continue
            product = product_by_id.get(product_id)
            if product:
                line_items.append((product, quantity))

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
            address = _get_contact_address(profile.contact)
            if not address:
                errors.append("Adresse association manquante.")
            else:
                destination_address = _build_destination_address(
                    line1=address.address_line1,
                    line2=address.address_line2,
                    postal_code=address.postal_code,
                    city=address.city,
                    country=address.country,
                )
                destination_city = address.city or ""
                destination_country = address.country or "France"
        else:
            recipient_id = parse_int(form_data["recipient_id"])
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
                destination_address = _build_destination_address(
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
                with transaction.atomic():
                    order = Order.objects.create(
                        reference="",
                        status=OrderStatus.DRAFT,
                        association_contact=profile.contact,
                        shipper_name="Aviation Sans Frontieres",
                        recipient_name=recipient_name,
                        recipient_contact=recipient_contact,
                        destination_address=destination_address,
                        destination_city=destination_city,
                        destination_country=destination_country or "France",
                        created_by=request.user,
                        notes=form_data["notes"],
                    )
                    for product, quantity in line_items:
                        order.lines.create(product=product, quantity=quantity)
                    create_shipment_for_order(order=order)
                    reserve_stock_for_order(order=order)
            except StockError as exc:
                errors.append(str(exc))
            else:
                base_url = _build_public_base_url(request)
                summary_url = f"{base_url}{reverse('portal:portal_order_detail', args=[order.id])}"
                admin_message = render_to_string(
                    "emails/order_admin_notification.txt",
                    {
                        "association_name": profile.contact.name,
                        "email": profile.contact.email or request.user.email,
                        "phone": profile.contact.phone,
                        "order_reference": order.reference or f"Commande {order.id}",
                        "summary_url": summary_url,
                        "admin_url": f"{base_url}{reverse('admin:wms_order_changelist')}",
                    },
                )
                _send_email_safe(
                    subject="ASF WMS - Nouvelle commande",
                    message=admin_message,
                    recipient=_get_admin_emails(),
                )
                confirmation_message = render_to_string(
                    "emails/order_confirmation.txt",
                    {
                        "association_name": profile.contact.name,
                        "order_reference": order.reference or f"Commande {order.id}",
                        "summary_url": summary_url,
                    },
                )
                recipients = [profile.contact.email or request.user.email]
                recipients += profile.get_notification_emails()
                _send_email_safe(
                    subject="ASF WMS - Commande recue",
                    message=confirmation_message,
                    recipient=recipients,
                )
                messages.success(request, "Commande envoyee.")
                return redirect("portal:portal_order_detail", order_id=order.id)

    carton_format = _get_default_carton_format()
    carton_data = (
        {
            "length_cm": float(carton_format.length_cm),
            "width_cm": float(carton_format.width_cm),
            "height_cm": float(carton_format.height_cm),
            "max_weight_g": float(carton_format.max_weight_g),
            "name": carton_format.name,
        }
        if carton_format
        else None
    )
    total_estimated_cartons = 0
    product_rows = []
    for item in product_options:
        product_id = item.get("id")
        if not product_id:
            continue
        quantity_raw = line_quantities.get(str(product_id), "")
        quantity_value = parse_int(quantity_raw) if quantity_raw else None
        estimate = None
        product = product_by_id.get(product_id)
        if product and quantity_value and quantity_value > 0:
            estimate = _estimate_cartons_for_line(
                product=product,
                quantity=quantity_value,
                carton_format=carton_format,
            )
            if estimate:
                total_estimated_cartons += estimate
        product_rows.append(
            {
                "id": product_id,
                "name": item.get("name"),
                "available_stock": int(item.get("available_stock") or 0),
                "quantity": quantity_raw,
                "estimate": estimate,
            }
        )
    if total_estimated_cartons <= 0:
        total_estimated_cartons = None

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
        doc_type = (request.POST.get("doc_type") or "").strip()
        uploaded = request.FILES.get("doc_file")
        valid_types = {choice[0] for choice in OrderDocumentType.choices}
        if doc_type not in valid_types:
            messages.error(request, "Type de document invalide.")
            return redirect("portal:portal_order_detail", order_id=order.id)
        if not uploaded:
            messages.error(request, "Fichier requis.")
            return redirect("portal:portal_order_detail", order_id=order.id)
        validation_error = _validate_upload(uploaded)
        if validation_error:
            messages.error(request, validation_error)
            return redirect("portal:portal_order_detail", order_id=order.id)
        OrderDocument.objects.create(
            order=order,
            doc_type=doc_type,
            status=DocumentReviewStatus.PENDING,
            file=uploaded,
            uploaded_by=request.user,
        )
        messages.success(request, "Document ajoute.")
        return redirect("portal:portal_order_detail", order_id=order.id)

    carton_format = _get_default_carton_format()
    line_rows = []
    total_estimated_cartons = 0
    for line in order.lines.select_related("product"):
        estimate = _estimate_cartons_for_line(
            product=line.product,
            quantity=line.quantity,
            carton_format=carton_format,
        )
        if estimate:
            total_estimated_cartons += estimate
        line_rows.append(
            {
                "product": line.product.name,
                "quantity": line.quantity,
                "estimate": estimate,
            }
        )
    if total_estimated_cartons <= 0:
        total_estimated_cartons = None

    return render(
        request,
        "portal/order_detail.html",
        {
            "order": order,
            "line_rows": line_rows,
            "total_estimated_cartons": total_estimated_cartons,
            "order_documents": order.documents.all(),
            "order_doc_types": _sorted_choices(OrderDocumentType.choices),
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
    address = _get_contact_address(association)

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
            doc_type = (request.POST.get("doc_type") or "").strip()
            uploaded = request.FILES.get("doc_file")
            valid_types = {choice[0] for choice in AccountDocumentType.choices}
            if doc_type not in valid_types:
                messages.error(request, "Type de document invalide.")
                return redirect("portal:portal_account")
            if not uploaded:
                messages.error(request, "Fichier requis.")
                return redirect("portal:portal_account")
            validation_error = _validate_upload(uploaded)
            if validation_error:
                messages.error(request, validation_error)
                return redirect("portal:portal_account")
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
            "account_doc_types": _sorted_choices(AccountDocumentType.choices),
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

    carton_format = _get_default_carton_format()
    line_rows = []
    total_cartons = 0
    for line in order.lines.all():
        estimate = _estimate_cartons_for_line(
            product=line.product,
            quantity=line.quantity,
            carton_format=carton_format,
        )
        if estimate:
            total_cartons += estimate
        line_rows.append(
            {
                "product": line.product.name,
                "quantity": line.quantity,
                "cartons_estimated": estimate,
            }
        )

    return render(
        request,
        "print/order_summary.html",
        {
            "order": order,
            "line_rows": line_rows,
            "total_cartons": total_cartons or None,
            "carton_format": carton_format,
        },
    )


def _handle_account_request_form(request, *, link=None, redirect_url=""):
    contacts = list(
        contacts_with_tags(TAG_SHIPPER).prefetch_related("addresses").order_by("name")
    )
    contact_payload = []
    for contact in contacts:
        address = _get_contact_address(contact)
        contact_payload.append(
            {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email or "",
                "phone": contact.phone or "",
                "address_line1": address.address_line1 if address else "",
                "address_line2": address.address_line2 if address else "",
                "postal_code": address.postal_code if address else "",
                "city": address.city if address else "",
                "country": address.country if address else "",
            }
        )

    form_data = {
        "association_name": "",
        "email": "",
        "phone": "",
        "line1": "",
        "line2": "",
        "postal_code": "",
        "city": "",
        "country": "France",
        "notes": "",
        "contact_id": "",
    }
    errors = []

    if request.method == "POST":
        form_data.update(
            {
                "association_name": (request.POST.get("association_name") or "").strip(),
                "email": (request.POST.get("email") or "").strip(),
                "phone": (request.POST.get("phone") or "").strip(),
                "line1": (request.POST.get("line1") or "").strip(),
                "line2": (request.POST.get("line2") or "").strip(),
                "postal_code": (request.POST.get("postal_code") or "").strip(),
                "city": (request.POST.get("city") or "").strip(),
                "country": (request.POST.get("country") or "France").strip(),
                "notes": (request.POST.get("notes") or "").strip(),
                "contact_id": (request.POST.get("contact_id") or "").strip(),
            }
        )
        if not form_data["association_name"]:
            errors.append("Nom de l'association requis.")
        if not form_data["email"]:
            errors.append("Email requis.")
        if not form_data["line1"]:
            errors.append("Adresse requise.")

        uploads = []
        doc_files = [
            (AccountDocumentType.STATUTES, request.FILES.get("doc_statutes")),
            (
                AccountDocumentType.REGISTRATION_PROOF,
                request.FILES.get("doc_registration"),
            ),
            (AccountDocumentType.ACTIVITY_REPORT, request.FILES.get("doc_report")),
        ]
        for doc_type, file_obj in doc_files:
            if not file_obj:
                continue
            validation_error = _validate_upload(file_obj)
            if validation_error:
                errors.append(validation_error)
            else:
                uploads.append((doc_type, file_obj))
        for file_obj in request.FILES.getlist("doc_other"):
            if not file_obj:
                continue
            validation_error = _validate_upload(file_obj)
            if validation_error:
                errors.append(validation_error)
            else:
                uploads.append((AccountDocumentType.OTHER, file_obj))

        existing = PublicAccountRequest.objects.filter(
            email__iexact=form_data["email"],
            status=PublicAccountRequestStatus.PENDING,
        ).first()
        if existing:
            errors.append("Une demande est deja en attente pour cet email.")

        if not errors:
            contact = None
            contact_id = parse_int(form_data["contact_id"])
            if contact_id:
                contact = Contact.objects.filter(id=contact_id, is_active=True).first()
            if not contact:
                contact = Contact.objects.filter(
                    name__iexact=form_data["association_name"], is_active=True
                ).first()
            account_request = PublicAccountRequest.objects.create(
                link=link,
                contact=contact,
                association_name=form_data["association_name"],
                email=form_data["email"],
                phone=form_data["phone"],
                address_line1=form_data["line1"],
                address_line2=form_data["line2"],
                postal_code=form_data["postal_code"],
                city=form_data["city"],
                country=form_data["country"] or "France",
                notes=form_data["notes"],
            )
            for doc_type, file_obj in uploads:
                AccountDocument.objects.create(
                    association_contact=contact,
                    account_request=account_request,
                    doc_type=doc_type,
                    status=DocumentReviewStatus.PENDING,
                    file=file_obj,
                )
            base_url = _build_public_base_url(request)
            admin_message = render_to_string(
                "emails/account_request_admin_notification.txt",
                {
                    "association_name": form_data["association_name"],
                    "email": form_data["email"],
                    "phone": form_data["phone"],
                    "admin_url": f"{base_url}{reverse('admin:wms_publicaccountrequest_changelist')}",
                },
            )
            _send_email_safe(
                subject="ASF WMS - Nouvelle demande de compte",
                message=admin_message,
                recipient=_get_admin_emails(),
            )
            message = render_to_string(
                "emails/account_request_received.txt",
                {"association_name": form_data["association_name"]},
            )
            _send_email_safe(
                subject="ASF WMS - Demande de compte recue",
                message=message,
                recipient=form_data["email"],
            )
            messages.success(
                request,
                "Demande envoyee. Un superuser ASF validera votre compte.",
            )
            return redirect(redirect_url)

    return render(
        request,
        "scan/public_account_request.html",
        {
            "link": link,
            "contacts": contact_payload,
            "form_data": form_data,
            "errors": errors,
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

    return _handle_account_request_form(
        request,
        link=link,
        redirect_url=reverse("scan:scan_public_account_request", args=[token]),
    )


@require_http_methods(["GET", "POST"])
def portal_account_request(request):
    return _handle_account_request_form(
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

    product_options = build_product_options()
    product_ids = [item["id"] for item in product_options if item.get("id")]
    products = Product.objects.filter(id__in=product_ids, is_active=True)
    product_by_id = {product.id: product for product in products}
    available_by_id = {
        item["id"]: int(item.get("available_stock") or 0) for item in product_options
    }

    contacts = list(
        contacts_with_tags(TAG_SHIPPER).prefetch_related("addresses").order_by("name")
    )
    contact_payload = []
    for contact in contacts:
        address = (
            contact.get_effective_address()
            if hasattr(contact, "get_effective_address")
            else contact.addresses.filter(is_default=True).first()
            or contact.addresses.first()
        )
        contact_payload.append(
            {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email or "",
                "phone": contact.phone or "",
                "address_line1": address.address_line1 if address else "",
                "address_line2": address.address_line2 if address else "",
                "postal_code": address.postal_code if address else "",
                "city": address.city if address else "",
                "country": address.country if address else "",
            }
        )

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

        line_items = []
        for item in product_options:
            product_id = item.get("id")
            if not product_id:
                continue
            raw_qty = (request.POST.get(f"product_{product_id}_qty") or "").strip()
            if raw_qty:
                line_quantities[str(product_id)] = raw_qty
            if not raw_qty:
                continue
            quantity = parse_int(raw_qty)
            if quantity is None or quantity <= 0:
                line_errors[str(product_id)] = "Quantite invalide."
                continue
            available = available_by_id.get(product_id, 0)
            if quantity > available:
                line_errors[str(product_id)] = "Stock insuffisant."
                continue
            product = product_by_id.get(product_id)
            if product:
                line_items.append((product, quantity))

        if not line_items:
            errors.append("Ajoutez au moins un produit.")

        if not errors and not line_errors:
            contact = None
            contact_id = parse_int(form_data["association_contact_id"])
            if contact_id:
                contact = Contact.objects.filter(id=contact_id, is_active=True).first()
            if not contact:
                contact = Contact.objects.filter(
                    name__iexact=form_data["association_name"], is_active=True
                ).first()

            try:
                with transaction.atomic():
                    if not contact:
                        contact = Contact.objects.create(
                            name=form_data["association_name"],
                            email=form_data["association_email"],
                            phone=form_data["association_phone"],
                            is_active=True,
                        )
                        tag, _ = ContactTag.objects.get_or_create(name=TAG_SHIPPER[0])
                        contact.tags.add(tag)
                        ContactAddress.objects.create(
                            contact=contact,
                            address_line1=form_data["association_line1"],
                            address_line2=form_data["association_line2"],
                            postal_code=form_data["association_postal_code"],
                            city=form_data["association_city"],
                            country=form_data["association_country"] or "France",
                            phone=form_data["association_phone"],
                            email=form_data["association_email"],
                            is_default=True,
                        )
                    else:
                        updated_fields = []
                        if form_data["association_email"] and contact.email != form_data[
                            "association_email"
                        ]:
                            contact.email = form_data["association_email"]
                            updated_fields.append("email")
                        if form_data["association_phone"] and contact.phone != form_data[
                            "association_phone"
                        ]:
                            contact.phone = form_data["association_phone"]
                            updated_fields.append("phone")
                        if updated_fields:
                            contact.save(update_fields=updated_fields)

                        address = (
                            contact.addresses.filter(is_default=True).first()
                            or contact.addresses.first()
                        )
                        if address:
                            address.address_line1 = form_data["association_line1"]
                            address.address_line2 = form_data["association_line2"]
                            address.postal_code = form_data["association_postal_code"]
                            address.city = form_data["association_city"]
                            address.country = form_data["association_country"] or "France"
                            address.phone = form_data["association_phone"]
                            address.email = form_data["association_email"]
                            address.save(
                                update_fields=[
                                    "address_line1",
                                    "address_line2",
                                    "postal_code",
                                    "city",
                                    "country",
                                    "phone",
                                    "email",
                                ]
                            )
                        else:
                            ContactAddress.objects.create(
                                contact=contact,
                                address_line1=form_data["association_line1"],
                                address_line2=form_data["association_line2"],
                                postal_code=form_data["association_postal_code"],
                                city=form_data["association_city"],
                                country=form_data["association_country"] or "France",
                                phone=form_data["association_phone"],
                                email=form_data["association_email"],
                                is_default=True,
                            )

                    destination_address = _build_destination_address(
                        line1=form_data["association_line1"],
                        line2=form_data["association_line2"],
                        postal_code=form_data["association_postal_code"],
                        city=form_data["association_city"],
                        country=form_data["association_country"],
                    )

                    order = Order.objects.create(
                        reference="",
                        status=OrderStatus.DRAFT,
                        public_link=link,
                        shipper_name="Aviation Sans Frontieres",
                        recipient_name=form_data["association_name"],
                        recipient_contact=contact,
                        destination_address=destination_address,
                        destination_city=form_data["association_city"] or "",
                        destination_country=form_data["association_country"] or "France",
                        requested_delivery_date=None,
                        created_by=None,
                        notes=form_data["association_notes"] or "",
                    )
                    for product, quantity in line_items:
                        order.lines.create(product=product, quantity=quantity)
                    create_shipment_for_order(order=order)
                    reserve_stock_for_order(order=order)
            except StockError as exc:
                errors.append(str(exc))
            else:
                summary_url = reverse("scan:scan_public_order_summary", args=[token, order.id])
                base_url = _build_public_base_url(request)
                summary_abs = f"{base_url}{summary_url}"
                email_message = render_to_string(
                    "emails/order_confirmation.txt",
                    {
                        "association_name": form_data["association_name"],
                        "order_reference": order.reference or f"Commande {order.id}",
                        "summary_url": summary_abs,
                    },
                )
                admin_message = render_to_string(
                    "emails/order_admin_notification.txt",
                    {
                        "association_name": form_data["association_name"],
                        "email": form_data["association_email"] or contact.email,
                        "phone": form_data["association_phone"] or contact.phone,
                        "order_reference": order.reference or f"Commande {order.id}",
                        "summary_url": summary_abs,
                        "admin_url": f"{base_url}{reverse('admin:wms_order_change', args=[order.id])}",
                    },
                )
                _send_email_safe(
                    subject="ASF WMS - Nouvelle commande publique",
                    message=admin_message,
                    recipient=_get_admin_emails(),
                )
                if not _send_email_safe(
                    subject="ASF WMS - Confirmation de commande",
                    message=email_message,
                    recipient=form_data["association_email"] or contact.email,
                ):
                    messages.warning(
                        request,
                        "Commande envoyee, mais l'email de confirmation n'a pas pu etre envoye.",
                    )
                messages.success(
                    request,
                    "Commande envoyee. L'equipe ASF va la traiter rapidement.",
                )
                return redirect(
                    f"{reverse('scan:scan_public_order', args=[token])}?order={order.id}"
                )

    carton_format = _get_default_carton_format()
    carton_data = (
        {
            "length_cm": float(carton_format.length_cm),
            "width_cm": float(carton_format.width_cm),
            "height_cm": float(carton_format.height_cm),
            "max_weight_g": float(carton_format.max_weight_g),
            "name": carton_format.name,
        }
        if carton_format
        else None
    )

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


ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".xlsx",
    ".xls",
    ".doc",
    ".docx",
}
PORTAL_MAX_FILE_SIZE_MB = 10


@login_required
def scan_stock(request):
    query = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    warehouse_id = (request.GET.get("warehouse") or "").strip()
    sort = (request.GET.get("sort") or "name").strip()

    products = Product.objects.filter(is_active=True).select_related("category")
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)

    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    stock_lots = ProductLot.objects.filter(
        product_id=OuterRef("pk"),
        quantity_on_hand__gt=0,
    )
    if warehouse_id:
        stock_lots = stock_lots.filter(location__warehouse_id=warehouse_id)
    stock_total_subquery = (
        stock_lots.values("product_id")
        .annotate(total=Sum(available_expr))
        .values("total")
    )

    movements = StockMovement.objects.filter(product_id=OuterRef("pk"))
    if warehouse_id:
        movements = movements.filter(
            Q(to_location__warehouse_id=warehouse_id)
            | Q(from_location__warehouse_id=warehouse_id)
        )
    last_movement_subquery = (
        movements.values("product_id")
        .annotate(last=Max("created_at"))
        .values("last")
    )

    products = products.annotate(
        stock_total=Coalesce(Subquery(stock_total_subquery, output_field=IntegerField()), 0),
        last_movement_at=Subquery(last_movement_subquery, output_field=DateTimeField()),
    ).filter(stock_total__gt=0)

    sort_map = {
        "name": "name",
        "sku": "sku",
        "qty_desc": "-stock_total",
        "qty_asc": "stock_total",
        "category": "category__name",
    }
    products = products.order_by(sort_map.get(sort, "name"), "name")

    categories = ProductCategory.objects.all().order_by("name")
    warehouses = Warehouse.objects.all().order_by("name")

    return render(
        request,
        "scan/stock.html",
        {
            "active": "stock",
            "products": products,
            "categories": categories,
            "warehouses": warehouses,
            "query": query,
            "category_id": category_id,
            "warehouse_id": warehouse_id,
            "sort": sort,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_cartons_ready(request):
    if request.method == "POST" and request.POST.get("action") == "update_carton_status":
        carton_id = request.POST.get("carton_id")
        status_value = (request.POST.get("status") or "").strip()
        carton = Carton.objects.filter(pk=carton_id).select_related("shipment").first()
        allowed = {
            CartonStatus.DRAFT,
            CartonStatus.PICKING,
            CartonStatus.PACKED,
        }
        if (
            carton
            and carton.status != CartonStatus.SHIPPED
            and status_value in allowed
            and carton.shipment_id is None
        ):
            if carton.status != status_value:
                carton.status = status_value
                carton.save(update_fields=["status"])
        return redirect("scan:scan_cartons_ready")

    default_format = CartonFormat.objects.filter(is_default=True).first()
    if default_format is None:
        default_format = CartonFormat.objects.first()
    carton_capacity_cm3 = None
    if default_format:
        carton_capacity_cm3 = (
            default_format.length_cm * default_format.width_cm * default_format.height_cm
        )

    cartons_qs = (
        Carton.objects.filter(cartonitem__isnull=False)
        .select_related("shipment", "current_location")
        .prefetch_related("cartonitem_set__product_lot__product")
        .distinct()
        .order_by("-created_at")
    )
    cartons = []
    for carton in cartons_qs:
        product_totals = {}
        weight_total_g = 0
        volume_total_cm3 = 0
        missing_weight = False
        missing_volume = False
        for item in carton.cartonitem_set.all():
            name = item.product_lot.product.name
            product_totals[name] = product_totals.get(name, 0) + item.quantity
            product = item.product_lot.product
            if product.weight_g:
                weight_total_g += product.weight_g * item.quantity
            else:
                missing_weight = True
            if product.volume_cm3:
                volume_total_cm3 += product.volume_cm3 * item.quantity
            else:
                missing_volume = True
        packing_list = [
            {"name": name, "quantity": qty}
            for name, qty in sorted(product_totals.items(), key=lambda row: row[0])
        ]
        if weight_total_g == 0 and missing_weight:
            weight_kg = None
        else:
            weight_kg = weight_total_g / 1000 if weight_total_g else None
        if carton_capacity_cm3 and volume_total_cm3 and not missing_volume:
            volume_percent = round(
                float(volume_total_cm3) / float(carton_capacity_cm3) * 100
            )
        else:
            volume_percent = None
        is_assigned = carton.shipment_id is not None
        if is_assigned and carton.status != CartonStatus.SHIPPED:
            status_label = "Affecte"
        else:
            try:
                status_label = CartonStatus(carton.status).label
            except ValueError:
                status_label = carton.status
        if carton.shipment_id:
            packing_list_url = reverse(
                "scan:scan_shipment_carton_document",
                args=[carton.shipment_id, carton.id],
            )
        else:
            packing_list_url = reverse("scan:scan_carton_document", args=[carton.id])
        cartons.append(
            {
                "id": carton.id,
                "code": carton.code,
                "created_at": carton.created_at,
                "status_label": status_label,
                "status_value": carton.status,
                "can_toggle": (not is_assigned) and carton.status != CartonStatus.SHIPPED,
                "shipment_reference": carton.shipment.reference if carton.shipment else "",
                "location": carton.current_location,
                "packing_list": packing_list,
                "packing_list_url": packing_list_url,
                "weight_kg": weight_kg,
                "volume_percent": volume_percent,
            }
        )

    return render(
        request,
        "scan/cartons_ready.html",
        {
            "active": "cartons_ready",
            "cartons": cartons,
            "carton_status_choices": _sorted_choices(
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
        .prefetch_related("carton_set")
        .order_by("-created_at")
    )
    shipments = []
    for shipment in shipments_qs:
        total, ready, computed_status, status_label = _compute_shipment_progress(
            shipment
        )
        if shipment.status in {ShipmentStatus.DRAFT, ShipmentStatus.PICKING, ShipmentStatus.PACKED}:
            if shipment.status != computed_status or (
                computed_status == ShipmentStatus.PACKED and shipment.ready_at is None
            ):
                _sync_shipment_ready_state(shipment)
        shipments.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "carton_count": total,
                "destination_iata": shipment.destination.iata_code
                if shipment.destination
                else "",
                "shipper_name": shipment.shipper_name,
                "recipient_name": shipment.recipient_name,
                "created_at": shipment.created_at,
                "ready_at": shipment.ready_at,
                "status_label": status_label,
                "can_edit": shipment.status
                not in {ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED},
            }
        )

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

    receipts = []
    for receipt in receipts_qs:
        name = receipt.source_contact.name if receipt.source_contact else "-"
        quantity = "-"
        if receipt.pallet_count:
            quantity = f"{receipt.pallet_count} palettes"
        elif receipt.carton_count:
            quantity = f"{receipt.carton_count} colis"

        hors_format_count = receipt.hors_format_count
        hors_format_desc = "; ".join(
            item.description.strip()
            for item in receipt.hors_format_items.all()
            if item.description
        )
        if hors_format_count and hors_format_desc:
            hors_format = f"{hors_format_count} : {hors_format_desc}"
        elif hors_format_count:
            hors_format = str(hors_format_count)
        elif hors_format_desc:
            hors_format = hors_format_desc
        else:
            hors_format = "-"

        carrier = receipt.carrier_contact.name if receipt.carrier_contact else "-"

        receipts.append(
            {
                "received_on": receipt.received_on,
                "name": name,
                "quantity": quantity,
                "hors_format": hors_format,
                "carrier": carrier,
            }
        )

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
    if request.method == "POST" and create_form.is_valid():
        product = getattr(create_form, "product", None)
        location = product.default_location if product else None
        if location is None:
            create_form.add_error(None, "Emplacement requis pour ce produit.")
        else:
            try:
                source_receipt = None
                donor_contact = create_form.cleaned_data.get("donor_contact")
                if donor_contact:
                    source_receipt = Receipt.objects.create(
                        receipt_type=ReceiptType.DONATION,
                        status=ReceiptStatus.RECEIVED,
                        source_contact=donor_contact,
                        received_on=timezone.localdate(),
                        warehouse=location.warehouse,
                        created_by=request.user,
                        notes="Auto MAJ stock",
                    )
                receive_stock(
                    user=request.user,
                    product=product,
                    quantity=create_form.cleaned_data["quantity"],
                    location=location,
                    lot_code=create_form.cleaned_data["lot_code"] or "",
                    received_on=timezone.localdate(),
                    expires_on=create_form.cleaned_data["expires_on"],
                    source_receipt=source_receipt,
                )
                messages.success(request, "Stock mis a jour.")
                return redirect("scan:scan_stock_update")
            except StockError as exc:
                create_form.add_error(None, str(exc))
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
    receipts_qs = Receipt.objects.select_related("warehouse").order_by(
        "reference", "id"
    )[:50]
    select_form = ScanReceiptSelectForm(
        request.POST if action == "select_receipt" else None, receipts_qs=receipts_qs
    )
    create_form = ScanReceiptCreateForm(
        request.POST if action == "create_receipt" else None
    )

    receipt_id = request.GET.get("receipt") or request.POST.get("receipt_id")
    selected_receipt = None
    if receipt_id:
        selected_receipt = Receipt.objects.filter(id=receipt_id).first()

    line_form = ScanReceiptLineForm(
        request.POST if action == "add_line" else None,
        initial={"receipt_id": selected_receipt.id} if selected_receipt else None,
    )
    receipt_lines = []
    pending_count = 0
    if selected_receipt:
        receipt_lines = list(
            selected_receipt.lines.select_related("product", "location", "received_lot").all()
        )
        pending_count = sum(1 for line in receipt_lines if not line.received_lot_id)

    if request.method == "POST":
        if action == "select_receipt" and select_form.is_valid():
            receipt = select_form.cleaned_data["receipt"]
            return redirect(f"{reverse('scan:scan_receive')}?receipt={receipt.id}")
        if action == "create_receipt" and create_form.is_valid():
            receipt = Receipt.objects.create(
                reference="",
                receipt_type=create_form.cleaned_data["receipt_type"],
                status=ReceiptStatus.DRAFT,
                source_contact=create_form.cleaned_data["source_contact"],
                carrier_contact=create_form.cleaned_data["carrier_contact"],
                origin_reference=create_form.cleaned_data["origin_reference"],
                carrier_reference=create_form.cleaned_data["carrier_reference"],
                received_on=create_form.cleaned_data["received_on"],
                warehouse=create_form.cleaned_data["warehouse"],
                created_by=request.user,
                notes=create_form.cleaned_data["notes"] or "",
            )
            messages.success(
                request,
                f"Reception creee: {receipt.reference or f'Reception {receipt.id}'}",
            )
            return redirect(f"{reverse('scan:scan_receive')}?receipt={receipt.id}")
        if action == "add_line":
            if not selected_receipt:
                line_form.add_error(None, "Selectionnez une reception.")
            elif selected_receipt.status != ReceiptStatus.DRAFT:
                line_form.add_error(None, "Reception deja cloturee.")
            elif line_form.is_valid():
                product = resolve_product(line_form.cleaned_data["product_code"])
                if not product:
                    line_form.add_error("product_code", "Produit introuvable.")
                else:
                    location = (
                        line_form.cleaned_data["location"] or product.default_location
                    )
                    if location is None:
                        line_form.add_error(
                            "location",
                            "Emplacement requis ou definir un emplacement par defaut.",
                        )
                    else:
                        line = selected_receipt.lines.create(
                            product=product,
                            quantity=line_form.cleaned_data["quantity"],
                            lot_code=line_form.cleaned_data["lot_code"] or "",
                            expires_on=line_form.cleaned_data["expires_on"],
                            lot_status=line_form.cleaned_data["lot_status"] or "",
                            location=location,
                            storage_conditions=(
                                line_form.cleaned_data["storage_conditions"]
                                or product.storage_conditions
                            ),
                        )
                        if line_form.cleaned_data["receive_now"]:
                            try:
                                receive_receipt_line(user=request.user, line=line)
                                messages.success(
                                    request,
                                    f"Ligne receptionnee: {product.name} ({line.quantity}).",
                                )
                            except StockError as exc:
                                line_form.add_error(None, str(exc))
                                receipt_lines = list(
                                    selected_receipt.lines.select_related(
                                        "product", "location", "received_lot"
                                    ).all()
                                )
                                pending_count = sum(
                                    1 for line in receipt_lines if not line.received_lot_id
                                )
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
                        else:
                            messages.success(
                                request,
                                f"Ligne ajoutee: {product.name} ({line.quantity}).",
                            )
                        return redirect(
                            f"{reverse('scan:scan_receive')}?receipt={selected_receipt.id}"
                        )
        if action == "receive_lines" and selected_receipt:
            processed = 0
            errors = []
            for line in selected_receipt.lines.select_related("product"):
                if line.received_lot_id:
                    continue
                try:
                    receive_receipt_line(user=request.user, line=line)
                    processed += 1
                except StockError as exc:
                    errors.append(str(exc))
            if processed:
                messages.success(
                    request, f"{processed} ligne(s) receptionnee(s)."
                )
            for error in errors:
                messages.error(request, error)
            return redirect(f"{reverse('scan:scan_receive')}?receipt={selected_receipt.id}")
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


PALLET_LISTING_MAPPING_FIELDS = [
    ("name", "Nom produit"),
    ("brand", "Marque"),
    ("color", "Couleur"),
    ("category_l1", "Categorie L1"),
    ("category_l2", "Categorie L2"),
    ("category_l3", "Categorie L3"),
    ("category_l4", "Categorie L4"),
    ("barcode", "Barcode"),
    ("ean", "EAN"),
    ("pu_ht", "PU HT"),
    ("tva", "TVA"),
    ("tags", "Tags"),
    ("warehouse", "Entrepot"),
    ("zone", "Rack"),
    ("aisle", "Etagere"),
    ("shelf", "Bac"),
    ("rack_color", "Couleur rack"),
    ("notes", "Notes"),
    ("length_cm", "Longueur cm"),
    ("width_cm", "Largeur cm"),
    ("height_cm", "Hauteur cm"),
    ("weight_g", "Poids g"),
    ("volume_cm3", "Volume cm3"),
    ("storage_conditions", "Conditions stockage"),
    ("perishable", "Perissable"),
    ("quarantine_default", "Quarantaine par defaut"),
    ("quantity", "Quantite"),
]

PALLET_LISTING_REQUIRED_FIELDS = {"name", "quantity"}

PALLET_LISTING_HEADER_MAP = {
    "nom": "name",
    "nom_produit": "name",
    "produit": "name",
    "designation": "name",
    "marque": "brand",
    "brand": "brand",
    "couleur": "color",
    "categorie_l1": "category_l1",
    "categorie_1": "category_l1",
    "category_l1": "category_l1",
    "category_1": "category_l1",
    "categorie_l2": "category_l2",
    "categorie_2": "category_l2",
    "category_l2": "category_l2",
    "category_2": "category_l2",
    "categorie_l3": "category_l3",
    "categorie_3": "category_l3",
    "category_l3": "category_l3",
    "category_3": "category_l3",
    "categorie_l4": "category_l4",
    "categorie_4": "category_l4",
    "category_l4": "category_l4",
    "category_4": "category_l4",
    "code_barre": "barcode",
    "barcode": "barcode",
    "ean": "ean",
    "code_ean": "ean",
    "tags": "tags",
    "etiquettes": "tags",
    "entrepot": "warehouse",
    "warehouse": "warehouse",
    "zone": "zone",
    "rack": "zone",
    "etagere": "aisle",
    "aisle": "aisle",
    "bac": "shelf",
    "shelf": "shelf",
    "couleur_rack": "rack_color",
    "rack_color": "rack_color",
    "notes": "notes",
    "longueur_cm": "length_cm",
    "length_cm": "length_cm",
    "largeur_cm": "width_cm",
    "width_cm": "width_cm",
    "hauteur_cm": "height_cm",
    "height_cm": "height_cm",
    "poids_g": "weight_g",
    "weight_g": "weight_g",
    "volume_cm3": "volume_cm3",
    "conditions_stockage": "storage_conditions",
    "storage_conditions": "storage_conditions",
    "perissable": "perishable",
    "perishable": "perishable",
    "quarantaine_defaut": "quarantine_default",
    "quarantine_default": "quarantine_default",
    "quantite": "quantity",
    "qty": "quantity",
    "stock": "quantity",
    "pu_ht": "pu_ht",
    "puht": "pu_ht",
    "price_ht": "pu_ht",
    "unit_price_ht": "pu_ht",
    "tva": "tva",
    "vat": "tva",
}

PALLET_REVIEW_FIELDS = [
    ("name", "Nom"),
    ("brand", "Marque"),
    ("color", "Couleur"),
    ("category_l1", "Cat L1"),
    ("category_l2", "Cat L2"),
    ("category_l3", "Cat L3"),
    ("category_l4", "Cat L4"),
    ("barcode", "Barcode"),
    ("ean", "EAN"),
    ("tags", "Tags"),
    ("pu_ht", "PU HT"),
    ("tva", "TVA"),
    ("length_cm", "L cm"),
    ("width_cm", "l cm"),
    ("height_cm", "h cm"),
    ("weight_g", "Poids g"),
    ("volume_cm3", "Volume"),
    ("storage_conditions", "Stockage"),
    ("perishable", "Perissable"),
    ("quarantine_default", "Quarantaine"),
    ("notes", "Notes"),
]

PALLET_LOCATION_FIELDS = [
    ("warehouse", "Entrepot"),
    ("zone", "Rack"),
    ("aisle", "Etagere"),
    ("shelf", "Bac"),
]


def _listing_row_empty(row):
    return all(not str(value or "").strip() for value in row)


def _build_listing_mapping_defaults(headers):
    mapping = {}
    for idx, header in enumerate(headers):
        normalized = normalize_header(header)
        mapped = PALLET_LISTING_HEADER_MAP.get(normalized)
        if mapped:
            mapping[idx] = mapped
    return mapping


def _apply_listing_mapping(rows, mapping):
    mapped_rows = []
    for row in rows:
        if _listing_row_empty(row):
            continue
        mapped = {}
        for idx, field in mapping.items():
            if idx < len(row):
                mapped[field] = row[idx]
        mapped_rows.append(mapped)
    return mapped_rows


def _clean_listing_value(value):
    return parse_str(value) or ""


def _build_product_display(product):
    category_levels = _category_levels(product.category)
    tags = " | ".join(product.tags.values_list("name", flat=True))
    location = product.default_location
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "color": product.color,
        "category_l1": category_levels[0],
        "category_l2": category_levels[1],
        "category_l3": category_levels[2],
        "category_l4": category_levels[3],
        "barcode": product.barcode,
        "ean": product.ean,
        "tags": tags,
        "pu_ht": product.pu_ht or "",
        "tva": product.tva or "",
        "length_cm": product.length_cm or "",
        "width_cm": product.width_cm or "",
        "height_cm": product.height_cm or "",
        "weight_g": product.weight_g or "",
        "volume_cm3": product.volume_cm3 or "",
        "storage_conditions": product.storage_conditions or "",
        "perishable": "Oui" if product.perishable else "Non",
        "quarantine_default": "Oui" if product.quarantine_default else "Non",
        "notes": product.notes or "",
        "warehouse": location.warehouse.name if location else "",
        "zone": location.zone if location else "",
        "aisle": location.aisle if location else "",
        "shelf": location.shelf if location else "",
    }


def _resolve_listing_location(row, default_warehouse):
    warehouse_name = parse_str(row.get("warehouse")) or (
        default_warehouse.name if default_warehouse else None
    )
    zone = parse_str(row.get("zone"))
    aisle = parse_str(row.get("aisle"))
    shelf = parse_str(row.get("shelf"))
    if any([zone, aisle, shelf]):
        if not all([warehouse_name, zone, aisle, shelf]):
            raise ValueError("Emplacement incomplet (entrepot/rack/etagere/bac).")
        warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
        location, _ = Location.objects.get_or_create(
            warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
        )
        return location
    return None


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    action = request.POST.get("action", "")
    create_form = ScanReceiptPalletForm(
        request.POST
        if request.method == "POST" and action in ("", "pallet_create")
        else None
    )
    listing_form = ScanReceiptPalletForm(
        request.POST if action == "listing_upload" else None,
        prefix="listing",
    )
    listing_stage = None
    listing_columns = []
    listing_rows = []
    listing_errors = []
    pending = request.session.get("pallet_listing_pending")
    listing_sheet_names = []
    listing_sheet_name = ""
    listing_header_row = 1
    listing_pdf_pages_mode = "all"
    listing_pdf_page_start = ""
    listing_pdf_page_end = ""

    def _build_listing_extract_options(extension, sheet_name, header_row, pdf_mode, page_start, page_end):
        options = {}
        if extension in {".xlsx", ".xls"}:
            if sheet_name:
                options["sheet_name"] = sheet_name
            options["header_row"] = header_row or 1
        if extension == ".pdf" and pdf_mode == "custom":
            options["pdf_pages"] = (page_start, page_end)
        return options

    def _pending_extract_options(pending_data):
        pdf_pages = pending_data.get("pdf_pages") or {}
        return _build_listing_extract_options(
            pending_data.get("extension", ""),
            pending_data.get("sheet_name", ""),
            pending_data.get("header_row") or 1,
            pdf_pages.get("mode") or "all",
            pdf_pages.get("start"),
            pdf_pages.get("end"),
        )

    def clear_pending():
        pending_data = request.session.pop("pallet_listing_pending", None)
        if pending_data and pending_data.get("file_path"):
            try:
                Path(pending_data["file_path"]).unlink(missing_ok=True)
            except OSError:
                pass

    def build_review_rows(headers, rows, mapping):
        mapped_rows = _apply_listing_mapping(rows, mapping)
        match_labels = {"name_brand": "Nom + Marque"}
        review = []
        for row_index, row in enumerate(mapped_rows, start=2):
            values = {field: _clean_listing_value(row.get(field)) for field, _ in PALLET_REVIEW_FIELDS}
            for key, _ in PALLET_LOCATION_FIELDS:
                values[key] = _clean_listing_value(row.get(key))
            values["quantity"] = _clean_listing_value(row.get("quantity"))
            values["rack_color"] = _clean_listing_value(row.get("rack_color"))

            _, name, brand = extract_product_identity(row)
            matches, match_type = find_product_matches(sku=None, name=name, brand=brand)
            match_options = []
            for product in matches:
                label = f"{product.sku} - {product.name}"
                if product.brand:
                    label = f"{label} ({product.brand})"
                match_options.append(
                    {
                        "id": product.id,
                        "value": f"product:{product.id}",
                        "label": label,
                        "data": _build_product_display(product),
                    }
                )
            existing = match_options[0]["data"] if match_options else None
            default_match = f"product:{match_options[0]['id']}" if match_options else "new"

            if existing:
                for key, _ in PALLET_LOCATION_FIELDS:
                    if not values.get(key):
                        values[key] = existing.get(key, "")

            fields = []
            for field, label in PALLET_REVIEW_FIELDS:
                fields.append(
                    {
                        "name": field,
                        "label": label,
                        "value": values.get(field, ""),
                        "existing": existing.get(field, "") if existing else "",
                    }
                )
            locations = []
            for key, label in PALLET_LOCATION_FIELDS:
                locations.append(
                    {
                        "name": key,
                        "label": label,
                        "value": values.get(key, ""),
                        "existing": existing.get(key, "") if existing else "",
                    }
                )

            review.append(
                {
                    "index": row_index,
                    "values": values,
                    "fields": fields,
                    "locations": locations,
                    "existing": existing,
                    "match_type": match_labels.get(match_type, "-"),
                    "match_options": match_options,
                    "default_match": default_match,
                }
            )
        return review

    if action == "listing_cancel":
        clear_pending()
        return redirect("scan:scan_receive_pallet")

    if action == "listing_upload":
        listing_pdf_pages_mode = (
            request.POST.get("listing_pdf_pages_mode") or "all"
        ).strip()
        listing_pdf_page_start = (request.POST.get("listing_pdf_page_start") or "").strip()
        listing_pdf_page_end = (request.POST.get("listing_pdf_page_end") or "").strip()
        listing_sheet_name = (request.POST.get("listing_sheet_name") or "").strip()
        header_row_raw = (request.POST.get("listing_header_row") or "").strip()
        pdf_page_start = None
        pdf_page_end = None
        header_row_error = None

        if header_row_raw:
            try:
                listing_header_row = parse_int(header_row_raw)
            except ValueError:
                header_row_error = "Ligne des titres invalide."
        if not listing_form.is_valid():
            listing_errors.append("Renseignez les informations de reception.")
        uploaded = request.FILES.get("listing_file")
        if not uploaded:
            listing_errors.append("Fichier requis pour importer le listing.")
        else:
            extension = Path(uploaded.name).suffix.lower()
            if extension not in {".csv", ".xlsx", ".xls", ".pdf"}:
                listing_errors.append("Format de fichier non supporte.")
            else:
                data = uploaded.read()
                sheet_names = []
                if extension in {".xlsx", ".xls"} and not listing_errors:
                    if header_row_error:
                        listing_errors.append(header_row_error)
                    if listing_header_row < 1:
                        listing_errors.append("Ligne des titres invalide (>= 1).")
                        listing_header_row = 1
                    try:
                        sheet_names = list_excel_sheets(data, extension)
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                    if sheet_names:
                        listing_sheet_names = sheet_names
                        if listing_sheet_name:
                            if listing_sheet_name not in sheet_names:
                                listing_errors.append(
                                    f"Feuille inconnue: {listing_sheet_name}."
                                )
                        else:
                            listing_sheet_name = sheet_names[0]
                if extension == ".pdf" and listing_pdf_pages_mode == "custom" and not listing_errors:
                    if not listing_pdf_page_start or not listing_pdf_page_end:
                        listing_errors.append("Renseignez les pages PDF debut et fin.")
                    else:
                        try:
                            pdf_page_start = parse_int(listing_pdf_page_start)
                            pdf_page_end = parse_int(listing_pdf_page_end)
                        except ValueError:
                            listing_errors.append("Pages PDF invalides.")
                    if pdf_page_start is not None and pdf_page_end is not None:
                        if pdf_page_start < 1 or pdf_page_end < pdf_page_start:
                            listing_errors.append("Plage de pages PDF invalide.")
                    if listing_errors:
                        pdf_page_start = None
                        pdf_page_end = None
                if not listing_errors:
                    extract_options = _build_listing_extract_options(
                        extension,
                        listing_sheet_name,
                        listing_header_row,
                        listing_pdf_pages_mode,
                        pdf_page_start,
                        pdf_page_end,
                    )
                    try:
                        headers, rows = extract_tabular_data(
                            data,
                            extension,
                            **extract_options,
                        )
                        if not rows:
                            listing_errors.append("Fichier vide ou sans lignes exploitables.")
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                if not listing_errors:
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix=extension
                    )
                    temp_file.write(data)
                    temp_file.close()
                    mapping_defaults = _build_listing_mapping_defaults(headers)
                    pending = {
                        "token": uuid.uuid4().hex,
                        "file_path": temp_file.name,
                        "extension": extension,
                        "headers": headers,
                        "mapping": mapping_defaults,
                        "sheet_names": sheet_names,
                        "sheet_name": listing_sheet_name,
                        "header_row": listing_header_row,
                        "pdf_pages": {
                            "mode": listing_pdf_pages_mode,
                            "start": pdf_page_start,
                            "end": pdf_page_end,
                        },
                        "receipt_meta": {
                            "received_on": listing_form.cleaned_data["received_on"].isoformat(),
                            "pallet_count": listing_form.cleaned_data["pallet_count"],
                            "source_contact_id": listing_form.cleaned_data["source_contact"].id,
                            "carrier_contact_id": listing_form.cleaned_data["carrier_contact"].id,
                            "transport_request_date": (
                                listing_form.cleaned_data["transport_request_date"].isoformat()
                                if listing_form.cleaned_data["transport_request_date"]
                                else ""
                            ),
                        },
                    }
                    request.session["pallet_listing_pending"] = pending
                    listing_stage = "mapping"
                    for idx, header in enumerate(headers):
                        sample = ""
                        for row in rows:
                            if idx < len(row) and str(row[idx] or "").strip():
                                sample = row[idx]
                                break
                        listing_columns.append(
                            {
                                "index": idx,
                                "name": header,
                                "sample": sample,
                                "mapped": mapping_defaults.get(idx, ""),
                            }
                        )

    if action == "listing_map":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_pallet")
        headers = pending.get("headers") or []
        mapping = {}
        used_fields = {}
        for idx, _header in enumerate(headers):
            field = (request.POST.get(f"map_{idx}") or "").strip()
            if not field:
                continue
            if field in used_fields:
                listing_errors.append(
                    f"Champ {field} assigne deux fois ({used_fields[field]})."
                )
                continue
            mapping[idx] = field
            used_fields[field] = idx + 1
        missing_fields = PALLET_LISTING_REQUIRED_FIELDS - set(mapping.values())
        if missing_fields:
            listing_errors.append(
                "Champs requis manquants: " + ", ".join(sorted(missing_fields))
            )
        if listing_errors:
            listing_stage = "mapping"
            data = Path(pending["file_path"]).read_bytes()
            headers, rows = extract_tabular_data(
                data,
                pending["extension"],
                **_pending_extract_options(pending),
            )
            for idx, header in enumerate(headers):
                sample = ""
                for row in rows:
                    if idx < len(row) and str(row[idx] or "").strip():
                        sample = row[idx]
                        break
                listing_columns.append(
                    {
                        "index": idx,
                        "name": header,
                        "sample": sample,
                        "mapped": mapping.get(idx, ""),
                    }
                )
        else:
            pending["mapping"] = mapping
            request.session["pallet_listing_pending"] = pending
            data = Path(pending["file_path"]).read_bytes()
            headers, rows = extract_tabular_data(
                data,
                pending["extension"],
                **_pending_extract_options(pending),
            )
            listing_rows = build_review_rows(headers, rows, mapping)
            listing_stage = "review"

    if action == "listing_confirm":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_pallet")
        data = Path(pending["file_path"]).read_bytes()
        headers, rows = extract_tabular_data(
            data,
            pending["extension"],
            **_pending_extract_options(pending),
        )
        mapping = pending.get("mapping") or {}
        mapped_rows = _apply_listing_mapping(rows, mapping)
        receipt_meta = pending.get("receipt_meta") or {}

        warehouse = resolve_default_warehouse()
        if not warehouse:
            messages.error(request, "Aucun entrepot configure.")
            return redirect("scan:scan_receive_pallet")

        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            status=ReceiptStatus.DRAFT,
            source_contact=Contact.objects.filter(
                id=receipt_meta.get("source_contact_id")
            ).first(),
            carrier_contact=Contact.objects.filter(
                id=receipt_meta.get("carrier_contact_id")
            ).first(),
            received_on=receipt_meta.get("received_on") or timezone.localdate(),
            pallet_count=receipt_meta.get("pallet_count") or 0,
            transport_request_date=receipt_meta.get("transport_request_date") or None,
            warehouse=warehouse,
            created_by=request.user,
        )

        created = 0
        skipped = 0
        errors = []
        for row_index, row in enumerate(mapped_rows, start=2):
            if not request.POST.get(f"row_{row_index}_apply"):
                skipped += 1
                continue
            override_code = (request.POST.get(f"row_{row_index}_match_override") or "").strip()
            product = None
            if override_code:
                product = resolve_product(override_code)
                if not product:
                    errors.append(
                        f"Ligne {row_index}: produit introuvable pour {override_code}."
                    )
                    continue
            selection = (request.POST.get(f"row_{row_index}_match") or "").strip()
            if not product and selection.startswith("product:"):
                product_id = selection.split("product:", 1)[1]
                if product_id.isdigit():
                    product = Product.objects.filter(id=int(product_id)).first()
                if not product:
                    errors.append(f"Ligne {row_index}: produit cible introuvable.")
                    continue

            row_data = {}
            for field, _ in PALLET_REVIEW_FIELDS:
                row_data[field] = request.POST.get(
                    f"row_{row_index}_{field}"
                ) or row.get(field)
            for key, _ in PALLET_LOCATION_FIELDS:
                row_data[key] = request.POST.get(
                    f"row_{row_index}_{key}"
                ) or row.get(key)
            row_data["quantity"] = request.POST.get(
                f"row_{row_index}_quantity"
            ) or row.get("quantity")
            row_data["rack_color"] = request.POST.get(
                f"row_{row_index}_rack_color"
            ) or row.get("rack_color")

            quantity = parse_int(row_data.get("quantity"))
            if not quantity or quantity <= 0:
                errors.append(f"Ligne {row_index}: quantite invalide.")
                continue

            if product is None and selection == "new":
                new_row = dict(row_data)
                new_row.pop("quantity", None)
                try:
                    product, _created, _warnings = import_product_row(
                        new_row,
                        user=request.user,
                    )
                except ValueError as exc:
                    errors.append(f"Ligne {row_index}: {exc}")
                    continue

            if product is None:
                errors.append(f"Ligne {row_index}: produit non determine.")
                continue

            try:
                location = _resolve_listing_location(row_data, warehouse)
                if location is None:
                    location = product.default_location
                if location is None:
                    raise ValueError("Emplacement requis pour reception.")
                line = ReceiptLine.objects.create(
                    receipt=receipt,
                    product=product,
                    quantity=quantity,
                    location=location,
                    storage_conditions=product.storage_conditions or "",
                )
                receive_receipt_line(user=request.user, line=line)
                created += 1
            except (ValueError, StockError) as exc:
                errors.append(f"Ligne {row_index}: {exc}")

        if errors:
            messages.error(request, f"Import termine avec {len(errors)} erreur(s).")
            for error in errors[:10]:
                messages.error(request, error)
        if created:
            messages.success(
                request,
                f"{created} ligne(s) receptionnee(s) (ref {receipt.reference}).",
            )
        if skipped:
            messages.warning(request, f"{skipped} ligne(s) ignoree(s).")
        clear_pending()
        return redirect("scan:scan_receive_pallet")

    if (
        request.method == "POST"
        and action in ("", "pallet_create")
        and create_form.is_valid()
    ):
        warehouse = resolve_default_warehouse()
        if not warehouse:
            create_form.add_error(None, "Aucun entrepot configure.")
        else:
            receipt = Receipt.objects.create(
                receipt_type=ReceiptType.PALLET,
                status=ReceiptStatus.DRAFT,
                source_contact=create_form.cleaned_data["source_contact"],
                carrier_contact=create_form.cleaned_data["carrier_contact"],
                received_on=create_form.cleaned_data["received_on"],
                pallet_count=create_form.cleaned_data["pallet_count"],
                transport_request_date=create_form.cleaned_data[
                    "transport_request_date"
                ],
                warehouse=warehouse,
                created_by=request.user,
            )
            messages.success(
                request,
                f"Reception palette enregistree (ref {receipt.reference}).",
            )
            return redirect("scan:scan_receive_pallet")

    listing_meta = None
    if pending:
        receipt_meta = pending.get("receipt_meta") or {}
        pdf_pages = pending.get("pdf_pages") or {}
        extension = pending.get("extension")
        sheet_names = pending.get("sheet_names") or []
        sheet_names_display = ", ".join(sheet_names) if sheet_names else ""
        sheet_name_value = pending.get("sheet_name") if extension in {".xlsx", ".xls"} else ""
        header_row_value = pending.get("header_row") if extension in {".xlsx", ".xls"} else ""
        pdf_pages_label = ""
        if extension == ".pdf":
            if pdf_pages.get("mode") == "custom" and pdf_pages.get("start") and pdf_pages.get("end"):
                pdf_pages_label = f"{pdf_pages['start']} - {pdf_pages['end']}"
            else:
                pdf_pages_label = "Toutes les pages"
        source_contact = Contact.objects.filter(
            id=receipt_meta.get("source_contact_id")
        ).first()
        carrier_contact = Contact.objects.filter(
            id=receipt_meta.get("carrier_contact_id")
        ).first()
        listing_meta = {
            "received_on": receipt_meta.get("received_on"),
            "pallet_count": receipt_meta.get("pallet_count"),
            "source_contact": source_contact.name if source_contact else "",
            "carrier_contact": carrier_contact.name if carrier_contact else "",
            "transport_request_date": receipt_meta.get("transport_request_date") or "",
            "sheet_name": sheet_name_value or "",
            "header_row": header_row_value or "",
            "sheet_names": sheet_names_display if extension in {".xlsx", ".xls"} else "",
            "pdf_pages": pdf_pages_label,
        }

        if extension in {".xlsx", ".xls"} and sheet_names and not listing_sheet_names:
            listing_sheet_names = sheet_names
        if sheet_name_value:
            listing_sheet_name = sheet_name_value
        if header_row_value:
            listing_header_row = header_row_value
        if pdf_pages.get("mode"):
            listing_pdf_pages_mode = pdf_pages.get("mode")
        if pdf_pages.get("start") is not None:
            listing_pdf_page_start = str(pdf_pages.get("start"))
        if pdf_pages.get("end") is not None:
            listing_pdf_page_end = str(pdf_pages.get("end"))

    return render(
        request,
        "scan/receive_pallet.html",
        {
            "active": "receive_pallet",
            "create_form": create_form,
            "listing_form": listing_form,
            "listing_stage": listing_stage,
            "listing_columns": listing_columns,
            "listing_rows": listing_rows,
            "listing_errors": listing_errors,
            "listing_token": pending.get("token") if pending else "",
            "listing_meta": listing_meta,
            "mapping_fields": PALLET_LISTING_MAPPING_FIELDS,
            "review_fields": PALLET_REVIEW_FIELDS,
            "location_fields": PALLET_LOCATION_FIELDS,
            "listing_sheet_names": listing_sheet_names,
            "listing_sheet_name": listing_sheet_name,
            "listing_header_row": listing_header_row,
            "listing_pdf_pages_mode": listing_pdf_pages_mode,
            "listing_pdf_page_start": listing_pdf_page_start,
            "listing_pdf_page_end": listing_pdf_page_end,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_association(request):
    line_errors = {}
    line_count = parse_int(request.POST.get("hors_format_count")) or 0
    line_count = max(0, line_count)
    line_values = []
    for index in range(1, line_count + 1):
        description = (request.POST.get(f"line_{index}_description") or "").strip()
        line_values.append({"description": description})

    create_form = ScanReceiptAssociationForm(request.POST or None)
    if request.method == "POST" and create_form.is_valid():
        for index, line in enumerate(line_values, start=1):
            if not line["description"]:
                line_errors[str(index)] = ["Description requise."]

        if line_errors:
            create_form.add_error(None, "Renseignez les descriptions hors format.")
        else:
            warehouse = resolve_default_warehouse()
            if not warehouse:
                create_form.add_error(None, "Aucun entrepot configure.")
            else:
                receipt = Receipt.objects.create(
                    receipt_type=ReceiptType.ASSOCIATION,
                    status=ReceiptStatus.DRAFT,
                    source_contact=create_form.cleaned_data["source_contact"],
                    carrier_contact=create_form.cleaned_data["carrier_contact"],
                    received_on=create_form.cleaned_data["received_on"],
                    carton_count=create_form.cleaned_data["carton_count"],
                    hors_format_count=line_count or None,
                    warehouse=warehouse,
                    created_by=request.user,
                )
                for index, line in enumerate(line_values, start=1):
                    if line["description"]:
                        ReceiptHorsFormat.objects.create(
                            receipt=receipt,
                            line_number=index,
                            description=line["description"],
                        )
                messages.success(
                    request,
                    f"Reception association enregistree (ref {receipt.reference}).",
                )
                return redirect("scan:scan_receive_association")

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
    orders_qs = Order.objects.select_related("shipment").order_by("reference", "id")[:50]
    select_form = ScanOrderSelectForm(
        request.POST if action == "select_order" else None, orders_qs=orders_qs
    )
    create_form = ScanOrderCreateForm(
        request.POST if action == "create_order" else None
    )

    order_id = request.GET.get("order") or request.POST.get("order_id")
    selected_order = None
    if order_id:
        selected_order = Order.objects.select_related("shipment").filter(id=order_id).first()

    line_form = ScanOrderLineForm(
        request.POST if action == "add_line" else None,
        initial={"order_id": selected_order.id} if selected_order else None,
    )
    order_lines = []
    remaining_total = 0
    if selected_order:
        order_lines = list(selected_order.lines.select_related("product"))
        remaining_total = sum(line.remaining_quantity for line in order_lines)

    if request.method == "POST":
        if action == "select_order" and select_form.is_valid():
            order = select_form.cleaned_data["order"]
            return redirect(f"{reverse('scan:scan_order')}?order={order.id}")
        if action == "create_order" and create_form.is_valid():
            shipper_contact = create_form.cleaned_data["shipper_contact"]
            recipient_contact = create_form.cleaned_data["recipient_contact"]
            correspondent_contact = create_form.cleaned_data["correspondent_contact"]
            order = Order.objects.create(
                reference="",
                status=OrderStatus.DRAFT,
                shipper_name=create_form.cleaned_data["shipper_name"]
                or (shipper_contact.name if shipper_contact else ""),
                recipient_name=create_form.cleaned_data["recipient_name"]
                or (recipient_contact.name if recipient_contact else ""),
                correspondent_name=create_form.cleaned_data["correspondent_name"]
                or (correspondent_contact.name if correspondent_contact else ""),
                shipper_contact=shipper_contact,
                recipient_contact=recipient_contact,
                correspondent_contact=correspondent_contact,
                destination_address=create_form.cleaned_data["destination_address"],
                destination_city=create_form.cleaned_data["destination_city"] or "",
                destination_country=create_form.cleaned_data["destination_country"] or "France",
                requested_delivery_date=create_form.cleaned_data["requested_delivery_date"],
                created_by=request.user,
                notes=create_form.cleaned_data["notes"] or "",
            )
            create_shipment_for_order(order=order)
            messages.success(
                request,
                f"Commande creee: {order.reference or f'Commande {order.id}'}",
            )
            return redirect(f"{reverse('scan:scan_order')}?order={order.id}")
        if action == "add_line":
            if not selected_order:
                line_form.add_error(None, "Selectionnez une commande.")
            elif selected_order.status in {OrderStatus.CANCELLED, OrderStatus.READY}:
                line_form.add_error(None, "Commande annulee.")
            elif selected_order.status == OrderStatus.PREPARING:
                line_form.add_error(None, "Commande en preparation.")
            elif line_form.is_valid():
                product = resolve_product(line_form.cleaned_data["product_code"])
                if not product:
                    line_form.add_error("product_code", "Produit introuvable.")
                else:
                    line, created = selected_order.lines.get_or_create(
                        product=product, defaults={"quantity": 0}
                    )
                    previous_qty = line.quantity
                    line.quantity += line_form.cleaned_data["quantity"]
                    line.save(update_fields=["quantity"])
                    try:
                        reserve_stock_for_order(order=selected_order)
                        messages.success(
                            request,
                            f"Ligne reservee: {product.name} ({line_form.cleaned_data['quantity']}).",
                        )
                    except StockError as exc:
                        line.quantity = previous_qty
                        if line.quantity <= 0:
                            line.delete()
                        else:
                            line.save(update_fields=["quantity"])
                        line_form.add_error(None, str(exc))
                        order_lines = list(
                            selected_order.lines.select_related("product")
                        )
                        remaining_total = sum(
                            line.remaining_quantity for line in order_lines
                        )
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
                    return redirect(f"{reverse('scan:scan_order')}?order={selected_order.id}")
        if action == "prepare_order" and selected_order:
            try:
                prepare_order(user=request.user, order=selected_order)
                messages.success(request, "Commande preparee.")
            except StockError as exc:
                messages.error(request, str(exc))
            return redirect(f"{reverse('scan:scan_order')}?order={selected_order.id}")

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
        action = (request.POST.get("action") or "").strip()
        order_id = parse_int(request.POST.get("order_id"))
        order = orders_qs.filter(id=order_id).first() if order_id else None
        if not order:
            messages.error(request, "Commande introuvable.")
            return redirect("scan:scan_orders_view")

        if action == "update_status":
            status = (request.POST.get("review_status") or "").strip()
            valid = {choice[0] for choice in OrderReviewStatus.choices}
            if status not in valid:
                messages.error(request, "Statut invalide.")
            else:
                order.review_status = status
                order.save(update_fields=["review_status"])
                messages.success(request, "Statut de validation mis a jour.")
            return redirect("scan:scan_orders_view")

        if action == "create_shipment":
            if order.review_status != OrderReviewStatus.APPROVED:
                messages.error(request, "Commande non validee.")
                return redirect("scan:scan_orders_view")
            shipment = order.shipment or create_shipment_for_order(order=order)
            _attach_order_documents_to_shipment(order, shipment)
            return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    wanted_docs = {
        OrderDocumentType.DONATION_ATTESTATION,
        OrderDocumentType.HUMANITARIAN_ATTESTATION,
    }
    rows = []
    for order in orders_qs:
        association_contact = order.association_contact or order.recipient_contact
        association_name = (
            association_contact.name
            if association_contact
            else order.recipient_name
            or "-"
        )
        creator = _build_order_creator_info(order)
        docs = [
            {"label": doc.get_doc_type_display(), "url": doc.file.url}
            for doc in order.documents.all()
            if doc.doc_type in wanted_docs and doc.file
        ]
        rows.append(
            {
                "order": order,
                "association_name": association_name,
                "creator": creator,
                "documents": docs,
            }
        )

    return render(
        request,
        "scan/orders_view.html",
        {
            "active": "orders_view",
            "orders": rows,
            "review_status_choices": _sorted_choices(OrderReviewStatus.choices),
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
    carton_errors = []
    line_errors = {}
    line_items = []
    packing_result = None

    packed_carton_ids = request.session.pop("pack_results", None)
    if packed_carton_ids:
        packing_result = build_packing_result(packed_carton_ids)

    if request.method == "POST":
        carton_format_id = (request.POST.get("carton_format_id") or "").strip()
        carton_custom = {
            "length_cm": request.POST.get("carton_length_cm", ""),
            "width_cm": request.POST.get("carton_width_cm", ""),
            "height_cm": request.POST.get("carton_height_cm", ""),
            "max_weight_g": request.POST.get("carton_max_weight_g", ""),
        }
        line_count = parse_int(request.POST.get("line_count")) or 1
        line_count = max(1, line_count)
        line_values = build_pack_line_values(line_count, request.POST)
        carton_size, carton_errors = resolve_carton_size(
            carton_format_id=carton_format_id, default_format=default_format, data=request.POST
        )
        if not carton_format_id:
            carton_format_id = (
                str(default_format.id) if default_format is not None else "custom"
            )

        if form.is_valid():
            shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
            if form.cleaned_data["shipment_reference"] and not shipment:
                form.add_error("shipment_reference", "Expedition introuvable.")
            if carton_errors:
                for error in carton_errors:
                    form.add_error(None, error)

            for index in range(1, line_count + 1):
                prefix = f"line_{index}_"
                product_code = (request.POST.get(prefix + "product_code") or "").strip()
                quantity_raw = (request.POST.get(prefix + "quantity") or "").strip()
                if not product_code and not quantity_raw:
                    continue
                errors = []
                if not product_code:
                    errors.append("Produit requis.")
                quantity = None
                if not quantity_raw:
                    errors.append("Quantite requise.")
                else:
                    quantity = parse_int(quantity_raw)
                    if quantity is None or quantity <= 0:
                        errors.append("Quantite invalide.")
                product = (
                    resolve_product(product_code, include_kits=True) if product_code else None
                )
                if product_code and not product:
                    errors.append("Produit introuvable.")
                if errors:
                    line_errors[str(index)] = errors
                else:
                    line_items.append({"product": product, "quantity": quantity, "index": index})

            if form.is_valid() and not line_errors and not carton_errors:
                if not line_items:
                    form.add_error(None, "Ajoutez au moins un produit.")
                else:
                    bins, pack_errors, pack_warnings = build_packing_bins(
                        line_items, carton_size
                    )
                    if pack_errors:
                        for error in pack_errors:
                            form.add_error(None, error)
                    else:
                        try:
                            created_cartons = []
                            with transaction.atomic():
                                for bin_data in bins:
                                    carton = None
                                    for entry in bin_data["items"].values():
                                        carton = pack_carton(
                                            user=request.user,
                                            product=entry["product"],
                                            quantity=entry["quantity"],
                                            carton=carton,
                                            carton_code=None,
                                            shipment=shipment,
                                            current_location=form.cleaned_data[
                                                "current_location"
                                            ],
                                            carton_size=carton_size,
                                        )
                                    if carton:
                                        created_cartons.append(carton)
                            for warning in pack_warnings:
                                messages.warning(request, warning)
                            request.session["pack_results"] = [
                                carton.id for carton in created_cartons
                            ]
                            messages.success(
                                request,
                                f"{len(created_cartons)} carton(s) prepare(s).",
                            )
                            return redirect("scan:scan_pack")
                        except StockError as exc:
                            form.add_error(None, str(exc))
    else:
        carton_format_id = (
            str(default_format.id) if default_format is not None else "custom"
        )
        carton_custom = {
            "length_cm": default_format.length_cm if default_format else Decimal("40"),
            "width_cm": default_format.width_cm if default_format else Decimal("30"),
            "height_cm": default_format.height_cm if default_format else Decimal("30"),
            "max_weight_g": default_format.max_weight_g if default_format else 8000,
        }
        line_count = 1
        line_values = build_pack_line_values(line_count)
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
    product_options = build_product_options()
    available_cartons = build_available_cartons()
    available_carton_ids = {str(carton["id"]) for carton in available_cartons}
    line_errors = {}
    line_items = []

    if request.method == "POST":
        carton_count = form.cleaned_data["carton_count"] if form.is_valid() else 1
        if not form.is_valid():
            try:
                carton_count = max(1, int(request.POST.get("carton_count", 1)))
            except (TypeError, ValueError):
                carton_count = 1
        line_values, line_items, line_errors = _parse_shipment_lines(
            carton_count=carton_count,
            data=request.POST,
            allowed_carton_ids=available_carton_ids,
        )

        if form.is_valid() and not line_errors:
            try:
                with transaction.atomic():
                    destination = form.cleaned_data["destination"]
                    shipper_contact = form.cleaned_data["shipper_contact"]
                    recipient_contact = form.cleaned_data["recipient_contact"]
                    correspondent_contact = form.cleaned_data["correspondent_contact"]
                    destination_label = _build_destination_label(destination)
                    shipment = Shipment.objects.create(
                        status=ShipmentStatus.DRAFT,
                        shipper_name=shipper_contact.name,
                        recipient_name=recipient_contact.name,
                        correspondent_name=correspondent_contact.name,
                        destination=destination,
                        destination_address=destination_label,
                        destination_country=destination.country,
                        created_by=request.user,
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
                            carton.save(update_fields=["shipment"])
                        else:
                            pack_carton(
                                user=request.user,
                                product=item["product"],
                                quantity=item["quantity"],
                                carton=None,
                                carton_code=None,
                                shipment=shipment,
                            )
                _sync_shipment_ready_state(shipment)
                messages.success(
                    request,
                    f"Expedition creee: {shipment.reference}.",
                )
                return redirect("scan:scan_shipment_create")
            except StockError as exc:
                form.add_error(None, str(exc))
    else:
        carton_count = form.initial.get("carton_count", 1)
        line_values = build_shipment_line_values(carton_count)

    destinations_json, recipient_contacts_json, correspondent_contacts_json = (
        _build_shipment_contact_payload()
    )

    return render(
        request,
        "scan/shipment_create.html",
        {
            "form": form,
            "active": "shipment",
            "products_json": product_options,
            "cartons_json": available_cartons,
            "carton_count": carton_count,
            "line_values": line_values,
            "line_errors": line_errors,
            "destinations_json": destinations_json,
            "recipient_contacts_json": recipient_contacts_json,
            "correspondent_contacts_json": correspondent_contacts_json,
        },
    )


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
    assigned_carton_options = _build_carton_options(assigned_cartons)

    shipper_contact = _resolve_contact_by_name(TAG_SHIPPER, shipment.shipper_name)
    recipient_contact = _resolve_contact_by_name(TAG_RECIPIENT, shipment.recipient_name)
    correspondent_contact = None
    if shipment.destination and shipment.destination.correspondent_contact_id:
        correspondent_contact = shipment.destination.correspondent_contact
    else:
        correspondent_contact = _resolve_contact_by_name(
            TAG_CORRESPONDENT, shipment.correspondent_name
        )

    destination_id = request.POST.get("destination") or shipment.destination_id
    initial = {
        "destination": shipment.destination_id,
        "shipper_contact": shipper_contact.id if shipper_contact else None,
        "recipient_contact": recipient_contact.id if recipient_contact else None,
        "correspondent_contact": correspondent_contact.id
        if correspondent_contact
        else None,
        "carton_count": max(1, len(assigned_cartons)),
    }
    form = ScanShipmentForm(
        request.POST or None, destination_id=destination_id, initial=initial
    )
    product_options = build_product_options()
    available_cartons = build_available_cartons()
    cartons_by_id = {str(carton["id"]): carton for carton in available_cartons}
    for carton in assigned_carton_options:
        cartons_by_id.setdefault(str(carton["id"]), carton)
    cartons_json = list(cartons_by_id.values())
    allowed_carton_ids = set(cartons_by_id.keys())
    line_errors = {}
    line_items = []

    if request.method == "POST":
        carton_count = form.cleaned_data["carton_count"] if form.is_valid() else 1
        if not form.is_valid():
            try:
                carton_count = max(1, int(request.POST.get("carton_count", 1)))
            except (TypeError, ValueError):
                carton_count = 1
        line_values, line_items, line_errors = _parse_shipment_lines(
            carton_count=carton_count,
            data=request.POST,
            allowed_carton_ids=allowed_carton_ids,
        )

        if form.is_valid() and not line_errors:
            try:
                with transaction.atomic():
                    destination = form.cleaned_data["destination"]
                    shipper_contact = form.cleaned_data["shipper_contact"]
                    recipient_contact = form.cleaned_data["recipient_contact"]
                    correspondent_contact = form.cleaned_data["correspondent_contact"]
                    destination_label = _build_destination_label(destination)

                    shipment.destination = destination
                    shipment.shipper_name = shipper_contact.name
                    shipment.recipient_name = recipient_contact.name
                    shipment.correspondent_name = correspondent_contact.name
                    shipment.destination_address = destination_label
                    shipment.destination_country = destination.country
                    shipment.save(
                        update_fields=[
                            "destination",
                            "shipper_name",
                            "recipient_name",
                            "correspondent_name",
                            "destination_address",
                            "destination_country",
                        ]
                    )

                    selected_carton_ids = {
                        item["carton_id"]
                        for item in line_items
                        if "carton_id" in item
                    }
                    cartons_to_remove = shipment.carton_set.exclude(
                        id__in=selected_carton_ids
                    )
                    for carton in cartons_to_remove:
                        if carton.status == CartonStatus.SHIPPED:
                            raise StockError("Impossible de retirer un carton expedie.")
                        carton.shipment = None
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
                        if carton.shipment_id != shipment.id:
                            carton.shipment = shipment
                            carton.save(update_fields=["shipment"])

                    for item in line_items:
                        if "product" in item:
                            pack_carton(
                                user=request.user,
                                product=item["product"],
                                quantity=item["quantity"],
                                carton=None,
                                carton_code=None,
                                shipment=shipment,
                            )
                _sync_shipment_ready_state(shipment)
                messages.success(
                    request,
                    f"Expedition mise a jour: {shipment.reference}.",
                )
                return redirect("scan:scan_shipments_ready")
            except StockError as exc:
                form.add_error(None, str(exc))
    else:
        carton_count = max(1, len(assigned_cartons))
        if assigned_cartons:
            line_values = [
                {"carton_id": carton.id, "product_code": "", "quantity": ""}
                for carton in assigned_cartons
            ]
        else:
            line_values = build_shipment_line_values(carton_count)

    documents = Document.objects.filter(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL
    ).order_by("-generated_at")
    carton_docs = [{"id": carton.id, "code": carton.code} for carton in assigned_cartons]

    destinations_json, recipient_contacts_json, correspondent_contacts_json = (
        _build_shipment_contact_payload()
    )

    return render(
        request,
        "scan/shipment_create.html",
        {
            "form": form,
            "active": "shipments_ready",
            "is_edit": True,
            "shipment": shipment,
            "tracking_url": shipment.get_tracking_url(request=request),
            "documents": documents,
            "carton_docs": carton_docs,
            "products_json": product_options,
            "cartons_json": cartons_json,
            "carton_count": carton_count,
            "line_values": line_values,
            "line_errors": line_errors,
            "destinations_json": destinations_json,
            "recipient_contacts_json": recipient_contacts_json,
            "correspondent_contacts_json": correspondent_contacts_json,
        },
    )


@require_http_methods(["GET", "POST"])
def scan_shipment_track(request, shipment_ref):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    shipment.ensure_qr_code(request=request)
    documents, carton_docs, additional_docs = _build_shipment_document_links(
        shipment, public=True
    )
    last_event = shipment.tracking_events.order_by("-created_at").first()
    next_status = _next_tracking_status(last_event.status if last_event else None)
    form = ShipmentTrackingForm(request.POST or None, initial_status=next_status)
    if request.method == "POST" and form.is_valid():
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=form.cleaned_data["status"],
            actor_name=form.cleaned_data["actor_name"],
            actor_structure=form.cleaned_data["actor_structure"],
            comments=form.cleaned_data["comments"] or "",
            created_by=request.user if request.user.is_authenticated else None,
        )
        messages.success(request, "Suivi mis a jour.")
        return redirect("scan:scan_shipment_track", shipment_ref=shipment.reference)
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
    return _render_shipment_document(request, shipment, doc_type)


@require_http_methods(["GET"])
def scan_shipment_document_public(request, shipment_ref, doc_type):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    return _render_shipment_document(request, shipment, doc_type)


@login_required
@require_http_methods(["GET"])
def scan_shipment_carton_document(request, shipment_id, carton_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return _render_carton_document(request, shipment, carton)


@require_http_methods(["GET"])
def scan_shipment_carton_document_public(request, shipment_ref, carton_id):
    shipment = get_object_or_404(Shipment, reference=shipment_ref)
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404("Carton not found for shipment")
    return _render_carton_document(request, shipment, carton)


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


def _render_shipment_document(request, shipment, doc_type):
    allowed = {
        "donation_certificate": "print/attestation_donation.html",
        "humanitarian_certificate": "print/attestation_aide_humanitaire.html",
        "customs": "print/attestation_douane.html",
        "shipment_note": "print/bon_expedition.html",
        "packing_list_shipment": "print/liste_colisage_lot.html",
    }
    template = allowed.get(doc_type)
    if template is None:
        raise Http404("Document type not found")
    context = build_shipment_document_context(shipment, doc_type)
    layout_override = get_template_layout(doc_type)
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, "print/dynamic_document.html", {"blocks": blocks})
    return render(request, template, context)


def _render_carton_document(request, shipment, carton):
    context = build_carton_document_context(shipment, carton)
    doc_type = "packing_list_carton"
    layout_override = get_template_layout(doc_type)
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, "print/dynamic_document.html", {"blocks": blocks})
    return render(request, "print/liste_colisage_carton.html", context)


def _render_shipment_labels(request, shipment):
    shipment.ensure_qr_code(request=request)
    cartons = list(shipment.carton_set.order_by("code"))
    total = len(cartons)
    qr_url = shipment.qr_code_image.url if shipment.qr_code_image else ""
    labels = []
    for index, carton in enumerate(cartons, start=1):
        label_context = build_label_context(shipment, position=index, total=total)
        labels.append(
            {
                "city": label_context["label_city"],
                "iata": label_context["label_iata"],
                "shipment_ref": label_context["label_shipment_ref"],
                "position": label_context["label_position"],
                "total": label_context["label_total"],
                "qr_url": label_context.get("label_qr_url") or qr_url,
                "carton_id": carton.id,
            }
        )

    layout_override = get_template_layout("shipment_label")
    if layout_override:
        rendered_labels = []
        for label in labels:
            label_context = {
                "label_city": label["city"],
                "label_iata": label["iata"],
                "label_shipment_ref": label["shipment_ref"],
                "label_position": label["position"],
                "label_total": label["total"],
                "label_qr_url": label.get("qr_url", ""),
            }
            blocks = render_layout_from_layout(layout_override, label_context)
            rendered_labels.append({"blocks": blocks})
        return render(request, "print/dynamic_labels.html", {"labels": rendered_labels})
    return render(request, "print/etiquette_expedition.html", {"labels": labels})


@login_required
@require_http_methods(["GET"])
def scan_shipment_labels(request, shipment_id):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), pk=shipment_id
    )
    return _render_shipment_labels(request, shipment)


@require_http_methods(["GET"])
def scan_shipment_labels_public(request, shipment_ref):
    shipment = get_object_or_404(
        Shipment.objects.select_related("destination"), reference=shipment_ref
    )
    return _render_shipment_labels(request, shipment)


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


def _bool_to_csv(value):
    if value is None:
        return ""
    return "true" if value else "false"


def _category_levels(category):
    if not category:
        return ["", "", "", ""]
    parts = []
    current = category
    while current:
        parts.append(current.name)
        current = current.parent
    parts.reverse()
    parts = parts[:4]
    while len(parts) < 4:
        parts.append("")
    return parts


def _build_csv_response(filename, header, rows):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    content = "\ufeff" + output.getvalue()
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _export_products_csv():
    header = [
        "sku",
        "nom",
        "marque",
        "couleur",
        "category_l1",
        "category_l2",
        "category_l3",
        "category_l4",
        "tags",
        "entrepot",
        "rack",
        "etagere",
        "bac",
        "rack_color",
        "barcode",
        "ean",
        "pu_ht",
        "tva",
        "pu_ttc",
        "length_cm",
        "width_cm",
        "height_cm",
        "weight_g",
        "volume_cm3",
        "quantity",
        "storage_conditions",
        "perishable",
        "quarantine_default",
        "notes",
        "photo",
    ]
    rack_colors = {
        (rack.warehouse_id, rack.zone): rack.color for rack in RackColor.objects.all()
    }
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"), output_field=IntegerField()
    )
    stock_totals = (
        ProductLot.objects.filter(status=ProductLotStatus.AVAILABLE)
        .values("product_id")
        .annotate(total=Sum(available_expr))
    )
    quantity_by_product = {
        row["product_id"]: max(0, row["total"] or 0) for row in stock_totals
    }
    rows = []
    products = (
        Product.objects.select_related(
            "category", "default_location", "default_location__warehouse"
        )
        .prefetch_related("tags")
        .all()
    )
    for product in products:
        cat_l1, cat_l2, cat_l3, cat_l4 = _category_levels(product.category)
        tags = "|".join(sorted(tag.name for tag in product.tags.all()))
        location = product.default_location
        warehouse = location.warehouse.name if location else ""
        zone = location.zone if location else ""
        aisle = location.aisle if location else ""
        shelf = location.shelf if location else ""
        rack_color = ""
        if location:
            rack_color = rack_colors.get((location.warehouse_id, location.zone), "")
        quantity = quantity_by_product.get(product.id) or 0
        rows.append(
            [
                product.sku or "",
                product.name or "",
                product.brand or "",
                product.color or "",
                cat_l1,
                cat_l2,
                cat_l3,
                cat_l4,
                tags,
                warehouse,
                zone,
                aisle,
                shelf,
                rack_color,
                product.barcode or "",
                product.ean or "",
                product.pu_ht or "",
                product.tva or "",
                product.pu_ttc or "",
                product.length_cm or "",
                product.width_cm or "",
                product.height_cm or "",
                product.weight_g or "",
                product.volume_cm3 or "",
                quantity if quantity > 0 else "",
                product.storage_conditions or "",
                _bool_to_csv(product.perishable),
                _bool_to_csv(product.quarantine_default),
                product.notes or "",
                product.photo.name if product.photo else "",
            ]
        )
    return _build_csv_response("products_export.csv", header, rows)


def _export_locations_csv():
    header = ["entrepot", "rack", "etagere", "bac", "notes", "rack_color"]
    rack_colors = {
        (rack.warehouse_id, rack.zone): rack.color for rack in RackColor.objects.all()
    }
    rows = []
    locations = Location.objects.select_related("warehouse").all()
    for location in locations:
        rack_color = rack_colors.get((location.warehouse_id, location.zone), "")
        rows.append(
            [
                location.warehouse.name,
                location.zone,
                location.aisle,
                location.shelf,
                location.notes or "",
                rack_color,
            ]
        )
    return _build_csv_response("locations_export.csv", header, rows)


def _export_categories_csv():
    header = ["name", "parent"]
    rows = []
    for category in ProductCategory.objects.select_related("parent").all():
        rows.append([category.name, category.parent.name if category.parent else ""])
    return _build_csv_response("categories_export.csv", header, rows)


def _export_warehouses_csv():
    header = ["name", "code"]
    rows = []
    for warehouse in Warehouse.objects.all():
        rows.append([warehouse.name, warehouse.code or ""])
    return _build_csv_response("warehouses_export.csv", header, rows)


def _export_contacts_csv():
    header = [
        "contact_type",
        "title",
        "first_name",
        "last_name",
        "name",
        "organization",
        "role",
        "email",
        "email2",
        "phone",
        "phone2",
        "use_organization_address",
        "tags",
        "destination",
        "siret",
        "vat_number",
        "legal_registration_number",
        "asf_id",
        "address_label",
        "address_line1",
        "address_line2",
        "postal_code",
        "city",
        "region",
        "country",
        "address_phone",
        "address_email",
        "address_is_default",
        "notes",
    ]
    rows = []
    contacts = Contact.objects.select_related("organization", "destination").prefetch_related(
        "tags", "addresses"
    )
    for contact in contacts:
        tags = "|".join(sorted(tag.name for tag in contact.tags.all()))
        destination = str(contact.destination) if contact.destination else ""
        address_source = (
            contact.get_effective_addresses()
            if hasattr(contact, "get_effective_addresses")
            else contact.addresses.all()
        )
        addresses = list(address_source)
        if not addresses:
            rows.append(
                [
                    contact.contact_type,
                    contact.title or "",
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.name,
                    contact.organization.name if contact.organization else "",
                    contact.role or "",
                    contact.email or "",
                    contact.email2 or "",
                    contact.phone or "",
                    contact.phone2 or "",
                    _bool_to_csv(contact.use_organization_address),
                    tags,
                    destination,
                    contact.siret or "",
                    contact.vat_number or "",
                    contact.legal_registration_number or "",
                    contact.asf_id or "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    contact.notes or "",
                ]
            )
            continue
        for address in addresses:
            rows.append(
                [
                    contact.contact_type,
                    contact.title or "",
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.name,
                    contact.organization.name if contact.organization else "",
                    contact.role or "",
                    contact.email or "",
                    contact.email2 or "",
                    contact.phone or "",
                    contact.phone2 or "",
                    _bool_to_csv(contact.use_organization_address),
                    tags,
                    destination,
                    contact.siret or "",
                    contact.vat_number or "",
                    contact.legal_registration_number or "",
                    contact.asf_id or "",
                    address.label or "",
                    address.address_line1 or "",
                    address.address_line2 or "",
                    address.postal_code or "",
                    address.city or "",
                    address.region or "",
                    address.country or "",
                    address.phone or "",
                    address.email or "",
                    _bool_to_csv(address.is_default),
                    contact.notes or "",
                ]
            )
    return _build_csv_response("contacts_export.csv", header, rows)


def _export_users_csv():
    header = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
        "password",
    ]
    rows = []
    User = get_user_model()
    for user in User.objects.all():
        rows.append(
            [
                user.username,
                user.email or "",
                user.first_name or "",
                user.last_name or "",
                _bool_to_csv(user.is_staff),
                _bool_to_csv(user.is_superuser),
                _bool_to_csv(user.is_active),
                "",
            ]
        )
    return _build_csv_response("users_export.csv", header, rows)


@login_required
@require_http_methods(["GET", "POST"])
def scan_import(request):
    _require_superuser(request)
    export_target = (request.GET.get("export") or "").strip().lower()
    if export_target:
        export_handlers = {
            "products": _export_products_csv,
            "locations": _export_locations_csv,
            "categories": _export_categories_csv,
            "warehouses": _export_warehouses_csv,
            "contacts": _export_contacts_csv,
            "users": _export_users_csv,
        }
        handler = export_handlers.get(export_target)
        if handler is None:
            raise Http404
        return handler()
    default_password = getattr(settings, "IMPORT_DEFAULT_PASSWORD", None)
    pending_import = request.session.get("product_import_pending")

    def clear_pending_import():
        pending = request.session.pop("product_import_pending", None)
        if pending and pending.get("temp_path"):
            Path(pending["temp_path"]).unlink(missing_ok=True)

    def row_is_empty(row):
        return all(not str(value or "").strip() for value in row.values())

    def format_import_location(row):
        warehouse = parse_str(get_value(row, "warehouse", "entrepot"))
        zone = parse_str(get_value(row, "zone", "rack"))
        aisle = parse_str(get_value(row, "aisle", "etagere"))
        shelf = parse_str(get_value(row, "shelf", "bac", "emplacement"))
        if all([warehouse, zone, aisle, shelf]):
            return f"{warehouse} {zone}-{aisle}-{shelf}"
        return "-"

    def summarize_import_row(row):
        quantity = parse_int(get_value(row, "quantity", "quantite", "stock", "qty"))
        return {
            "sku": parse_str(get_value(row, "sku")) or "",
            "name": parse_str(get_value(row, "name", "nom", "nom_produit", "produit")) or "",
            "brand": parse_str(get_value(row, "brand", "marque")) or "",
            "quantity": quantity if quantity is not None else "-",
            "location": format_import_location(row),
        }

    def build_match_context(pending):
        if not pending:
            return None
        match_ids = {
            match_id
            for item in pending.get("matches", [])
            for match_id in item.get("match_ids", [])
        }
        if match_ids:
            available_expr = ExpressionWrapper(
                F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
                output_field=IntegerField(),
            )
            products = (
                Product.objects.filter(id__in=match_ids)
                .select_related("default_location")
                .annotate(
                    available_stock=Coalesce(
                        Sum(
                            available_expr,
                            filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
                        ),
                        0,
                    )
                )
            )
            products_by_id = {
                product.id: {
                    "id": product.id,
                    "sku": product.sku or "",
                    "name": product.name,
                    "brand": product.brand or "",
                    "available_stock": int(product.available_stock or 0),
                    "location": str(product.default_location)
                    if product.default_location
                    else "-",
                }
                for product in products
            }
        else:
            products_by_id = {}

        matches = []
        match_labels = {"sku": "SKU", "name_brand": "Nom + Marque"}
        for item in pending.get("matches", []):
            match_products = [
                products_by_id[match_id]
                for match_id in item.get("match_ids", [])
                if match_id in products_by_id
            ]
            matches.append(
                {
                    "row_index": item.get("row_index"),
                    "match_type": match_labels.get(item.get("match_type"), ""),
                    "row": item.get("row_summary", {}),
                    "products": match_products,
                }
            )
        return {
            "token": pending.get("token"),
            "matches": matches,
            "default_action": pending.get("default_action", "update"),
        }
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "product_confirm":
            pending = request.session.get("product_import_pending")
            token = (request.POST.get("pending_token") or "").strip()
            if not pending or token != pending.get("token"):
                messages.error(request, "Import produit: confirmation invalide.")
                return redirect("scan:scan_import")
            if request.POST.get("cancel"):
                clear_pending_import()
                messages.info(request, "Import produit annule.")
                return redirect("scan:scan_import")

            decisions = {}
            for item in pending.get("matches", []):
                row_index = item.get("row_index")
                action_choice = request.POST.get(f"decision_{row_index}") or pending.get(
                    "default_action", "update"
                )
                if action_choice == "create":
                    decisions[row_index] = {"action": "create"}
                    continue
                match_id = request.POST.get(f"match_id_{row_index}")
                if not match_id:
                    messages.error(
                        request,
                        "Import produit: selection requise pour la mise a jour.",
                    )
                    return redirect("scan:scan_import")
                if str(match_id) not in {str(mid) for mid in item.get("match_ids", [])}:
                    messages.error(
                        request,
                        "Import produit: produit cible invalide.",
                    )
                    return redirect("scan:scan_import")
                decisions[row_index] = {
                    "action": "update",
                    "product_id": int(match_id),
                }

            if pending.get("source") == "file":
                temp_path = Path(pending["temp_path"])
                if not temp_path.exists():
                    clear_pending_import()
                    messages.error(request, "Import produit: fichier temporaire introuvable.")
                    return redirect("scan:scan_import")
                extension = pending.get("extension", "")
                data = temp_path.read_bytes()
                rows = list(iter_import_rows(data, extension))
                base_dir = temp_path.parent
                start_index = pending.get("start_index", 2)
            else:
                rows = pending.get("rows", [])
                base_dir = None
                start_index = pending.get("start_index", 1)

            created, updated, errors, warnings = import_products_rows(
                rows,
                user=request.user,
                decisions=decisions,
                base_dir=base_dir,
                start_index=start_index,
            )
            clear_pending_import()
            if errors:
                messages.warning(request, f"Import produits: {len(errors)} erreur(s).")
                for message in errors[:3]:
                    messages.warning(request, message)
            if warnings:
                messages.warning(request, f"Import produits: {len(warnings)} alerte(s).")
                for message in warnings[:3]:
                    messages.warning(request, message)
            messages.success(
                request,
                f"Import produits: {created} cree(s), {updated} maj.",
            )
            return redirect("scan:scan_import")

        if action == "product_single":
            row = {
                key: value
                for key, value in request.POST.items()
                if key not in {"csrfmiddlewaretoken", "action"}
            }
            sku, name, brand = extract_product_identity(row)
            matches, match_type = find_product_matches(
                sku=sku, name=name, brand=brand
            )
            if matches:
                pending = {
                    "token": uuid.uuid4().hex,
                    "source": "single",
                    "rows": [row],
                    "start_index": 1,
                    "default_action": "update",
                    "matches": [
                        {
                            "row_index": 1,
                            "match_type": match_type,
                            "match_ids": [product.id for product in matches],
                            "row_summary": summarize_import_row(row),
                        }
                    ],
                }
                request.session["product_import_pending"] = pending
                return render(
                    request,
                    "scan/imports.html",
                    {
                        "active": "imports",
                        "shell_class": "scan-shell-wide",
                        "product_match_pending": build_match_context(pending),
                    },
                )
            created, updated, errors, warnings = import_products_rows(
                [row],
                user=request.user,
                start_index=1,
            )
            if errors:
                messages.error(request, errors[0])
            else:
                if warnings:
                    for message in warnings[:3]:
                        messages.warning(request, message)
                messages.success(request, "Produit cree.")
            return redirect("scan:scan_import")
        if action == "product_file":
            uploaded = request.FILES.get("import_file")
            update_existing = bool(request.POST.get("update_existing"))
            if not uploaded:
                messages.error(request, "Fichier requis pour importer les produits.")
                return redirect("scan:scan_import")
            extension = Path(uploaded.name).suffix.lower()
            data = uploaded.read()
            if extension == ".csv":
                data = decode_text(data).encode("utf-8")
            if extension not in {".csv", ".xlsx", ".xlsm", ".xls"}:
                messages.error(request, "Format non supporte. Utilisez CSV/XLS/XLSX.")
                return redirect("scan:scan_import")
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
                temp.write(data)
                temp_path = temp.name
            rows = list(iter_import_rows(data, extension))
            matches = []
            for index, row in enumerate(rows, start=2):
                if row_is_empty(row):
                    continue
                sku, name, brand = extract_product_identity(row)
                matched, match_type = find_product_matches(
                    sku=sku, name=name, brand=brand
                )
                if matched:
                    matches.append(
                        {
                            "row_index": index,
                            "match_type": match_type,
                            "match_ids": [product.id for product in matched],
                            "row_summary": summarize_import_row(row),
                        }
                    )
            if matches:
                pending = {
                    "token": uuid.uuid4().hex,
                    "source": "file",
                    "temp_path": temp_path,
                    "extension": extension,
                    "start_index": 2,
                    "default_action": "update" if update_existing else "create",
                    "matches": matches,
                }
                request.session["product_import_pending"] = pending
                return render(
                    request,
                    "scan/imports.html",
                    {
                        "active": "imports",
                        "shell_class": "scan-shell-wide",
                        "product_match_pending": build_match_context(pending),
                    },
                )

            created, updated, errors, warnings = import_products_rows(
                rows,
                user=request.user,
                base_dir=Path(temp_path).parent,
                start_index=2,
            )
            Path(temp_path).unlink(missing_ok=True)
            if errors:
                messages.warning(request, f"Import produits: {len(errors)} erreur(s).")
                for message in errors[:3]:
                    messages.warning(request, message)
            if warnings:
                messages.warning(request, f"Import produits: {len(warnings)} alerte(s).")
                for message in warnings[:3]:
                    messages.warning(request, message)
            messages.success(
                request,
                f"Import produits: {created} cree(s), {updated} maj.",
            )
            return redirect("scan:scan_import")

        import_file_actions = {
            "location_file": ("emplacements", import_locations),
            "category_file": ("categories", import_categories),
            "warehouse_file": ("entrepots", import_warehouses),
            "contact_file": ("contacts", import_contacts),
            "user_file": ("utilisateurs", import_users),
        }
        if action in import_file_actions:
            label, importer = import_file_actions[action]
            uploaded = request.FILES.get("import_file")
            if not uploaded:
                messages.error(request, f"Fichier requis pour importer les {label}.")
                return redirect("scan:scan_import")
            extension = Path(uploaded.name).suffix.lower()
            data = uploaded.read()
            try:
                rows = iter_import_rows(data, extension)
                if action == "user_file":
                    result = importer(rows, default_password)
                else:
                    result = importer(rows)
            except ValueError as exc:
                messages.error(request, f"Import {label}: {exc}")
                return redirect("scan:scan_import")
            if len(result) == 4:
                created, updated, errors, warnings = result
            else:
                created, updated, errors = result
                warnings = []
            if errors:
                messages.warning(request, f"Import {label}: {len(errors)} erreur(s).")
                for message in errors[:3]:
                    messages.warning(request, message)
            if warnings:
                messages.warning(request, f"Import {label}: {len(warnings)} alerte(s).")
                for message in warnings[:3]:
                    messages.warning(request, message)
            messages.success(
                request,
                f"Import {label}: {created} cree(s), {updated} maj.",
            )
            return redirect("scan:scan_import")

        single_actions = {
            "location_single": ("emplacement", import_locations),
            "category_single": ("categorie", import_categories),
            "warehouse_single": ("entrepot", import_warehouses),
            "contact_single": ("contact", import_contacts),
            "user_single": ("utilisateur", import_users),
        }
        if action in single_actions:
            label, importer = single_actions[action]
            row = dict(request.POST.items())
            try:
                if action == "user_single":
                    result = importer([row], default_password)
                else:
                    result = importer([row])
            except ValueError as exc:
                messages.error(request, f"Ajout {label}: {exc}")
                return redirect("scan:scan_import")
            if len(result) == 4:
                created, updated, errors, warnings = result
            else:
                created, updated, errors = result
                warnings = []
            if errors:
                messages.error(request, errors[0])
            elif warnings:
                for message in warnings[:3]:
                    messages.warning(request, message)
            else:
                messages.success(request, f"{label.capitalize()} ajoute.")
            return redirect("scan:scan_import")

    return render(
        request,
        "scan/imports.html",
        {
            "active": "imports",
            "shell_class": "scan-shell-wide",
            "product_match_pending": build_match_context(pending_import),
        },
    )


@login_required
@require_http_methods(["POST"])
def scan_shipment_document_upload(request, shipment_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    uploaded = request.FILES.get("document_file")
    if not uploaded:
        messages.error(request, "Fichier requis.")
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    extension = Path(uploaded.name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        messages.error(request, "Format de fichier non autorise.")
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    Document.objects.create(
        shipment=shipment, doc_type=DocumentType.ADDITIONAL, file=uploaded
    )
    messages.success(request, "Document ajoute.")
    return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)


@login_required
@require_http_methods(["POST"])
def scan_shipment_document_delete(request, shipment_id, document_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    document = get_object_or_404(
        Document, pk=document_id, shipment=shipment, doc_type=DocumentType.ADDITIONAL
    )
    if document.file:
        document.file.delete(save=False)
    document.delete()
    messages.success(request, "Document supprime.")
    return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)


@login_required
@require_http_methods(["GET", "POST"])
def scan_out(request):
    form = ScanOutForm(request.POST or None)
    product_options = build_product_options()
    if request.method == "POST" and form.is_valid():
        product = resolve_product(form.cleaned_data["product_code"])
        if not product:
            form.add_error("product_code", "Produit introuvable.")
        else:
            shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
            if form.cleaned_data["shipment_reference"] and not shipment:
                form.add_error("shipment_reference", "Expedition introuvable.")
            else:
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
                    messages.success(
                        request,
                        f"Suppression enregistree: {product.name} ({form.cleaned_data['quantity']}).",
                    )
                    return redirect("scan:scan_out")
                except StockError as exc:
                    form.add_error(None, str(exc))
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
