from django.contrib import messages
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from contacts.models import Contact

from .contact_payloads import build_shipper_contact_payload
from .emailing import get_admin_emails, send_email_safe
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


def handle_account_request_form(request, *, link=None, redirect_url=""):
    contact_payload = build_shipper_contact_payload()

    form_data = {
        "association_name": "",
        "email": "",
        "phone": "",
        "line1": "",
        "line2": "",
        "postal_code": "",
        "city": "",
        "country": "France",
        "notes": "",
        "contact_id": "",
    }
    errors = []

    if request.method == "POST":
        form_data.update(
            {
                "association_name": (request.POST.get("association_name") or "").strip(),
                "email": (request.POST.get("email") or "").strip(),
                "phone": (request.POST.get("phone") or "").strip(),
                "line1": (request.POST.get("line1") or "").strip(),
                "line2": (request.POST.get("line2") or "").strip(),
                "postal_code": (request.POST.get("postal_code") or "").strip(),
                "city": (request.POST.get("city") or "").strip(),
                "country": (request.POST.get("country") or "France").strip(),
                "notes": (request.POST.get("notes") or "").strip(),
                "contact_id": (request.POST.get("contact_id") or "").strip(),
            }
        )
        if not form_data["association_name"]:
            errors.append("Nom de l'association requis.")
        if not form_data["email"]:
            errors.append("Email requis.")
        if not form_data["line1"]:
            errors.append("Adresse requise.")

        uploads = []
        doc_files = [
            (AccountDocumentType.STATUTES, request.FILES.get("doc_statutes")),
            (
                AccountDocumentType.REGISTRATION_PROOF,
                request.FILES.get("doc_registration"),
            ),
            (AccountDocumentType.ACTIVITY_REPORT, request.FILES.get("doc_report")),
        ]
        for doc_type, file_obj in doc_files:
            if not file_obj:
                continue
            validation_error = validate_upload(file_obj)
            if validation_error:
                errors.append(validation_error)
            else:
                uploads.append((doc_type, file_obj))
        for file_obj in request.FILES.getlist("doc_other"):
            if not file_obj:
                continue
            validation_error = validate_upload(file_obj)
            if validation_error:
                errors.append(validation_error)
            else:
                uploads.append((AccountDocumentType.OTHER, file_obj))

        existing = PublicAccountRequest.objects.filter(
            email__iexact=form_data["email"],
            status=PublicAccountRequestStatus.PENDING,
        ).first()
        if existing:
            errors.append("Une demande est deja en attente pour cet email.")

        if not errors:
            contact = None
            contact_id = parse_int(form_data["contact_id"])
            if contact_id:
                contact = Contact.objects.filter(id=contact_id, is_active=True).first()
            if not contact:
                contact = Contact.objects.filter(
                    name__iexact=form_data["association_name"], is_active=True
                ).first()
            account_request = PublicAccountRequest.objects.create(
                link=link,
                contact=contact,
                association_name=form_data["association_name"],
                email=form_data["email"],
                phone=form_data["phone"],
                address_line1=form_data["line1"],
                address_line2=form_data["line2"],
                postal_code=form_data["postal_code"],
                city=form_data["city"],
                country=form_data["country"] or "France",
                notes=form_data["notes"],
            )
            for doc_type, file_obj in uploads:
                AccountDocument.objects.create(
                    association_contact=contact,
                    account_request=account_request,
                    doc_type=doc_type,
                    status=DocumentReviewStatus.PENDING,
                    file=file_obj,
                )
            base_url = build_public_base_url(request)
            admin_message = render_to_string(
                "emails/account_request_admin_notification.txt",
                {
                    "association_name": form_data["association_name"],
                    "email": form_data["email"],
                    "phone": form_data["phone"],
                    "admin_url": f"{base_url}{reverse('admin:wms_publicaccountrequest_changelist')}",
                },
            )
            send_email_safe(
                subject="ASF WMS - Nouvelle demande de compte",
                message=admin_message,
                recipient=get_admin_emails(),
            )
            message = render_to_string(
                "emails/account_request_received.txt",
                {"association_name": form_data["association_name"]},
            )
            send_email_safe(
                subject="ASF WMS - Demande de compte recue",
                message=message,
                recipient=form_data["email"],
            )
            messages.success(
                request,
                "Demande envoyee. Un superuser ASF validera votre compte.",
            )
            return redirect(redirect_url)

    return render(
        request,
        "scan/public_account_request.html",
        {
            "link": link,
            "contacts": contact_payload,
            "form_data": form_data,
            "errors": errors,
        },
    )
