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
        self.assertContains(response, "design_font_heading")
        self.assertContains(response, "design_color_primary")

    def test_scan_admin_design_post_updates_runtime_design_values(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_admin_design"),
            {
                "action": "save",
                "design_font_heading": '"DM Sans", "Segoe UI", sans-serif',
                "design_font_body": '"Nunito Sans", "Segoe UI", sans-serif',
                "design_color_primary": "#3a7f6f",
                "design_color_secondary": "#f0caa9",
                "design_color_background": "#f4f8f3",
                "design_color_surface": "#fffefa",
                "design_color_border": "#cfded6",
                "design_color_text": "#22322e",
                "design_color_text_soft": "#4f625c",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_admin_design"))

        runtime = WmsRuntimeSettings.get_solo()
        self.assertEqual(runtime.design_color_primary, "#3a7f6f")
        self.assertEqual(runtime.design_color_secondary, "#f0caa9")
        self.assertEqual(runtime.design_font_heading, '"DM Sans", "Segoe UI", sans-serif')

        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "--wms-color-primary: #3a7f6f;")
