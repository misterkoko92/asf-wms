import logging

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from contacts.models import Contact

from .contact_payloads import build_shipper_contact_payload
from .emailing import enqueue_email_safe, get_admin_emails
from .models import (
    AccountDocument,
    AccountDocumentType,
    DocumentReviewStatus,
    PublicAccountRequest,
    PublicAccountRequestStatus,
)
from .portal_helpers import build_public_base_url
from .scan_helpers import parse_int
from .upload_utils import validate_upload

LOGGER = logging.getLogger(__name__)
ACCOUNT_REQUEST_THROTTLE_SECONDS_DEFAULT = 300
DEFAULT_COUNTRY = "France"

TEMPLATE_PUBLIC_ACCOUNT_REQUEST = "scan/public_account_request.html"
ADMIN_PUBLIC_ACCOUNT_REQUEST_CHANGE_LIST = "admin:wms_publicaccountrequest_changelist"

ERROR_ASSOCIATION_NAME_REQUIRED = "Nom de l'association requis."
ERROR_EMAIL_REQUIRED = "Email requis."
ERROR_ADDRESS_REQUIRED = "Adresse requise."
ERROR_PENDING_REQUEST_EXISTS = "Une demande est deja en attente pour cet email."
ERROR_THROTTLE_LIMIT = (
    "Une demande recente a deja ete envoyee. Merci de patienter quelques minutes."
)

SUCCESS_ACCOUNT_REQUEST_SENT = "Demande envoyee. Un superuser ASF validera votre compte."

DOC_UPLOAD_FIELD_MAPPINGS = (
    (AccountDocumentType.STATUTES, "doc_statutes"),
    (AccountDocumentType.REGISTRATION_PROOF, "doc_registration"),
    (AccountDocumentType.ACTIVITY_REPORT, "doc_report"),
)


def _build_account_request_form_defaults():
    return {
        "association_name": "",
        "email": "",
        "phone": "",
        "line1": "",
        "line2": "",
        "postal_code": "",
        "city": "",
        "country": DEFAULT_COUNTRY,
        "notes": "",
        "contact_id": "",
    }


def _extract_account_request_form_data(post_data):
    return {
        "association_name": (post_data.get("association_name") or "").strip(),
        "email": (post_data.get("email") or "").strip(),
        "phone": (post_data.get("phone") or "").strip(),
        "line1": (post_data.get("line1") or "").strip(),
        "line2": (post_data.get("line2") or "").strip(),
        "postal_code": (post_data.get("postal_code") or "").strip(),
        "city": (post_data.get("city") or "").strip(),
        "country": (post_data.get("country") or DEFAULT_COUNTRY).strip(),
        "notes": (post_data.get("notes") or "").strip(),
        "contact_id": (post_data.get("contact_id") or "").strip(),
    }


def _append_required_field_errors(form_data, errors):
    if not form_data["association_name"]:
        errors.append(ERROR_ASSOCIATION_NAME_REQUIRED)
    if not form_data["email"]:
        errors.append(ERROR_EMAIL_REQUIRED)
    if not form_data["line1"]:
        errors.append(ERROR_ADDRESS_REQUIRED)


def _collect_account_request_uploads(files, errors):
    uploads = []

    for doc_type, field_name in DOC_UPLOAD_FIELD_MAPPINGS:
        file_obj = files.get(field_name)
        if not file_obj:
            continue
        validation_error = validate_upload(file_obj)
        if validation_error:
            errors.append(validation_error)
            continue
        uploads.append((doc_type, file_obj))

    for file_obj in files.getlist("doc_other"):
        if not file_obj:
            continue
        validation_error = validate_upload(file_obj)
        if validation_error:
            errors.append(validation_error)
            continue
        uploads.append((AccountDocumentType.OTHER, file_obj))

    return uploads


def _has_pending_request_for_email(email):
    return PublicAccountRequest.objects.filter(
        email__iexact=email,
        status=PublicAccountRequestStatus.PENDING,
    ).exists()


def _resolve_account_request_contact(form_data):
    contact = None
    contact_id = parse_int(form_data["contact_id"])
    if contact_id:
        contact = Contact.objects.filter(id=contact_id, is_active=True).first()
    if contact:
        return contact
    return Contact.objects.filter(
        name__iexact=form_data["association_name"],
        is_active=True,
    ).first()


def _create_account_request(*, link, contact, form_data):
    return PublicAccountRequest.objects.create(
        link=link,
        contact=contact,
        association_name=form_data["association_name"],
        email=form_data["email"],
        phone=form_data["phone"],
        address_line1=form_data["line1"],
        address_line2=form_data["line2"],
        postal_code=form_data["postal_code"],
        city=form_data["city"],
        country=form_data["country"] or DEFAULT_COUNTRY,
        notes=form_data["notes"],
    )


def _create_account_request_documents(*, account_request, contact, uploads):
    for doc_type, file_obj in uploads:
        AccountDocument.objects.create(
            association_contact=contact,
            account_request=account_request,
            doc_type=doc_type,
            status=DocumentReviewStatus.PENDING,
            file=file_obj,
        )


def _build_admin_account_request_url(request):
    base_url = build_public_base_url(request)
    return f"{base_url}{reverse(ADMIN_PUBLIC_ACCOUNT_REQUEST_CHANGE_LIST)}"


def _render_account_request_form(request, *, link, contact_payload, form_data, errors):
    return render(
        request,
        TEMPLATE_PUBLIC_ACCOUNT_REQUEST,
        {
            "link": link,
            "contacts": contact_payload,
            "form_data": form_data,
            "errors": errors,
        },
    )


def _get_client_ip(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _get_account_request_throttle_seconds():
    raw_value = getattr(
        settings,
        "ACCOUNT_REQUEST_THROTTLE_SECONDS",
        ACCOUNT_REQUEST_THROTTLE_SECONDS_DEFAULT,
    )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return ACCOUNT_REQUEST_THROTTLE_SECONDS_DEFAULT
    return max(0, value)


def _get_throttle_keys(*, email, client_ip):
    normalized_email = (email or "").strip().lower()
    normalized_ip = (client_ip or "").strip() or "unknown"
    return (
        f"account-request:email:{normalized_email}",
        f"account-request:ip:{normalized_ip}",
    )


def _reserve_throttle_slot(*, email, client_ip):
    timeout = _get_account_request_throttle_seconds()
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
    timeout = _get_account_request_throttle_seconds()
    if timeout <= 0:
        return
    email_key, ip_key = _get_throttle_keys(email=email, client_ip=client_ip)
    cache.delete(email_key)
    cache.delete(ip_key)


def _queue_account_request_emails(*, association_name, email, phone, admin_url):
    admin_message = render_to_string(
        "emails/account_request_admin_notification.txt",
        {
            "association_name": association_name,
            "email": email,
            "phone": phone,
            "admin_url": admin_url,
        },
    )
    requester_message = render_to_string(
        "emails/account_request_received.txt",
        {"association_name": association_name},
    )
    admin_recipients = get_admin_emails()

    def _send_notifications():
        admin_sent = True
        if admin_recipients:
            admin_sent = enqueue_email_safe(
                subject="ASF WMS - Nouvelle demande de compte",
                message=admin_message,
                recipient=admin_recipients,
            )
        requester_sent = enqueue_email_safe(
            subject="ASF WMS - Demande de compte recue",
            message=requester_message,
            recipient=email,
        )
        if not admin_sent:
            LOGGER.warning(
                "Account request admin notification was not queued for %s", email
            )
        if not requester_sent:
            LOGGER.warning(
                "Account request confirmation was not queued for %s", email
            )

    transaction.on_commit(_send_notifications)


def handle_account_request_form(request, *, link=None, redirect_url=""):
    contact_payload = build_shipper_contact_payload()
    form_data = _build_account_request_form_defaults()
    errors = []

    if request.method == "POST":
        form_data = _extract_account_request_form_data(request.POST)
        _append_required_field_errors(form_data, errors)

        uploads = _collect_account_request_uploads(request.FILES, errors)

        if _has_pending_request_for_email(form_data["email"]):
            errors.append(ERROR_PENDING_REQUEST_EXISTS)

        if not errors:
            client_ip = _get_client_ip(request)
            slot_reserved = _reserve_throttle_slot(
                email=form_data["email"],
                client_ip=client_ip,
            )
            if not slot_reserved:
                errors.append(ERROR_THROTTLE_LIMIT)

        if not errors:
            contact = _resolve_account_request_contact(form_data)
            try:
                with transaction.atomic():
                    account_request = _create_account_request(
                        link=link,
                        contact=contact,
                        form_data=form_data,
                    )
                    _create_account_request_documents(
                        account_request=account_request,
                        contact=contact,
                        uploads=uploads,
                    )
                    _queue_account_request_emails(
                        association_name=form_data["association_name"],
                        email=form_data["email"],
                        phone=form_data["phone"],
                        admin_url=_build_admin_account_request_url(request),
                    )
            except Exception:
                _release_throttle_slot(email=form_data["email"], client_ip=client_ip)
                raise
            messages.success(request, SUCCESS_ACCOUNT_REQUEST_SENT)
            return redirect(redirect_url)

    return _render_account_request_form(
        request,
        link=link,
        contact_payload=contact_payload,
        form_data=form_data,
        errors=errors,
    )
