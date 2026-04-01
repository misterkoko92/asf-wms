from datetime import date
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from wms.scan_dashboard_destination_risk import build_destination_risk_snapshot


class DestinationRiskSnapshotTests(SimpleTestCase):
    @mock.patch("wms.scan_dashboard_destination_risk.timezone.localdate")
    @mock.patch(
        "wms.scan_dashboard_destination_risk.build_destination_week_workflow_projection_rows"
    )
    @mock.patch("wms.scan_dashboard_destination_risk.build_destination_workflow_projection_rows")
    def test_build_destination_risk_snapshot_supports_missing_destination_and_negative_trend(
        self,
        destination_rows_mock,
        destination_week_rows_mock,
        localdate_mock,
    ):
        localdate_mock.return_value = date(2026, 4, 1)
        destination_rows_mock.return_value = [
            {
                "destination_id": None,
                "destination_label": "",
                "delayed_shipment_count": 0,
                "critical_shipment_count": 0,
                "open_dispute_count": 0,
                "top_blockage_category": None,
                "oldest_open_segment_age_hours": 0.0,
            }
        ]
        destination_week_rows_mock.side_effect = [
            [
                {
                    "destination_id": None,
                    "delayed_shipment_count": 0,
                    "open_dispute_count": 0,
                    "critical_shipment_count": 0,
                }
            ],
            [
                {
                    "destination_id": None,
                    "delayed_shipment_count": 1,
                    "open_dispute_count": 1,
                    "critical_shipment_count": 0,
                }
            ],
        ]

        snapshot = build_destination_risk_snapshot(mock.sentinel.queryset, limit=1)

        self.assertEqual(len(snapshot["rows"]), 1)
        row = snapshot["rows"][0]
        self.assertEqual(row["url"], reverse("scan:scan_shipments_tracking"))
        self.assertEqual(row["trend_direction"], "down")
        self.assertEqual(row["trend_label"], "-2")
        self.assertEqual(row["top_blockage_category"], "Aucun blocage actif")
