import logging

from django.template.loader import render_to_string
from django.urls import reverse

from .emailing import enqueue_email_safe, get_admin_emails
from .portal_helpers import build_public_base_url

LOGGER = logging.getLogger(__name__)

TEMPLATE_ORDER_ADMIN_NOTIFICATION = "emails/order_admin_notification_portal.txt"
TEMPLATE_ORDER_CONFIRMATION = "emails/order_confirmation.txt"

SUBJECT_NEW_ORDER = "ASF WMS - Nouvelle commande"
SUBJECT_ORDER_CONFIRMATION = "ASF WMS - Commande reçue"

ROUTE_PORTAL_ORDER_DETAIL = "portal:portal_order_detail"
ROUTE_ADMIN_ORDER_CHANGELIST = "admin:wms_order_changelist"


def _order_reference(order):
    return order.reference or f"Commande {order.id}"


def _build_portal_order_urls(request, order):
    base_url = build_public_base_url(request)
    summary_path = reverse(ROUTE_PORTAL_ORDER_DETAIL, args=[order.id])
    admin_path = reverse(ROUTE_ADMIN_ORDER_CHANGELIST)
    return {
        "summary_url": f"{base_url}{summary_path}",
        "admin_url": f"{base_url}{admin_path}",
    }


def _build_admin_notification_context(request, profile, order, urls):
    return {
        "association_name": profile.contact.name,
        "email": profile.contact.email or request.user.email,
        "phone": profile.contact.phone,
        "order_reference": _order_reference(order),
        "summary_url": urls["summary_url"],
        "admin_url": urls["admin_url"],
    }


def _build_order_confirmation_context(profile, order, urls):
    return {
        "association_name": profile.contact.name,
        "order_reference": _order_reference(order),
        "summary_url": urls["summary_url"],
    }


def _build_confirmation_recipients(request, profile):
    recipients = [profile.contact.email or request.user.email]
    recipients += profile.get_notification_emails()
    return recipients


def send_portal_order_notifications(request, *, profile, order):
    urls = _build_portal_order_urls(request, order)

    admin_message = render_to_string(
        TEMPLATE_ORDER_ADMIN_NOTIFICATION,
        _build_admin_notification_context(request, profile, order, urls),
    )
    admin_queued = enqueue_email_safe(
        subject=SUBJECT_NEW_ORDER,
        message=admin_message,
        recipient=get_admin_emails(),
    )
    if not admin_queued:
        LOGGER.warning(
            "Portal order admin notification was not queued for %s",
            _order_reference(order),
        )

    confirmation_message = render_to_string(
        TEMPLATE_ORDER_CONFIRMATION,
        _build_order_confirmation_context(profile, order, urls),
    )

    confirmation_queued = enqueue_email_safe(
        subject=SUBJECT_ORDER_CONFIRMATION,
        message=confirmation_message,
        recipient=_build_confirmation_recipients(request, profile),
    )
    if not confirmation_queued:
        LOGGER.warning(
            "Portal order confirmation was not queued for %s",
            _order_reference(order),
        )
