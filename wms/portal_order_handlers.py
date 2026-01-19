from django.db import transaction

from .models import Order, OrderStatus
from .services import create_shipment_for_order, reserve_stock_for_order


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
):
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
            created_by=user,
            notes=notes,
        )
        for product, quantity in line_items:
            order.lines.create(product=product, quantity=quantity)
        create_shipment_for_order(order=order)
        reserve_stock_for_order(order=order)
    return order
