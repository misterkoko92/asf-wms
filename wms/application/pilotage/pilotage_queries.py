from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from wms.models import (
    OpsEscalation,
    OpsPilotageSnapshot,
    Order,
    OrderReviewStatus,
    ShipmentWorkflowProjection,
)
from wms.ops_escalations import OPS_ESCALATION_STATUS_ACKNOWLEDGED, OPS_ESCALATION_STATUS_OPEN
from wms.pilotage_runtime import build_pilotage_threshold_context
from wms.runtime_settings import get_runtime_config
from wms.scan_dashboard_destination_risk import build_destination_risk_snapshot

PILOTAGE_ESCALATION_CATEGORY_LABELS = {
    "sla_persistent": "Retard SLA persistant",
    "dispute_unassigned": "Litige sans owner",
    "workflow_blockage_unclaimed": "Blocage sans prise en charge",
    "planning_capacity_overload": "Vol en surcharge",
    "planning_pdf_missing": "PDF planning manquant",
    "queue_backlog": "Queue en anomalie",
    "portal_stalled": "Commande portail en attente",
}
PILOTAGE_ESCALATION_CTA_LABELS = {
    "sla_persistent": "Ouvrir le suivi",
    "dispute_unassigned": "Ouvrir le suivi",
    "workflow_blockage_unclaimed": "Ouvrir le suivi",
    "planning_capacity_overload": "Ouvrir planning",
    "planning_pdf_missing": "Ouvrir planning",
    "queue_backlog": "Ouvrir scan",
    "portal_stalled": "Ouvrir commandes",
}
PILOTAGE_ESCALATION_STATUS_LABELS = {
    OPS_ESCALATION_STATUS_OPEN: "Ouverte",
    OPS_ESCALATION_STATUS_ACKNOWLEDGED: "Prise en charge",
}
PILOTAGE_SEVERITY_LABELS = {
    "critical": "Critique",
    "high": "Elevee",
    "medium": "Moyenne",
    "low": "Faible",
}
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_PORTAL_REVIEW_LABELS = {
    OrderReviewStatus.PENDING: "En attente",
    OrderReviewStatus.CHANGES_REQUESTED: "Corrections demandees",
}


def _latest_snapshot_date(snapshot_date=None):
    if snapshot_date is not None:
        return snapshot_date
    return (
        OpsPilotageSnapshot.objects.order_by("-snapshot_date")
        .values_list("snapshot_date", flat=True)
        .first()
    )


def _snapshot_label(snapshot_date):
    if snapshot_date is None:
        return "Aucune capture"
    return snapshot_date.isoformat()


def _global_metric_map(snapshot_date):
    if snapshot_date is None:
        return {}
    return {
        row.metric_key: row.metric_value
        for row in OpsPilotageSnapshot.objects.filter(
            snapshot_date=snapshot_date,
            scope_type="global",
            scope_key="all",
        )
    }


def _planning_version_url(version_id):
    if version_id in ("", None):
        return reverse("planning:run_list")
    try:
        return reverse("planning:version_detail", args=[int(version_id)])
    except (TypeError, ValueError):
        return reverse("planning:run_list")


def _escalation_url(category, payload):
    if category in {
        "sla_persistent",
        "dispute_unassigned",
        "workflow_blockage_unclaimed",
    }:
        return reverse("scan:scan_shipments_tracking")
    if category in {"planning_capacity_overload", "planning_pdf_missing"}:
        return _planning_version_url(payload.get("version_id"))
    if category == "portal_stalled":
        return reverse("scan:scan_orders_view")
    return reverse("scan:scan_dashboard")


def _active_escalations():
    escalations = []
    now = timezone.now()
    queryset = OpsEscalation.objects.filter(
        status__in=[OPS_ESCALATION_STATUS_OPEN, OPS_ESCALATION_STATUS_ACKNOWLEDGED]
    )
    for escalation in queryset:
        url = _escalation_url(escalation.category, escalation.payload or {})
        age_hours = round(
            max((now - escalation.first_detected_at).total_seconds(), 0) / 3600,
            1,
        )
        escalations.append(
            {
                "escalation_key": escalation.escalation_key,
                "category": escalation.category,
                "category_label": PILOTAGE_ESCALATION_CATEGORY_LABELS.get(
                    escalation.category,
                    escalation.category,
                ),
                "scope_type": escalation.scope_type,
                "reference": escalation.scope_key,
                "owner": escalation.owner or "-",
                "severity": escalation.severity,
                "severity_label": PILOTAGE_SEVERITY_LABELS.get(
                    escalation.severity,
                    escalation.severity,
                ),
                "status": escalation.status,
                "status_label": PILOTAGE_ESCALATION_STATUS_LABELS.get(
                    escalation.status,
                    escalation.status,
                ),
                "age_hours": age_hours,
                "last_detected_at": timezone.localtime(escalation.last_detected_at).isoformat(),
                "url": url,
                "cta_label": PILOTAGE_ESCALATION_CTA_LABELS.get(
                    escalation.category,
                    "Ouvrir",
                ),
            }
        )
    return sorted(
        escalations,
        key=lambda row: (
            _SEVERITY_RANK.get(row["severity"], 99),
            -row["age_hours"],
            row["category"],
            row["reference"],
        ),
    )


def _planning_export_rows(snapshot_date):
    if snapshot_date is None:
        return []
    grouped: dict[str, dict[str, object]] = {}
    for snapshot in OpsPilotageSnapshot.objects.filter(
        snapshot_date=snapshot_date,
        scope_type="planning_export",
    ).order_by("scope_key", "metric_key"):
        payload = snapshot.payload or {}
        row = grouped.setdefault(
            snapshot.scope_key,
            {
                "scope_key": snapshot.scope_key,
                "version_id": payload.get("version_id") or snapshot.scope_key,
                "run_id": payload.get("run_id") or "",
                "pdf_ok": False,
                "workbook_ok": False,
            },
        )
        if snapshot.metric_key == "planning_pdf_ok":
            row["pdf_ok"] = bool(snapshot.metric_value)
        elif snapshot.metric_key == "planning_workbook_ok":
            row["workbook_ok"] = bool(snapshot.metric_value)
    rows = []
    for row in grouped.values():
        row["url"] = _planning_version_url(row["version_id"])
        row["pdf_label"] = "OK" if row["pdf_ok"] else "Manquant"
        row["workbook_label"] = "OK" if row["workbook_ok"] else "Manquant"
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            row["pdf_ok"],
            row["workbook_ok"],
            str(row["version_id"]),
        ),
    )


def _portal_backlog_rows(*, limit=5):
    now = timezone.now()
    queryset = Order.objects.filter(
        review_status__in=[OrderReviewStatus.PENDING, OrderReviewStatus.CHANGES_REQUESTED],
        shipment__isnull=True,
    ).order_by("created_at", "id")
    rows = []
    for order in queryset[:limit]:
        rows.append(
            {
                "reference": order.reference or f"CMD-{order.pk}",
                "review_status": order.review_status,
                "review_status_label": _PORTAL_REVIEW_LABELS.get(
                    order.review_status,
                    order.review_status,
                ),
                "age_hours": round(
                    max((now - order.created_at).total_seconds(), 0) / 3600,
                    1,
                ),
                "url": reverse("scan:scan_orders_view"),
            }
        )
    return queryset.count(), rows


def _summary_cards(
    *, snapshot_label, global_metrics, escalation_rows, planning_export_rows, portal_backlog_count
):
    critical_sla_count = int(global_metrics.get("sla_critical_count", 0) or 0)
    open_dispute_count = int(global_metrics.get("open_dispute_count", 0) or 0)
    pdf_missing_count = sum(1 for row in planning_export_rows if not row["pdf_ok"])
    critical_escalation_count = sum(1 for row in escalation_rows if row["severity"] == "critical")
    return [
        {
            "label": "SLA critiques",
            "value": critical_sla_count,
            "help": f"Derniere capture: {snapshot_label}.",
            "url": reverse("scan:scan_dashboard"),
            "tone": "danger" if critical_sla_count else "neutral",
        },
        {
            "label": "Litiges ouverts",
            "value": open_dispute_count,
            "help": f"Derniere capture: {snapshot_label}.",
            "url": reverse("scan:scan_shipments_tracking"),
            "tone": "warn" if open_dispute_count else "neutral",
        },
        {
            "label": "Escalades critiques",
            "value": critical_escalation_count,
            "help": "Incidents pilotage encore actifs.",
            "url": "#scan-pilotage-escalations",
            "tone": "danger" if critical_escalation_count else "neutral",
        },
        {
            "label": "PDF planning KO",
            "value": pdf_missing_count,
            "help": f"Derniere capture: {snapshot_label}.",
            "url": reverse("planning:run_list"),
            "tone": "danger" if pdf_missing_count else "neutral",
        },
        {
            "label": "Backlog portail",
            "value": portal_backlog_count,
            "help": "Commandes sans expedition encore ouvertes.",
            "url": reverse("scan:scan_orders_view"),
            "tone": "warn" if portal_backlog_count else "neutral",
        },
    ]


def _priority_rows(escalation_rows, *, portal_backlog_rows):
    rows = [
        {
            "label": row["category_label"],
            "reference": row["reference"],
            "owner": row["owner"],
            "severity": row["severity_label"],
            "age_hours": row["age_hours"],
            "url": row["url"],
            "cta_label": row["cta_label"],
        }
        for row in escalation_rows[:6]
    ]
    if rows:
        return rows
    for row in portal_backlog_rows[:3]:
        rows.append(
            {
                "label": "Commande portail en attente",
                "reference": row["reference"],
                "owner": "portal",
                "severity": row["review_status_label"],
                "age_hours": row["age_hours"],
                "url": row["url"],
                "cta_label": "Ouvrir commandes",
            }
        )
    return rows


def build_scan_pilotage_payload(*, snapshot_date=None):
    runtime = get_runtime_config()
    runtime_values: dict[str, object] = {
        "tracking_alert_hours": runtime.tracking_alert_hours,
        "workflow_blockage_hours": runtime.workflow_blockage_hours,
        "pilotage_dispute_unassigned_hours": runtime.pilotage_dispute_unassigned_hours,
        "pilotage_workflow_blockage_unclaimed_hours": runtime.pilotage_workflow_blockage_unclaimed_hours,
        "pilotage_queue_backlog_threshold": runtime.pilotage_queue_backlog_threshold,
        "pilotage_planning_tension_pct": runtime.pilotage_planning_tension_pct,
        "pilotage_planning_critical_pct": runtime.pilotage_planning_critical_pct,
        "email_queue_processing_timeout_seconds": runtime.email_queue_processing_timeout_seconds,
    }
    latest_snapshot_date = _latest_snapshot_date(snapshot_date=snapshot_date)
    snapshot_label = _snapshot_label(latest_snapshot_date)
    global_metrics = _global_metric_map(latest_snapshot_date)
    escalation_rows = _active_escalations()
    planning_export_rows = _planning_export_rows(latest_snapshot_date)
    portal_backlog_count, portal_backlog_rows = _portal_backlog_rows()
    destination_snapshot = build_destination_risk_snapshot(
        ShipmentWorkflowProjection.objects.all(),
        limit=5,
    )
    destination_trend_rows = [
        {
            "destination_id": row["destination_id"],
            "destination_label": row["destination_label"],
            "current_week_label": row["current_week_label"],
            "current_week_score": row["current_week_score"],
            "previous_week_label": row["previous_week_label"],
            "previous_week_score": row["previous_week_score"],
            "trend_label": row["trend_label"],
            "trend_direction": row["trend_direction"],
            "critical_shipment_count": row["critical_shipment_count"],
            "open_dispute_count": row["open_dispute_count"],
            "url": row["url"],
            "cta_label": row["cta_label"],
        }
        for row in destination_snapshot["rows"]
    ]
    return {
        "snapshot_date": latest_snapshot_date.isoformat() if latest_snapshot_date else "",
        "snapshot_label": snapshot_label,
        "surface_links": {
            "scan_dashboard_url": reverse("scan:scan_dashboard"),
            "portal_dashboard_url": reverse("portal:portal_dashboard"),
            "planning_run_list_url": reverse("planning:run_list"),
        },
        "pilotage_threshold_context": build_pilotage_threshold_context(runtime_values),
        "summary_cards": _summary_cards(
            snapshot_label=snapshot_label,
            global_metrics=global_metrics,
            escalation_rows=escalation_rows,
            planning_export_rows=planning_export_rows,
            portal_backlog_count=portal_backlog_count,
        ),
        "priority_rows": _priority_rows(
            escalation_rows,
            portal_backlog_rows=portal_backlog_rows,
        ),
        "escalation_rows": escalation_rows,
        "destination_trend_rows": destination_trend_rows,
        "planning_export_rows": planning_export_rows,
        "portal_backlog_rows": portal_backlog_rows,
    }
