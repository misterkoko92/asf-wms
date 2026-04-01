from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .scan_pilotage import build_scan_pilotage_payload
from .view_permissions import scan_staff_required

ACTIVE_DASHBOARD = "pilotage"
TEMPLATE_PILOTAGE = "scan/pilotage.html"


@scan_staff_required
@require_http_methods(["GET"])
def scan_pilotage(request):
    context = build_scan_pilotage_payload()
    context.update(
        {
            "active_dashboard": ACTIVE_DASHBOARD,
            "page_actions": [
                {
                    "label": "Dashboard scan",
                    "url": context["surface_links"]["scan_dashboard_url"],
                    "tone": "primary",
                },
                {
                    "label": "Portail",
                    "url": context["surface_links"]["portal_dashboard_url"],
                    "tone": "secondary",
                },
                {
                    "label": "Planning",
                    "url": context["surface_links"]["planning_run_list_url"],
                    "tone": "secondary",
                },
            ],
        }
    )
    return render(request, TEMPLATE_PILOTAGE, context)
