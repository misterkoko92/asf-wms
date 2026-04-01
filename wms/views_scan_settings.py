from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .forms_scan_settings import ScanRuntimeSettingsForm
from .models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Shipment,
    ShipmentStatus,
    WmsRuntimeSettingsAudit,
)
from .ops_escalations import evaluate_ops_escalations
from .pilotage_runtime import SCAN_SETTINGS_PRESETS, build_pilotage_threshold_context
from .runtime_settings import get_runtime_settings_instance, is_shipment_track_legacy_enabled
from .scan_dashboard_sla import (
    annotate_shipment_tracking_dates,
    build_sla_alert_rows,
    summarize_sla_alert_rows,
)
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_SETTINGS = "scan/settings.html"
ACTIVE_SETTINGS = "settings"
ACTION_SAVE = "save"
ACTION_PREVIEW = "preview"
ACTION_APPLY_PRESET = "apply_preset"
DEFAULT_ACTION = ACTION_SAVE


def _runtime_values_dict(runtime_settings):
    return {
        field_name: getattr(runtime_settings, field_name)
        for field_name in ScanRuntimeSettingsForm.RUNTIME_FIELDS
    }


def _changed_runtime_fields(before_values, after_values):
    return [
        field_name
        for field_name in ScanRuntimeSettingsForm.RUNTIME_FIELDS
        if before_values.get(field_name) != after_values.get(field_name)
    ]


def _build_impact_preview(values):
    stale_days = max(1, int(values["stale_drafts_age_days"]))
    stale_cutoff = timezone.now() - timedelta(days=stale_days)
    stale_draft_count = Shipment.objects.filter(
        archived_at__isnull=True,
        status=ShipmentStatus.DRAFT,
        reference__startswith=TEMP_SHIPMENT_REFERENCE_PREFIX,
        created_at__lt=stale_cutoff,
    ).count()

    queue_timeout_seconds = max(1, int(values["email_queue_processing_timeout_seconds"]))
    queue_cutoff = timezone.now() - timedelta(seconds=queue_timeout_seconds)
    stale_processing_count = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source="wms.email",
        event_type="send_email",
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=queue_cutoff,
    ).count()

    env_flag = bool(getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True))
    runtime_flag = bool(values["enable_shipment_track_legacy"])
    shipments_with_tracking = annotate_shipment_tracking_dates(
        Shipment.objects.filter(archived_at__isnull=True)
    )
    sla_alert_rows = build_sla_alert_rows(
        shipments_with_tracking,
        tracking_alert_hours=max(1, int(values["tracking_alert_hours"])),
    )
    sla_alert_summary = summarize_sla_alert_rows(sla_alert_rows)
    ops_escalation_preview = _build_ops_escalation_preview(values)

    return {
        "stale_drafts_age_days": stale_days,
        "stale_draft_count": stale_draft_count,
        "queue_processing_timeout_seconds": queue_timeout_seconds,
        "queue_stale_processing_count": stale_processing_count,
        "legacy_effective_enabled": env_flag and runtime_flag,
        "sla_new_delay_count": sla_alert_summary["new_count"],
        "sla_persistent_delay_count": sla_alert_summary["persistent_count"],
        "sla_critical_delay_count": sla_alert_summary["critical_count"],
        "ops_escalation_count": ops_escalation_preview["total_count"],
        "ops_escalation_category_counts": ops_escalation_preview["category_counts"],
        "pilotage_threshold_context": build_pilotage_threshold_context(values),
    }


def _build_ops_escalation_preview(values):
    escalation_rows = evaluate_ops_escalations(now=timezone.now(), config=values)
    category_counts = {}
    for row in escalation_rows:
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1
    return {
        "total_count": len(escalation_rows),
        "category_counts": category_counts,
        "rows": escalation_rows[:5],
    }


def _preset_options():
    return [
        {
            "key": key,
            "label": preset["label"],
            "description": preset["description"],
        }
        for key, preset in SCAN_SETTINGS_PRESETS.items()
    ]


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_settings(request):
    _require_superuser(request)
    runtime_settings = get_runtime_settings_instance()
    runtime_values = _runtime_values_dict(runtime_settings)
    preview = None
    selected_preset = ""
    ops_escalation_preview = _build_ops_escalation_preview(runtime_values)
    active_pilotage_threshold_context = build_pilotage_threshold_context(runtime_values)

    if request.method == "POST":
        action = (request.POST.get("action") or DEFAULT_ACTION).strip()
        selected_preset = (request.POST.get("preset") or "").strip()
        if action == ACTION_APPLY_PRESET:
            preset = SCAN_SETTINGS_PRESETS.get(selected_preset)
            if preset is None:
                form = ScanRuntimeSettingsForm(instance=runtime_settings)
                messages.error(request, _("Preset introuvable."))
            else:
                preset_values = dict(runtime_values)
                preset_values.update(preset["values"])
                changed_fields = _changed_runtime_fields(runtime_values, preset_values)
                initial_values = dict(preset_values)
                initial_values["change_note"] = (request.POST.get("change_note") or "").strip()
                form = ScanRuntimeSettingsForm(
                    initial=initial_values,
                    instance=runtime_settings,
                )
                preview = _build_impact_preview(preset_values)
                ops_escalation_preview = _build_ops_escalation_preview(preset_values)
                preview["changed_fields"] = changed_fields
                preview["preset_label"] = preset["label"]
                messages.info(
                    request,
                    _("Preset charge. Verifiez l'impact puis enregistrez."),
                )
        else:
            form = ScanRuntimeSettingsForm(request.POST, instance=runtime_settings)
            if form.is_valid():
                submitted_values = {
                    field_name: form.cleaned_data[field_name]
                    for field_name in ScanRuntimeSettingsForm.RUNTIME_FIELDS
                }
                changed_fields = _changed_runtime_fields(runtime_values, submitted_values)
                preview = _build_impact_preview(submitted_values)
                ops_escalation_preview = _build_ops_escalation_preview(submitted_values)
                preview["changed_fields"] = changed_fields
                if action == ACTION_PREVIEW:
                    messages.info(request, _("Apercu d'impact calcule."))
                else:
                    if not changed_fields:
                        messages.info(request, _("Aucun changement detecte."))
                        return redirect("scan:scan_settings")
                    runtime_settings = form.save(commit=False)
                    runtime_settings.updated_by = (
                        request.user if request.user.is_authenticated else None
                    )
                    runtime_settings.save()
                    try:
                        WmsRuntimeSettingsAudit.objects.create(
                            settings=runtime_settings,
                            changed_by=runtime_settings.updated_by,
                            change_note=(form.cleaned_data.get("change_note") or "").strip(),
                            changed_fields=changed_fields,
                            previous_values=runtime_values,
                            new_values=_runtime_values_dict(runtime_settings),
                        )
                    except (ProgrammingError, OperationalError):
                        messages.warning(
                            request,
                            _("Parametres enregistres, mais journal d'audit indisponible."),
                        )
                    messages.success(request, _("Parametres mis a jour."))
                    return redirect("scan:scan_settings")
    else:
        form = ScanRuntimeSettingsForm(instance=runtime_settings)

    try:
        recent_audits = WmsRuntimeSettingsAudit.objects.select_related("changed_by").filter(
            settings=runtime_settings
        )[:10]
    except (ProgrammingError, OperationalError):
        recent_audits = []

    return render(
        request,
        TEMPLATE_SCAN_SETTINGS,
        {
            "active": ACTIVE_SETTINGS,
            "form": form,
            "runtime_settings": runtime_settings,
            "preset_options": _preset_options(),
            "selected_preset": selected_preset,
            "preview": preview,
            "ops_escalation_preview": ops_escalation_preview,
            "active_pilotage_threshold_context": active_pilotage_threshold_context,
            "recent_audits": recent_audits,
            "legacy_env_disabled": not bool(
                getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True)
            ),
            "legacy_effective_enabled": is_shipment_track_legacy_enabled(),
        },
    )
