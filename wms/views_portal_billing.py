from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .billing_document_handlers import build_billing_document_render_payload
from .models import BillingDocument, BillingDocumentStatus, BillingIssue
from .view_permissions import association_required

TEMPLATE_BILLING_LIST = "portal/billing_list.html"
TEMPLATE_BILLING_DETAIL = "portal/billing_detail.html"

ACTION_REQUEST_CORRECTION = "request_correction"
MESSAGE_CORRECTION_REQUESTED = "Votre demande de correction a bien ete envoyee."
ERROR_CORRECTION_DESCRIPTION_REQUIRED = "Precisez le motif de correction."


def _issued_billing_documents_queryset(profile):
    return (
        BillingDocument.objects.filter(
            association_profile=profile,
            status=BillingDocumentStatus.ISSUED,
        )
        .select_related(
            "association_profile__contact",
            "association_profile__billing_profile",
        )
        .prefetch_related("lines", "shipment_links__shipment", "payments", "issues")
        .order_by("-issued_at", "-created_at", "-id")
    )


def _build_billing_entry(document):
    payload = build_billing_document_render_payload(document=document)
    return {
        "document": document,
        "payload": payload,
        "number": payload["number"],
        "total_amount": payload["total_amount"],
        "shipment_count": len(payload["shipments"]),
        "line_count": len(payload["lines"]),
    }


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET"])
def portal_billing(request):
    documents = [
        _build_billing_entry(document)
        for document in _issued_billing_documents_queryset(request.association_profile)
    ]
    return render(
        request,
        TEMPLATE_BILLING_LIST,
        {
            "documents": documents,
        },
    )


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_billing_detail(request, document_id):
    document = get_object_or_404(
        _issued_billing_documents_queryset(request.association_profile),
        pk=document_id,
    )
    if document.status != BillingDocumentStatus.ISSUED:
        raise Http404("Billing document not found")

    if (
        request.method == "POST"
        and (request.POST.get("action") or "").strip() == ACTION_REQUEST_CORRECTION
    ):
        description = (request.POST.get("issue_description") or "").strip()
        if not description:
            messages.error(request, ERROR_CORRECTION_DESCRIPTION_REQUIRED)
        else:
            BillingIssue.objects.create(
                document=document,
                description=description,
                reported_by=request.user,
            )
            messages.success(request, MESSAGE_CORRECTION_REQUESTED)
            return redirect("portal:portal_billing_detail", document_id=document.id)

    billing_entry = _build_billing_entry(document)
    return render(
        request,
        TEMPLATE_BILLING_DETAIL,
        {
            "billing_entry": billing_entry,
            "billing_document": document,
            "payments": list(document.payments.order_by("-paid_on", "-id")),
            "issues": list(document.issues.order_by("-reported_at")),
        },
    )
