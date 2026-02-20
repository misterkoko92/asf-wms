import logging

from django.contrib import messages
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

from .emailing import enqueue_email_safe, get_admin_emails
from .models import Order, OrderStatus
from .portal_helpers import build_destination_address, build_public_base_url
from .public_order_helpers import upsert_public_order_contact
from .services import create_shipment_for_order, reserve_stock_for_order

DEFAULT_DESTINATION_COUNTRY = "France"
DEFAULT_SHIPPER_NAME = "Aviation Sans Frontieres"

LOGGER = logging.getLogger(__name__)

TEMPLATE_ORDER_CONFIRMATION = "emails/order_confirmation.txt"
TEMPLATE_ORDER_ADMIN_NOTIFICATION = "emails/order_admin_notification_public.txt"

SUBJECT_PUBLIC_ORDER_ADMIN = "ASF WMS - Nouvelle commande publique"
SUBJECT_PUBLIC_ORDER_CONFIRMATION = "ASF WMS - Confirmation de commande"
MESSAGE_CONFIRMATION_WARNING = (
    "Commande envoyée, mais la confirmation email n'a pas pu être planifiée."
)

ROUTE_PUBLIC_ORDER_SUMMARY = "scan:scan_public_order_summary"
ROUTE_ADMIN_ORDER_CHANGE = "admin:wms_order_change"


def _form_value(form_data, key, default=""):
    return form_data.get(key, default) or default


def _order_reference(order):
    return order.reference or f"Commande {order.id}"


def _build_public_order_urls(request, *, token, order):
    base_url = build_public_base_url(request)
    summary_path = reverse(ROUTE_PUBLIC_ORDER_SUMMARY, args=[token, order.id])
    admin_path = reverse(ROUTE_ADMIN_ORDER_CHANGE, args=[order.id])
    return {
        "summary_url": f"{base_url}{summary_path}",
        "admin_url": f"{base_url}{admin_path}",
    }


def _build_order_confirmation_context(form_data, order, urls):
    return {
        "association_name": _form_value(form_data, "association_name"),
        "order_reference": _order_reference(order),
        "summary_url": urls["summary_url"],
    }


def _build_admin_notification_context(form_data, contact, order, urls):
    return {
        "association_name": _form_value(form_data, "association_name"),
        "email": _form_value(form_data, "association_email") or contact.email,
        "phone": _form_value(form_data, "association_phone") or contact.phone,
        "order_reference": _order_reference(order),
        "summary_url": urls["summary_url"],
        "admin_url": urls["admin_url"],
    }


def _confirmation_recipient(form_data, contact):
    return _form_value(form_data, "association_email") or contact.email or ""


def _destination_country(form_data):
    return _form_value(form_data, "association_country") or DEFAULT_DESTINATION_COUNTRY


def _destination_address(form_data):
    return build_destination_address(
        line1=_form_value(form_data, "association_line1"),
        line2=_form_value(form_data, "association_line2"),
        postal_code=_form_value(form_data, "association_postal_code"),
        city=_form_value(form_data, "association_city"),
        country=_form_value(form_data, "association_country"),
    )


def _create_order_lines(order, line_items):
    for product, quantity in line_items:
        order.lines.create(product=product, quantity=quantity)


def create_public_order(*, link, form_data, line_items):
    with transaction.atomic():
        contact = upsert_public_order_contact(form_data)

        order = Order.objects.create(
            reference="",
            status=OrderStatus.DRAFT,
            public_link=link,
            shipper_name=DEFAULT_SHIPPER_NAME,
            recipient_name=_form_value(form_data, "association_name"),
            recipient_contact=contact,
            destination_address=_destination_address(form_data),
            destination_city=_form_value(form_data, "association_city"),
            destination_country=_destination_country(form_data),
            requested_delivery_date=None,
            created_by=None,
            notes=_form_value(form_data, "association_notes"),
        )
        _create_order_lines(order, line_items)
        create_shipment_for_order(order=order)
        reserve_stock_for_order(order=order)

    return order, contact


def send_public_order_notifications(request, *, token, order, form_data, contact):
    urls = _build_public_order_urls(request, token=token, order=order)
    confirmation_message = render_to_string(
        TEMPLATE_ORDER_CONFIRMATION,
        _build_order_confirmation_context(form_data, order, urls),
    )
    admin_message = render_to_string(
        TEMPLATE_ORDER_ADMIN_NOTIFICATION,
        _build_admin_notification_context(form_data, contact, order, urls),
    )
    admin_queued = enqueue_email_safe(
        subject=SUBJECT_PUBLIC_ORDER_ADMIN,
        message=admin_message,
        recipient=get_admin_emails(),
    )
    if not admin_queued:
        LOGGER.warning(
            "Public order admin notification was not queued for %s",
            _order_reference(order),
        )
    if not enqueue_email_safe(
        subject=SUBJECT_PUBLIC_ORDER_CONFIRMATION,
        message=confirmation_message,
        recipient=_confirmation_recipient(form_data, contact),
    ):
        LOGGER.warning(
            "Public order confirmation was not queued for %s",
            _order_reference(order),
        )
        messages.warning(
            request,
            MESSAGE_CONFIRMATION_WARNING,
        )
