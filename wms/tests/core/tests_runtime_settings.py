from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase, override_settings

from wms.models import WmsRuntimeSettings
from wms.runtime_settings import get_runtime_config, is_shipment_track_legacy_enabled


class RuntimeSettingsTests(TestCase):
    def test_get_runtime_config_falls_back_when_runtime_table_unavailable(self):
        with override_settings(
            EMAIL_QUEUE_MAX_ATTEMPTS=0,
            EMAIL_QUEUE_RETRY_BASE_SECONDS=15,
            EMAIL_QUEUE_RETRY_MAX_SECONDS=10,
            EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS="invalid",
            ENABLE_SHIPMENT_TRACK_LEGACY=False,
        ):
            with mock.patch(
                "wms.runtime_settings.get_runtime_settings_instance",
                side_effect=OperationalError("missing table"),
            ):
                config = get_runtime_config()

        self.assertEqual(config.email_queue_max_attempts, 1)
        self.assertEqual(config.email_queue_retry_base_seconds, 15)
        self.assertEqual(config.email_queue_retry_max_seconds, 15)
        self.assertEqual(config.email_queue_processing_timeout_seconds, 900)
        self.assertFalse(config.enable_shipment_track_legacy)

    def test_get_runtime_config_clamps_invalid_persisted_values(self):
        runtime = WmsRuntimeSettings.get_solo()
        WmsRuntimeSettings.objects.filter(pk=runtime.pk).update(
            low_stock_threshold=0,
            tracking_alert_hours=0,
            workflow_blockage_hours=0,
            stale_drafts_age_days=0,
            email_queue_max_attempts=0,
            email_queue_retry_base_seconds=120,
            email_queue_retry_max_seconds=60,
            email_queue_processing_timeout_seconds=0,
            enable_shipment_track_legacy=False,
        )

        config = get_runtime_config()

        self.assertEqual(config.low_stock_threshold, 1)
        self.assertEqual(config.tracking_alert_hours, 1)
        self.assertEqual(config.workflow_blockage_hours, 1)
        self.assertEqual(config.stale_drafts_age_days, 1)
        self.assertEqual(config.email_queue_max_attempts, 1)
        self.assertEqual(config.email_queue_retry_base_seconds, 120)
        self.assertEqual(config.email_queue_retry_max_seconds, 120)
        self.assertEqual(config.email_queue_processing_timeout_seconds, 1)
        self.assertFalse(config.enable_shipment_track_legacy)

    def test_is_shipment_track_legacy_enabled_requires_env_and_runtime_flags(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.enable_shipment_track_legacy = True
        runtime.save(update_fields=["enable_shipment_track_legacy"])

        with override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=False):
            self.assertFalse(is_shipment_track_legacy_enabled())

        runtime.enable_shipment_track_legacy = False
        runtime.save(update_fields=["enable_shipment_track_legacy"])

        with override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=True):
            self.assertFalse(is_shipment_track_legacy_enabled())
