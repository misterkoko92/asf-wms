from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.decorators.http import require_http_methods

from .exports import EXPORT_HANDLERS
from .scan_import_handlers import handle_scan_import_action, render_scan_import
from .view_permissions import require_superuser as _require_superuser

@login_required
@require_http_methods(["GET", "POST"])
def scan_import(request):
    _require_superuser(request)
    export_target = (request.GET.get("export") or "").strip().lower()
    if export_target:
        handler = EXPORT_HANDLERS.get(export_target)
        if handler is None:
            raise Http404
        return handler()
    default_password = getattr(settings, "IMPORT_DEFAULT_PASSWORD", None)
    pending_import = request.session.get("product_import_pending")

    def clear_pending_import():
        pending = request.session.pop("product_import_pending", None)
        if pending and pending.get("temp_path"):
            Path(pending["temp_path"]).unlink(missing_ok=True)
    if request.method == "POST":
        response = handle_scan_import_action(
            request,
            default_password=default_password,
            clear_pending_import=clear_pending_import,
        )
        if response:
            return response

    return render_scan_import(request, pending_import)
