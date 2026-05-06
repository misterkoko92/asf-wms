from collections import defaultdict

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .carton_status_events import set_carton_status
from .models import (
    AssociationPickupAddress,
    Carton,
    CartonStatus,
    Order,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderStatus,
)
from .services import StockError, create_shipment_for_order, reserve_stock_for_order
from .shipment_status import sync_shipment_ready_state


def _resolve_ready_cartons(ready_carton_ids):
    ready_carton_ids = [int(carton_id) for carton_id in (ready_carton_ids or []) if carton_id]
    if not ready_carton_ids:
        return []
    if len(ready_carton_ids) != len(set(ready_carton_ids)):
        raise StockError(_("Colis prêt indisponible."))

    cartons = (
        Carton.objects.select_for_update()
        .filter(id__in=ready_carton_ids)
        .prefetch_related("cartonitem_set__product_lot__product")
    )
    cartons_by_id = {carton.id: carton for carton in cartons}
    selected_cartons = []
    for carton_id in ready_carton_ids:
        carton = cartons_by_id.get(carton_id)
        if carton is None:
            raise StockError(_("Colis prêt indisponible."))
        if carton.status != CartonStatus.PACKED or carton.shipment_id is not None:
            raise StockError(_("Colis prêt indisponible."))
        selected_cartons.append(carton)
    return selected_cartons


def _assign_ready_cartons_to_order(*, order, shipment, ready_cartons, user):
    if not ready_cartons:
        return

    line_by_product_id = {line.product_id: line for line in order.lines.all()}
    for carton in ready_cartons:
        carton.shipment = shipment
        set_carton_status(
            carton=carton,
            new_status=CartonStatus.ASSIGNED,
            update_fields=["shipment"],
            reason="portal_order_assign_ready_carton",
            user=user,
        )

        quantity_by_product_id = defaultdict(int)
        for item in carton.cartonitem_set.all():
            quantity_by_product_id[item.product_lot.product_id] += item.quantity
        for product_id, quantity in quantity_by_product_id.items():
            if quantity <= 0:
                continue
            line = line_by_product_id.get(product_id)
            if line is None:
                line = order.lines.create(
                    product_id=product_id,
                    quantity=0,
                    reserved_quantity=0,
                    prepared_quantity=0,
                )
                line_by_product_id[product_id] = line
            line.quantity += quantity
            line.prepared_quantity += quantity
            line.save(update_fields=["quantity", "prepared_quantity"])
    sync_shipment_ready_state(shipment)


def _build_pickup_address_label(inbound_delivery_data):
    label = (inbound_delivery_data.get("pickup_company_name") or "").strip()
    if label:
        return label
    address_line = (inbound_delivery_data.get("pickup_address_line1") or "").strip()
    city = (inbound_delivery_data.get("pickup_city") or "").strip()
    if address_line and city:
        return f"{address_line} - {city}"
    return address_line or city or ""


def _sync_pickup_address_entry(*, profile, inbound_delivery, selected_entry, save_requested):
    if inbound_delivery.arrival_mode != OrderInboundArrivalMode.PICKUP_REQUESTED:
        return selected_entry

    address_fields = {
        "pickup_company_name": inbound_delivery.pickup_company_name,
        "pickup_contact_name": inbound_delivery.pickup_contact_name,
        "pickup_contact_phone": inbound_delivery.pickup_contact_phone,
        "pickup_contact_phone_2": inbound_delivery.pickup_contact_phone_2,
        "pickup_address_line1": inbound_delivery.pickup_address_line1,
        "pickup_address_line2": inbound_delivery.pickup_address_line2,
        "pickup_postal_code": inbound_delivery.pickup_postal_code,
        "pickup_city": inbound_delivery.pickup_city,
        "pickup_country": inbound_delivery.pickup_country,
        "pickup_open_weekdays": list(inbound_delivery.pickup_open_weekdays or []),
        "pickup_opening_slot_1_start": inbound_delivery.pickup_opening_slot_1_start,
        "pickup_opening_slot_1_end": inbound_delivery.pickup_opening_slot_1_end,
        "pickup_has_midday_break": inbound_delivery.pickup_has_midday_break,
        "pickup_opening_slot_2_start": inbound_delivery.pickup_opening_slot_2_start,
        "pickup_opening_slot_2_end": inbound_delivery.pickup_opening_slot_2_end,
        "pickup_has_no_access_constraints": inbound_delivery.pickup_has_no_access_constraints,
        "pickup_access_constraints_details": inbound_delivery.pickup_access_constraints_details,
        "tail_lift_required": inbound_delivery.tail_lift_required,
        "pallet_truck_required": inbound_delivery.pallet_truck_required,
        "pickup_information_confirmed": inbound_delivery.pickup_information_confirmed,
    }

    address_entry = selected_entry
    if address_entry is None and save_requested:
        address_entry = AssociationPickupAddress.objects.create(
            association_contact=profile.contact,
            label=_build_pickup_address_label(address_fields),
            **address_fields,
        )
    elif address_entry is not None and save_requested:
        for field_name, value in address_fields.items():
            setattr(address_entry, field_name, value)
        if not address_entry.label:
            address_entry.label = _build_pickup_address_label(address_fields)
        address_entry.save(
            update_fields=[
                "label",
                *address_fields.keys(),
                "updated_at",
            ]
        )

    if address_entry is None:
        return None

    address_entry.times_used = int(address_entry.times_used or 0) + 1
    address_entry.last_used_at = timezone.now()
    address_entry.save(update_fields=["times_used", "last_used_at", "updated_at"])
    return address_entry


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
    with transaction.atomic():
        ready_cartons = _resolve_ready_cartons(ready_carton_ids)
        shipper_contact = profile.contact
        inbound_delivery_data = dict(inbound_delivery_data or {})
        selected_pickup_address_entry = inbound_delivery_data.pop("pickup_address_book_entry", None)
        save_pickup_address = bool(inbound_delivery_data.pop("save_pickup_address", False))
        order = Order.objects.create(
            reference="",
            status=OrderStatus.DRAFT,
            association_contact=profile.contact,
            shipper_name=(shipper_contact.name or "").strip(),
            shipper_contact=shipper_contact,
            recipient_name=recipient_name,
            recipient_contact=recipient_contact,
            destination_address=destination_address,
            destination_city=destination_city,
            destination_country=destination_country or "France",
            created_by=user,
            notes=notes,
        )
        for product, quantity in line_items:
            order.lines.create(product=product, quantity=quantity)
        inbound_delivery = None
        if inbound_delivery_data:
            inbound_delivery = OrderInboundDelivery.objects.create(
                order=order,
                pickup_address_book_entry=selected_pickup_address_entry,
                **inbound_delivery_data,
            )
            pickup_address_entry = _sync_pickup_address_entry(
                profile=profile,
                inbound_delivery=inbound_delivery,
                selected_entry=selected_pickup_address_entry,
                save_requested=save_pickup_address,
            )
            if (
                pickup_address_entry is not None
                and inbound_delivery.pickup_address_book_entry_id != pickup_address_entry.id
            ):
                inbound_delivery.pickup_address_book_entry = pickup_address_entry
                inbound_delivery.save(update_fields=["pickup_address_book_entry"])
        shipment = create_shipment_for_order(order=order)
        if line_items or ready_cartons:
            reserve_stock_for_order(order=order)
        _assign_ready_cartons_to_order(
            order=order,
            shipment=shipment,
            ready_cartons=ready_cartons,
            user=user,
        )

        if order.lines.exists() and all(line.remaining_quantity == 0 for line in order.lines.all()):
            order.status = OrderStatus.READY
            order.save(update_fields=["status"])
    return order
