from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .account_request_handlers import handle_account_request_form
from .models import PublicOrderLink

@require_http_methods(["GET", "POST"])
def scan_public_account_request(request, token):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    return handle_account_request_form(
        request,
        link=link,
        redirect_url=reverse("scan:scan_public_account_request", args=[token]),
    )
