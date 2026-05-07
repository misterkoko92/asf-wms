from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import models
from .account_request_review_service import (
    apply_review_payload_to_account_request,
    build_account_request_review_payload,
    ensure_review_organization_contact,
    provision_recipient_review_runtime,
    resolve_review_destination,
)
from .application.parties.use_cases import (
    update_recipient_shared_profile,
    upsert_recipient_structure_documents,
)
from .default_shipper_bindings import _resolve_default_shipper
from .portal_permissions import assign_association_portal_group
from .shipment_party_setup import ensure_shipment_shipper

ACCOUNT_ACCESS_PENDING = gettext_lazy("Disponible après validation.")
ACCOUNT_ACCESS_USER_NOT_FOUND = gettext_lazy("Utilisateur introuvable.")
ACCOUNT_ACCESS_MISSING_BASE_URL = gettext_lazy(
    "SITE_BASE_URL non configurée, utiliser l'URL du site."
)
INITIAL_RECIPIENT_DOCUMENT_TYPE_MAP = {
    models.AccountDocumentType.REGISTRATION_PROOF: models.RecipientStructureDocumentType.REGISTRATION_PROOF,
    models.AccountDocumentType.STATUTES: models.RecipientStructureDocumentType.STATUTES,
}


def describe_account_request_skip_reason(reason):
    reason_labels = {
        "email reserve": _("email reserve"),
        "username manquant": _("username manquant"),
        "username reserve": _("username reserve"),
        "destination manquante": _("destination manquante"),
        "expediteur ASF manquant": _("expediteur ASF manquant"),
    }
    return reason_labels.get(reason, reason)


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


def _ensure_portal_user(*, user_model, existing_user, account_request):
    user = existing_user
    if not user:
        user = user_model.objects.create_user(
            username=account_request.email,
            email=account_request.email,
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
    if not user.is_active:
        user.is_active = True
        user_updates.append("is_active")
    if user_updates:
        user.save(update_fields=user_updates)
    return user


def _initial_recipient_payload(account_request) -> dict:
    payload = getattr(account_request, "initial_recipient_payload", None) or {}
    return payload if isinstance(payload, dict) else {}


def _initial_recipient_document_files(account_request) -> dict:
    files_by_type = {}
    documents = (
        account_request.documents.filter(
            document_scope=models.AccountDocumentScope.INITIAL_RECIPIENT,
            doc_type__in=INITIAL_RECIPIENT_DOCUMENT_TYPE_MAP,
        )
        .exclude(file="")
        .order_by("id")
    )
    for document in documents:
        recipient_doc_type = INITIAL_RECIPIENT_DOCUMENT_TYPE_MAP.get(document.doc_type)
        if recipient_doc_type:
            files_by_type[recipient_doc_type] = document.file
    return files_by_type


def _provision_initial_recipient_documents(*, contact, account_request):
    files_by_type = _initial_recipient_document_files(account_request)
    if not files_by_type:
        return []
    return upsert_recipient_structure_documents(
        contact=contact,
        files_by_type=files_by_type,
        uploaded_by=getattr(account_request, "reviewed_by", None),
        queue_scan=True,
    )


def _provision_initial_delivery_recipient(*, shipper_contact, account_request):
    payload = _initial_recipient_payload(account_request)
    if not payload:
        return None

    destination = models.Destination.objects.filter(
        pk=payload.get("destination_id"),
        is_active=True,
    ).first()
    if destination is None:
        return None

    result = update_recipient_shared_profile(
        association_contact=shipper_contact,
        destination=destination,
        structure_name=payload.get("structure_name", ""),
        contact_first_name=payload.get("contact_first_name", ""),
        contact_last_name=payload.get("contact_last_name", ""),
        emails=payload.get("email", ""),
        phones=payload.get("phone", ""),
        address_line1=payload.get("address_line1", ""),
        address_line2=payload.get("address_line2", ""),
        postal_code=payload.get("postal_code", ""),
        city=payload.get("city", ""),
        country=payload.get("country", "") or "France",
        legal_form=payload.get("legal_form", ""),
        beneficiary_count=payload.get("beneficiary_count"),
        notes=payload.get("notes", ""),
        notify_deliveries=False,
        is_delivery_contact=True,
        persist_projection=True,
        prefer_existing_structure=True,
        set_as_default=True,
    )
    recipient_organization = result.recipient_organization
    if recipient_organization.validation_status != models.ShipmentValidationStatus.REJECTED:
        recipient_organization.validation_status = models.ShipmentValidationStatus.VALIDATED
        recipient_organization.save(update_fields=["validation_status"])
    _provision_initial_recipient_documents(
        contact=result.synced_contact,
        account_request=account_request,
    )
    return result


def approve_account_request(
    *,
    request,
    account_request,
    enqueue_email,
    portal_url_builder=build_portal_urls,
    review_overrides=None,
):
    original_account_type = account_request.account_type
    payload = build_account_request_review_payload(
        account_request=account_request,
        review_overrides=review_overrides,
    )
    review_update_fields = apply_review_payload_to_account_request(
        account_request=account_request,
        payload=payload,
    )
    review_update_fields = list(dict.fromkeys(review_update_fields))
    user_model = get_user_model()
    existing_user = user_model.objects.filter(email__iexact=account_request.email).first()
    if existing_user and (existing_user.is_staff or existing_user.is_superuser):
        return False, "email reserve"
    is_recipient_request = payload.final_account_type == models.PublicAccountRequestType.RECIPIENT
    was_recipient_request = original_account_type == models.PublicAccountRequestType.RECIPIENT

    if account_request.account_type == models.PublicAccountRequestType.USER:
        requested_username = (
            account_request.requested_username or account_request.email or ""
        ).strip()
        if not requested_username:
            return False, "username manquant"

        username_reserved = user_model.objects.filter(username__iexact=requested_username).exclude(
            email__iexact=account_request.email
        )
        if username_reserved.exists():
            return False, "username reserve"

        with transaction.atomic():
            user = existing_user
            if not user:
                user = user_model.objects.create_user(
                    username=requested_username,
                    email=account_request.email,
                )
            user_updates = []
            if user.username != requested_username:
                user.username = requested_username
                user_updates.append("username")
            if user.email != account_request.email:
                user.email = account_request.email
                user_updates.append("email")
            if not user.is_active:
                user.is_active = True
                user_updates.append("is_active")
            if not user.is_staff:
                user.is_staff = True
                user_updates.append("is_staff")
            if account_request.requested_password_hash:
                user.password = account_request.requested_password_hash
                user_updates.append("password")
            if user_updates:
                user.save(update_fields=user_updates)

            account_request.status = models.PublicAccountRequestStatus.APPROVED
            account_request.reviewed_at = timezone.now()
            account_request.reviewed_by = request.user
            account_request.save(
                update_fields=list(
                    dict.fromkeys(
                        [
                            *review_update_fields,
                            "status",
                            "reviewed_at",
                            "reviewed_by",
                        ]
                    )
                )
            )

        login_url = request.build_absolute_uri(reverse("admin:login"))
        message = render_to_string(
            "emails/account_request_approved_user.txt",
            {
                "requested_username": requested_username,
                "email": account_request.email,
                "login_url": login_url,
            },
        )
        enqueue_email(
            subject=_("ASF WMS - Compte utilisateur valide"),
            message=message,
            recipient=[account_request.email],
        )
        return True, ""

    if is_recipient_request:
        review_destination = resolve_review_destination(payload)
        if review_destination is None:
            return False, "destination manquante"
        if was_recipient_request and _resolve_default_shipper() is None:
            return False, "expediteur ASF manquant"

    user = existing_user
    with transaction.atomic():
        contact = ensure_review_organization_contact(
            account_request=account_request,
            payload=payload,
        )
        account_request.contact = contact
        user = _ensure_portal_user(
            user_model=user_model,
            existing_user=user,
            account_request=account_request,
        )
        account_request.status = models.PublicAccountRequestStatus.APPROVED
        account_request.reviewed_at = timezone.now()
        account_request.reviewed_by = request.user

        if is_recipient_request:
            contact = provision_recipient_review_runtime(
                request_user=request.user,
                account_request=account_request,
                user=user,
                payload=payload,
            )
            account_request.contact = contact
        else:
            profile, created = models.AssociationProfile.objects.get_or_create(
                user=user,
                defaults={"contact": contact},
            )
            if not created and profile.contact_id != contact.id:
                profile.contact = contact
            profile.must_change_password = True
            profile.save(update_fields=["contact", "must_change_password"])
            assign_association_portal_group(user)
            ensure_shipment_shipper(contact)
            _provision_initial_delivery_recipient(
                shipper_contact=contact,
                account_request=account_request,
            )

        models.AccountDocument.objects.filter(
            account_request=account_request,
            association_contact__isnull=True,
            document_scope=models.AccountDocumentScope.ACCOUNT,
        ).update(association_contact=contact)

        account_request.save(
            update_fields=list(
                dict.fromkeys(
                    [
                        *review_update_fields,
                        "status",
                        "reviewed_at",
                        "reviewed_by",
                        "contact",
                    ]
                )
            )
        )

    login_url, set_password_url = portal_url_builder(request=request, user=user)
    message = render_to_string(
        "emails/account_request_approved.txt",
        {
            "association_name": contact.name,
            "account_type": account_request.account_type,
            "email": account_request.email,
            "set_password_url": set_password_url,
            "login_url": login_url,
        },
    )
    enqueue_email(
        subject=_("ASF WMS - Compte valide"),
        message=message,
        recipient=[account_request.email],
    )
    return True, ""


def build_account_access_lines(*, account_request, site_base_url):
    if not account_request or account_request.status != models.PublicAccountRequestStatus.APPROVED:
        return None, ACCOUNT_ACCESS_PENDING

    user = get_user_model().objects.filter(email__iexact=account_request.email).first()
    if not user:
        return None, ACCOUNT_ACCESS_USER_NOT_FOUND

    if account_request.account_type == models.PublicAccountRequestType.USER:
        base_url = (site_base_url or "").strip().rstrip("/")
        login_path = reverse("admin:login")
        has_base_url = bool(base_url)
        login_url = f"{base_url}{login_path}" if has_base_url else login_path
        lines = [
            _("Profil: Utilisateur WMS"),
            _("Nom d'utilisateur: %(username)s") % {"username": user.username or "-"},
            _("Email: %(email)s") % {"email": account_request.email or "-"},
            _("Login: %(url)s") % {"url": login_url},
            _("Mot de passe: defini par l'utilisateur lors de la demande."),
        ]
    else:
        login_url, set_password_url, has_base_url = build_portal_urls_from_base_url(
            site_base_url=site_base_url,
            user=user,
        )
        profile_label = _("Profil: Association")
        if account_request.account_type == models.PublicAccountRequestType.SHIPPER:
            profile_label = _("Profil: Expediteur")
        elif account_request.account_type == models.PublicAccountRequestType.RECIPIENT:
            profile_label = _("Profil: Destinataire")
        lines = [
            profile_label,
            _("Email: %(email)s") % {"email": account_request.email or "-"},
            _("Login: %(url)s") % {"url": login_url},
            _("Lien definir mot de passe: %(url)s") % {"url": set_password_url},
        ]
    if not has_base_url:
        lines.append(ACCOUNT_ACCESS_MISSING_BASE_URL)
    return lines, None
