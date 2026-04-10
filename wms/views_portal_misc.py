"""Misc portal views."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

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
