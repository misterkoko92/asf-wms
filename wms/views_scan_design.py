from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .design_style_presets import (
    DEFAULT_STYLE_PRESET_KEY,
    build_custom_style_preset_key,
    build_style_snapshot_from_runtime,
    get_builtin_style_presets,
    normalize_custom_style_presets,
)
from .design_tokens import PRIORITY_ONE_TOKEN_FIELD_TO_KEY, normalize_priority_one_tokens
from .forms_scan_design import ScanDesignSettingsForm
from .runtime_settings import get_runtime_settings_instance
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_ADMIN_DESIGN = "scan/admin_design.html"
ACTIVE_SCAN_ADMIN_DESIGN = "admin_design"
ACTION_SAVE = "save"
ACTION_RESET = "reset"
ACTION_APPLY_PRESET = "apply_preset"
ACTION_SAVE_CUSTOM_PRESET = "save_custom_preset"


def _design_values_dict(runtime_settings):
    values = {
        field_name: getattr(runtime_settings, field_name)
        for field_name in ScanDesignSettingsForm.DESIGN_FIELDS
    }
    tokens = normalize_priority_one_tokens(getattr(runtime_settings, "design_tokens", {}))
    for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items():
        values[field_name] = tokens[token_key]
    return values


def _empty_preview_values():
    return {field_name: "" for field_name in ScanDesignSettingsForm.PREVIEW_FIELDS}


def _preview_values_from_post(form, post_data):
    preview_values = _empty_preview_values()
    for field_name in ScanDesignSettingsForm.PREVIEW_FIELDS:
        preview_values[field_name] = post_data.get(field_name, "")
    for field_name in form.cleaned_data:
        value = form.cleaned_data.get(field_name)
        if field_name in preview_values and value not in (None, ""):
            preview_values[field_name] = value
    return preview_values


def _build_style_presets(runtime_settings):
    presets = get_builtin_style_presets()
    custom_presets = normalize_custom_style_presets(
        getattr(runtime_settings, "design_custom_presets", {})
    )
    for key, preset in custom_presets.items():
        presets.append(
            {
                "key": key,
                "label": preset["label"],
                "description": preset.get("description") or "Style personnalise",
                "fields": preset["fields"],
                "tokens": preset["tokens"],
                "is_custom": True,
            }
        )
    return presets, custom_presets


def _style_preset_map(style_presets):
    return {preset["key"]: preset for preset in style_presets}


def _resolve_selected_style_preset(runtime_settings, preset_map):
    current = str(getattr(runtime_settings, "design_selected_preset", "") or "").strip()
    if current in preset_map:
        return current
    if DEFAULT_STYLE_PRESET_KEY in preset_map:
        return DEFAULT_STYLE_PRESET_KEY
    return next(iter(preset_map), "")


def _build_design_form(*, runtime_settings, style_presets, selected_style_preset, data=None):
    return ScanDesignSettingsForm(
        data=data,
        instance=runtime_settings,
        style_presets=style_presets,
        selected_style_preset=selected_style_preset,
    )


def _apply_style_snapshot(runtime_settings, snapshot):
    fields = snapshot.get("fields", {})
    for field_name in ScanDesignSettingsForm.DESIGN_FIELDS:
        value = str(fields.get(field_name) or "").strip()
        if value:
            setattr(runtime_settings, field_name, value)
    runtime_settings.design_tokens = normalize_priority_one_tokens(snapshot.get("tokens", {}))
    runtime_settings.design_font_heading = runtime_settings.design_font_h2


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_admin_design(request):
    _require_superuser(request)
    runtime_settings = get_runtime_settings_instance()
    style_presets, custom_presets = _build_style_presets(runtime_settings)
    preset_map = _style_preset_map(style_presets)
    selected_style_preset = _resolve_selected_style_preset(runtime_settings, preset_map)

    if request.method == "POST":
        action = (request.POST.get("action") or ACTION_SAVE).strip().lower()
        posted_style_preset = (request.POST.get("style_preset") or "").strip()
        if posted_style_preset in preset_map:
            selected_style_preset = posted_style_preset

        if action == ACTION_RESET:
            defaults = runtime_settings._defaults_from_settings()  # noqa: SLF001
            for field_name in ScanDesignSettingsForm.RUNTIME_FIELDS:
                setattr(runtime_settings, field_name, defaults[field_name])
            runtime_settings.design_selected_preset = DEFAULT_STYLE_PRESET_KEY
            runtime_settings.updated_by = (
                request.user if request.user.is_authenticated else None
            )
            runtime_settings.save(
                update_fields=[
                    *ScanDesignSettingsForm.RUNTIME_FIELDS,
                    "design_selected_preset",
                    "updated_by",
                    "updated_at",
                ]
            )
            messages.success(request, "Design réinitialisé aux valeurs recommandées.")
            return redirect("scan:scan_admin_design")

        if action == ACTION_APPLY_PRESET:
            preset = preset_map.get(selected_style_preset)
            if not preset:
                form = _build_design_form(
                    runtime_settings=runtime_settings,
                    style_presets=style_presets,
                    selected_style_preset=selected_style_preset,
                    data=request.POST,
                )
                form.add_error("style_preset", "Selectionnez un style valide.")
                preview_values = _preview_values_from_post(form, request.POST)
            else:
                _apply_style_snapshot(runtime_settings, preset)
                runtime_settings.design_selected_preset = preset["key"]
                runtime_settings.updated_by = (
                    request.user if request.user.is_authenticated else None
                )
                runtime_settings.save(
                    update_fields=[
                        *ScanDesignSettingsForm.RUNTIME_FIELDS,
                        "design_selected_preset",
                        "updated_by",
                        "updated_at",
                    ]
                )
                messages.success(request, f'Style "{preset["label"]}" applique.')
                return redirect("scan:scan_admin_design")
        else:
            form = _build_design_form(
                runtime_settings=runtime_settings,
                style_presets=style_presets,
                selected_style_preset=selected_style_preset,
                data=request.POST,
            )
        if form.is_valid():
            if action == ACTION_SAVE_CUSTOM_PRESET:
                custom_label = (form.cleaned_data.get("style_custom_name") or "").strip()
                if not custom_label:
                    form.add_error("style_custom_name", "Le nom du style est obligatoire.")
                else:
                    runtime_settings = form.save(commit=False)
                    runtime_settings.design_font_heading = runtime_settings.design_font_h2
                    runtime_settings.design_custom_presets = normalize_custom_style_presets(
                        runtime_settings.design_custom_presets
                    )
                    custom_key = build_custom_style_preset_key(
                        custom_label,
                        existing_keys=[
                            *preset_map.keys(),
                            *custom_presets.keys(),
                        ],
                    )
                    style_snapshot = build_style_snapshot_from_runtime(runtime_settings)
                    runtime_settings.design_custom_presets[custom_key] = {
                        "label": custom_label,
                        "description": "Style personnalise enregistre depuis l'admin design.",
                        "fields": style_snapshot["fields"],
                        "tokens": style_snapshot["tokens"],
                    }
                    runtime_settings.design_selected_preset = custom_key
                    runtime_settings.updated_by = (
                        request.user if request.user.is_authenticated else None
                    )
                    runtime_settings.save()
                    messages.success(request, f'Style personnalise "{custom_label}" enregistre.')
                    return redirect("scan:scan_admin_design")
            elif action == ACTION_APPLY_PRESET:
                pass
            else:
                runtime_settings = form.save(commit=False)
                runtime_settings.design_font_heading = runtime_settings.design_font_h2
                if selected_style_preset in preset_map:
                    runtime_settings.design_selected_preset = selected_style_preset
                runtime_settings.updated_by = (
                    request.user if request.user.is_authenticated else None
                )
                runtime_settings.save()
                messages.success(request, "Paramètres design enregistrés.")
                return redirect("scan:scan_admin_design")

        if "preview_values" not in locals():
            preview_values = _preview_values_from_post(form, request.POST)
    else:
        form = _build_design_form(
            runtime_settings=runtime_settings,
            style_presets=style_presets,
            selected_style_preset=selected_style_preset,
        )
        preview_values = _design_values_dict(runtime_settings)

    return render(
        request,
        TEMPLATE_SCAN_ADMIN_DESIGN,
        {
            "active": ACTIVE_SCAN_ADMIN_DESIGN,
            "form": form,
            "design_sections": form.get_section_context(),
            "preview_values": preview_values,
        },
    )
