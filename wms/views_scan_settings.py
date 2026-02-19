from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms_scan_settings import ScanRuntimeSettingsForm
from .runtime_settings import get_runtime_settings_instance, is_shipment_track_legacy_enabled
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_SETTINGS = "scan/settings.html"
ACTIVE_SETTINGS = "settings"


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_settings(request):
    _require_superuser(request)
    runtime_settings = get_runtime_settings_instance()
    if request.method == "POST":
        form = ScanRuntimeSettingsForm(request.POST, instance=runtime_settings)
        if form.is_valid():
            runtime_settings = form.save(commit=False)
            runtime_settings.updated_by = (
                request.user if request.user.is_authenticated else None
            )
            runtime_settings.save()
            messages.success(request, "Paramètres mis à jour.")
            return redirect("scan:scan_settings")
    else:
        form = ScanRuntimeSettingsForm(instance=runtime_settings)
    return render(
        request,
        TEMPLATE_SCAN_SETTINGS,
        {
            "active": ACTIVE_SETTINGS,
            "form": form,
            "runtime_settings": runtime_settings,
            "legacy_env_disabled": not bool(
                getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True)
            ),
            "legacy_effective_enabled": is_shipment_track_legacy_enabled(),
        },
    )
