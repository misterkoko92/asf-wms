from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import PlanningVersion
from .ops_escalations import evaluate_ops_escalations
from .planning.stats import build_version_stats
from .policies.pilotage import normalize_planning_thresholds

SCAN_SETTINGS_PRESETS = {
    "standard": {
        "label": _("Standard"),
        "description": _("Valeurs operationnelles recommandees."),
        "values": {
            "low_stock_threshold": 20,
            "tracking_alert_hours": 72,
            "workflow_blockage_hours": 72,
            "stale_drafts_age_days": 30,
            "pilotage_dispute_unassigned_hours": 12,
            "pilotage_workflow_blockage_unclaimed_hours": 12,
            "pilotage_queue_backlog_threshold": 3,
            "pilotage_planning_tension_pct": 80,
            "pilotage_planning_critical_pct": 95,
            "email_queue_max_attempts": 5,
            "email_queue_retry_base_seconds": 60,
            "email_queue_retry_max_seconds": 3600,
            "email_queue_processing_timeout_seconds": 900,
            "enable_shipment_track_legacy": True,
        },
    },
    "incident_email_queue": {
        "label": _("Incident queue email"),
        "description": _("Accroit l'agressivite de reprise et baisse le timeout."),
        "values": {
            "pilotage_queue_backlog_threshold": 1,
            "email_queue_max_attempts": 8,
            "email_queue_retry_base_seconds": 30,
            "email_queue_retry_max_seconds": 300,
            "email_queue_processing_timeout_seconds": 120,
        },
    },
    "incident_sla": {
        "label": _("Incident SLA"),
        "description": _("Resserre la detection des retards de suivi et des blocages."),
        "values": {
            "tracking_alert_hours": 48,
            "workflow_blockage_hours": 48,
            "pilotage_dispute_unassigned_hours": 8,
            "pilotage_workflow_blockage_unclaimed_hours": 8,
        },
    },
    "pilotage_tendu": {
        "label": _("Pilotage tendu"),
        "description": _("Resserre les seuils scan et planning pour une journee de forte tension."),
        "values": {
            "tracking_alert_hours": 24,
            "workflow_blockage_hours": 48,
            "pilotage_dispute_unassigned_hours": 8,
            "pilotage_workflow_blockage_unclaimed_hours": 8,
            "pilotage_queue_backlog_threshold": 3,
            "pilotage_planning_tension_pct": 75,
            "pilotage_planning_critical_pct": 90,
        },
    },
}

_CUSTOM_PRESET_LABEL = _("Personnalise")


def resolve_active_scan_settings_preset(values: dict[str, object]) -> dict[str, object]:
    best_match = None
    best_score = -1
    for key, preset in SCAN_SETTINGS_PRESETS.items():
        preset_values = preset["values"]
        if all(
            values.get(field_name) == expected for field_name, expected in preset_values.items()
        ):
            score = len(preset_values)
            if score > best_score:
                best_match = {
                    "key": key,
                    "label": preset["label"],
                    "description": preset["description"],
                }
                best_score = score
    if best_match is not None:
        return best_match
    return {
        "key": "",
        "label": _CUSTOM_PRESET_LABEL,
        "description": _("Configuration locale ajustee manuellement."),
    }


def _latest_planning_versions():
    latest_by_run = {}
    for version in PlanningVersion.objects.select_related("run").order_by(
        "run_id", "-number", "-id"
    ):
        latest_by_run.setdefault(version.run_id, version)
    return list(latest_by_run.values())


def _planning_capacity_impact(values: dict[str, object]) -> dict[str, int]:
    tension_pct, critical_pct = normalize_planning_thresholds(
        values.get("pilotage_planning_tension_pct"),
        values.get("pilotage_planning_critical_pct"),
        default_tension=80,
        default_critical=95,
    )
    counts = {"tension": 0, "critical": 0, "overload": 0}
    for version in _latest_planning_versions():
        stats = build_version_stats(
            version,
            tension_pct=tension_pct,
            critical_pct=critical_pct,
        )
        for row in stats["flight_load_breakdown"]:
            state = row["load_state"]
            if state in counts:
                counts[state] += 1
    return counts


def build_pilotage_threshold_context(values: dict[str, object]) -> dict[str, object]:
    active_preset = resolve_active_scan_settings_preset(values)
    tension_pct, critical_pct = normalize_planning_thresholds(
        values.get("pilotage_planning_tension_pct"),
        values.get("pilotage_planning_critical_pct"),
        default_tension=80,
        default_critical=95,
    )
    escalation_count = len(evaluate_ops_escalations(now=timezone.now(), config=values))
    planning_impact = _planning_capacity_impact(
        {
            **values,
            "pilotage_planning_tension_pct": tension_pct,
            "pilotage_planning_critical_pct": critical_pct,
        }
    )
    return {
        "active_preset_key": active_preset["key"],
        "active_preset_label": active_preset["label"],
        "active_preset_description": active_preset["description"],
        "threshold_rows": [
            {
                "key": "tracking_alert_hours",
                "label": "SLA suivi",
                "value": f"{values['tracking_alert_hours']}h",
            },
            {
                "key": "workflow_blockage_hours",
                "label": "Blocage workflow",
                "value": f"{values['workflow_blockage_hours']}h",
            },
            {
                "key": "pilotage_dispute_unassigned_hours",
                "label": "Litige sans owner",
                "value": f"{values['pilotage_dispute_unassigned_hours']}h",
            },
            {
                "key": "pilotage_workflow_blockage_unclaimed_hours",
                "label": "Blocage non pris en charge",
                "value": f"{values['pilotage_workflow_blockage_unclaimed_hours']}h",
            },
            {
                "key": "pilotage_queue_backlog_threshold",
                "label": "Backlog queue",
                "value": str(values["pilotage_queue_backlog_threshold"]),
            },
            {
                "key": "pilotage_planning_tension_pct",
                "label": "Planning tension",
                "value": f"{tension_pct}%",
            },
            {
                "key": "pilotage_planning_critical_pct",
                "label": "Planning critique",
                "value": f"{critical_pct}%",
            },
        ],
        "impact_rows": [
            {
                "key": "ops_escalations",
                "label": "Escalades estimees",
                "value": escalation_count,
            },
            {
                "key": "planning_tension",
                "label": "Vols en tension",
                "value": planning_impact["tension"],
            },
            {
                "key": "planning_critical",
                "label": "Vols critiques",
                "value": planning_impact["critical"],
            },
            {
                "key": "planning_overload",
                "label": "Vols en surcharge",
                "value": planning_impact["overload"],
            },
        ],
    }
