from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.application.scan.dashboard_queries import build_scan_dashboard_payload


class ScanDashboardQueriesTests(TestCase):
    def test_build_scan_dashboard_payload_includes_pending_actions(self):
        user = get_user_model().objects.create(
            username="dashboard-query-user",
            is_staff=True,
        )

        payload = build_scan_dashboard_payload(user=user)

        self.assertIn("pending_actions", payload)
