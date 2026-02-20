from django.test import TestCase

from wms.forms_scan_settings import ScanRuntimeSettingsForm


class ScanRuntimeSettingsFormTests(TestCase):
    def _payload(self, **overrides):
        data = {
            "low_stock_threshold": 20,
            "tracking_alert_hours": 72,
            "workflow_blockage_hours": 72,
            "stale_drafts_age_days": 30,
            "email_queue_max_attempts": 5,
            "email_queue_retry_base_seconds": 60,
            "email_queue_retry_max_seconds": 3600,
            "email_queue_processing_timeout_seconds": 900,
            "enable_shipment_track_legacy": "on",
        }
        data.update(overrides)
        return data

    def test_form_accepts_minimum_one_values(self):
        form = ScanRuntimeSettingsForm(
            data=self._payload(
                low_stock_threshold=1,
                tracking_alert_hours=1,
                workflow_blockage_hours=1,
                stale_drafts_age_days=1,
                email_queue_max_attempts=1,
                email_queue_retry_base_seconds=1,
                email_queue_retry_max_seconds=1,
                email_queue_processing_timeout_seconds=1,
            )
        )

        self.assertTrue(form.is_valid())

    def test_form_rejects_values_below_one(self):
        form = ScanRuntimeSettingsForm(
            data=self._payload(
                low_stock_threshold=0,
                tracking_alert_hours=0,
                workflow_blockage_hours=0,
                stale_drafts_age_days=0,
                email_queue_max_attempts=0,
                email_queue_retry_base_seconds=0,
                email_queue_retry_max_seconds=0,
                email_queue_processing_timeout_seconds=0,
            )
        )

        self.assertFalse(form.is_valid())
        for field_name in ScanRuntimeSettingsForm.MIN_ONE_FIELDS:
            self.assertIn(field_name, form.errors)

    def test_form_rejects_retry_max_below_retry_base(self):
        form = ScanRuntimeSettingsForm(
            data=self._payload(
                email_queue_retry_base_seconds=120,
                email_queue_retry_max_seconds=60,
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email_queue_retry_max_seconds", form.errors)
