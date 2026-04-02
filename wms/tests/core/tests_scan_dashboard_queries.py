from datetime import date, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from wms.application.scan.dashboard_queries import (
    PERIOD_7D,
    _build_action_queue_row,
    _build_pending_action,
    _param_value,
    _parse_date_window,
    _period_start,
    _positive_int,
    build_scan_dashboard_payload,
)


class ScanDashboardQueriesTests(TestCase):
    def test_build_scan_dashboard_payload_includes_pending_actions(self):
        user = get_user_model().objects.create(
            username="dashboard-query-user",
            is_staff=True,
        )

        payload = build_scan_dashboard_payload(user=user)

        self.assertIn("pending_actions", payload)


class ScanDashboardQueryHelpersTests(SimpleTestCase):
    def test_param_value_supports_mapping_without_get(self):
        class NoGetMapping(dict):
            get = None

        self.assertEqual(_param_value(NoGetMapping(period="week"), "period"), "week")

    def test_period_start_supports_7d_and_unknown_periods(self):
        now = timezone.make_aware(datetime(2026, 4, 2, 14, 30))
        with mock.patch("wms.application.scan.dashboard_queries.timezone.now", return_value=now):
            self.assertEqual(_period_start(PERIOD_7D), now - timedelta(days=7))
            self.assertEqual(_period_start("unexpected"), now - timedelta(days=7))

    def test_parse_date_window_resets_invalid_ranges_to_current_week_defaults(self):
        default_start = date(2026, 3, 30)
        default_end = date(2026, 4, 5)
        with mock.patch(
            "wms.application.scan.dashboard_queries._current_week_date_bounds",
            return_value=(default_start, default_end),
        ):
            start_date, end_date, _start_at, _end_exclusive = _parse_date_window(
                "2026-04-10",
                "2026-04-01",
            )

        self.assertEqual((start_date, end_date), (default_start, default_end))

    def test_positive_int_returns_default_for_invalid_values(self):
        self.assertEqual(_positive_int("invalid", default=7), 7)

    def test_build_action_queue_row_rejects_invalid_owner(self):
        with self.assertRaisesMessage(ValueError, "Unsupported action queue owner"):
            _build_action_queue_row(
                label="Action",
                reference="REF",
                owner="unsupported",
                priority="high",
                url="/scan/",
            )

    def test_build_action_queue_row_rejects_invalid_priority(self):
        with self.assertRaisesMessage(ValueError, "Unsupported action queue priority"):
            _build_action_queue_row(
                label="Action",
                reference="REF",
                owner="admin",
                priority="urgent",
                url="/scan/",
            )

    def test_build_pending_action_rejects_invalid_owner(self):
        with self.assertRaisesMessage(ValueError, "Unsupported dashboard action owner"):
            _build_pending_action(
                action_type="workflow",
                reference="REF",
                label="Action",
                priority="high",
                owner="unsupported",
                url="/scan/",
            )

    def test_build_pending_action_rejects_invalid_priority(self):
        with self.assertRaisesMessage(ValueError, "Unsupported dashboard action priority"):
            _build_pending_action(
                action_type="workflow",
                reference="REF",
                label="Action",
                priority="urgent",
                owner="admin",
                url="/scan/",
            )
