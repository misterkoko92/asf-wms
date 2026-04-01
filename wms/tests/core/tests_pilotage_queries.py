from django.test import TestCase

from wms.application.pilotage.pilotage_queries import build_scan_pilotage_payload


class PilotageQueriesTests(TestCase):
    def test_build_scan_pilotage_payload_exposes_summary_cards(self):
        payload = build_scan_pilotage_payload()

        self.assertIn("summary_cards", payload)
