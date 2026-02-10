from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .account_request_handlers import handle_account_request_form
from .public_link_helpers import get_active_public_order_link_or_404

ROUTE_PUBLIC_ACCOUNT_REQUEST = "scan:scan_public_account_request"


def _build_public_account_request_url(token):
    return reverse(ROUTE_PUBLIC_ACCOUNT_REQUEST, args=[token])


@require_http_methods(["GET", "POST"])
def scan_public_account_request(request, token):
    link = get_active_public_order_link_or_404(token)

    return handle_account_request_form(
        request,
        link=link,
        redirect_url=_build_public_account_request_url(token),
    )
