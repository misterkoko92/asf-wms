from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .admin_account_request_approval import (
    approve_account_request,
    describe_account_request_skip_reason,
)
from .emailing import enqueue_email_safe
from .forms_scan_account_validations import ScanAccountValidationReviewForm
from .models import PublicAccountRequest, PublicAccountRequestStatus
from .view_permissions import scan_account_validator_required

ACTIVE_SCAN_ACCOUNT_VALIDATIONS = "account_validations"
TEMPLATE_ACCOUNT_VALIDATION_LIST = "scan/account_validation_list.html"
TEMPLATE_ACCOUNT_VALIDATION_DETAIL = "scan/account_validation_detail.html"


def _account_validation_list_queryset():
    return (
        PublicAccountRequest.objects.filter(status=PublicAccountRequestStatus.PENDING)
        .select_related("destination", "contact")
        .prefetch_related("documents")
        .order_by("-created_at")
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
