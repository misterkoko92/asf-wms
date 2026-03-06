from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from wms.views_scan_shipments_support import (
    CLOSED_FILTER_ALL,
    CLOSED_FILTER_EXCLUDE,
    _build_shipments_tracking_redirect_url,
    _parse_planned_week,
    _shipment_can_be_closed,
)


class ScanShipmentsSupportHelpersTests(SimpleTestCase):
    def test_parse_planned_week_normalizes_valid_inputs(self):
        cleaned, start, end = _parse_planned_week("2026-05")
        self.assertEqual(cleaned, "2026-W05")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(end - start, timedelta(days=7))

        cleaned_with_w, start_with_w, end_with_w = _parse_planned_week("2026-W05")
        self.assertEqual(cleaned_with_w, "2026-W05")
        self.assertEqual(start_with_w, start)
        self.assertEqual(end_with_w, end)

    def test_parse_planned_week_handles_invalid_iso_week(self):
        cleaned, start, end = _parse_planned_week("2026-W54")

        self.assertEqual(cleaned, "2026-W54")
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_build_shipments_tracking_redirect_url_keeps_filters(self):
        redirect_url = _build_shipments_tracking_redirect_url(
            planned_week_value="2026-W05",
            closed_filter=CLOSED_FILTER_ALL,
        )

        self.assertEqual(
            redirect_url,
            f"{reverse('scan:scan_shipments_tracking')}?planned_week=2026-W05&closed=all",
        )

    def test_build_shipments_tracking_redirect_url_returns_base_without_filters(self):
        redirect_url = _build_shipments_tracking_redirect_url(
            planned_week_value="",
            closed_filter=CLOSED_FILTER_EXCLUDE,
        )

        self.assertEqual(redirect_url, reverse("scan:scan_shipments_tracking"))

    def test_shipment_can_be_closed_returns_false_when_row_is_missing(self):
        with mock.patch(
            "wms.views_scan_shipments_support.build_shipments_tracking_rows",
            return_value=[],
        ):
            self.assertFalse(_shipment_can_be_closed(mock.Mock()))

    def test_shipment_can_be_closed_reads_can_close_flag(self):
        with mock.patch(
            "wms.views_scan_shipments_support.build_shipments_tracking_rows",
            return_value=[{"can_close": True}],
        ):
            self.assertTrue(_shipment_can_be_closed(mock.Mock()))
