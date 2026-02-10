from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from contacts.models import Contact, ContactAddress, ContactTag

from . import models
from .contact_filters import TAG_SHIPPER

ACCOUNT_ACCESS_PENDING = "Disponible apres validation."
ACCOUNT_ACCESS_USER_NOT_FOUND = "Utilisateur introuvable."
ACCOUNT_ACCESS_MISSING_BASE_URL = (
    "SITE_BASE_URL non configuree, utiliser l'URL du site."
)


def _portal_paths(*, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return (
        reverse("portal:portal_login"),
        reverse("portal:portal_set_password", args=[uid, token]),
    )


def build_portal_urls(*, request, user):
    login_path, set_password_path = _portal_paths(user=user)
    return (
        request.build_absolute_uri(login_path),
        request.build_absolute_uri(set_password_path),
    )


def build_portal_urls_from_base_url(*, site_base_url, user):
    login_path, set_password_path = _portal_paths(user=user)
    base_url = (site_base_url or "").strip().rstrip("/")
    if not base_url:
        return login_path, set_password_path, False
    return (
        f"{base_url}{login_path}",
        f"{base_url}{set_password_path}",
        True,
    )


def approve_account_request(
    *,
    request,
    account_request,
    enqueue_email,
    portal_url_builder=build_portal_urls,
):
    user_model = get_user_model()
    user = user_model.objects.filter(email__iexact=account_request.email).first()
    if user and (user.is_staff or user.is_superuser):
        return False, "email reserve"

    with transaction.atomic():
        contact = account_request.contact
        if not contact:
            contact = Contact.objects.create(
                name=account_request.association_name,
                email=account_request.email,
                phone=account_request.phone,
                is_active=True,
            )
            account_request.contact = contact
        tag, _ = ContactTag.objects.get_or_create(name=TAG_SHIPPER[0])
        contact.tags.add(tag)

        contact_updates = []
        if account_request.email and contact.email != account_request.email:
            contact.email = account_request.email
            contact_updates.append("email")
        if account_request.phone and contact.phone != account_request.phone:
            contact.phone = account_request.phone
            contact_updates.append("phone")
        if contact_updates:
            contact.save(update_fields=contact_updates)

        address = (
            contact.get_effective_address()
            if hasattr(contact, "get_effective_address")
            else contact.addresses.filter(is_default=True).first()
            or contact.addresses.first()
        )
        if not address:
            ContactAddress.objects.create(
                contact=contact,
                address_line1=account_request.address_line1,
                address_line2=account_request.address_line2,
                postal_code=account_request.postal_code,
                city=account_request.city,
                country=account_request.country or "France",
                phone=account_request.phone,
                email=account_request.email,
                is_default=True,
            )

        if not user:
            user = user_model.objects.create_user(
                username=account_request.email,
                email=account_request.email,
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

        profile, created = models.AssociationProfile.objects.get_or_create(
            user=user,
            defaults={"contact": contact},
        )
        if not created and profile.contact_id != contact.id:
            profile.contact = contact
        profile.must_change_password = True
        profile.save(update_fields=["contact", "must_change_password"])

        models.AccountDocument.objects.filter(
            account_request=account_request,
            association_contact__isnull=True,
        ).update(association_contact=contact)

        account_request.status = models.PublicAccountRequestStatus.APPROVED
        account_request.reviewed_at = timezone.now()
        account_request.reviewed_by = request.user
        account_request.save(
            update_fields=["status", "reviewed_at", "reviewed_by", "contact"]
        )

    login_url, set_password_url = portal_url_builder(request=request, user=user)
    message = render_to_string(
        "emails/account_request_approved.txt",
        {
            "association_name": contact.name,
            "email": account_request.email,
            "set_password_url": set_password_url,
            "login_url": login_url,
        },
    )
    enqueue_email(
        subject="ASF WMS - Compte valide",
        message=message,
        recipient=[account_request.email],
    )
    return True, ""


def build_account_access_lines(*, account_request, site_base_url):
    if (
        not account_request
        or account_request.status != models.PublicAccountRequestStatus.APPROVED
    ):
        return None, ACCOUNT_ACCESS_PENDING

    user = get_user_model().objects.filter(email__iexact=account_request.email).first()
    if not user:
        return None, ACCOUNT_ACCESS_USER_NOT_FOUND

    login_url, set_password_url, has_base_url = build_portal_urls_from_base_url(
        site_base_url=site_base_url,
        user=user,
    )
    lines = [
        f"Email: {account_request.email or '-'}",
        f"Login: {login_url}",
        f"Lien definir mot de passe: {set_password_url}",
    ]
    if not has_base_url:
        lines.append(ACCOUNT_ACCESS_MISSING_BASE_URL)
    return lines, None
