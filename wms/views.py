import json
import math
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
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

from contacts.models import Contact, ContactAddress, ContactTag

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
    Product,
    ProductCategory,
    ProductLot,
    Receipt,
    ReceiptHorsFormat,
    ReceiptStatus,
    ReceiptType,
    Order,
    OrderStatus,
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
    build_preview_context,
    build_sample_label_context,
    build_shipment_document_context,
)
from .print_layouts import BLOCK_LIBRARY, DEFAULT_LAYOUTS, DOCUMENT_TEMPLATES
from .print_renderer import get_template_layout, layout_changed, render_layout_from_layout
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
    recipient_contacts = contacts_with_tags(TAG_RECIPIENT).prefetch_related("addresses")
    correspondent_contacts = contacts_with_tags(TAG_CORRESPONDENT)

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
        countries = {
            address.country
            for address in contact.addresses.all()
            if address.country
        }
        recipient_contacts_json.append(
            {
                "id": contact.id,
                "name": contact.name,
                "countries": sorted(countries),
            }
        )
    correspondent_contacts_json = [
        {"id": contact.id, "name": contact.name}
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
    recipients = recipient
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [item for item in recipients if item]
    if not recipients:
        return False
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception:
        return False
    return True


def _get_admin_emails():
    User = get_user_model()
    return list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


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


@require_http_methods(["GET", "POST"])
def scan_public_account_request(request, token):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    contacts = list(
        contacts_with_tags(TAG_SHIPPER).prefetch_related("addresses").order_by("name")
    )
    contact_payload = []
    for contact in contacts:
        address = (
            contact.addresses.filter(is_default=True).first()
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

    summary_url = None
    if request.method == "GET":
        order_id = parse_int(request.GET.get("order"))
        if order_id:
            order = Order.objects.filter(id=order_id, public_link=link).first()
            if order:
                summary_url = reverse("scan:scan_public_order_summary", args=[token, order.id])

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
            PublicAccountRequest.objects.create(
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
            return redirect(reverse("scan:scan_public_account_request", args=[token]))

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
            contact.addresses.filter(is_default=True).first()
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
            "carton_status_choices": [
                (CartonStatus.DRAFT, CartonStatus.DRAFT.label),
                (CartonStatus.PICKING, CartonStatus.PICKING.label),
                (CartonStatus.PACKED, CartonStatus.PACKED.label),
            ],
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
                receive_stock(
                    user=request.user,
                    product=product,
                    quantity=create_form.cleaned_data["quantity"],
                    location=location,
                    lot_code=create_form.cleaned_data["lot_code"] or "",
                    received_on=timezone.localdate(),
                    expires_on=create_form.cleaned_data["expires_on"],
                    source_receipt=create_form.cleaned_data["donor_receipt"],
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
        "-received_on", "-created_at"
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


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    create_form = ScanReceiptPalletForm(request.POST or None)
    if request.method == "POST" and create_form.is_valid():
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

    return render(
        request,
        "scan/receive_pallet.html",
        {
            "active": "receive_pallet",
            "create_form": create_form,
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
    orders_qs = Order.objects.select_related("shipment").order_by("-created_at")[:50]
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
        "-created_at"
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

    context = build_preview_context(doc_type, shipment=shipment)
    blocks = render_layout_from_layout(layout_data, context)
    return render(request, "print/dynamic_document.html", {"blocks": blocks})


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
    return render(request, "scan/out.html", {"form": form, "active": "out"})


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


SERVICE_WORKER_JS = """const CACHE_NAME = 'wms-scan-v29';
const ASSETS = [
  '/scan/',
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
