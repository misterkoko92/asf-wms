from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .models import PublicAccountRequest, PublicAccountRequestStatus
from .runtime_settings import get_runtime_settings_instance
from .ui_mode import UiMode, get_ui_mode_for_user


def _normalize_font_name(value, fallback):
    raw = (value or "").strip()
    if not raw:
        return fallback
    first = raw.split(",")[0].strip()
    normalized = first.strip('"').strip("'").strip()
    return normalized or fallback


def _default_design_tokens():
    return {
        "font_h1": "DM Sans",
        "font_h2": "DM Sans",
        "font_h3": "DM Sans",
        "font_heading": "DM Sans",
        "font_body": "Nunito Sans",
        "color_primary": "#6f9a8d",
        "color_secondary": "#e7c3a8",
        "color_background": "#f6f8f5",
        "color_surface": "#fffdf9",
        "color_border": "#d9e2dc",
        "color_text": "#2f3a36",
        "color_text_soft": "#5a6964",
    }


def _resolve_design_tokens():
    defaults = _default_design_tokens()
    try:
        runtime = get_runtime_settings_instance()
    except (ProgrammingError, OperationalError):
        return defaults
    font_h1 = _normalize_font_name(
        getattr(runtime, "design_font_h1", ""),
        defaults["font_h1"],
    )
    font_h2 = _normalize_font_name(
        getattr(runtime, "design_font_h2", ""),
        defaults["font_h2"],
    )
    font_h3 = _normalize_font_name(
        getattr(runtime, "design_font_h3", ""),
        defaults["font_h3"],
    )
    font_body = _normalize_font_name(
        runtime.design_font_body,
        defaults["font_body"],
    )
    return {
        "font_h1": font_h1,
        "font_h2": font_h2,
        "font_h3": font_h3,
        "font_heading": font_h2,
        "font_body": font_body,
        "color_primary": runtime.design_color_primary or defaults["color_primary"],
        "color_secondary": runtime.design_color_secondary or defaults["color_secondary"],
        "color_background": runtime.design_color_background or defaults["color_background"],
        "color_surface": runtime.design_color_surface or defaults["color_surface"],
        "color_border": runtime.design_color_border or defaults["color_border"],
        "color_text": runtime.design_color_text or defaults["color_text"],
        "color_text_soft": runtime.design_color_text_soft or defaults["color_text_soft"],
    }


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
        "wms_design_tokens": _resolve_design_tokens(),
    }
