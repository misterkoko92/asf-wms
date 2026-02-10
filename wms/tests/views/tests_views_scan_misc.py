from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse


class ScanMiscViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-misc-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def test_scan_faq_renders_template(self):
        response = self.client.get(reverse("scan:scan_faq"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "faq")
        self.assertEqual(response.context["shell_class"], "scan-shell-wide")

    def test_scan_service_worker_returns_expected_headers_and_body(self):
        response = self.client.get(reverse("scan:scan_service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["Service-Worker-Allowed"], "/scan/")
        self.assertIn("CACHE_NAME", response.content.decode())
        self.assertEqual(response["Content-Type"], "application/javascript")

    def test_scan_faq_requires_staff(self):
        non_staff = get_user_model().objects.create_user(
            username="scan-misc-non-staff",
            password="pass1234",
            is_staff=False,
        )
        self.client.force_login(non_staff)
        response = self.client.get(reverse("scan:scan_faq"))
        self.assertEqual(response.status_code, 403)
