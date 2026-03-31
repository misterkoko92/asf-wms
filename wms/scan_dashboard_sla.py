from datetime import timedelta

from django.db.models import Max, Q
from django.utils import timezone

from .models import ShipmentStatus, ShipmentTrackingStatus

OPEN_SLA_SEGMENTS = (
    {
        "key": "planned_to_boarding",
        "shipment_status": ShipmentStatus.PLANNED,
        "start": "planned_at",
        "end": "boarding_ok_at",
        "owner": "magasin",
    },
    {
        "key": "boarding_to_correspondent",
        "shipment_status": ShipmentStatus.SHIPPED,
        "start": "boarding_ok_at",
        "end": "received_correspondent_at",
        "owner": "qualite",
    },
    {
        "key": "correspondent_to_delivery",
        "shipment_status": ShipmentStatus.RECEIVED_CORRESPONDENT,
        "start": "received_correspondent_at",
        "end": "received_recipient_at",
        "owner": "portal",
    },
)

AGGREGATE_SLA_SEGMENTS = (
    {
        "key": "planned_to_boarding",
        "start": "planned_at",
        "end": "boarding_ok_at",
        "target_multiplier": 1,
    },
    {
        "key": "boarding_to_correspondent",
        "start": "boarding_ok_at",
        "end": "received_correspondent_at",
        "target_multiplier": 1,
    },
    {
        "key": "correspondent_to_delivery",
        "start": "received_correspondent_at",
        "end": "received_recipient_at",
        "target_multiplier": 1,
    },
    {
        "key": "planned_to_delivery",
        "start": "planned_at",
        "end": "received_recipient_at",
        "target_multiplier": 3,
    },
)


def annotate_shipment_tracking_dates(queryset):
    return queryset.annotate(
        planned_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.PLANNED),
        ),
        boarding_ok_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.BOARDING_OK),
        ),
        received_correspondent_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT),
        ),
        received_recipient_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT),
        ),
    )


def _hours_between(start_at, end_at):
    if start_at is None or end_at is None:
        return None
    if end_at < start_at:
        return 0.0
    return (end_at - start_at).total_seconds() / 3600


def build_sla_rows(shipments_with_tracking, *, tracking_alert_hours):
    rows = list(
        shipments_with_tracking.values(
            "planned_at",
            "boarding_ok_at",
            "received_correspondent_at",
            "received_recipient_at",
        )
    )
    sla_rows = []
    for segment in AGGREGATE_SLA_SEGMENTS:
        durations = []
        for row in rows:
            duration_hours = _hours_between(row[segment["start"]], row[segment["end"]])
            if duration_hours is None:
                continue
            durations.append(duration_hours)
        completed_count = len(durations)
        breach_count = sum(
            1
            for duration_hours in durations
            if duration_hours > tracking_alert_hours * segment["target_multiplier"]
        )
        average_hours = round(sum(durations) / completed_count, 1) if durations else None
        max_hours = round(max(durations), 1) if durations else None
        sla_rows.append(
            {
                "segment_key": segment["key"],
                "target_hours": tracking_alert_hours * segment["target_multiplier"],
                "completed_count": completed_count,
                "breach_count": breach_count,
                "average_hours": average_hours,
                "max_hours": max_hours,
            }
        )
    return sla_rows


def _classify_alert(age_hours, *, tracking_alert_hours):
    if age_hours > tracking_alert_hours * 3:
        return {
            "freshness": "persistent",
            "severity": "critical",
            "priority": "high",
        }
    if age_hours > tracking_alert_hours * 2:
        return {
            "freshness": "persistent",
            "severity": "high",
            "priority": "high",
        }
    return {
        "freshness": "new",
        "severity": "high",
        "priority": "medium",
    }


def build_sla_alert_rows(shipments_with_tracking, *, tracking_alert_hours):
    now = timezone.now()
    cutoff = now - timedelta(hours=tracking_alert_hours)
    alert_rows = []
    for segment_index, segment in enumerate(OPEN_SLA_SEGMENTS):
        filters = {
            "closed_at__isnull": True,
            "is_disputed": False,
            "status": segment["shipment_status"],
            f"{segment['start']}__isnull": False,
            f"{segment['start']}__lt": cutoff,
            f"{segment['end']}__isnull": True,
        }
        rows = shipments_with_tracking.filter(**filters).values(
            "id",
            "reference",
            "tracking_token",
            segment["start"],
        )
        for row in rows:
            started_at = row[segment["start"]]
            age_hours = round(_hours_between(started_at, now) or 0.0, 1)
            delay_hours = round(max(age_hours - tracking_alert_hours, 0.0), 1)
            classification = _classify_alert(
                age_hours,
                tracking_alert_hours=tracking_alert_hours,
            )
            alert_rows.append(
                {
                    "shipment_id": row["id"],
                    "reference": row["reference"] or f"EXP-{row['id']}",
                    "tracking_token": row["tracking_token"],
                    "segment_key": segment["key"],
                    "owner": segment["owner"],
                    "started_at": started_at,
                    "age_hours": age_hours,
                    "delay_hours": delay_hours,
                    "freshness": classification["freshness"],
                    "severity": classification["severity"],
                    "priority": classification["priority"],
                    "_segment_index": segment_index,
                }
            )
    severity_rank = {"critical": 0, "high": 1}
    freshness_rank = {"persistent": 0, "new": 1}
    alert_rows.sort(
        key=lambda row: (
            severity_rank.get(row["severity"], 9),
            freshness_rank.get(row["freshness"], 9),
            -row["delay_hours"],
            row["_segment_index"],
            row["reference"],
        )
    )
    for row in alert_rows:
        row.pop("_segment_index", None)
    return alert_rows


def summarize_sla_alert_rows(alert_rows):
    return {
        "new_count": sum(1 for row in alert_rows if row["freshness"] == "new"),
        "persistent_count": sum(
            1
            for row in alert_rows
            if row["freshness"] == "persistent" and row["severity"] != "critical"
        ),
        "critical_count": sum(1 for row in alert_rows if row["severity"] == "critical"),
    }
