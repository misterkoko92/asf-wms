from django.contrib import messages
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

from .emailing import get_admin_emails, send_email_safe
from .portal_helpers import build_destination_address, build_public_base_url
from .public_order_helpers import upsert_public_order_contact
from .services import create_shipment_for_order, reserve_stock_for_order
from .models import Order, OrderStatus


def create_public_order(*, request, link, form_data, line_items):
    with transaction.atomic():
        contact = upsert_public_order_contact(form_data)

        destination_address = build_destination_address(
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

    return order, contact


def send_public_order_notifications(request, *, token, order, form_data, contact):
    summary_url = reverse("scan:scan_public_order_summary", args=[token, order.id])
    base_url = build_public_base_url(request)
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
    send_email_safe(
        subject="ASF WMS - Nouvelle commande publique",
        message=admin_message,
        recipient=get_admin_emails(),
    )
    if not send_email_safe(
        subject="ASF WMS - Confirmation de commande",
        message=email_message,
        recipient=form_data["association_email"] or contact.email,
    ):
        messages.warning(
            request,
            "Commande envoyee, mais l'email de confirmation n'a pas pu etre envoye.",
        )
