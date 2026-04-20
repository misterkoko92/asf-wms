from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .application.scan.dashboard_queries import build_scan_dashboard_payload
from .scan_permissions import user_is_preparateur
from .view_permissions import scan_staff_required
from .workflow_blockage_queue import (
    claim_workflow_blockage,
    release_workflow_blockage,
    workflow_blockage_row_by_key,
)

TEMPLATE_DASHBOARD = "scan/dashboard.html"

DASHBOARD_QUERY_ONLY_KEYS = {
    "workflow_blockage_base_rows",
    "shipments_scope",
    "shipments_with_tracking",
    "status_map",
    "stock_snapshot",
    "email_queue_snapshot",
    "document_scan_snapshot",
    "workflow_blockage_snapshot",
    "period_start",
    "week_start",
    "week_end",
    "pending_actions",
    "queue_processing_timeout_seconds",
    "document_scan_processing_timeout_seconds",
    "shipment_chart_rows",
    "shipments_total",
}


@scan_staff_required
@require_http_methods(["GET"])
def scan_root(request):
    if user_is_preparateur(request.user):
        return redirect("scan:scan_preparateur_order_select")
    return redirect("scan:scan_dashboard")


def _build_scan_dashboard_context(dashboard_payload):
    return {
        key: value
        for key, value in dashboard_payload.items()
        if key not in DASHBOARD_QUERY_ONLY_KEYS
    }


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_dashboard(request):
    dashboard_payload = build_scan_dashboard_payload(user=request.user, params=request.GET)
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        blockage_key = (request.POST.get("blockage_key") or "").strip()
        blockage_row = workflow_blockage_row_by_key(
            dashboard_payload.get("workflow_blockage_base_rows", []),
            blockage_key,
        )
        if action == "claim_workflow_blockage":
            if blockage_row is None:
                messages.error(request, _("Blocage introuvable ou déjà résolu."))
            else:
                claim_workflow_blockage(row=blockage_row, user=request.user)
                messages.success(request, _("Blocage pris en charge."))
        elif action == "release_workflow_blockage":
            release_workflow_blockage(blockage_key=blockage_key)
            messages.success(request, _("Prise en charge libérée."))
        else:
            messages.error(request, _("Action dashboard inconnue."))
        return redirect(request.get_full_path())

    return render(
        request,
        TEMPLATE_DASHBOARD,
        _build_scan_dashboard_context(dashboard_payload),
    )
