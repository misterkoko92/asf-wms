from django.test import TestCase

from wms.forms_scan_settings import ScanRuntimeSettingsForm
from wms.models import WmsRuntimeSettings


class ScanRuntimeSettingsFormTests(TestCase):
    def setUp(self):
        self.runtime_settings = WmsRuntimeSettings.get_solo()

    def _payload(self, **overrides):
        runtime = self.runtime_settings
        data = {
            "low_stock_threshold": runtime.low_stock_threshold,
            "tracking_alert_hours": runtime.tracking_alert_hours,
            "workflow_blockage_hours": runtime.workflow_blockage_hours,
            "stale_drafts_age_days": runtime.stale_drafts_age_days,
            "email_queue_max_attempts": runtime.email_queue_max_attempts,
            "email_queue_retry_base_seconds": runtime.email_queue_retry_base_seconds,
            "email_queue_retry_max_seconds": runtime.email_queue_retry_max_seconds,
            "email_queue_processing_timeout_seconds": runtime.email_queue_processing_timeout_seconds,
            "enable_shipment_track_legacy": (
                "on" if runtime.enable_shipment_track_legacy else ""
            ),
            "change_note": "Mise a jour test",
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

    def test_form_requires_change_note_when_runtime_values_change(self):
        form = ScanRuntimeSettingsForm(
            data=self._payload(low_stock_threshold=12, change_note=""),
            instance=self.runtime_settings,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("change_note", form.errors)

    def test_form_allows_empty_change_note_when_values_unchanged(self):
        form = ScanRuntimeSettingsForm(
            data=self._payload(change_note=""),
            instance=self.runtime_settings,
        )

        self.assertTrue(form.is_valid())

    def test_form_allows_empty_change_note_for_preview_action(self):
        form = ScanRuntimeSettingsForm(
            data=self._payload(
                low_stock_threshold=self.runtime_settings.low_stock_threshold + 1,
                change_note="",
                action="preview",
            ),
            instance=self.runtime_settings,
        )

        self.assertTrue(form.is_valid())
