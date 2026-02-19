import re

from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.shortcuts import redirect
from django.urls import reverse

from .models import (
    Carton,
    CartonStatus,
    Shipment,
    ShipmentStatus,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
)
from .services import StockError, pack_carton
from .shipment_helpers import build_destination_label, parse_shipment_lines
from .shipment_status import sync_shipment_ready_state

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
SAVE_DRAFT_ACTION = "save_draft"
SAVE_DRAFT_PACK_ACTION = "save_draft_pack"
TEMP_SHIPMENT_REFERENCE_RE = re.compile(r"^EXP-TEMP-(\d+)$")
TEMP_SHIPMENT_REFERENCE_MAX_RETRIES = 5


def _parse_carton_count(raw_value):
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 1


def _get_carton_count(form, request):
    if form.is_valid():
        return form.cleaned_data["carton_count"]
    return _parse_carton_count(request.POST.get("carton_count", 1))


def _get_carton_count_from_post(request):
    return _parse_carton_count(request.POST.get("carton_count", 1))


def _is_save_draft_action(request):
    return (request.POST.get("action") or "").strip() in {
        SAVE_DRAFT_ACTION,
        SAVE_DRAFT_PACK_ACTION,
    }


def _is_save_draft_pack_action(request):
    return (request.POST.get("action") or "").strip() == SAVE_DRAFT_PACK_ACTION


def _next_temp_shipment_reference():
    max_number = 0
    references = Shipment.objects.filter(
        reference__startswith=TEMP_SHIPMENT_REFERENCE_PREFIX
    ).values_list("reference", flat=True)
    for reference in references:
        match = TEMP_SHIPMENT_REFERENCE_RE.match(reference or "")
        if not match:
            continue
        max_number = max(max_number, int(match.group(1)))
    return f"{TEMP_SHIPMENT_REFERENCE_PREFIX}{max_number + 1:02d}"


def _resolve_optional_contact(form, field_name):
    raw_value = (form.data.get(field_name) or "").strip()
    if not raw_value:
        return None, None
    field = form.fields.get(field_name)
    if field is None:
        return raw_value, None
    contact = field.queryset.filter(pk=raw_value).first()
    return raw_value, contact


def _build_pack_redirect_url(*, shipment_reference):
    base_url = reverse("scan:scan_pack")
    return f"{base_url}?shipment_reference={shipment_reference}"


def _handle_shipment_save_draft_post(request, *, form, redirect_to_pack=False):
    destination_value = (form.data.get("destination") or "").strip()
    if not destination_value:
        form.add_error(
            "destination",
            "Merci de sélectionner une destination avant d'enregistrer un brouillon.",
        )
        return None

    destination_field = form.fields.get("destination")
    destination = (
        destination_field.queryset.filter(pk=destination_value).first()
        if destination_field is not None
        else None
    )
    if destination is None:
        form.add_error("destination", "Destination invalide.")
        return None

    shipper_value, shipper_contact = _resolve_optional_contact(form, "shipper_contact")
    recipient_value, recipient_contact = _resolve_optional_contact(form, "recipient_contact")
    correspondent_value, correspondent_contact = _resolve_optional_contact(
        form, "correspondent_contact"
    )

    if shipper_value and shipper_contact is None:
        form.add_error("shipper_contact", "Contact non disponible pour cette destination.")
        return None
    if recipient_value and recipient_contact is None:
        form.add_error("recipient_contact", "Destinataire non disponible pour cet expéditeur.")
        return None
    if correspondent_value and correspondent_contact is None:
        form.add_error(
            "correspondent_contact",
            "Contact non disponible pour cette destination.",
        )
        return None

    destination_label = build_destination_label(destination)
    last_error = None
    for _ in range(TEMP_SHIPMENT_REFERENCE_MAX_RETRIES):
        draft_reference = _next_temp_shipment_reference()
        try:
            with transaction.atomic():
                shipment = Shipment.objects.create(
                    reference=draft_reference,
                    status=ShipmentStatus.DRAFT,
                    shipper_name=shipper_contact.name if shipper_contact else "",
                    shipper_contact_ref=shipper_contact,
                    recipient_name=recipient_contact.name if recipient_contact else "",
                    recipient_contact_ref=recipient_contact,
                    correspondent_name=correspondent_contact.name if correspondent_contact else "",
                    correspondent_contact_ref=correspondent_contact,
                    destination=destination,
                    destination_address=destination_label,
                    destination_country=destination.country,
                    created_by=request.user,
                )
        except IntegrityError as exc:
            last_error = exc
            continue

        messages.success(
            request,
            f"Brouillon enregistré: {shipment.reference}.",
        )
        if redirect_to_pack:
            return redirect(_build_pack_redirect_url(shipment_reference=shipment.reference))
        return redirect("scan:scan_shipment_edit", shipment.id)

    raise StockError("Impossible de générer une référence de brouillon unique.") from last_error


def handle_shipment_create_post(request, *, form, available_carton_ids):
    if _is_save_draft_action(request):
        carton_count = _get_carton_count_from_post(request)
        line_values, _line_items, _ignored_line_errors = parse_shipment_lines(
            carton_count=carton_count,
            data=request.POST,
            allowed_carton_ids=available_carton_ids,
        )
        response = _handle_shipment_save_draft_post(
            request,
            form=form,
            redirect_to_pack=_is_save_draft_pack_action(request),
        )
        return response, carton_count, line_values, {}

    carton_count = _get_carton_count(form, request)
    line_values, line_items, line_errors = parse_shipment_lines(
        carton_count=carton_count,
        data=request.POST,
        allowed_carton_ids=available_carton_ids,
    )
    response = None
    if form.is_valid() and not line_errors:
        try:
            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = form.cleaned_data["correspondent_contact"]
                destination_label = build_destination_label(destination)
                shipment = Shipment.objects.create(
                    status=ShipmentStatus.DRAFT,
                    shipper_name=shipper_contact.name,
                    shipper_contact_ref=shipper_contact,
                    recipient_name=recipient_contact.name,
                    recipient_contact_ref=recipient_contact,
                    correspondent_name=correspondent_contact.name,
                    correspondent_contact_ref=correspondent_contact,
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
                        carton.status = CartonStatus.ASSIGNED
                        carton.save(update_fields=["shipment", "status"])
                    else:
                        carton = pack_carton(
                            user=request.user,
                            product=item["product"],
                            quantity=item["quantity"],
                            carton=None,
                            carton_code=None,
                            shipment=shipment,
                        )
                        if carton.status != CartonStatus.ASSIGNED:
                            carton.status = CartonStatus.ASSIGNED
                            carton.save(update_fields=["status"])
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                f"Expédition créée: {shipment.reference}.",
            )
            response = redirect("scan:scan_shipment_create")
        except StockError as exc:
            form.add_error(None, str(exc))
    return response, carton_count, line_values, line_errors


def handle_shipment_edit_post(request, *, form, shipment, allowed_carton_ids):
    carton_count = _get_carton_count(form, request)
    line_values, line_items, line_errors = parse_shipment_lines(
        carton_count=carton_count,
        data=request.POST,
        allowed_carton_ids=allowed_carton_ids,
    )
    response = None
    if form.is_valid() and not line_errors:
        try:
            shipment_status = getattr(shipment, "status", ShipmentStatus.DRAFT)
            if shipment_status in LOCKED_SHIPMENT_STATUSES:
                raise StockError("Expédition verrouillée: modification des colis impossible.")
            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = form.cleaned_data["correspondent_contact"]
                destination_label = build_destination_label(destination)

                shipment.destination = destination
                shipment.shipper_name = shipper_contact.name
                shipment.shipper_contact_ref = shipper_contact
                shipment.recipient_name = recipient_contact.name
                shipment.recipient_contact_ref = recipient_contact
                shipment.correspondent_name = correspondent_contact.name
                shipment.correspondent_contact_ref = correspondent_contact
                shipment.destination_address = destination_label
                shipment.destination_country = destination.country
                shipment.save(
                    update_fields=[
                        "destination",
                        "shipper_name",
                        "shipper_contact_ref",
                        "recipient_name",
                        "recipient_contact_ref",
                        "correspondent_name",
                        "correspondent_contact_ref",
                        "destination_address",
                        "destination_country",
                    ]
                )

                selected_carton_ids = {
                    item["carton_id"] for item in line_items if "carton_id" in item
                }
                cartons_to_remove = shipment.carton_set.exclude(
                    id__in=selected_carton_ids
                )
                for carton in cartons_to_remove:
                    if carton.status == CartonStatus.SHIPPED:
                        raise StockError("Impossible de retirer un carton expédié.")
                    carton.shipment = None
                    if carton.status in {CartonStatus.ASSIGNED, CartonStatus.LABELED}:
                        carton.status = CartonStatus.PACKED
                        carton.save(update_fields=["shipment", "status"])
                    else:
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
                    if carton.shipment_id != shipment.id and carton.status != CartonStatus.PACKED:
                        raise StockError("Carton indisponible.")
                    if carton.shipment_id != shipment.id:
                        carton.shipment = shipment
                        carton.status = CartonStatus.ASSIGNED
                        carton.save(update_fields=["shipment", "status"])
                    elif carton.status == CartonStatus.PACKED:
                        carton.status = CartonStatus.ASSIGNED
                        carton.save(update_fields=["status"])

                for item in line_items:
                    if "product" in item:
                        carton = pack_carton(
                            user=request.user,
                            product=item["product"],
                            quantity=item["quantity"],
                            carton=None,
                            carton_code=None,
                            shipment=shipment,
                        )
                        if carton.status != CartonStatus.ASSIGNED:
                            carton.status = CartonStatus.ASSIGNED
                            carton.save(update_fields=["status"])
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                f"Expédition mise à jour: {shipment.reference}.",
            )
            response = redirect("scan:scan_shipments_ready")
        except StockError as exc:
            form.add_error(None, str(exc))
    return response, carton_count, line_values, line_errors
