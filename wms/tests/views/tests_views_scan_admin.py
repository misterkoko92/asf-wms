from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactTag
from wms.models import Destination, Product, ProductKitItem, WmsRuntimeSettings


class ScanAdminViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-admin-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-admin-superuser",
            password="pass1234",
            email="scan-admin-superuser@example.com",
        )
        self.correspondent_tag = ContactTag.objects.create(name="Correspondant")
        self.correspondent = Contact.objects.create(
            name="Correspondant Test",
            email="corr@example.com",
            is_active=True,
        )
        self.correspondent.tags.add(self.correspondent_tag)
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.correspondent.destinations.add(self.destination)
        self.component = Product.objects.create(
            sku="SCAN-ADMIN-COMP",
            name="Seringue",
            qr_code_image="qr_codes/scan_admin_comp.png",
        )
        self.kit = Product.objects.create(
            sku="SCAN-ADMIN-KIT",
            name="Kit Pediatrique",
            qr_code_image="qr_codes/scan_admin_kit.png",
        )
        ProductKitItem.objects.create(kit=self.kit, component=self.component, quantity=5)

    def _design_form_payload(self, *, bootstrap_enabled):
        payload = {
            "action": "save",
            "design_font_h1": "Manrope",
            "design_font_h2": "Manrope",
            "design_font_h3": "DM Sans",
            "design_font_body": "Nunito Sans",
            "design_color_primary": "#3a7f6f",
            "design_color_secondary": "#f0caa9",
            "design_color_background": "#f4f8f3",
            "design_color_surface": "#fffefa",
            "design_color_border": "#cfded6",
            "design_color_text": "#22322e",
            "design_color_text_soft": "#4f625c",
            "design_density_mode": "dense",
            "design_btn_style_mode": "outlined",
            "design_btn_radius": "12",
            "design_btn_height_md": "44",
            "design_btn_shadow": "none",
            "design_card_radius": "18",
            "design_card_shadow": "none",
            "design_input_height": "45",
            "design_input_radius": "11",
            "design_nav_item_active_bg": "#e2ece7",
            "design_nav_item_active_text": "#20322e",
            "design_dropdown_shadow": "none",
            "design_table_row_hover_bg": "#edf6f2",
            "design_color_btn_success_bg": "#dcefe4",
            "design_color_btn_success_text": "#1f4f3e",
            "design_color_btn_success_border": "#8fc3ad",
            "design_color_btn_warning_bg": "#faecd9",
            "design_color_btn_warning_text": "#6d4f1f",
            "design_color_btn_warning_border": "#dbb782",
            "design_color_btn_danger_bg": "#f9e4e2",
            "design_color_btn_danger_text": "#7b2f2f",
            "design_color_btn_danger_border": "#d49a9a",
        }
        if bootstrap_enabled:
            payload["scan_bootstrap_enabled"] = "on"
        return payload

    def test_scan_admin_views_redirect_anonymous_to_admin_login(self):
        for route_name in (
            "scan:scan_admin_contacts",
            "scan:scan_admin_products",
            "scan:scan_admin_design",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login/", response.url)

    def test_scan_admin_views_require_superuser(self):
        self.client.force_login(self.staff_user)
        for route_name in (
            "scan:scan_admin_contacts",
            "scan:scan_admin_products",
            "scan:scan_admin_design",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 403)

    def test_scan_admin_contacts_renders_admin_management_links(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_admin_contacts"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "admin_contacts")
        self.assertContains(response, reverse("admin:contacts_contact_changelist"))
        self.assertContains(response, reverse("admin:contacts_contact_add"))
        self.assertContains(response, reverse("admin:contacts_contacttag_add"))
        self.assertContains(response, reverse("admin:wms_destination_changelist"))
        self.assertContains(response, self.correspondent.name)
        self.assertContains(response, self.destination.city)

    def test_scan_admin_products_renders_kit_rows_and_admin_links(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_admin_products"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "admin_products")
        self.assertContains(response, reverse("admin:wms_product_changelist"))
        self.assertContains(response, reverse("admin:wms_product_add"))
        self.assertContains(response, reverse("admin:wms_product_change", args=[self.kit.id]))
        self.assertContains(response, reverse("admin:wms_product_delete", args=[self.kit.id]))
        self.assertContains(response, self.kit.name)
        self.assertContains(response, self.component.name)

    def test_scan_admin_design_renders_design_form(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_admin_design"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "admin_design")
        self.assertContains(response, "Admin - Design")
        self.assertContains(response, "wms-design-vars")
        self.assertContains(response, "design_font_h1")
        self.assertContains(response, "design_font_h2")
        self.assertContains(response, "design_font_h3")
        self.assertContains(response, "scan-design-color-grid")
        self.assertContains(response, "scan-design-form")
        self.assertContains(response, "design_color_primary")
        self.assertContains(response, "scan_bootstrap_enabled")
        self.assertContains(response, "design_density_mode")
        self.assertContains(response, "design_btn_style_mode")
        self.assertContains(response, "design_btn_radius")
        self.assertContains(response, "design_nav_item_active_bg")
        self.assertContains(response, "design_color_btn_success_bg")
        self.assertContains(response, "design_color_btn_warning_bg")
        self.assertContains(response, "design_color_btn_danger_bg")
        self.assertContains(response, '<select name="design_font_h1"')
        self.assertContains(response, "<option value=\"DM Sans\"")

    def test_scan_admin_design_post_updates_runtime_design_values(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_admin_design"),
            self._design_form_payload(bootstrap_enabled=True),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_admin_design"))

        runtime = WmsRuntimeSettings.get_solo()
        self.assertEqual(runtime.design_color_primary, "#3a7f6f")
        self.assertEqual(runtime.design_color_secondary, "#f0caa9")
        self.assertEqual(runtime.design_font_h1, "Manrope")
        self.assertEqual(runtime.design_font_h2, "Manrope")
        self.assertEqual(runtime.design_font_h3, "DM Sans")
        self.assertTrue(runtime.scan_bootstrap_enabled)
        self.assertEqual(runtime.design_tokens["density_mode"], "dense")
        self.assertEqual(runtime.design_tokens["btn_style_mode"], "outlined")
        self.assertEqual(runtime.design_tokens["btn_radius"], 12)
        self.assertEqual(runtime.design_tokens["btn_height_md"], 44)
        self.assertEqual(runtime.design_tokens["nav_item_active_bg"], "#e2ece7")
        self.assertEqual(runtime.design_tokens["nav_item_active_text"], "#20322e")
        self.assertEqual(runtime.design_tokens["table_row_hover_bg"], "#edf6f2")
        self.assertEqual(runtime.design_tokens["color_btn_success_bg"], "#dcefe4")
        self.assertEqual(runtime.design_tokens["color_btn_warning_bg"], "#faecd9")
        self.assertEqual(runtime.design_tokens["color_btn_danger_bg"], "#f9e4e2")

        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "--wms-color-primary: #3a7f6f;")
        self.assertContains(dashboard_response, "--wms-font-heading-h1: Manrope;")
        self.assertContains(dashboard_response, "--wms-density-mode: dense;")
        self.assertContains(dashboard_response, "--wms-btn-style-mode: outlined;")
        self.assertContains(dashboard_response, "--wms-btn-radius: 12px;")
        self.assertContains(dashboard_response, "--wms-table-row-hover-bg: #edf6f2;")

    def test_scan_admin_design_bootstrap_toggle_applies_on_scan_portal_home_and_admin(self):
        self.client.force_login(self.superuser)

        enable_response = self.client.post(
            reverse("scan:scan_admin_design"),
            self._design_form_payload(bootstrap_enabled=True),
        )
        self.assertEqual(enable_response.status_code, 302)
        self.assertEqual(enable_response.url, reverse("scan:scan_admin_design"))
        runtime = WmsRuntimeSettings.get_solo()
        self.assertTrue(runtime.scan_bootstrap_enabled)

        scan_response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(scan_response.status_code, 200)
        self.assertContains(scan_response, "scan-bootstrap.css")
        self.assertContains(scan_response, "bootstrap@5.3.3")

        self.client.logout()
        portal_login_response = self.client.get(reverse("portal:portal_login"))
        self.assertEqual(portal_login_response.status_code, 200)
        self.assertContains(portal_login_response, "scan-bootstrap.css")
        self.assertContains(portal_login_response, "portal-bootstrap.css")

        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "bootstrap@5.3.3")
        self.assertContains(home_response, '<body class="home-bootstrap-enabled">')

        self.client.force_login(self.superuser)
        admin_response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, "wms/admin-bootstrap.css")
        self.assertContains(admin_response, "admin-bootstrap-enabled")

        disable_response = self.client.post(
            reverse("scan:scan_admin_design"),
            self._design_form_payload(bootstrap_enabled=False),
        )
        self.assertEqual(disable_response.status_code, 302)
        self.assertEqual(disable_response.url, reverse("scan:scan_admin_design"))
        runtime = WmsRuntimeSettings.get_solo()
        self.assertFalse(runtime.scan_bootstrap_enabled)

        scan_response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(scan_response.status_code, 200)
        self.assertNotContains(scan_response, "scan-bootstrap.css")
        self.assertNotContains(scan_response, "bootstrap@5.3.3")

        self.client.logout()
        portal_login_response = self.client.get(reverse("portal:portal_login"))
        self.assertEqual(portal_login_response.status_code, 200)
        self.assertNotContains(portal_login_response, "scan-bootstrap.css")
        self.assertNotContains(portal_login_response, "portal-bootstrap.css")
        self.assertNotContains(portal_login_response, "bootstrap@5.3.3")

        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertNotContains(home_response, '<body class="home-bootstrap-enabled">')
        self.assertNotContains(home_response, "bootstrap@5.3.3")

        self.client.force_login(self.superuser)
        admin_response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertNotContains(admin_response, "wms/admin-bootstrap.css")
