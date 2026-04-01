from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
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
    OpsPilotageSnapshot,
    PlanningArtifact,
    PlanningVersion,
    ShipmentWorkflowProjection,
)
from wms.planning.exports import PLANNING_PDF_ARTIFACT, PLANNING_WORKBOOK_ARTIFACT
from wms.planning.stats import build_version_stats
from wms.workflow_projection import (
    DELAY_STATE_CRITICAL,
    DELAY_STATE_NEW,
    DELAY_STATE_PERSISTENT,
    build_destination_workflow_projection_rows,
)

OPS_PILOTAGE_SCOPE_TYPES = (
    "global",
    "destination",
    "flight",
    "queue",
    "planning_export",
)


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


def _queue_snapshot_rows(
    *,
    snapshot_date,
    source,
    event_type,
    metric_prefix,
    processing_timeout_seconds,
):
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
    payload = {"source": source, "event_type": event_type}
    metric_values = {
        f"{metric_prefix}_pending_count": status_counts.get(IntegrationStatus.PENDING, 0),
        f"{metric_prefix}_processing_count": status_counts.get(IntegrationStatus.PROCESSING, 0),
        f"{metric_prefix}_failed_count": status_counts.get(IntegrationStatus.FAILED, 0),
        f"{metric_prefix}_processed_count": status_counts.get(IntegrationStatus.PROCESSED, 0),
        f"{metric_prefix}_stale_processing_count": stale_processing_count,
    }
    return [
        {
            "snapshot_date": snapshot_date,
            "scope_type": "queue",
            "scope_key": source,
            "metric_key": metric_key,
            "metric_value": float(metric_value),
            "payload": payload,
            "captured_at": timezone.now(),
        }
        for metric_key, metric_value in metric_values.items()
    ]


def _global_projection_rows(*, snapshot_date):
    projection_qs = ShipmentWorkflowProjection.objects.all()
    counts = projection_qs.aggregate(
        sla_new_count=Count("id", filter=Q(delay_state=DELAY_STATE_NEW)),
        sla_persistent_count=Count("id", filter=Q(delay_state=DELAY_STATE_PERSISTENT)),
        sla_critical_count=Count("id", filter=Q(delay_state=DELAY_STATE_CRITICAL)),
        open_dispute_count=Count("id", filter=Q(has_open_dispute=True)),
        open_shipment_count=Count("id", filter=Q(is_closed=False)),
    )
    return [
        {
            "snapshot_date": snapshot_date,
            "scope_type": "global",
            "scope_key": "all",
            "metric_key": metric_key,
            "metric_value": float(metric_value or 0),
            "payload": {},
            "captured_at": timezone.now(),
        }
        for metric_key, metric_value in counts.items()
    ]


def _destination_projection_rows(*, snapshot_date):
    rows = build_destination_workflow_projection_rows(ShipmentWorkflowProjection.objects.all())
    metric_rows = []
    captured_at = timezone.now()
    for row in rows:
        scope_key = str(row["destination_id"] or row["destination_label"] or "unknown")
        payload = {"destination_label": row["destination_label"]}
        for metric_key in (
            "shipment_count",
            "open_shipment_count",
            "open_dispute_count",
            "delayed_shipment_count",
            "critical_shipment_count",
        ):
            metric_rows.append(
                {
                    "snapshot_date": snapshot_date,
                    "scope_type": "destination",
                    "scope_key": scope_key,
                    "metric_key": metric_key,
                    "metric_value": float(row.get(metric_key) or 0),
                    "payload": payload,
                    "captured_at": captured_at,
                }
            )
    return metric_rows


def _latest_planning_versions():
    latest_by_run = {}
    for version in PlanningVersion.objects.select_related("run").order_by(
        "run_id",
        "-number",
        "-id",
    ):
        latest_by_run.setdefault(version.run_id, version)
    return list(latest_by_run.values())


def _planning_flight_rows(*, snapshot_date):
    metric_rows = []
    captured_at = timezone.now()
    for version in _latest_planning_versions():
        stats = build_version_stats(version)
        for row in stats["flight_load_breakdown"]:
            scope_key = f"{version.pk}:{row['flight_snapshot_id']}"
            payload = {
                "version_id": version.pk,
                "flight_number": row["flight_number"],
                "destination_iata": row["destination_iata"],
                "load_state": row["load_state"],
            }
            remaining_units = row["remaining_units"]
            metric_rows.extend(
                [
                    {
                        "snapshot_date": snapshot_date,
                        "scope_type": "flight",
                        "scope_key": scope_key,
                        "metric_key": "capacity_overload_count",
                        "metric_value": 1.0 if row["load_state"] == "overload" else 0.0,
                        "payload": payload,
                        "captured_at": captured_at,
                    },
                    {
                        "snapshot_date": snapshot_date,
                        "scope_type": "flight",
                        "scope_key": scope_key,
                        "metric_key": "capacity_critical_count",
                        "metric_value": 1.0 if row["load_state"] == "critical" else 0.0,
                        "payload": payload,
                        "captured_at": captured_at,
                    },
                    {
                        "snapshot_date": snapshot_date,
                        "scope_type": "flight",
                        "scope_key": scope_key,
                        "metric_key": "capacity_tension_count",
                        "metric_value": 1.0 if row["load_state"] == "tension" else 0.0,
                        "payload": payload,
                        "captured_at": captured_at,
                    },
                    {
                        "snapshot_date": snapshot_date,
                        "scope_type": "flight",
                        "scope_key": scope_key,
                        "metric_key": "capacity_remaining_units",
                        "metric_value": float(
                            remaining_units if remaining_units is not None else 0
                        ),
                        "payload": payload,
                        "captured_at": captured_at,
                    },
                ]
            )
    return metric_rows


def _planning_export_rows(*, snapshot_date):
    metric_rows = []
    captured_at = timezone.now()
    for version in _latest_planning_versions():
        artifact_types = set(
            PlanningArtifact.objects.filter(version=version).values_list("artifact_type", flat=True)
        )
        payload = {"version_id": version.pk, "run_id": version.run_id}
        metric_rows.extend(
            [
                {
                    "snapshot_date": snapshot_date,
                    "scope_type": "planning_export",
                    "scope_key": str(version.pk),
                    "metric_key": "planning_pdf_ok",
                    "metric_value": 1.0 if PLANNING_PDF_ARTIFACT in artifact_types else 0.0,
                    "payload": payload,
                    "captured_at": captured_at,
                },
                {
                    "snapshot_date": snapshot_date,
                    "scope_type": "planning_export",
                    "scope_key": str(version.pk),
                    "metric_key": "planning_workbook_ok",
                    "metric_value": 1.0 if PLANNING_WORKBOOK_ARTIFACT in artifact_types else 0.0,
                    "payload": payload,
                    "captured_at": captured_at,
                },
            ]
        )
    return metric_rows


def build_ops_pilotage_snapshots(*, snapshot_date):
    rows = []
    rows.extend(_global_projection_rows(snapshot_date=snapshot_date))
    rows.extend(_destination_projection_rows(snapshot_date=snapshot_date))
    rows.extend(_planning_flight_rows(snapshot_date=snapshot_date))
    rows.extend(_planning_export_rows(snapshot_date=snapshot_date))
    rows.extend(
        _queue_snapshot_rows(
            snapshot_date=snapshot_date,
            source=DOCUMENT_SCAN_QUEUE_SOURCE,
            event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            metric_prefix="document_scan",
            processing_timeout_seconds=_document_scan_timeout_seconds(),
        )
    )
    rows.extend(
        _queue_snapshot_rows(
            snapshot_date=snapshot_date,
            source="wms.email",
            event_type="send_email",
            metric_prefix="email_queue",
            processing_timeout_seconds=900,
        )
    )
    return rows


def capture_ops_pilotage_snapshots(*, snapshot_date):
    rows = build_ops_pilotage_snapshots(snapshot_date=snapshot_date)
    with transaction.atomic():
        OpsPilotageSnapshot.objects.filter(snapshot_date=snapshot_date).delete()
        OpsPilotageSnapshot.objects.bulk_create(OpsPilotageSnapshot(**row) for row in rows)
    return len(rows)
