from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import redirect

from .models import Carton, CartonStatus, Shipment, ShipmentStatus
from .services import StockError, pack_carton
from .shipment_helpers import build_destination_label, parse_shipment_lines
from .shipment_status import sync_shipment_ready_state


def _get_carton_count(form, request):
    if form.is_valid():
        return form.cleaned_data["carton_count"]
    try:
        return max(1, int(request.POST.get("carton_count", 1)))
    except (TypeError, ValueError):
        return 1


def handle_shipment_create_post(request, *, form, available_carton_ids):
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
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                f"Expedition creee: {shipment.reference}.",
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
            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = form.cleaned_data["correspondent_contact"]
                destination_label = build_destination_label(destination)

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
                    item["carton_id"] for item in line_items if "carton_id" in item
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
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                f"Expedition mise a jour: {shipment.reference}.",
            )
            response = redirect("scan:scan_shipments_ready")
        except StockError as exc:
            form.add_error(None, str(exc))
    return response, carton_count, line_values, line_errors
