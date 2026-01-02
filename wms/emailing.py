import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

LOGGER = logging.getLogger(__name__)
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def get_admin_emails():
    User = get_user_model()
    return list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _brevo_settings():
    api_key = getattr(settings, "BREVO_API_KEY", "") or os.environ.get("BREVO_API_KEY", "")
    sender_email = (
        getattr(settings, "BREVO_SENDER_EMAIL", "")
        or os.environ.get("BREVO_SENDER_EMAIL", "")
        or settings.DEFAULT_FROM_EMAIL
    )
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or os.environ.get(
        "BREVO_SENDER_NAME", ""
    )
    reply_to = getattr(settings, "BREVO_REPLY_TO_EMAIL", "") or os.environ.get(
        "BREVO_REPLY_TO_EMAIL", ""
    )
    return api_key, sender_email, sender_name, reply_to


def _send_with_brevo(*, subject, message, recipients, html_message=None, tags=None):
    api_key, sender_email, sender_name, reply_to = _brevo_settings()
    if not api_key or not sender_email:
        return False
    payload = {
        "sender": {"email": sender_email, "name": sender_name or sender_email},
        "to": [{"email": email} for email in recipients],
        "subject": subject,
        "textContent": message,
    }
    if html_message:
        payload["htmlContent"] = html_message
    if reply_to:
        payload["replyTo"] = {"email": reply_to}
    if tags:
        payload["tags"] = list(tags)
    try:
        request = Request(
            BREVO_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"api-key": api_key, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=10) as response:
            response.read()
        return True
    except (HTTPError, URLError, ValueError) as exc:
        LOGGER.warning("Brevo email failed: %s", exc)
    return False


def send_email_safe(*, subject, message, recipient, html_message=None, tags=None):
    recipients = recipient
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [item for item in recipients if item]
    if not recipients:
        return False
    if _send_with_brevo(
        subject=subject,
        message=message,
        recipients=recipients,
        html_message=html_message,
        tags=tags,
    ):
        return True
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
            html_message=html_message,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("Django send_mail failed: %s", exc)
        return False
    return True
