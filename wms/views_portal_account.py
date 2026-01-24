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


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_recipients(request):
    profile = request.association_profile
    errors = []
    form_data = {
        "name": "",
        "email": "",
        "phone": "",
        "address_line1": "",
        "address_line2": "",
        "postal_code": "",
        "city": "",
        "country": "France",
        "notes": "",
    }

    if request.method == "POST" and request.POST.get("action") == "create_recipient":
        form_data.update(
            {
                "name": (request.POST.get("name") or "").strip(),
                "email": (request.POST.get("email") or "").strip(),
                "phone": (request.POST.get("phone") or "").strip(),
                "address_line1": (request.POST.get("address_line1") or "").strip(),
                "address_line2": (request.POST.get("address_line2") or "").strip(),
                "postal_code": (request.POST.get("postal_code") or "").strip(),
                "city": (request.POST.get("city") or "").strip(),
                "country": (request.POST.get("country") or "France").strip(),
                "notes": (request.POST.get("notes") or "").strip(),
            }
        )
        if not form_data["name"]:
            errors.append("Nom requis.")
        if not form_data["address_line1"]:
            errors.append("Adresse requise.")
        if not errors:
            AssociationRecipient.objects.create(
                association_contact=profile.contact,
                name=form_data["name"],
                email=form_data["email"],
                phone=form_data["phone"],
                address_line1=form_data["address_line1"],
                address_line2=form_data["address_line2"],
                postal_code=form_data["postal_code"],
                city=form_data["city"],
                country=form_data["country"] or "France",
                notes=form_data["notes"],
            )
            messages.success(request, "Destinataire ajoute.")
            return redirect("portal:portal_recipients")

    recipients = AssociationRecipient.objects.filter(
        association_contact=profile.contact, is_active=True
    ).order_by("name")
    return render(
        request,
        "portal/recipients.html",
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
        if action == "update_notifications":
            profile.notification_emails = (
                request.POST.get("notification_emails") or ""
            ).strip()
            profile.save(update_fields=["notification_emails"])
            messages.success(request, "Contacts mis a jour.")
            return redirect("portal:portal_account")
        if action == "upload_account_doc":
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
            messages.success(request, "Document ajoute.")
            return redirect("portal:portal_account")

    account_documents = AccountDocument.objects.filter(
        association_contact=association
    ).order_by("-uploaded_at")
    return render(
        request,
        "portal/account.html",
        {
            "association": association,
            "address": address,
            "notification_emails": profile.notification_emails,
            "account_documents": account_documents,
            "account_doc_types": sorted_choices(AccountDocumentType.choices),
            "user": request.user,
        },
    )


@require_http_methods(["GET", "POST"])
def portal_account_request(request):
    return handle_account_request_form(
        request,
        link=None,
        redirect_url=reverse("portal:portal_account_request"),
    )
