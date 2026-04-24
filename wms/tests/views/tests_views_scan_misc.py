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
        self.assertIn("faq_change_log_entries", response.context)
        self.assertEqual(response.context["shell_class"], "scan-shell-wide")

    def test_scan_faq_includes_summary_container(self):
        response = self.client.get(reverse("scan:scan_faq"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sommaire")
        self.assertContains(response, 'class="scan-faq-layout"')
        self.assertContains(response, 'id="scan-faq-summary-nav"')
        self.assertContains(response, "scan-faq-summary-scroll-region")
        self.assertContains(response, 'id="scan-faq-summary-list"')
        self.assertContains(response, "scan-faq-summary-scroll-list")
        self.assertContains(response, "scan-faq-summary-list")
        self.assertContains(response, "scan-faq-nav-list")
        self.assertContains(response, 'id="scan-faq-content"')

    def test_scan_faq_summary_supports_grouped_nav_sections(self):
        response = self.client.get(reverse("scan:scan_faq"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-faq-group=")
        self.assertContains(response, "data-faq-group-title=")
        self.assertContains(response, "data-faq-summary-group=")
        self.assertContains(response, "scan-faq-nav-group-heading")

    def test_scan_faq_sections_are_marked_collapsible(self):
        response = self.client.get(reverse("scan:scan_faq"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-faq-section="true"')
        self.assertContains(response, 'data-faq-collapsible="true"')
        self.assertContains(response, 'data-faq-default-expanded="false"')
        self.assertContains(response, 'data-faq-open-on-summary-click="true"')

    def test_scan_faq_covers_cross_area_sections_and_main_workflows(self):
        response = self.client.get(reverse("scan:scan_faq"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Flux principaux")
        self.assertContains(response, "Référence planning")
        self.assertContains(response, "Portal association")
        self.assertContains(response, "Espace bénévole")
        self.assertContains(response, "Administration & support")
        self.assertContains(response, "Créer une expédition avec des colis déjà préparés")
        self.assertContains(response, "Créer une expédition sans colis préparés")

    def test_scan_faq_exposes_structured_change_log_section(self):
        response = self.client.get(reverse("scan:scan_faq"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change Log")
        first_entry = response.context["faq_change_log_entries"][0]
        self.assertIn("date", first_entry)
        self.assertIn("pr_number", first_entry)
        self.assertIn("summary", first_entry)
        self.assertContains(response, first_entry["summary"])

    def test_scan_ui_lab_renders_template(self):
        response = self.client.get(reverse("scan:scan_ui_lab"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "ui_lab")
        self.assertEqual(response.context["shell_class"], "scan-shell-wide")
        self.assertContains(response, 'id="ui-lab-palette"')
        self.assertContains(response, 'id="ui-lab-typography"')
        self.assertContains(response, 'id="ui-lab-density"')
        self.assertContains(response, 'id="ui-lab-preview"')
        self.assertContains(response, "scan/ui-lab.js")

    def test_scan_service_worker_returns_expected_headers_and_body(self):
        response = self.client.get(reverse("scan:scan_service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["Service-Worker-Allowed"], "/scan/")
        body = response.content.decode()
        self.assertIn("CACHE_NAME", body)
        self.assertIn("wms-scan-v57", body)
        self.assertIn("/static/scan/scan-bootstrap.css", body)
        self.assertIn("/static/scan/modules/core.js", body)
        self.assertIn("new Request(url, { cache: 'reload' })", body)
        self.assertEqual(response["Content-Type"], "application/javascript")

    def test_scan_base_registers_versioned_service_worker_url(self):
        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'{reverse("scan:scan_service_worker")}?v=57',
        )

    def test_scan_faq_requires_staff(self):
        non_staff = get_user_model().objects.create_user(
            username="scan-misc-non-staff",
            password="pass1234",
            is_staff=False,
        )
        self.client.force_login(non_staff)
        response = self.client.get(reverse("scan:scan_faq"))
        self.assertEqual(response.status_code, 403)

    def test_scan_ui_lab_requires_staff(self):
        non_staff = get_user_model().objects.create_user(
            username="scan-misc-ui-lab-non-staff",
            password="pass1234",
            is_staff=False,
        )
        self.client.force_login(non_staff)
        response = self.client.get(reverse("scan:scan_ui_lab"))
        self.assertEqual(response.status_code, 403)
