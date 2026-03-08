from django.contrib.auth import get_user_model
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from .emailing import enqueue_email_safe
from .models import VolunteerAccountRequestStatus, VolunteerProfile
from .volunteer_access import build_volunteer_urls

VOLUNTEER_ACCOUNT_APPROVED_TEMPLATE = "emails/volunteer_account_approved.txt"
VOLUNTEER_ACCOUNT_APPROVED_SUBJECT = _("ASF WMS - Demande benevole approuvee")


def describe_volunteer_account_request_skip_reason(reason):
    reason_labels = {
        "email reserve": _("email reserve"),
    }
    return reason_labels.get(reason, reason)


def approve_volunteer_account_request(
    *,
    request,
    account_request,
    enqueue_email=enqueue_email_safe,
    url_builder=build_volunteer_urls,
):
    user_model = get_user_model()
    existing_user = user_model.objects.filter(email__iexact=account_request.email).first()
    if existing_user and (existing_user.is_staff or existing_user.is_superuser):
        return False, "email reserve"

    with transaction.atomic():
        user = existing_user
        if not user:
            user = user_model.objects.create_user(
                username=account_request.email,
                email=account_request.email,
                first_name=account_request.first_name,
                last_name=account_request.last_name,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

        user_updates = []
        if user.username != account_request.email:
            user.username = account_request.email
            user_updates.append("username")
        if user.email != account_request.email:
            user.email = account_request.email
            user_updates.append("email")
        if account_request.first_name and user.first_name != account_request.first_name:
            user.first_name = account_request.first_name
            user_updates.append("first_name")
        if user.last_name != account_request.last_name:
            user.last_name = account_request.last_name
            user_updates.append("last_name")
        if not user.is_active:
            user.is_active = True
            user_updates.append("is_active")
        if user_updates:
            user.save(update_fields=user_updates)

        profile, _created = VolunteerProfile.objects.get_or_create(user=user)
        profile.phone = account_request.phone
        profile.address_line1 = account_request.address_line1
        profile.postal_code = account_request.postal_code
        profile.city = account_request.city
        profile.country = account_request.country
        if account_request.first_name:
            profile.short_name = account_request.first_name[:30]
        profile.geo_latitude = account_request.geo_latitude
        profile.geo_longitude = account_request.geo_longitude
        profile.is_active = True
        profile.must_change_password = True
        profile.save()

        account_request.status = VolunteerAccountRequestStatus.APPROVED
        account_request.reviewed_at = timezone.now()
        account_request.reviewed_by = request.user
        account_request.save(update_fields=["status", "reviewed_at", "reviewed_by"])

    login_url, set_password_url = url_builder(request=request, user=user)
    message = render_to_string(
        VOLUNTEER_ACCOUNT_APPROVED_TEMPLATE,
        {
            "email": account_request.email,
            "first_name": account_request.first_name,
            "login_url": login_url,
            "set_password_url": set_password_url,
        },
    )
    enqueue_email(
        subject=VOLUNTEER_ACCOUNT_APPROVED_SUBJECT,
        message=message,
        recipient=[account_request.email],
    )
    return True, ""
