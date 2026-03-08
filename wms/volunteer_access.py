from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _

from .emailing import enqueue_email_safe

VOLUNTEER_ACCESS_EMAIL_TEMPLATE = "emails/volunteer_access_created.txt"
VOLUNTEER_ACCESS_EMAIL_SUBJECT = _("ASF WMS - Acces benevole")


def _volunteer_paths(*, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return (
        reverse("volunteer:login"),
        reverse("volunteer:set_password", args=[uid, token]),
    )


def build_volunteer_urls(*, request, user):
    login_path, set_password_path = _volunteer_paths(user=user)
    return (
        request.build_absolute_uri(login_path),
        request.build_absolute_uri(set_password_path),
    )


def build_volunteer_urls_from_base_url(*, site_base_url, user):
    login_path, set_password_path = _volunteer_paths(user=user)
    base_url = (site_base_url or "").strip().rstrip("/")
    if not base_url:
        return login_path, set_password_path, False
    return (
        f"{base_url}{login_path}",
        f"{base_url}{set_password_path}",
        True,
    )


def send_volunteer_access_email(
    *,
    request,
    user,
    email=None,
    enqueue_email=enqueue_email_safe,
    url_builder=build_volunteer_urls,
):
    recipient_email = (email or user.email or "").strip()
    if not recipient_email:
        return False
    login_url, set_password_url = url_builder(request=request, user=user)
    message = render_to_string(
        VOLUNTEER_ACCESS_EMAIL_TEMPLATE,
        {
            "email": recipient_email,
            "login_url": login_url,
            "set_password_url": set_password_url,
            "user": user,
        },
    )
    return enqueue_email(
        subject=VOLUNTEER_ACCESS_EMAIL_SUBJECT,
        message=message,
        recipient=[recipient_email],
    )
