from datetime import date

from django.test import SimpleTestCase, TestCase

from wms.application.pilotage.pilotage_queries import (
    _escalation_url,
    _latest_snapshot_date,
    _planning_version_url,
    _priority_rows,
    build_scan_pilotage_payload,
)


class PilotageQueriesTests(TestCase):
    def test_build_scan_pilotage_payload_exposes_summary_cards(self):
        payload = build_scan_pilotage_payload()

        self.assertIn("summary_cards", payload)


class PilotageQueryHelpersTests(SimpleTestCase):
    def test_latest_snapshot_date_returns_explicit_value(self):
        snapshot_date = date(2026, 4, 2)

        self.assertEqual(_latest_snapshot_date(snapshot_date=snapshot_date), snapshot_date)

    def test_planning_version_url_falls_back_to_run_list_for_empty_and_invalid_values(self):
        self.assertEqual(_planning_version_url(None), "/planning/")
        self.assertEqual(_planning_version_url("invalid"), "/planning/")

    def test_escalation_url_routes_categories_to_expected_pages(self):
        self.assertEqual(_escalation_url("sla_persistent", {}), "/scan/shipments-tracking/")
        self.assertEqual(
            _escalation_url("planning_pdf_missing", {"version_id": 12}),
            "/planning/versions/12/",
        )
        self.assertEqual(_escalation_url("portal_stalled", {}), "/scan/orders-view/")
        self.assertEqual(_escalation_url("unknown", {}), "/scan/dashboard/")

    def test_priority_rows_falls_back_to_portal_backlog_when_no_escalations_exist(self):
        rows = _priority_rows(
            [],
            portal_backlog_rows=[
                {
                    "reference": "CMD-1",
                    "review_status_label": "En attente",
                    "age_hours": 6.5,
                    "url": "/scan/orders/",
                }
            ],
        )

        self.assertEqual(rows[0]["label"], "Commande portail en attente")
        self.assertEqual(rows[0]["reference"], "CMD-1")
