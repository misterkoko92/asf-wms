import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings, tag
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import AssociationProfile, UiMode, UserUiPreference


@tag("next_frontend")
class NextFrontendViewsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="next-staff",
            password="pass1234",
            is_staff=True,
        )
        self.portal_user = user_model.objects.create_user(
            username="next-portal",
            password="pass1234",
            email="portal@example.com",
        )
        association_contact = Contact.objects.create(
            name="Association Next",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="association@example.com",
        )
        AssociationProfile.objects.create(
            user=self.portal_user,
            contact=association_contact,
        )

    def _build_export_tree(self, files):
        temp_dir = TemporaryDirectory()
        root = Path(temp_dir.name)
        for relative_path, content in files.items():
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return temp_dir, root

    def test_ui_mode_requires_authentication(self):
        response = self.client.get(reverse("ui_mode_set_mode", args=["next"]))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_ui_mode_set_next_redirects_staff_to_scan_app(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse("ui_mode_set"), {"mode": "next"})

        self.assertRedirects(
            response,
            "/app/scan/dashboard/",
            fetch_redirect_response=False,
        )
        preference = UserUiPreference.objects.get(user=self.staff_user)
        self.assertEqual(preference.ui_mode, UiMode.NEXT)

    def test_ui_mode_set_next_redirects_portal_user_to_portal_app(self):
        self.client.force_login(self.portal_user)

        response = self.client.post(reverse("ui_mode_set"), {"mode": "next"})

        self.assertRedirects(
            response,
            "/app/portal/dashboard/",
            fetch_redirect_response=False,
        )
        preference = UserUiPreference.objects.get(user=self.portal_user)
        self.assertEqual(preference.ui_mode, UiMode.NEXT)

    def test_ui_mode_set_legacy_redirects_portal_user_to_portal_legacy(self):
        self.client.force_login(self.portal_user)

        response = self.client.get(reverse("ui_mode_set_mode", args=["legacy"]))

        self.assertRedirects(
            response,
            "/portal/",
            fetch_redirect_response=False,
        )
        preference = UserUiPreference.objects.get(user=self.portal_user)
        self.assertEqual(preference.ui_mode, UiMode.LEGACY)

    def test_next_frontend_returns_503_when_export_is_missing(self):
        self.client.force_login(self.staff_user)

        with mock.patch(
            "wms.views_next_frontend._next_export_root",
            return_value=Path("/tmp/non-existent-next-out"),
        ):
            response = self.client.get("/app/scan/dashboard/")

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Frontend Next indisponible", status_code=503)

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_next_frontend_missing_build_includes_bootstrap_assets_when_enabled(self):
        self.client.force_login(self.staff_user)

        with mock.patch(
            "wms.views_next_frontend._next_export_root",
            return_value=Path("/tmp/non-existent-next-out"),
        ):
            response = self.client.get("/app/scan/dashboard/")

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "family=DM+Sans", status_code=503)
        self.assertContains(response, "family=Nunito+Sans", status_code=503)
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
            status_code=503,
        )
        self.assertContains(response, "app/next-bootstrap.css", status_code=503)

    def test_next_frontend_blocks_portal_user_on_scan_routes(self):
        self.client.force_login(self.portal_user)
        temp_dir, root = self._build_export_tree(
            {"scan/dashboard/index.html": "<html><body>scan dashboard</body></html>"}
        )
        self.addCleanup(temp_dir.cleanup)

        with mock.patch("wms.views_next_frontend._next_export_root", return_value=root):
            response = self.client.get("/app/scan/dashboard/")

        self.assertEqual(response.status_code, 403)

    def test_next_frontend_serves_portal_route_for_association_profile(self):
        self.client.force_login(self.portal_user)
        temp_dir, root = self._build_export_tree(
            {"portal/dashboard/index.html": "<html><body>portal dashboard</body></html>"}
        )
        self.addCleanup(temp_dir.cleanup)

        with mock.patch("wms.views_next_frontend._next_export_root", return_value=root):
            response = self.client.get("/app/portal/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal dashboard")

    def test_frontend_log_event_accepts_authenticated_payload(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("frontend_log_event"),
            data=json.dumps(
                {
                    "event": "page.view",
                    "level": "info",
                    "path": "/app/scan/dashboard/",
                    "meta": {"load_ms": 123},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 204)
