"""Misc portal views."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .application.portal.onboarding import mark_portal_onboarding_seen
from .view_permissions import portal_scope_required

TEMPLATE_PORTAL_FAQ = "portal/faq.html"


@login_required(login_url="portal:portal_login")
@portal_scope_required
@require_http_methods(["GET"])
def portal_faq(request):
    scope = request.portal_scope
    return render(
        request,
        TEMPLATE_PORTAL_FAQ,
        {
            "faq_scope_role": scope.role,
            "faq_recipient_organization": scope.recipient_organization,
        },
    )


@login_required(login_url="portal:portal_login")
@portal_scope_required
@require_http_methods(["POST"])
def portal_onboarding_preference(request):
    show_on_next_login = request.POST.get("show_on_next_login") == "1"
    mark_portal_onboarding_seen(
        request,
        show_on_next_login=show_on_next_login,
    )
    return JsonResponse({"ok": True})
