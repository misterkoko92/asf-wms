from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from wms.models import WmsRuntimeSettings


class ScanSettingsViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-settings-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-settings-admin",
            password="pass1234",
            email="scan-settings-admin@example.com",
        )

    def test_scan_settings_requires_superuser(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("scan:scan_settings"))
        self.assertEqual(response.status_code, 403)

    def test_scan_settings_get_renders_form_for_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "settings")
        self.assertTrue(response.context["form"].fields)

    def test_scan_settings_post_updates_runtime_values(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_settings"),
            {
                "low_stock_threshold": 12,
                "tracking_alert_hours": 36,
                "workflow_blockage_hours": 84,
                "stale_drafts_age_days": 20,
                "email_queue_max_attempts": 9,
                "email_queue_retry_base_seconds": 45,
                "email_queue_retry_max_seconds": 600,
                "email_queue_processing_timeout_seconds": 500,
                "enable_shipment_track_legacy": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_settings"))
        runtime_settings = WmsRuntimeSettings.get_solo()
        self.assertEqual(runtime_settings.low_stock_threshold, 12)
        self.assertEqual(runtime_settings.tracking_alert_hours, 36)
        self.assertEqual(runtime_settings.workflow_blockage_hours, 84)
        self.assertEqual(runtime_settings.stale_drafts_age_days, 20)
        self.assertEqual(runtime_settings.email_queue_max_attempts, 9)
        self.assertEqual(runtime_settings.email_queue_retry_base_seconds, 45)
        self.assertEqual(runtime_settings.email_queue_retry_max_seconds, 600)
        self.assertEqual(runtime_settings.email_queue_processing_timeout_seconds, 500)
        self.assertFalse(runtime_settings.enable_shipment_track_legacy)
        self.assertEqual(runtime_settings.updated_by, self.superuser)

    def test_scan_settings_retry_max_must_be_greater_or_equal_base(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_settings"),
            {
                "low_stock_threshold": 12,
                "tracking_alert_hours": 36,
                "workflow_blockage_hours": 84,
                "stale_drafts_age_days": 20,
                "email_queue_max_attempts": 9,
                "email_queue_retry_base_seconds": 600,
                "email_queue_retry_max_seconds": 45,
                "email_queue_processing_timeout_seconds": 500,
                "enable_shipment_track_legacy": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email_queue_retry_max_seconds", response.context["form"].errors)
