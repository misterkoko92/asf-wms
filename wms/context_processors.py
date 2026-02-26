from django.conf import settings

from .models import PublicAccountRequest, PublicAccountRequestStatus
from .ui_mode import UiMode, get_ui_mode_for_user


def admin_notifications(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return {}
    pending = PublicAccountRequest.objects.filter(
        status=PublicAccountRequestStatus.PENDING
    ).count()
    return {"admin_pending_account_requests": pending}


def ui_mode_context(request):
    mode = get_ui_mode_for_user(getattr(request, "user", None))
    return {
        "wms_ui_mode": mode,
        "wms_ui_mode_is_next": mode == UiMode.NEXT,
        "scan_bootstrap_enabled": getattr(settings, "SCAN_BOOTSTRAP_ENABLED", False),
    }
