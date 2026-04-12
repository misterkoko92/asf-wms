from types import SimpleNamespace

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .admin_account_request_approval import (
    approve_account_request,
    describe_account_request_skip_reason,
)
from .admin_contacts_crud import (
    ACTION_SAVE_CONTACT,
    build_admin_contacts_forms,
    handle_contact_submission,
)
from .emailing import enqueue_email_safe
from .forms_scan_account_validations import ScanAccountValidationReviewForm
from .models import (
    PublicAccountRequest,
    PublicAccountRequestStatus,
    ShipmentRecipientOrganization,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from .view_permissions import (
    require_superuser as _require_superuser,
)
from .view_permissions import (
    scan_account_validator_required,
    scan_staff_required,
    user_can_review_account_requests,
)

ACTIVE_SCAN_ACCOUNT_VALIDATIONS = "account_validations"
ACTIVE_SCAN_CONTACT_VALIDATIONS = "contacts_validations"
ACTIVE_SCAN_RECIPIENT_VALIDATIONS = "recipient_validations"
TEMPLATE_ACCOUNT_VALIDATION_LIST = "scan/account_validation_list.html"
TEMPLATE_ACCOUNT_VALIDATION_DETAIL = "scan/account_validation_detail.html"
TEMPLATE_CONTACT_VALIDATIONS_HUB = "scan/contact_validations_hub.html"
TEMPLATE_RECIPIENT_VALIDATION_LIST = "scan/recipient_validation_list.html"
TEMPLATE_RECIPIENT_VALIDATION_DETAIL = "scan/recipient_validation_detail.html"
RECIPIENT_VALIDATION_ALLOWED_BUSINESS_TYPES = ("shipper", "recipient")


def _account_validation_list_queryset():
    return (
        PublicAccountRequest.objects.filter(status=PublicAccountRequestStatus.PENDING)
        .select_related("destination", "contact")
        .prefetch_related("documents")
        .order_by("-created_at")
    )


def _recipient_validation_list_queryset():
    return (
        ShipmentRecipientOrganization.objects.filter(
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
            organization__is_active=True,
            destination__is_active=True,
        )
        .select_related("organization", "destination")
        .prefetch_related(
            Prefetch(
                "shipper_links",
                queryset=ShipmentShipperRecipientLink.objects.filter(
                    is_active=True,
                    shipper__is_active=True,
                    shipper__organization__is_active=True,
                )
                .select_related("shipper__organization")
                .order_by("shipper__organization__name", "id"),
                to_attr="active_shipper_links",
            )
        )
        .order_by("destination__city", "organization__name", "id")
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_contact_validations_hub(request):
    if not user_can_review_account_requests(request.user):
        raise PermissionDenied
    return render(
        request,
        TEMPLATE_CONTACT_VALIDATIONS_HUB,
        {
            "active": ACTIVE_SCAN_CONTACT_VALIDATIONS,
            "account_validation_count": _account_validation_list_queryset().count(),
            "recipient_validation_count": _recipient_validation_list_queryset().count(),
        },
    )


@scan_account_validator_required
@require_http_methods(["GET"])
def scan_account_validation_list(request):
    return render(
        request,
        TEMPLATE_ACCOUNT_VALIDATION_LIST,
        {
            "active": ACTIVE_SCAN_ACCOUNT_VALIDATIONS,
            "account_requests": list(_account_validation_list_queryset()),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_recipient_validation_list(request):
    _require_superuser(request)
    return render(
        request,
        TEMPLATE_RECIPIENT_VALIDATION_LIST,
        {
            "active": ACTIVE_SCAN_RECIPIENT_VALIDATIONS,
            "recipient_validations": list(_recipient_validation_list_queryset()),
        },
    )


@scan_account_validator_required
@require_http_methods(["GET", "POST"])
def scan_account_validation_detail(request, account_request_id):
    account_request = get_object_or_404(
        PublicAccountRequest.objects.select_related("destination", "contact").prefetch_related(
            "documents"
        ),
        pk=account_request_id,
    )
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "reject_request":
            account_request.status = PublicAccountRequestStatus.REJECTED
            account_request.reviewed_by = request.user
            account_request.reviewed_at = timezone.now()
            account_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
            messages.success(request, "Demande refusée.")
            return redirect("scan:scan_account_validation_list")

        form = ScanAccountValidationReviewForm(
            request.POST,
            account_request=account_request,
        )
        if form.is_valid():
            ok, reason = approve_account_request(
                request=request,
                account_request=account_request,
                enqueue_email=enqueue_email_safe,
                review_overrides=form.build_review_overrides(),
            )
            if ok:
                messages.success(request, "Compte validé.")
                return redirect("scan:scan_account_validation_list")
            messages.error(
                request,
                f"Validation ignorée ({describe_account_request_skip_reason(reason)}).",
            )
    else:
        form = ScanAccountValidationReviewForm(account_request=account_request)

    return render(
        request,
        TEMPLATE_ACCOUNT_VALIDATION_DETAIL,
        {
            "active": ACTIVE_SCAN_ACCOUNT_VALIDATIONS,
            "account_request": account_request,
            "form": form,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_recipient_validation_detail(request, recipient_organization_id):
    _require_superuser(request)
    recipient_organization = get_object_or_404(
        _recipient_validation_list_queryset(),
        pk=recipient_organization_id,
    )
    organization = recipient_organization.organization
    crud_context = build_admin_contacts_forms(
        edit_contact_id=organization.id,
        allowed_business_types=RECIPIENT_VALIDATION_ALLOWED_BUSINESS_TYPES,
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == ACTION_SAVE_CONTACT:
            outcome = handle_contact_submission(
                request.POST,
                allowed_business_types=RECIPIENT_VALIDATION_ALLOWED_BUSINESS_TYPES,
            )
            if outcome.should_redirect:
                selected_business_type = (request.POST.get("business_type") or "").strip()
                if selected_business_type == "recipient":
                    recipient_organization.validation_status = ShipmentValidationStatus.VALIDATED
                elif selected_business_type == "shipper":
                    recipient_organization.validation_status = ShipmentValidationStatus.REJECTED
                recipient_organization.save(update_fields=["validation_status"])
                getattr(messages, outcome.message_level or "success")(
                    request, outcome.message or ""
                )
                return redirect("scan:scan_recipient_validation_list")
            crud_context.update(
                {
                    "contact_form": outcome.contact_form or crud_context["contact_form"],
                    "contact_duplicate_candidates": outcome.contact_duplicate_candidates,
                    "contact_form_mode": outcome.contact_form_mode,
                    "editing_contact": outcome.editing_contact,
                }
            )
        else:
            messages.error(request, "Action de validation destinataire non reconnue.")

    return render(
        request,
        TEMPLATE_RECIPIENT_VALIDATION_DETAIL,
        {
            "active": ACTIVE_SCAN_RECIPIENT_VALIDATIONS,
            "recipient_organization": recipient_organization,
            "allowed_shipper_names": [
                link.shipper.organization.name
                for link in recipient_organization.active_shipper_links
            ],
            "editing_contact_requires_recipient_validation": True,
            "editing_structure_contact": organization,
            "editing_structure_documents": list(
                organization.recipient_structure_documents.order_by("-uploaded_at")
            ),
            "contacts_current_url": "/scan/contacts/validations/recipients/",
            "contacts_page": SimpleNamespace(number=1),
            "query": "",
            "contact_filter": "all",
            "destination_filter": str(recipient_organization.destination_id),
            **crud_context,
        },
    )
