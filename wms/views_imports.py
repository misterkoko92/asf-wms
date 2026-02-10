from pathlib import Path

from django.conf import settings
from django.http import Http404
from django.views.decorators.http import require_http_methods

from .exports import EXPORT_HANDLERS
from .scan_import_handlers import handle_scan_import_action, render_scan_import
from .view_permissions import (
    require_superuser as _require_superuser,
    scan_staff_required,
)

QUERY_EXPORT = "export"
SESSION_PENDING_IMPORT = "product_import_pending"


def _resolve_export_handler(request):
    export_target = (request.GET.get(QUERY_EXPORT) or "").strip().lower()
    if not export_target:
        return None
    handler = EXPORT_HANDLERS.get(export_target)
    if handler is None:
        raise Http404
    return handler


def _get_pending_import(request):
    return request.session.get(SESSION_PENDING_IMPORT)


def _clear_pending_import(request):
    pending = request.session.pop(SESSION_PENDING_IMPORT, None)
    if pending and pending.get("temp_path"):
        Path(pending["temp_path"]).unlink(missing_ok=True)


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_import(request):
    _require_superuser(request)
    export_handler = _resolve_export_handler(request)
    if export_handler:
        return export_handler()

    default_password = getattr(settings, "IMPORT_DEFAULT_PASSWORD", None)

    if request.method == "POST":
        response = handle_scan_import_action(
            request,
            default_password=default_password,
            clear_pending_import=lambda: _clear_pending_import(request),
        )
        if response:
            return response

    return render_scan_import(request, _get_pending_import(request))
