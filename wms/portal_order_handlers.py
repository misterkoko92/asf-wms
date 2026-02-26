from collections import defaultdict

from django.db import transaction

from .carton_status_events import set_carton_status
from .models import Carton, CartonStatus, Order, OrderStatus
from .services import StockError, create_shipment_for_order, reserve_stock_for_order
from .shipment_status import sync_shipment_ready_state


def _resolve_ready_cartons(ready_carton_ids):
    ready_carton_ids = [int(carton_id) for carton_id in (ready_carton_ids or []) if carton_id]
    if not ready_carton_ids:
        return []
    if len(ready_carton_ids) != len(set(ready_carton_ids)):
        raise StockError("Colis prêt indisponible.")

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
            raise StockError("Colis prêt indisponible.")
        if carton.status != CartonStatus.PACKED or carton.shipment_id is not None:
            raise StockError("Colis prêt indisponible.")
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
):
    with transaction.atomic():
        ready_cartons = _resolve_ready_cartons(ready_carton_ids)
        shipper_contact = profile.contact
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
        shipment = create_shipment_for_order(order=order)
        reserve_stock_for_order(order=order)
        _assign_ready_cartons_to_order(
            order=order,
            shipment=shipment,
            ready_cartons=ready_cartons,
            user=user,
        )

        if order.lines.exists() and all(
            line.remaining_quantity == 0 for line in order.lines.all()
        ):
            order.status = OrderStatus.READY
            order.save(update_fields=["status"])
    return order
