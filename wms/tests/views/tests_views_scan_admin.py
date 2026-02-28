from pathlib import Path

from django.conf import settings
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
            "design_nav_item_border": "#b7cbc2",
            "design_nav_item_font_size": "15px",
            "design_nav_item_font_weight": "600",
            "design_nav_item_line_height": "1.3",
            "design_nav_item_letter_spacing": "0.02em",
            "design_nav_item_active_bg": "#e2ece7",
            "design_nav_item_active_text": "#20322e",
            "design_dropdown_item_font_size": "14px",
            "design_dropdown_item_font_weight": "600",
            "design_dropdown_item_padding_y": "8",
            "design_dropdown_item_padding_x": "11",
            "design_dropdown_shadow": "none",
            "design_table_row_hover_bg": "#edf6f2",
            "design_table_header_font_size": "13px",
            "design_table_header_letter_spacing": "0.06em",
            "design_table_header_padding_y": "10",
            "design_table_header_padding_x": "11",
            "design_table_cell_padding_y": "9",
            "design_table_cell_padding_x": "11",
            "design_color_btn_success_bg": "#dcefe4",
            "design_color_btn_success_text": "#1f4f3e",
            "design_color_btn_success_border": "#8fc3ad",
            "design_color_btn_success_hover_bg": "#cfe9d8",
            "design_color_btn_success_active_bg": "#c2e0ce",
            "design_color_btn_primary_bg": "#245648",
            "design_color_btn_primary_text": "#f5fbf8",
            "design_color_btn_primary_border": "#163f34",
            "design_color_btn_secondary_bg": "#efd5bb",
            "design_color_btn_secondary_text": "#2f3a36",
            "design_color_btn_secondary_border": "#d7b998",
            "design_color_btn_warning_bg": "#faecd9",
            "design_color_btn_warning_text": "#6d4f1f",
            "design_color_btn_warning_border": "#dbb782",
            "design_color_btn_warning_hover_bg": "#f0debd",
            "design_color_btn_warning_active_bg": "#e6d0aa",
            "design_color_btn_danger_bg": "#f9e4e2",
            "design_color_btn_danger_text": "#7b2f2f",
            "design_color_btn_danger_border": "#d49a9a",
            "design_color_btn_danger_hover_bg": "#f1d6d3",
            "design_color_btn_danger_active_bg": "#e8c8c4",
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
        self.assertContains(response, "scan-switch-card")
        self.assertContains(response, reverse("admin:contacts_contact_changelist"))
        self.assertContains(response, reverse("admin:contacts_contact_add"))
        self.assertContains(response, reverse("admin:contacts_contacttag_add"))
        self.assertContains(response, reverse("admin:wms_destination_changelist"))
        self.assertContains(response, self.correspondent.name)
        self.assertContains(response, self.destination.city)

    def test_scan_admin_contacts_filters_by_contact_type(self):
        self.client.force_login(self.superuser)
        person = Contact.objects.create(
            name="Personne Contact",
            contact_type="person",
            is_active=True,
        )
        org = Contact.objects.create(
            name="Organisation Contact",
            contact_type="organization",
            is_active=True,
        )

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {"contact_type": "person"},
        )
        self.assertEqual(response.status_code, 200)
        rendered_contact_names = [contact.name for contact in response.context["contacts"]]
        self.assertIn(person.name, rendered_contact_names)
        self.assertNotIn(org.name, rendered_contact_names)

    def test_scan_admin_contacts_can_create_update_and_delete_contact_in_page(self):
        self.client.force_login(self.superuser)
        shipper_tag = ContactTag.objects.create(name="Expediteur")
        donor_tag = ContactTag.objects.create(name="Donateur")
        shipper = Contact.objects.create(name="Shipper Link", is_active=True)
        shipper.tags.add(shipper_tag)

        create_response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "create_contact",
                "q": "",
                "contact_type": "all",
                "create-contact_type": "organization",
                "create-name": "Contact Scan",
                "create-title": "",
                "create-first_name": "",
                "create-last_name": "",
                "create-organization": "",
                "create-role": "Coordination",
                "create-email": "scan-contact@example.com",
                "create-email2": "",
                "create-phone": "0102030405",
                "create-phone2": "",
                "create-siret": "",
                "create-vat_number": "",
                "create-legal_registration_number": "",
                "create-use_organization_address": "",
                "create-notes": "Note initiale",
                "create-is_active": "on",
                "create-tag_ids": [str(self.correspondent_tag.id), str(donor_tag.id)],
                "create-destination_ids": [str(self.destination.id)],
                "create-linked_shipper_ids": [str(shipper.id)],
                "create-address_label": "Siège",
                "create-address_line1": "1 Rue du Test",
                "create-address_line2": "",
                "create-address_postal_code": "75001",
                "create-address_city": "Paris",
                "create-address_region": "",
                "create-address_country": "France",
                "create-address_phone": "",
                "create-address_email": "",
                "create-remove_default_address": "",
            },
        )
        self.assertEqual(create_response.status_code, 302)

        created = Contact.objects.get(name="Contact Scan")
        self.assertEqual(created.email, "scan-contact@example.com")
        self.assertEqual(created.phone, "0102030405")
        self.assertEqual(created.role, "Coordination")
        self.assertTrue(created.tags.filter(pk=self.correspondent_tag.id).exists())
        self.assertTrue(created.tags.filter(pk=donor_tag.id).exists())
        self.assertTrue(created.destinations.filter(pk=self.destination.id).exists())
        self.assertTrue(created.linked_shippers.filter(pk=shipper.id).exists())
        self.assertEqual(created.addresses.count(), 1)
        self.assertEqual(created.addresses.first().city, "Paris")

        update_response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "update_contact",
                "q": "",
                "contact_type": "all",
                "contact_id": str(created.id),
                "edit-contact_type": "organization",
                "edit-name": "Contact Scan Modifié",
                "edit-title": "",
                "edit-first_name": "",
                "edit-last_name": "",
                "edit-organization": "",
                "edit-role": "Logistique",
                "edit-email": "updated-contact@example.com",
                "edit-email2": "",
                "edit-phone": "0607080910",
                "edit-phone2": "",
                "edit-siret": "",
                "edit-vat_number": "",
                "edit-legal_registration_number": "",
                "edit-use_organization_address": "",
                "edit-notes": "Note modifiée",
                "edit-is_active": "on",
                "edit-tag_ids": [str(self.correspondent_tag.id)],
                "edit-destination_ids": [str(self.destination.id)],
                "edit-linked_shipper_ids": [str(shipper.id)],
                "edit-address_label": "Entrepôt",
                "edit-address_line1": "2 Rue du Test",
                "edit-address_line2": "",
                "edit-address_postal_code": "69000",
                "edit-address_city": "Lyon",
                "edit-address_region": "",
                "edit-address_country": "France",
                "edit-address_phone": "",
                "edit-address_email": "",
                "edit-remove_default_address": "",
            },
        )
        self.assertEqual(update_response.status_code, 302)

        created.refresh_from_db()
        self.assertEqual(created.name, "Contact Scan Modifié")
        self.assertEqual(created.email, "updated-contact@example.com")
        self.assertEqual(created.phone, "0607080910")
        self.assertEqual(created.role, "Logistique")
        self.assertEqual(created.addresses.count(), 1)
        self.assertEqual(created.addresses.first().city, "Lyon")

        delete_response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "delete_contact",
                "q": "",
                "contact_type": "all",
                "contact_id": str(created.id),
            },
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Contact.objects.filter(pk=created.id).exists())

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
        self.assertContains(response, "scan-design-family-grid")
        self.assertContains(response, "scan-design-form")
        self.assertContains(response, "design_color_primary")
        self.assertContains(response, "scan_bootstrap_enabled")
        self.assertContains(response, "design_density_mode")
        self.assertContains(response, "design_btn_style_mode")
        self.assertContains(response, "design_btn_radius")
        self.assertContains(response, "design_nav_item_border")
        self.assertContains(response, "design_nav_item_font_size")
        self.assertContains(response, "design_dropdown_item_padding_x")
        self.assertContains(response, "design_nav_item_active_bg")
        self.assertContains(response, "design_table_header_font_size")
        self.assertContains(response, "design_table_cell_padding_x")
        self.assertContains(response, "design_color_btn_success_bg")
        self.assertContains(response, "design_color_btn_success_hover_bg")
        self.assertContains(response, "design_color_btn_warning_bg")
        self.assertContains(response, "design_color_btn_warning_active_bg")
        self.assertContains(response, "design_color_btn_danger_bg")
        self.assertContains(response, "design_color_btn_danger_hover_bg")
        self.assertContains(response, "design_color_btn_primary_border")
        self.assertContains(response, 'id="design-family-foundations"')
        self.assertContains(response, 'id="design-family-buttons"')
        self.assertContains(response, "scan-design-accordion")
        self.assertContains(response, 'data-design-live-preview="1"')
        self.assertContains(response, '<select name="design_font_h1"')
        self.assertContains(response, "<option value=\"DM Sans\"")
        self.assertContains(response, '<select name="style_preset"')
        self.assertContains(response, 'name="style_custom_name"')
        self.assertContains(response, '<option value="wms-default"')
        self.assertContains(response, '<option value="wms-rect"')
        self.assertContains(response, '<option value="wms-contrast"')
        self.assertContains(response, 'value="apply_preset"')
        self.assertContains(response, 'value="save_custom_preset"')

    def test_scan_admin_design_preview_uses_non_bootstrap_progress_class(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_admin_design"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="preview-status in-progress"')
        self.assertContains(response, ".scan-design-preview .preview-status.in-progress {")
        self.assertNotContains(response, 'class="preview-status progress"')

    def test_scan_bootstrap_styles_override_legacy_ui_button_rounding(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(".scan-bootstrap-enabled .scan-scan-btn.btn,", css_content)
        self.assertIn(".scan-bootstrap-enabled .scan-submit.btn {", css_content)
        self.assertIn("border-radius: min(var(--wms-btn-radius), 0.45rem);", css_content)

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
        self.assertEqual(runtime.design_tokens["nav_item_border"], "#b7cbc2")
        self.assertEqual(runtime.design_tokens["nav_item_font_size"], "15px")
        self.assertEqual(runtime.design_tokens["dropdown_item_padding_x"], 11)
        self.assertEqual(runtime.design_tokens["nav_item_active_bg"], "#e2ece7")
        self.assertEqual(runtime.design_tokens["nav_item_active_text"], "#20322e")
        self.assertEqual(runtime.design_tokens["table_row_hover_bg"], "#edf6f2")
        self.assertEqual(runtime.design_tokens["table_header_font_size"], "13px")
        self.assertEqual(runtime.design_tokens["table_header_padding_y"], 10)
        self.assertEqual(runtime.design_tokens["table_cell_padding_x"], 11)
        self.assertEqual(runtime.design_tokens["color_btn_primary_bg"], "#245648")
        self.assertEqual(runtime.design_tokens["color_btn_primary_border"], "#163f34")
        self.assertEqual(runtime.design_tokens["color_btn_success_bg"], "#dcefe4")
        self.assertEqual(runtime.design_tokens["color_btn_success_hover_bg"], "#cfe9d8")
        self.assertEqual(runtime.design_tokens["color_btn_success_active_bg"], "#c2e0ce")
        self.assertEqual(runtime.design_tokens["color_btn_warning_bg"], "#faecd9")
        self.assertEqual(runtime.design_tokens["color_btn_warning_hover_bg"], "#f0debd")
        self.assertEqual(runtime.design_tokens["color_btn_warning_active_bg"], "#e6d0aa")
        self.assertEqual(runtime.design_tokens["color_btn_danger_bg"], "#f9e4e2")
        self.assertEqual(runtime.design_tokens["color_btn_danger_hover_bg"], "#f1d6d3")
        self.assertEqual(runtime.design_tokens["color_btn_danger_active_bg"], "#e8c8c4")

        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "--wms-color-primary: #3a7f6f;")
        self.assertContains(dashboard_response, "--wms-font-heading-h1: Manrope;")
        self.assertContains(dashboard_response, "--wms-density-mode: dense;")
        self.assertContains(dashboard_response, "--wms-btn-style-mode: outlined;")
        self.assertContains(dashboard_response, "--wms-btn-radius: 12px;")
        self.assertContains(dashboard_response, "--wms-nav-item-font-size: 15px;")
        self.assertContains(dashboard_response, "--wms-table-header-font-size: 13px;")
        self.assertContains(dashboard_response, "--wms-table-row-hover-bg: #edf6f2;")
        self.assertContains(dashboard_response, "--wms-color-btn-primary-bg: #245648;")
        self.assertContains(dashboard_response, "--wms-color-btn-primary-border: #163f34;")
        self.assertContains(dashboard_response, "--wms-color-btn-success-hover-bg: #cfe9d8;")
        self.assertContains(dashboard_response, "--wms-color-btn-danger-active-bg: #e8c8c4;")

    def test_scan_admin_design_apply_builtin_preset_updates_runtime_design_values(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_admin_design"),
            {
                "action": "apply_preset",
                "style_preset": "wms-rect",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_admin_design"))

        runtime = WmsRuntimeSettings.get_solo()
        self.assertEqual(runtime.design_selected_preset, "wms-rect")
        self.assertEqual(runtime.design_color_primary, "#2f6d5f")
        self.assertEqual(runtime.design_tokens["density_mode"], "dense")
        self.assertEqual(runtime.design_tokens["btn_style_mode"], "outlined")
        self.assertEqual(runtime.design_tokens["btn_radius"], 0)
        self.assertEqual(runtime.design_tokens["nav_item_radius"], 0)
        self.assertEqual(runtime.design_tokens["badge_radius"], 6)

    def test_scan_admin_design_can_save_custom_style_preset(self):
        self.client.force_login(self.superuser)
        payload = self._design_form_payload(bootstrap_enabled=True)
        payload.update(
            {
                "action": "save_custom_preset",
                "style_preset": "wms-default",
                "style_custom_name": "Mon Style Perso",
            }
        )
        response = self.client.post(reverse("scan:scan_admin_design"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_admin_design"))

        runtime = WmsRuntimeSettings.get_solo()
        self.assertTrue(runtime.design_selected_preset.startswith("custom-mon-style-perso"))
        self.assertIn(runtime.design_selected_preset, runtime.design_custom_presets)
        saved = runtime.design_custom_presets[runtime.design_selected_preset]
        self.assertEqual(saved["label"], "Mon Style Perso")
        self.assertEqual(saved["fields"]["design_color_primary"], "#3a7f6f")
        self.assertEqual(saved["tokens"]["btn_radius"], 12)
        self.assertEqual(saved["tokens"]["btn_style_mode"], "outlined")

        page = self.client.get(reverse("scan:scan_admin_design"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f'<option value="{runtime.design_selected_preset}"')
        self.assertContains(page, "Mon Style Perso")

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
