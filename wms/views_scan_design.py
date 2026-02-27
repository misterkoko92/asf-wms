from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .design_tokens import PRIORITY_ONE_TOKEN_FIELD_TO_KEY, normalize_priority_one_tokens
from .forms_scan_design import ScanDesignSettingsForm
from .runtime_settings import get_runtime_settings_instance
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_ADMIN_DESIGN = "scan/admin_design.html"
ACTIVE_SCAN_ADMIN_DESIGN = "admin_design"
ACTION_SAVE = "save"
ACTION_RESET = "reset"


def _design_values_dict(runtime_settings):
    values = {
        field_name: getattr(runtime_settings, field_name)
        for field_name in ScanDesignSettingsForm.DESIGN_FIELDS
    }
    tokens = normalize_priority_one_tokens(getattr(runtime_settings, "design_tokens", {}))
    for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items():
        values[field_name] = tokens[token_key]
    return values


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_design(request):
    _require_superuser(request)
    runtime_settings = get_runtime_settings_instance()

    if request.method == "POST":
        action = (request.POST.get("action") or ACTION_SAVE).strip().lower()
        if action == ACTION_RESET:
            defaults = runtime_settings._defaults_from_settings()  # noqa: SLF001
            for field_name in ScanDesignSettingsForm.RUNTIME_FIELDS:
                setattr(runtime_settings, field_name, defaults[field_name])
            runtime_settings.updated_by = (
                request.user if request.user.is_authenticated else None
            )
            runtime_settings.save(
                update_fields=[
                    *ScanDesignSettingsForm.RUNTIME_FIELDS,
                    "updated_by",
                    "updated_at",
                ]
            )
            messages.success(request, "Design réinitialisé aux valeurs recommandées.")
            return redirect("scan:scan_admin_design")

        form = ScanDesignSettingsForm(request.POST, instance=runtime_settings)
        if form.is_valid():
            runtime_settings = form.save(commit=False)
            runtime_settings.design_font_heading = runtime_settings.design_font_h2
            runtime_settings.updated_by = (
                request.user if request.user.is_authenticated else None
            )
            runtime_settings.save()
            messages.success(request, "Paramètres design enregistrés.")
            return redirect("scan:scan_admin_design")
        preview_values = {
            field_name: form.cleaned_data.get(field_name) or request.POST.get(field_name, "")
            for field_name in ScanDesignSettingsForm.PREVIEW_FIELDS
        }
    else:
        form = ScanDesignSettingsForm(instance=runtime_settings)
        preview_values = _design_values_dict(runtime_settings)

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_DESIGN,
        {
            "active": ACTIVE_SCAN_ADMIN_DESIGN,
            "form": form,
            "priority_form_fields": [
                form[field_name] for field_name in ScanDesignSettingsForm.PRIORITY_TOKEN_FIELDS
            ],
            "preview_values": preview_values,
        },
    )
