from datetime import timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone

from .workflow_projection import (
    build_destination_week_workflow_projection_rows,
    build_destination_workflow_projection_rows,
)

DESTINATION_RISK_BLOCKAGE_LABELS = {
    "creation_expedition": "Création expédition",
    "suivi": "Suivi",
    "cloture": "Clôture",
}
DESTINATION_RISK_EMPTY_BLOCKAGE_LABEL = "Aucun blocage actif"
DESTINATION_RISK_CTA_LABEL = "Ouvrir les dossiers"


def _shipments_tracking_url(destination_id):
    base_url = reverse("scan:scan_shipments_tracking")
    if not destination_id:
        return base_url
    return f"{base_url}?{urlencode({'destination': destination_id})}"


def _week_score(row):
    if not row:
        return 0
    return (
        row["delayed_shipment_count"] + row["open_dispute_count"] + row["critical_shipment_count"]
    )


def _trend_direction(delta):
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


def _trend_label(delta):
    if delta > 0:
        return f"+{delta}"
    if delta < 0:
        return str(delta)
    return "stable"


def _week_label(local_date):
    iso_year, iso_week, _ = local_date.isocalendar()
    return iso_year, iso_week, f"{iso_year}-W{iso_week:02d}"


def build_destination_risk_snapshot(queryset, *, limit=5):
    base_rows = build_destination_workflow_projection_rows(queryset)
    current_local_date = timezone.localdate()
    previous_local_date = current_local_date - timedelta(days=7)
    current_year, current_week, current_week_label = _week_label(current_local_date)
    previous_year, previous_week, previous_week_label = _week_label(previous_local_date)
    current_week_rows = {
        row["destination_id"]: row
        for row in build_destination_week_workflow_projection_rows(
            queryset,
            iso_year=current_year,
            iso_week=current_week,
        )
    }
    previous_week_rows = {
        row["destination_id"]: row
        for row in build_destination_week_workflow_projection_rows(
            queryset,
            iso_year=previous_year,
            iso_week=previous_week,
        )
    }
    oldest_open_segment_age_hours = max(
        (row["oldest_open_segment_age_hours"] or 0.0 for row in base_rows),
        default=0.0,
    )
    rows = []
    for row in base_rows[:limit]:
        current_week_row = current_week_rows.get(row["destination_id"])
        previous_week_row = previous_week_rows.get(row["destination_id"])
        current_week_score = _week_score(current_week_row)
        previous_week_score = _week_score(previous_week_row)
        trend_delta = current_week_score - previous_week_score
        rows.append(
            {
                "destination_id": row["destination_id"],
                "destination_label": row["destination_label"] or "Sans destination",
                "delayed_shipment_count": row["delayed_shipment_count"],
                "critical_shipment_count": row["critical_shipment_count"],
                "open_dispute_count": row["open_dispute_count"],
                "current_week_label": current_week_label,
                "current_week_score": current_week_score,
                "previous_week_label": previous_week_label,
                "previous_week_score": previous_week_score,
                "trend_delta": trend_delta,
                "trend_direction": _trend_direction(trend_delta),
                "trend_label": _trend_label(trend_delta),
                "top_blockage_category": DESTINATION_RISK_BLOCKAGE_LABELS.get(
                    row["top_blockage_category"],
                    DESTINATION_RISK_EMPTY_BLOCKAGE_LABEL,
                ),
                "oldest_open_segment_age_hours": row["oldest_open_segment_age_hours"] or 0.0,
                "url": _shipments_tracking_url(row["destination_id"]),
                "cta_label": DESTINATION_RISK_CTA_LABEL,
            }
        )
    return {
        "summary": {
            "critical_destinations_count": sum(
                1 for row in base_rows if row["critical_shipment_count"] > 0
            ),
            "disputed_destinations_count": sum(
                1 for row in base_rows if row["open_dispute_count"] > 0
            ),
            "oldest_open_segment_age_hours": oldest_open_segment_age_hours,
        },
        "rows": rows,
    }
