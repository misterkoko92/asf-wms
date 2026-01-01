from .models import PublicAccountRequest, PublicAccountRequestStatus


def admin_notifications(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return {}
    pending = PublicAccountRequest.objects.filter(
        status=PublicAccountRequestStatus.PENDING
    ).count()
    return {"admin_pending_account_requests": pending}
