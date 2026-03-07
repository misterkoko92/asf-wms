from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .billing_permissions import require_billing_staff_or_superuser
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_BILLING_SETTINGS = "scan/billing_settings.html"
TEMPLATE_SCAN_BILLING_EQUIVALENCE = "scan/billing_equivalence.html"
TEMPLATE_SCAN_BILLING_EDITOR = "scan/billing_editor.html"


@scan_staff_required
@require_http_methods(["GET"])
def scan_billing_settings(request):
    _require_superuser(request)
    return render(
        request,
        TEMPLATE_SCAN_BILLING_SETTINGS,
        {
            "active": "billing_settings",
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_billing_equivalence(request):
    _require_superuser(request)
    return render(
        request,
        TEMPLATE_SCAN_BILLING_EQUIVALENCE,
        {
            "active": "billing_equivalence",
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_billing_editor(request):
    require_billing_staff_or_superuser(request)
    return render(
        request,
        TEMPLATE_SCAN_BILLING_EDITOR,
        {
            "active": "billing_editor",
        },
    )
