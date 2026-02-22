import json
import logging
import mimetypes
import posixpath
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .portal_helpers import get_association_profile
from .ui_mode import UiMode, normalize_ui_mode, set_ui_mode_for_user

logger = logging.getLogger(__name__)

DEFAULT_NEXT_URL = "/app/scan/dashboard/"
DEFAULT_LEGACY_URL = "/scan/dashboard/"
DEFAULT_PORTAL_NEXT_URL = "/app/portal/dashboard/"
FRONTEND_LOG_BODY_MAX_BYTES = 16 * 1024


def _next_export_root() -> Path:
    return settings.BASE_DIR / "frontend-next" / "out"


def _safe_next_url(request, raw_next: str) -> str:
    candidate = (raw_next or "").strip()
    if not candidate:
        return ""
    if not url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    return candidate


def _normalize_export_path(path: str) -> str:
    normalized = posixpath.normpath("/" + (path or "")).lstrip("/")
    if normalized in {"", "."}:
        return ""
    if normalized == ".." or normalized.startswith("../"):
        raise Http404
    return normalized


def _resolve_export_file(path: str) -> Path | None:
    root = _next_export_root().resolve()
    normalized = _normalize_export_path(path)

    candidates: list[str] = []
    if not normalized:
        candidates = ["index.html"]
    else:
        file_name = Path(normalized).name
        if "." in file_name:
            candidates = [normalized]
        else:
            candidates = [f"{normalized}/index.html", f"{normalized}.html"]

    for candidate in candidates:
        resolved = (root / candidate).resolve()
        if not str(resolved).startswith(str(root)):
            continue
        if resolved.is_file():
            return resolved

    if normalized and "." not in Path(normalized).name:
        index_fallback = (root / "index.html").resolve()
        if str(index_fallback).startswith(str(root)) and index_fallback.is_file():
            return index_fallback
    return None


def _default_next_url_for_user(user) -> str:
    if not user or not user.is_authenticated:
        return DEFAULT_NEXT_URL
    if user.is_staff:
        return DEFAULT_NEXT_URL
    if get_association_profile(user):
        return DEFAULT_PORTAL_NEXT_URL
    return DEFAULT_NEXT_URL


def _default_legacy_url_for_user(user) -> str:
    if not user or not user.is_authenticated:
        return DEFAULT_LEGACY_URL
    if user.is_staff:
        return DEFAULT_LEGACY_URL
    if get_association_profile(user):
        return "/portal/"
    return DEFAULT_LEGACY_URL


def _portal_login_redirect(request):
    login_url = reverse("portal:portal_login")
    query = urlencode({"next": request.get_full_path()})
    return redirect(f"{login_url}?{query}")


def _enforce_next_access(request, path: str):
    normalized = _normalize_export_path(path)
    is_scan = normalized.startswith("scan/")
    is_portal = normalized.startswith("portal/")

    if is_portal:
        if not request.user.is_authenticated:
            return _portal_login_redirect(request)
        profile = get_association_profile(request.user)
        if not profile:
            raise PermissionDenied
        if profile.must_change_password:
            change_url = reverse("portal:portal_change_password")
            if request.path != change_url:
                return redirect(change_url)
        return None

    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url=reverse("admin:login"))

    if is_scan and not request.user.is_staff:
        raise PermissionDenied

    return None


@require_http_methods(["GET", "POST"])
def ui_mode_set(request, mode=None):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url=reverse("admin:login"))

    requested_mode = normalize_ui_mode(
        mode or request.POST.get("mode") or request.GET.get("mode")
    )
    set_ui_mode_for_user(request.user, requested_mode)
    if requested_mode == UiMode.NEXT:
        messages.success(request, "Mode Next active.")
    else:
        messages.success(request, "Mode interface actuelle active.")

    next_url = _safe_next_url(
        request, request.POST.get("next") or request.GET.get("next") or ""
    )
    if not next_url:
        if requested_mode == UiMode.NEXT:
            next_url = _default_next_url_for_user(request.user)
        else:
            next_url = _default_legacy_url_for_user(request.user)
    return redirect(next_url)


@require_http_methods(["GET"])
def next_frontend(request, path=""):
    access_response = _enforce_next_access(request, path)
    if access_response is not None:
        return access_response

    export_root = _next_export_root()
    if not export_root.exists():
        return render(
            request,
            "app/next_build_missing.html",
            {
                "frontend_root": str(settings.BASE_DIR / "frontend-next"),
                "legacy_url": DEFAULT_LEGACY_URL,
                "build_command": "cd frontend-next && npm ci && npm run build",
            },
            status=503,
        )

    export_file = _resolve_export_file(path)
    if export_file is None:
        raise Http404

    content_type, _ = mimetypes.guess_type(str(export_file))
    return FileResponse(
        export_file.open("rb"),
        content_type=content_type or "application/octet-stream",
    )


@csrf_exempt
@require_http_methods(["POST"])
def frontend_log_event(request):
    if not request.user.is_authenticated:
        return HttpResponse(status=204)

    if len(request.body or b"") > FRONTEND_LOG_BODY_MAX_BYTES:
        return HttpResponse(status=413)

    payload = {}
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return HttpResponse(status=400)

    event = str(payload.get("event") or "client.log")[:64]
    level = str(payload.get("level") or "info").lower()
    metadata = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    safe_meta = {
        str(key)[:80]: str(value)[:400]
        for key, value in metadata.items()
        if key is not None
    }

    log_payload = {
        "event": event,
        "path": str(payload.get("path") or "")[:240],
        "message": str(payload.get("message") or "")[:500],
        "meta": safe_meta,
        "user_id": request.user.id,
    }
    serialized = json.dumps(log_payload, ensure_ascii=True)
    if level == "error":
        logger.error("frontend_event %s", serialized)
    elif level == "warning":
        logger.warning("frontend_event %s", serialized)
    else:
        logger.info("frontend_event %s", serialized)

    return HttpResponse(status=204)
