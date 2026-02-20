from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from wms.models import Shipment, ShipmentStatus, WmsRuntimeSettings


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

    def test_scan_settings_redirects_anonymous_to_admin_login(self):
        response = self.client.get(reverse("scan:scan_settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_scan_settings_get_renders_form_for_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "settings")
        self.assertTrue(response.context["form"].fields)

    @override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=False)
    def test_scan_settings_get_exposes_effective_legacy_flags(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["legacy_env_disabled"])
        self.assertFalse(response.context["legacy_effective_enabled"])

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

    def test_scan_settings_rejects_values_below_one(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_settings"),
            {
                "low_stock_threshold": 0,
                "tracking_alert_hours": 0,
                "workflow_blockage_hours": 0,
                "stale_drafts_age_days": 0,
                "email_queue_max_attempts": 0,
                "email_queue_retry_base_seconds": 0,
                "email_queue_retry_max_seconds": 0,
                "email_queue_processing_timeout_seconds": 0,
                "enable_shipment_track_legacy": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        for field_name in (
            "low_stock_threshold",
            "tracking_alert_hours",
            "workflow_blockage_hours",
            "stale_drafts_age_days",
            "email_queue_max_attempts",
            "email_queue_retry_base_seconds",
            "email_queue_retry_max_seconds",
            "email_queue_processing_timeout_seconds",
        ):
            self.assertIn(field_name, response.context["form"].errors)


class ScanSettingsEndToEndTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-settings-e2e-admin",
            password="pass1234",
            email="scan-settings-e2e-admin@example.com",
        )
        self.client.force_login(self.superuser)

    def _settings_payload(self, **overrides):
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

    def _create_temp_draft_shipment(self, reference):
        return Shipment.objects.create(
            reference=reference,
            status=ShipmentStatus.DRAFT,
            shipper_name="Shipper E2E",
            recipient_name="Recipient E2E",
            destination_address="1 Rue Parametre",
            destination_country="France",
            created_by=self.superuser,
        )

    def test_settings_change_updates_stale_draft_detection_flow(self):
        stale = self._create_temp_draft_shipment(reference="EXP-TEMP-E2E-01")
        fresh = self._create_temp_draft_shipment(reference="EXP-TEMP-E2E-02")
        Shipment.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )
        Shipment.objects.filter(pk=fresh.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        response = self.client.post(
            reverse("scan:scan_settings"),
            self._settings_payload(stale_drafts_age_days=10),
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse("scan:scan_shipments_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stale_draft_days"], 10)
        self.assertEqual(response.context["stale_draft_count"], 1)

    @override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=True)
    def test_settings_change_disables_legacy_tracking_route(self):
        shipment = Shipment.objects.create(
            reference="260777",
            status=ShipmentStatus.DRAFT,
            shipper_name="Legacy Shipper",
            recipient_name="Legacy Recipient",
            destination_address="1 Rue Legacy",
            destination_country="France",
            created_by=self.superuser,
        )

        legacy_url = reverse(
            "scan:scan_shipment_track_legacy",
            kwargs={"shipment_ref": shipment.reference},
        )
        before = self.client.get(legacy_url)
        self.assertEqual(before.status_code, 200)

        response = self.client.post(
            reverse("scan:scan_settings"),
            self._settings_payload(enable_shipment_track_legacy=""),
        )
        self.assertEqual(response.status_code, 302)

        after = self.client.get(legacy_url)
        self.assertEqual(after.status_code, 404)
