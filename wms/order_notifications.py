from django.template.loader import render_to_string
from django.urls import reverse

from .emailing import get_admin_emails, send_email_safe
from .portal_helpers import build_public_base_url


def send_portal_order_notifications(request, *, profile, order):
    base_url = build_public_base_url(request)
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
    send_email_safe(
        subject="ASF WMS - Nouvelle commande",
        message=admin_message,
        recipient=get_admin_emails(),
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
    send_email_safe(
        subject="ASF WMS - Commande recue",
        message=confirmation_message,
        recipient=recipients,
    )
