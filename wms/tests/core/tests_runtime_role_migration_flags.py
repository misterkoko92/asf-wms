from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase, override_settings

from wms.models import WmsRuntimeSettings
from wms.runtime_settings import get_runtime_config


class RuntimeRoleMigrationFlagsTests(TestCase):
    def test_runtime_defaults_expose_current_runtime_flags(self):
        runtime = WmsRuntimeSettings.get_solo()
        self.assertEqual(runtime.low_stock_threshold, 20)
        self.assertTrue(runtime.enable_shipment_track_legacy)

        config = get_runtime_config()
        self.assertEqual(config.low_stock_threshold, 20)
        self.assertTrue(config.enable_shipment_track_legacy)

    def test_runtime_config_reads_current_settings_fallback(self):
        with override_settings(
            ENABLE_SHIPMENT_TRACK_LEGACY=False,
        ):
            with mock.patch(
                "wms.runtime_settings.get_runtime_settings_instance",
                side_effect=OperationalError("missing table"),
            ):
                config = get_runtime_config()

        self.assertFalse(config.enable_shipment_track_legacy)

    def test_runtime_config_clamps_low_stock_threshold_to_minimum_one(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.low_stock_threshold = 0
        runtime.save(update_fields=["low_stock_threshold"])
        runtime.refresh_from_db()
        self.assertEqual(runtime.low_stock_threshold, 0)

        config = get_runtime_config()
        self.assertEqual(config.low_stock_threshold, 1)
