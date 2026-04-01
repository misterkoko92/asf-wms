from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from wms.document_scan_queue import (
    DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
)
from wms.models import (
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    OpsEscalation,
    Order,
    OrderReviewStatus,
    PlanningArtifact,
    PlanningVersion,
    Shipment,
    ShipmentWorkflowProjection,
    WmsRuntimeSettings,
)
from wms.planning.exports import PLANNING_PDF_ARTIFACT
from wms.planning.stats import build_version_stats
from wms.scan_dashboard_sla import annotate_shipment_tracking_dates
from wms.workflow_blockage_queue import build_workflow_blockage_rows

OPS_ESCALATION_STATUS_OPEN = "open"
OPS_ESCALATION_STATUS_ACKNOWLEDGED = "acknowledged"
OPS_ESCALATION_STATUS_RESOLVED = "resolved"
OPS_ESCALATION_STATUS_SUPPRESSED = "suppressed"


def _config_dict(config=None):
    if config is not None:
        return {
            "tracking_alert_hours": int(config["tracking_alert_hours"]),
            "workflow_blockage_hours": int(config["workflow_blockage_hours"]),
            "email_queue_processing_timeout_seconds": int(
                config["email_queue_processing_timeout_seconds"]
            ),
            "pilotage_dispute_unassigned_hours": int(config["pilotage_dispute_unassigned_hours"]),
            "pilotage_workflow_blockage_unclaimed_hours": int(
                config["pilotage_workflow_blockage_unclaimed_hours"]
            ),
            "pilotage_queue_backlog_threshold": int(config["pilotage_queue_backlog_threshold"]),
        }
    runtime = WmsRuntimeSettings.get_solo()
    return {
        "tracking_alert_hours": int(runtime.tracking_alert_hours),
        "workflow_blockage_hours": int(runtime.workflow_blockage_hours),
        "email_queue_processing_timeout_seconds": int(
            runtime.email_queue_processing_timeout_seconds
        ),
        "pilotage_dispute_unassigned_hours": int(runtime.pilotage_dispute_unassigned_hours),
        "pilotage_workflow_blockage_unclaimed_hours": int(
            runtime.pilotage_workflow_blockage_unclaimed_hours
        ),
        "pilotage_queue_backlog_threshold": int(runtime.pilotage_queue_backlog_threshold),
    }


def _document_scan_timeout_seconds() -> int:
    try:
        timeout_seconds = int(
            getattr(
                settings,
                "DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS",
                DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
            )
        )
    except (TypeError, ValueError):
        return DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS
    return max(timeout_seconds, 1)


def _latest_planning_versions():
    latest_by_run = {}
    for version in PlanningVersion.objects.select_related("run").order_by(
        "run_id",
        "-number",
        "-id",
    ):
        latest_by_run.setdefault(version.run_id, version)
    return list(latest_by_run.values())


def _build_escalation(
    *,
    escalation_key,
    category,
    scope_type,
    scope_key,
    severity,
    owner,
    payload,
):
    return {
        "escalation_key": escalation_key,
        "category": category,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "severity": severity,
        "owner": owner,
        "payload": payload,
    }


def _queue_status_counts(*, source, event_type, processing_timeout_seconds):
    queue_qs = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=source,
        event_type=event_type,
    )
    status_counts = {
        item["status"]: item["total"]
        for item in queue_qs.values("status").annotate(total=Count("id"))
    }
    stale_cutoff = timezone.now() - timedelta(seconds=processing_timeout_seconds)
    stale_processing_count = queue_qs.filter(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_cutoff,
    ).count()
    return {
        "pending_count": status_counts.get(IntegrationStatus.PENDING, 0),
        "processing_count": status_counts.get(IntegrationStatus.PROCESSING, 0),
        "failed_count": status_counts.get(IntegrationStatus.FAILED, 0),
        "processed_count": status_counts.get(IntegrationStatus.PROCESSED, 0),
        "stale_processing_count": stale_processing_count,
    }


def evaluate_ops_escalations(*, now=None, config=None):
    current_time = now or timezone.now()
    values = _config_dict(config)
    escalations = []

    dispute_cutoff = current_time - timedelta(
        hours=max(values["pilotage_dispute_unassigned_hours"], 1)
    )
    open_unassigned_disputes = Shipment.objects.filter(
        archived_at__isnull=True,
        is_disputed=True,
        closed_at__isnull=True,
        dispute_owner="",
    ).order_by("dispute_opened_at", "disputed_at", "created_at")
    for shipment in open_unassigned_disputes.values(
        "id",
        "reference",
        "dispute_reason",
        "dispute_opened_at",
        "disputed_at",
        "created_at",
    ):
        started_at = (
            shipment["dispute_opened_at"] or shipment["disputed_at"] or shipment["created_at"]
        )
        if started_at is None or started_at > dispute_cutoff:
            continue
        escalations.append(
            _build_escalation(
                escalation_key=f"dispute_unassigned:shipment:{shipment['id']}",
                category="dispute_unassigned",
                scope_type="shipment",
                scope_key=shipment["reference"] or str(shipment["id"]),
                severity="high",
                owner="qualite",
                payload={
                    "shipment_id": shipment["id"],
                    "reference": shipment["reference"] or "",
                    "dispute_reason": shipment["dispute_reason"] or "",
                },
            )
        )

    for projection in ShipmentWorkflowProjection.objects.filter(
        is_closed=False,
        delay_state__in=["persistent", "critical"],
    ).values(
        "shipment_id",
        "reference",
        "delay_state",
        "current_delay_hours",
        "dispute_owner",
    ):
        escalations.append(
            _build_escalation(
                escalation_key=f"sla_persistent:shipment:{projection['shipment_id']}",
                category="sla_persistent",
                scope_type="shipment",
                scope_key=projection["reference"] or str(projection["shipment_id"]),
                severity="critical" if projection["delay_state"] == "critical" else "high",
                owner=projection["dispute_owner"] or "qualite",
                payload={
                    "shipment_id": projection["shipment_id"],
                    "reference": projection["reference"] or "",
                    "delay_state": projection["delay_state"],
                    "current_delay_hours": projection["current_delay_hours"] or 0.0,
                },
            )
        )

    shipments_scope = Shipment.objects.filter(archived_at__isnull=True)
    shipments_with_tracking = annotate_shipment_tracking_dates(shipments_scope)
    claim_cutoff_hours = max(values["pilotage_workflow_blockage_unclaimed_hours"], 1)
    for row in build_workflow_blockage_rows(
        shipments_scope=shipments_scope,
        shipments_with_tracking=shipments_with_tracking,
        workflow_blockage_hours=values["workflow_blockage_hours"],
        tracking_alert_hours=values["tracking_alert_hours"],
        email_queue_processing_timeout_seconds=values["email_queue_processing_timeout_seconds"],
        document_scan_processing_timeout_seconds=_document_scan_timeout_seconds(),
    ):
        if row["is_claimed"] or row["age_hours"] < claim_cutoff_hours:
            continue
        escalations.append(
            _build_escalation(
                escalation_key=f"workflow_blockage_unclaimed:{row['blockage_key']}",
                category="workflow_blockage_unclaimed",
                scope_type="workflow_blockage",
                scope_key=row["blockage_key"],
                severity="high" if row["priority"] == "high" else "medium",
                owner=row["owner"],
                payload={
                    "reference": row["reference"],
                    "category": row["category"],
                    "priority": row["priority"],
                    "age_hours": row["age_hours"],
                },
            )
        )

    for version in _latest_planning_versions():
        if not version.artifacts.filter(artifact_type=PLANNING_PDF_ARTIFACT).exists():
            escalations.append(
                _build_escalation(
                    escalation_key=f"planning_pdf_missing:version:{version.pk}",
                    category="planning_pdf_missing",
                    scope_type="planning_version",
                    scope_key=str(version.pk),
                    severity="high",
                    owner="admin",
                    payload={"version_id": version.pk, "run_id": version.run_id},
                )
            )
        stats = build_version_stats(version)
        for row in stats["flight_load_breakdown"]:
            if row["load_state"] != "overload":
                continue
            escalations.append(
                _build_escalation(
                    escalation_key=(
                        f"planning_capacity_overload:version:{version.pk}:"
                        f"flight:{row['flight_snapshot_id']}"
                    ),
                    category="planning_capacity_overload",
                    scope_type="flight",
                    scope_key=f"{version.pk}:{row['flight_snapshot_id']}",
                    severity="critical",
                    owner="admin",
                    payload={
                        "version_id": version.pk,
                        "flight_number": row["flight_number"],
                        "destination_iata": row["destination_iata"],
                        "remaining_units": row["remaining_units"],
                    },
                )
            )

    queue_threshold = max(values["pilotage_queue_backlog_threshold"], 1)
    for source, event_type, metric_label, timeout_seconds in (
        (
            DOCUMENT_SCAN_QUEUE_SOURCE,
            DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            "document_scan",
            _document_scan_timeout_seconds(),
        ),
        (
            "wms.email",
            "send_email",
            "email_queue",
            values["email_queue_processing_timeout_seconds"],
        ),
    ):
        counts = _queue_status_counts(
            source=source,
            event_type=event_type,
            processing_timeout_seconds=timeout_seconds,
        )
        backlog_size = (
            counts["pending_count"] + counts["failed_count"] + counts["stale_processing_count"]
        )
        if backlog_size < queue_threshold:
            continue
        escalations.append(
            _build_escalation(
                escalation_key=f"queue_backlog:{source}",
                category="queue_backlog",
                scope_type="queue",
                scope_key=source,
                severity="high" if counts["failed_count"] == 0 else "critical",
                owner="admin",
                payload={"metric_label": metric_label, **counts},
            )
        )

    portal_cutoff = current_time - timedelta(hours=max(values["workflow_blockage_hours"], 1))
    for order in Order.objects.filter(
        review_status__in=[
            OrderReviewStatus.PENDING,
            OrderReviewStatus.CHANGES_REQUESTED,
        ],
        shipment__isnull=True,
        created_at__lte=portal_cutoff,
    ).values("id", "reference", "review_status"):
        escalations.append(
            _build_escalation(
                escalation_key=f"portal_stalled:order:{order['id']}",
                category="portal_stalled",
                scope_type="order",
                scope_key=order["reference"] or str(order["id"]),
                severity="medium",
                owner="portal",
                payload={
                    "order_id": order["id"],
                    "reference": order["reference"] or "",
                    "review_status": order["review_status"],
                },
            )
        )

    escalations.sort(
        key=lambda item: (
            0 if item["severity"] == "critical" else 1 if item["severity"] == "high" else 2,
            item["category"],
            item["scope_key"],
        )
    )
    return escalations


def sync_ops_escalations(*, now=None, config=None):
    current_time = now or timezone.now()
    escalation_rows = evaluate_ops_escalations(now=current_time, config=config)
    active_keys = set()
    open_or_ack_statuses = [OPS_ESCALATION_STATUS_OPEN, OPS_ESCALATION_STATUS_ACKNOWLEDGED]

    with transaction.atomic():
        for row in escalation_rows:
            active_keys.add(row["escalation_key"])
            escalation, created = OpsEscalation.objects.get_or_create(
                escalation_key=row["escalation_key"],
                defaults={
                    **row,
                    "status": OPS_ESCALATION_STATUS_OPEN,
                    "first_detected_at": current_time,
                    "last_detected_at": current_time,
                },
            )
            if created:
                continue
            escalation.category = row["category"]
            escalation.scope_type = row["scope_type"]
            escalation.scope_key = row["scope_key"]
            escalation.severity = row["severity"]
            escalation.owner = row["owner"]
            escalation.payload = row["payload"]
            escalation.last_detected_at = current_time
            if escalation.status == OPS_ESCALATION_STATUS_RESOLVED:
                escalation.status = OPS_ESCALATION_STATUS_OPEN
                escalation.resolved_at = None
            escalation.save(
                update_fields=[
                    "category",
                    "scope_type",
                    "scope_key",
                    "severity",
                    "owner",
                    "payload",
                    "last_detected_at",
                    "status",
                    "resolved_at",
                ]
            )

        resolved_qs = OpsEscalation.objects.exclude(
            status=OPS_ESCALATION_STATUS_SUPPRESSED
        ).exclude(escalation_key__in=active_keys)
        resolved_qs = resolved_qs.exclude(status=OPS_ESCALATION_STATUS_RESOLVED)
        resolved_count = resolved_qs.update(
            status=OPS_ESCALATION_STATUS_RESOLVED,
            resolved_at=current_time,
            last_detected_at=current_time,
        )

    open_count = OpsEscalation.objects.filter(status__in=open_or_ack_statuses).count()
    return {
        "open_count": open_count,
        "resolved_count": resolved_count,
        "escalation_rows": escalation_rows,
    }
