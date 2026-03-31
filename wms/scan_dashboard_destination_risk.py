from urllib.parse import urlencode

from django.urls import reverse

from .workflow_projection import build_destination_workflow_projection_rows

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


def build_destination_risk_snapshot(queryset, *, limit=5):
    base_rows = build_destination_workflow_projection_rows(queryset)
    oldest_open_segment_age_hours = max(
        (row["oldest_open_segment_age_hours"] or 0.0 for row in base_rows),
        default=0.0,
    )
    rows = []
    for row in base_rows[:limit]:
        rows.append(
            {
                "destination_id": row["destination_id"],
                "destination_label": row["destination_label"] or "Sans destination",
                "delayed_shipment_count": row["delayed_shipment_count"],
                "critical_shipment_count": row["critical_shipment_count"],
                "open_dispute_count": row["open_dispute_count"],
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
