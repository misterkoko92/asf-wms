from django.http import Http404
from django.utils import timezone

from .models import PublicOrderLink


def get_active_public_order_link_or_404(token):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404
    return link
