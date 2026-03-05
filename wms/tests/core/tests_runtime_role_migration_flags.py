from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase, override_settings

from wms.models import WmsRuntimeSettings
from wms.runtime_settings import get_runtime_config


class RuntimeRoleMigrationFlagsTests(TestCase):
    def test_runtime_defaults_expose_org_role_migration_flags(self):
        runtime = WmsRuntimeSettings.get_solo()
        self.assertFalse(runtime.org_roles_engine_enabled)
        self.assertEqual(runtime.org_roles_review_max_open_percent, 20)

        config = get_runtime_config()
        self.assertFalse(config.org_roles_engine_enabled)
        self.assertEqual(config.org_roles_review_max_open_percent, 20)

    def test_runtime_config_reads_flags_from_settings_fallback(self):
        with override_settings(
            ORG_ROLES_ENGINE_ENABLED=True,
            ORG_ROLES_REVIEW_MAX_OPEN_PERCENT=35,
        ):
            with mock.patch(
                "wms.runtime_settings.get_runtime_settings_instance",
                side_effect=OperationalError("missing table"),
            ):
                config = get_runtime_config()

        self.assertTrue(config.org_roles_engine_enabled)
        self.assertEqual(config.org_roles_review_max_open_percent, 35)

    def test_runtime_config_clamps_review_threshold_to_100(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.org_roles_review_max_open_percent = 180
        runtime.save(update_fields=["org_roles_review_max_open_percent"])
        runtime.refresh_from_db()
        self.assertEqual(runtime.org_roles_review_max_open_percent, 100)

        config = get_runtime_config()
        self.assertEqual(config.org_roles_review_max_open_percent, 100)
