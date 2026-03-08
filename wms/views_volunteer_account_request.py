from django.conf import settings
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .client_ip import get_client_ip
from .emailing import enqueue_email_safe, get_admin_emails
from .forms_volunteer import VolunteerAccountRequestForm
from .models import VolunteerAccountRequestStatus

TEMPLATE_REQUEST_ACCOUNT = "benevole/request_account.html"
TEMPLATE_REQUEST_ACCOUNT_DONE = "benevole/request_account_done.html"
ADMIN_NOTIFICATION_TEMPLATE = "emails/volunteer_account_request_received.txt"
ADMIN_NOTIFICATION_SUBJECT = _("ASF WMS - Nouvelle demande benevole")
ERROR_THROTTLE_LIMIT = _(
    "Une demande recente a deja ete envoyee. Merci de patienter quelques minutes."
)
REQUEST_THROTTLE_SECONDS_DEFAULT = 300


def _normalize_email(value):
    return (value or "").strip().lower()


def _get_throttle_seconds():
    raw_value = getattr(
        settings,
        "VOLUNTEER_ACCOUNT_REQUEST_THROTTLE_SECONDS",
        REQUEST_THROTTLE_SECONDS_DEFAULT,
    )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return REQUEST_THROTTLE_SECONDS_DEFAULT
    return max(0, value)


def _get_throttle_keys(*, email, client_ip):
    normalized_email = _normalize_email(email)
    normalized_ip = (client_ip or "").strip() or "unknown"
    return (
        f"volunteer-account-request:email:{normalized_email}",
        f"volunteer-account-request:ip:{normalized_ip}",
    )


def _reserve_throttle_slot(*, email, client_ip):
    timeout = _get_throttle_seconds()
    if timeout <= 0:
        return True
    email_key, ip_key = _get_throttle_keys(email=email, client_ip=client_ip)
    email_reserved = cache.add(email_key, "1", timeout=timeout)
    ip_reserved = cache.add(ip_key, "1", timeout=timeout)
    if email_reserved and ip_reserved:
        return True
    if email_reserved and not ip_reserved:
        cache.delete(email_key)
    if ip_reserved and not email_reserved:
        cache.delete(ip_key)
    return False


def _release_throttle_slot(*, email, client_ip):
    timeout = _get_throttle_seconds()
    if timeout <= 0:
        return
    email_key, ip_key = _get_throttle_keys(email=email, client_ip=client_ip)
    cache.delete_many([email_key, ip_key])


def _notify_admins_of_request(*, request, account_request):
    recipients = get_admin_emails()
    if not recipients:
        return False
    message = render_to_string(
        ADMIN_NOTIFICATION_TEMPLATE,
        {
            "account_request": account_request,
            "admin_url": request.build_absolute_uri(
                reverse("admin:wms_volunteeraccountrequest_changelist")
            ),
        },
    )
    return enqueue_email_safe(
        subject=ADMIN_NOTIFICATION_SUBJECT,
        message=message,
        recipient=recipients,
    )


@require_http_methods(["GET", "POST"])
def volunteer_account_request(request):
    if request.method == "POST":
        form = VolunteerAccountRequestForm(request.POST)
        if form.is_valid():
            client_ip = get_client_ip(request)
            email = form.cleaned_data["email"]
            if not _reserve_throttle_slot(email=email, client_ip=client_ip):
                form.add_error(None, ERROR_THROTTLE_LIMIT)
            else:
                try:
                    account_request = form.save(commit=False)
                    account_request.status = VolunteerAccountRequestStatus.PENDING
                    account_request.save()
                except Exception:
                    _release_throttle_slot(email=email, client_ip=client_ip)
                    raise
                _notify_admins_of_request(request=request, account_request=account_request)
                return redirect("volunteer:request_account_done")
    else:
        form = VolunteerAccountRequestForm(initial={"country": "France"})
    return render(request, TEMPLATE_REQUEST_ACCOUNT, {"form": form})


@require_http_methods(["GET"])
def volunteer_account_request_done(request):
    return render(request, TEMPLATE_REQUEST_ACCOUNT_DONE)
