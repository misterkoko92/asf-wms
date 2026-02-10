from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .account_request_handlers import handle_account_request_form
from .document_uploads import validate_document_upload
from .models import (
    AccountDocument,
    AccountDocumentType,
    AssociationRecipient,
    DocumentReviewStatus,
)
from .portal_helpers import get_contact_address
from .view_permissions import association_required
from .view_utils import sorted_choices

TEMPLATE_RECIPIENTS = "portal/recipients.html"
TEMPLATE_ACCOUNT = "portal/account.html"

ACTION_CREATE_RECIPIENT = "create_recipient"
ACTION_UPDATE_NOTIFICATIONS = "update_notifications"
ACTION_UPLOAD_ACCOUNT_DOC = "upload_account_doc"

DEFAULT_COUNTRY = "France"
MESSAGE_RECIPIENT_ADDED = "Destinataire ajoute."
MESSAGE_CONTACTS_UPDATED = "Contacts mis a jour."
MESSAGE_DOCUMENT_ADDED = "Document ajoute."
ERROR_RECIPIENT_NAME_REQUIRED = "Nom requis."
ERROR_RECIPIENT_ADDRESS_REQUIRED = "Adresse requise."


def _build_default_recipient_form_data():
    return {
        "name": "",
        "email": "",
        "phone": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": DEFAULT_COUNTRY,
        "notes": "",
    }


def _extract_recipient_form_data(post_data):
    return {
        "name": (post_data.get("name") or "").strip(),
        "email": (post_data.get("email") or "").strip(),
        "phone": (post_data.get("phone") or "").strip(),
        "address_line1": (post_data.get("address_line1") or "").strip(),
        "address_line2": (post_data.get("address_line2") or "").strip(),
        "postal_code": (post_data.get("postal_code") or "").strip(),
        "city": (post_data.get("city") or "").strip(),
        "country": (post_data.get("country") or DEFAULT_COUNTRY).strip(),
        "notes": (post_data.get("notes") or "").strip(),
    }


def _validate_recipient_form_data(form_data):
    errors = []
    if not form_data["name"]:
        errors.append(ERROR_RECIPIENT_NAME_REQUIRED)
    if not form_data["address_line1"]:
        errors.append(ERROR_RECIPIENT_ADDRESS_REQUIRED)
    return errors


def _create_recipient(profile, form_data):
    AssociationRecipient.objects.create(
        association_contact=profile.contact,
        name=form_data["name"],
        email=form_data["email"],
        phone=form_data["phone"],
        address_line1=form_data["address_line1"],
        address_line2=form_data["address_line2"],
        postal_code=form_data["postal_code"],
        city=form_data["city"],
        country=form_data["country"] or DEFAULT_COUNTRY,
        notes=form_data["notes"],
    )


def _get_active_recipients(profile):
    return AssociationRecipient.objects.filter(
        association_contact=profile.contact,
        is_active=True,
    ).order_by("name")


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


def _build_portal_account_context(*, profile, address, user):
    association = profile.contact
    account_documents = AccountDocument.objects.filter(
        association_contact=association
    ).order_by("-uploaded_at")
    return {
        "association": association,
        "address": address,
        "notification_emails": profile.notification_emails,
        "account_documents": account_documents,
        "account_doc_types": sorted_choices(AccountDocumentType.choices),
        "user": user,
    }


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_recipients(request):
    profile = request.association_profile
    errors = []
    form_data = _build_default_recipient_form_data()

    if request.method == "POST" and request.POST.get("action") == ACTION_CREATE_RECIPIENT:
        form_data = _extract_recipient_form_data(request.POST)
        errors = _validate_recipient_form_data(form_data)
        if not errors:
            _create_recipient(profile, form_data)
            messages.success(request, MESSAGE_RECIPIENT_ADDED)
            return redirect("portal:portal_recipients")

    recipients = _get_active_recipients(profile)
    return render(
        request,
        TEMPLATE_RECIPIENTS,
        {"recipients": recipients, "errors": errors, "form_data": form_data},
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_account(request):
    profile = request.association_profile
    association = profile.contact
    address = get_contact_address(association)

    if request.method == "POST":
        action = request.POST.get("action") or ""
        if action == ACTION_UPDATE_NOTIFICATIONS:
            return _handle_notification_update(request, profile)
        if action == ACTION_UPLOAD_ACCOUNT_DOC:
            return _handle_account_document_upload(request, association)

    return render(
        request,
        TEMPLATE_ACCOUNT,
        _build_portal_account_context(
            profile=profile,
            address=address,
            user=request.user,
        ),
    )


@require_http_methods(["GET", "POST"])
def portal_account_request(request):
    return handle_account_request_form(
        request,
        link=None,
        redirect_url=reverse("portal:portal_account_request"),
    )
