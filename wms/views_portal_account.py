from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .account_request_handlers import handle_account_request_form
from .document_uploads import validate_document_upload
from .models import (
    AccountDocument,
    AccountDocumentType,
    AssociationContactTitle,
    AssociationPortalContact,
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
)
from .portal_helpers import get_contact_address
from .portal_recipient_sync import sync_association_recipient_to_contact
from .scan_helpers import parse_int
from .upload_utils import validate_upload
from .view_permissions import association_required

TEMPLATE_RECIPIENTS = "portal/recipients.html"
TEMPLATE_ACCOUNT = "portal/account.html"

ACTION_CREATE_RECIPIENT = "create_recipient"
ACTION_UPDATE_NOTIFICATIONS = "update_notifications"
ACTION_UPDATE_PROFILE = "update_profile"
ACTION_UPLOAD_ACCOUNT_DOC = "upload_account_doc"
ACTION_UPLOAD_ACCOUNT_DOCS = "upload_account_docs"

DEFAULT_COUNTRY = "France"
MAX_PORTAL_CONTACTS = 10
MESSAGE_RECIPIENT_ADDED = "Destinataire ajouté."
MESSAGE_PROFILE_UPDATED = "Compte mis à jour."
MESSAGE_CONTACTS_UPDATED = "Contacts emails mis à jour."
MESSAGE_DOCUMENT_ADDED = "Document ajouté."
MESSAGE_DOCUMENTS_ADDED = "Documents ajoutés."
ERROR_NO_DOCUMENT_SELECTED = "Aucun fichier sélectionné."
ERROR_RECIPIENT_DESTINATION_REQUIRED = "Escale de livraison requise."
ERROR_RECIPIENT_STRUCTURE_REQUIRED = "Nom de la structure requis."
ERROR_RECIPIENT_ADDRESS_REQUIRED = "Adresse requise."
ERROR_RECIPIENT_TITLE_INVALID = "Titre de contact invalide."
ERROR_RECIPIENT_EMAILS_INVALID = "Emails invalides: {values}."
ERROR_RECIPIENT_NOTIFY_EMAIL_REQUIRED = (
    "Ajoutez au moins un email pour activer l'alerte de livraison."
)
ERROR_ASSOCIATION_NAME_REQUIRED = "Nom de l'association requis."
ERROR_ASSOCIATION_ADDRESS_REQUIRED = "Adresse requise."
ERROR_CONTACT_ROWS_LIMIT = f"Maximum {MAX_PORTAL_CONTACTS} contacts."
ERROR_CONTACT_REQUIRED = "Ajoutez au moins un contact email."
BLOCKED_REASON_PARAM = "blocked"
BLOCKED_REASON_MISSING_DELIVERY_CONTACT = "missing_delivery_contact"
BLOCKED_MESSAGE_MISSING_DELIVERY_CONTACT = (
    "Compte bloqué: ajoutez au moins un destinataire avec la case "
    '"Contact utilisé pour la réception dans l\'escale de livraison" cochée.'
)


def _split_multi_values(value):
    raw = (value or "").replace("\n", ";").replace(",", ";")
    return [item.strip() for item in raw.split(";") if item.strip()]


def _build_default_recipient_form_data():
    return {
        "destination_id": "",
        "structure_name": "",
        "contact_title": "",
        "contact_last_name": "",
        "contact_first_name": "",
        "phones": "",
        "emails": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": DEFAULT_COUNTRY,
        "notes": "",
        "notify_deliveries": False,
        "is_delivery_contact": False,
    }


def _extract_recipient_form_data(post_data):
    return {
        "destination_id": (post_data.get("destination_id") or "").strip(),
        "structure_name": (post_data.get("structure_name") or "").strip(),
        "contact_title": (post_data.get("contact_title") or "").strip(),
        "contact_last_name": (post_data.get("contact_last_name") or "").strip(),
        "contact_first_name": (post_data.get("contact_first_name") or "").strip(),
        "phones": (post_data.get("phones") or "").strip(),
        "emails": (post_data.get("emails") or "").strip(),
        "address_line1": (post_data.get("address_line1") or "").strip(),
        "address_line2": (post_data.get("address_line2") or "").strip(),
        "postal_code": (post_data.get("postal_code") or "").strip(),
        "city": (post_data.get("city") or "").strip(),
        "country": (post_data.get("country") or DEFAULT_COUNTRY).strip(),
        "notes": (post_data.get("notes") or "").strip(),
        "notify_deliveries": bool(post_data.get("notify_deliveries")),
        "is_delivery_contact": bool(post_data.get("is_delivery_contact")),
    }


def _validate_recipient_form_data(form_data, destinations_by_id):
    errors = []
    valid_titles = {choice for choice, _label in AssociationContactTitle.choices}
    if form_data["contact_title"] and form_data["contact_title"] not in valid_titles:
        errors.append(ERROR_RECIPIENT_TITLE_INVALID)

    destination = None
    destination_id = parse_int(form_data["destination_id"])
    if destination_id is None:
        errors.append(ERROR_RECIPIENT_DESTINATION_REQUIRED)
    else:
        destination = destinations_by_id.get(destination_id)
        if destination is None:
            errors.append(ERROR_RECIPIENT_DESTINATION_REQUIRED)
    form_data["destination"] = destination

    if not form_data["structure_name"]:
        errors.append(ERROR_RECIPIENT_STRUCTURE_REQUIRED)
    if not form_data["address_line1"]:
        errors.append(ERROR_RECIPIENT_ADDRESS_REQUIRED)

    email_values = _split_multi_values(form_data["emails"])
    invalid_emails = []
    validator = EmailValidator()
    for value in email_values:
        try:
            validator(value)
        except ValidationError:
            invalid_emails.append(value)
    if invalid_emails:
        errors.append(ERROR_RECIPIENT_EMAILS_INVALID.format(values=", ".join(invalid_emails)))
    if form_data["notify_deliveries"] and not email_values:
        errors.append(ERROR_RECIPIENT_NOTIFY_EMAIL_REQUIRED)

    form_data["email_values"] = email_values
    form_data["phone_values"] = _split_multi_values(form_data["phones"])
    return errors


def _create_recipient(profile, form_data):
    contact_display = " ".join(
        part
        for part in [
            dict(AssociationContactTitle.choices).get(form_data["contact_title"], ""),
            form_data["contact_first_name"],
            (form_data["contact_last_name"] or "").upper(),
        ]
        if part
    ).strip()
    legacy_name = form_data["structure_name"] or contact_display
    primary_email = form_data["email_values"][0] if form_data["email_values"] else ""
    primary_phone = form_data["phone_values"][0] if form_data["phone_values"] else ""
    recipient = AssociationRecipient.objects.create(
        association_contact=profile.contact,
        destination=form_data.get("destination"),
        name=legacy_name,
        structure_name=form_data["structure_name"],
        contact_title=form_data["contact_title"],
        contact_last_name=form_data["contact_last_name"],
        contact_first_name=form_data["contact_first_name"],
        phones="; ".join(form_data["phone_values"]),
        emails="; ".join(form_data["email_values"]),
        email=primary_email,
        phone=primary_phone,
        address_line1=form_data["address_line1"],
        address_line2=form_data["address_line2"],
        postal_code=form_data["postal_code"],
        city=form_data["city"],
        country=form_data["country"] or DEFAULT_COUNTRY,
        notes=form_data["notes"],
        notify_deliveries=form_data["notify_deliveries"],
        is_delivery_contact=form_data["is_delivery_contact"],
    )
    sync_association_recipient_to_contact(recipient)


def _get_active_recipients(profile):
    return (
        AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
        )
        .select_related("destination")
        .order_by("structure_name", "name", "contact_last_name", "contact_first_name")
    )


def _handle_notification_update(request, profile):
    profile.notification_emails = (request.POST.get("notification_emails") or "").strip()
    profile.save(update_fields=["notification_emails"])
    messages.success(request, MESSAGE_CONTACTS_UPDATED)
    return redirect("portal:portal_account")


def _handle_account_document_upload(request, association):
    payload, error = validate_document_upload(
        request,
        doc_type_choices=AccountDocumentType.choices,
    )
    if error:
        messages.error(request, error)
        return redirect("portal:portal_account")

    doc_type, uploaded = payload
    AccountDocument.objects.create(
        association_contact=association,
        doc_type=doc_type,
        status=DocumentReviewStatus.PENDING,
        file=uploaded,
        uploaded_by=request.user,
    )
    messages.success(request, MESSAGE_DOCUMENT_ADDED)
    return redirect("portal:portal_account")


def _build_profile_form_data(*, association, address):
    return {
        "association_name": association.name or "",
        "association_email": association.email or "",
        "association_phone": association.phone or "",
        "address_line1": address.address_line1 if address else "",
        "address_line2": address.address_line2 if address else "",
        "postal_code": address.postal_code if address else "",
        "city": address.city if address else "",
        "country": (address.country if address else "") or DEFAULT_COUNTRY,
    }


def _build_default_contact_row(*, index):
    return {
        "index": index,
        "title": "",
        "last_name": "",
        "first_name": "",
        "phone": "",
        "email": "",
        "is_administrative": False,
        "is_shipping": False,
        "is_billing": False,
    }


def _build_contact_rows(profile):
    contacts = list(profile.portal_contacts.filter(is_active=True))
    if not contacts:
        return [_build_default_contact_row(index=0)]
    rows = []
    for index, contact in enumerate(contacts[:MAX_PORTAL_CONTACTS]):
        rows.append(
            {
                "index": index,
                "title": contact.title or "",
                "last_name": contact.last_name or "",
                "first_name": contact.first_name or "",
                "phone": contact.phone or "",
                "email": contact.email or "",
                "is_administrative": contact.is_administrative,
                "is_shipping": contact.is_shipping,
                "is_billing": contact.is_billing,
            }
        )
    return rows or [_build_default_contact_row(index=0)]


def _extract_profile_form_data(post_data):
    return {
        "association_name": (post_data.get("association_name") or "").strip(),
        "association_email": (post_data.get("association_email") or "").strip(),
        "association_phone": (post_data.get("association_phone") or "").strip(),
        "address_line1": (post_data.get("address_line1") or "").strip(),
        "address_line2": (post_data.get("address_line2") or "").strip(),
        "postal_code": (post_data.get("postal_code") or "").strip(),
        "city": (post_data.get("city") or "").strip(),
        "country": (post_data.get("country") or DEFAULT_COUNTRY).strip(),
    }


def _extract_contact_rows(post_data):
    errors = []
    requested_count = parse_int(post_data.get("contact_count")) or 1
    if requested_count > MAX_PORTAL_CONTACTS:
        errors.append(ERROR_CONTACT_ROWS_LIMIT)
    count = min(max(1, requested_count), MAX_PORTAL_CONTACTS)
    rows = []
    for index in range(count):
        row = {
            "index": index,
            "title": (post_data.get(f"contact_{index}_title") or "").strip(),
            "last_name": (post_data.get(f"contact_{index}_last_name") or "").strip(),
            "first_name": (post_data.get(f"contact_{index}_first_name") or "").strip(),
            "phone": (post_data.get(f"contact_{index}_phone") or "").strip(),
            "email": (post_data.get(f"contact_{index}_email") or "").strip(),
            "is_administrative": bool(post_data.get(f"contact_{index}_is_administrative")),
            "is_shipping": bool(post_data.get(f"contact_{index}_is_shipping")),
            "is_billing": bool(post_data.get(f"contact_{index}_is_billing")),
        }
        has_values = any(
            [
                row["title"],
                row["last_name"],
                row["first_name"],
                row["phone"],
                row["email"],
                row["is_administrative"],
                row["is_shipping"],
                row["is_billing"],
            ]
        )
        if not has_values:
            continue
        if not row["email"]:
            errors.append(f"Ligne {index + 1}: email requis.")
        if not (
            row["is_administrative"] or row["is_shipping"] or row["is_billing"]
        ):
            errors.append(f"Ligne {index + 1}: cochez au moins un type.")
        rows.append(row)

    if not rows:
        errors.append(ERROR_CONTACT_REQUIRED)
        rows = [_build_default_contact_row(index=0)]
    return rows, errors


def _validate_profile_form_data(form_data):
    errors = []
    if not form_data["association_name"]:
        errors.append(ERROR_ASSOCIATION_NAME_REQUIRED)
    if not form_data["address_line1"]:
        errors.append(ERROR_ASSOCIATION_ADDRESS_REQUIRED)
    return errors


def _sync_notification_emails_from_contacts(profile, rows):
    emails = []
    seen = set()
    for row in rows:
        value = (row.get("email") or "").strip()
        if not value:
            continue
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        emails.append(value)
    profile.notification_emails = ",".join(emails)


def _save_profile_updates(*, request, profile, form_data, contact_rows):
    association = profile.contact
    address = get_contact_address(association)

    with transaction.atomic():
        contact_updates = []
        if association.name != form_data["association_name"]:
            association.name = form_data["association_name"]
            contact_updates.append("name")
        if association.email != form_data["association_email"]:
            association.email = form_data["association_email"]
            contact_updates.append("email")
        if association.phone != form_data["association_phone"]:
            association.phone = form_data["association_phone"]
            contact_updates.append("phone")
        if contact_updates:
            association.save(update_fields=contact_updates)

        if not address:
            address = association.addresses.create(
                address_line1=form_data["address_line1"],
                address_line2=form_data["address_line2"],
                postal_code=form_data["postal_code"],
                city=form_data["city"],
                country=form_data["country"] or DEFAULT_COUNTRY,
                phone=form_data["association_phone"],
                email=form_data["association_email"],
                is_default=True,
            )
        else:
            address_updates = []
            if address.address_line1 != form_data["address_line1"]:
                address.address_line1 = form_data["address_line1"]
                address_updates.append("address_line1")
            if address.address_line2 != form_data["address_line2"]:
                address.address_line2 = form_data["address_line2"]
                address_updates.append("address_line2")
            if address.postal_code != form_data["postal_code"]:
                address.postal_code = form_data["postal_code"]
                address_updates.append("postal_code")
            if address.city != form_data["city"]:
                address.city = form_data["city"]
                address_updates.append("city")
            country = form_data["country"] or DEFAULT_COUNTRY
            if address.country != country:
                address.country = country
                address_updates.append("country")
            if address.phone != form_data["association_phone"]:
                address.phone = form_data["association_phone"]
                address_updates.append("phone")
            if address.email != form_data["association_email"]:
                address.email = form_data["association_email"]
                address_updates.append("email")
            if address_updates:
                address.save(update_fields=address_updates)

        user = request.user
        if form_data["association_email"] and user.email != form_data["association_email"]:
            user.email = form_data["association_email"]
            user.save(update_fields=["email"])

        profile.portal_contacts.all().delete()
        for index, row in enumerate(contact_rows):
            AssociationPortalContact.objects.create(
                profile=profile,
                position=index,
                title=row["title"],
                last_name=row["last_name"],
                first_name=row["first_name"],
                phone=row["phone"],
                email=row["email"],
                is_administrative=row["is_administrative"],
                is_shipping=row["is_shipping"],
                is_billing=row["is_billing"],
                is_active=True,
            )

        _sync_notification_emails_from_contacts(profile, contact_rows)
        profile.save(update_fields=["notification_emails"])


def _handle_account_document_uploads(request, association):
    created = 0
    for doc_type, _label in AccountDocumentType.choices:
        file_field = f"doc_file_{doc_type}"
        uploaded = request.FILES.get(file_field)
        if not uploaded:
            continue
        validation_error = validate_upload(uploaded)
        if validation_error:
            messages.error(request, validation_error)
            continue
        AccountDocument.objects.create(
            association_contact=association,
            doc_type=doc_type,
            status=DocumentReviewStatus.PENDING,
            file=uploaded,
            uploaded_by=request.user,
        )
        created += 1
    if not created:
        messages.error(request, ERROR_NO_DOCUMENT_SELECTED)
        return redirect("portal:portal_account")
    messages.success(request, MESSAGE_DOCUMENTS_ADDED)
    return redirect("portal:portal_account")


def _build_portal_account_context(
    *,
    profile,
    address,
    user,
    account_form_errors=None,
    profile_form_data=None,
    portal_contact_rows=None,
):
    association = profile.contact
    account_documents = AccountDocument.objects.filter(
        association_contact=association
    ).order_by("-uploaded_at")
    return {
        "association": association,
        "address": address,
        "notification_emails": profile.notification_emails,
        "account_documents": account_documents,
        "account_doc_types": list(AccountDocumentType.choices),
        "account_form_errors": account_form_errors or [],
        "profile_form_data": profile_form_data
        or _build_profile_form_data(association=association, address=address),
        "portal_contact_rows": portal_contact_rows or _build_contact_rows(profile),
        "contact_title_choices": list(AssociationContactTitle.choices),
        "max_portal_contacts": MAX_PORTAL_CONTACTS,
        "user": user,
    }


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_recipients(request):
    profile = request.association_profile
    errors = []
    form_data = _build_default_recipient_form_data()
    destinations = list(Destination.objects.filter(is_active=True).order_by("city"))
    destinations_by_id = {destination.id: destination for destination in destinations}
    blocked_reason = (request.GET.get(BLOCKED_REASON_PARAM) or "").strip()
    blocked_popup_message = ""
    if blocked_reason == BLOCKED_REASON_MISSING_DELIVERY_CONTACT:
        blocked_popup_message = BLOCKED_MESSAGE_MISSING_DELIVERY_CONTACT

    if request.method == "POST" and request.POST.get("action") == ACTION_CREATE_RECIPIENT:
        form_data = _extract_recipient_form_data(request.POST)
        errors = _validate_recipient_form_data(form_data, destinations_by_id)
        if not errors:
            _create_recipient(profile, form_data)
            messages.success(request, MESSAGE_RECIPIENT_ADDED)
            return redirect("portal:portal_recipients")

    recipients = _get_active_recipients(profile)
    return render(
        request,
        TEMPLATE_RECIPIENTS,
        {
            "recipients": recipients,
            "errors": errors,
            "form_data": form_data,
            "destinations": destinations,
            "contact_title_choices": list(AssociationContactTitle.choices),
            "blocked_popup_message": blocked_popup_message,
        },
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_account(request):
    profile = request.association_profile
    association = profile.contact
    address = get_contact_address(association)
    account_form_errors = []
    profile_form_data = _build_profile_form_data(association=association, address=address)
    portal_contact_rows = _build_contact_rows(profile)

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == ACTION_UPDATE_PROFILE:
            profile_form_data = _extract_profile_form_data(request.POST)
            portal_contact_rows, contact_errors = _extract_contact_rows(request.POST)
            account_form_errors = _validate_profile_form_data(profile_form_data)
            account_form_errors.extend(contact_errors)
            if not account_form_errors:
                _save_profile_updates(
                    request=request,
                    profile=profile,
                    form_data=profile_form_data,
                    contact_rows=portal_contact_rows,
                )
                messages.success(request, MESSAGE_PROFILE_UPDATED)
                return redirect("portal:portal_account")
        elif action == ACTION_UPDATE_NOTIFICATIONS:
            return _handle_notification_update(request, profile)
        elif action == ACTION_UPLOAD_ACCOUNT_DOCS:
            return _handle_account_document_uploads(request, association)
        elif action == ACTION_UPLOAD_ACCOUNT_DOC:
            return _handle_account_document_upload(request, association)

    return render(
        request,
        TEMPLATE_ACCOUNT,
        _build_portal_account_context(
            profile=profile,
            address=address,
            user=request.user,
            account_form_errors=account_form_errors,
            profile_form_data=profile_form_data,
            portal_contact_rows=portal_contact_rows,
        ),
    )


@require_http_methods(["GET", "POST"])
def portal_account_request(request):
    return handle_account_request_form(
        request,
        link=None,
        redirect_url=reverse("portal:portal_account_request"),
    )
