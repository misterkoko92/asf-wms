from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from wms.billing_permissions import BILLING_STAFF_GROUP_NAME
from wms.models import (
    Document,
    Location,
    Order,
    OrderReviewStatus,
    Product,
    ProductKitItem,
    ProductLot,
    ProductLotStatus,
    PublicOrderLink,
    Shipment,
    ShipmentStatus,
    Warehouse,
)


class ScanBootstrapUiTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-bootstrap-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-bootstrap-admin",
            password="pass1234",
            email="scan-bootstrap-admin@example.com",
        )
        self.client.force_login(self.staff_user)
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="BOOT-001",
            name="Produit Bootstrap",
            default_location=location,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-BOOT-001",
            received_on=date(2026, 1, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=12,
            location=location,
        )

    def _scan_nav_html(self, response):
        content = response.content.decode()
        nav_start = content.index(
            '<nav class="scan-nav scan-nav-bootstrap navbar navbar-expand-xl ui-comp-panel"'
        )
        nav_end = content.index("</nav>", nav_start)
        return content[nav_start:nav_end]

    def _assert_nav_labels_in_order(self, nav_html, expected_labels):
        last_position = -1
        for label in expected_labels:
            current_position = nav_html.index(label)
            self.assertGreater(current_position, last_position)
            last_position = current_position

    def test_scan_context_does_not_expose_deprecated_ui_flags(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        with self.assertRaises(KeyError):
            response.context["scan_bootstrap_enabled"]
        with self.assertRaises(KeyError):
            response.context["wms_ui_mode"]
        with self.assertRaises(KeyError):
            response.context["wms_ui_mode_is_next"]

    def test_scan_base_keeps_bootstrap_assets_without_ui_toggle(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-bootstrap.css")
        self.assertContains(response, "bootstrap@5.3.3")
        self.assertContains(response, "family=DM+Sans")
        self.assertContains(response, "family=Nunito+Sans")
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        )
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        )
        self.assertNotContains(response, 'id="ui-toggle"')
        self.assertNotContains(response, 'id="theme-toggle"')
        self.assertNotContains(response, 'id="ui-reset-default"')
        self.assertNotContains(response, "Essayer interface Next")

    def test_scan_stock_uses_bootstrap_layout_and_keeps_table_tools(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "row g-3")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, 'data-table-tools="1"')
        self.assertContains(response, "form-check form-switch")
        self.assertContains(response, "scan-inline-switch")
        self.assertContains(response, "id_include_zero")
        self.assertContains(response, "Inclure les produits avec stock")

    def test_scan_stock_keeps_filter_action_contract(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="include_zero"')
        self.assertContains(
            response,
            'class="scan-filter-actions scan-stock-filter-actions-inline col-12 d-flex flex-wrap flex-lg-nowrap gap-2 align-items-center ui-comp-actions"',
        )
        self.assertContains(
            response,
            '<button type="submit" class="scan-submit secondary scan-submit-inline btn btn-primary">Filtrer</button>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a class="btn btn-tertiary" href="{reverse("scan:scan_stock")}">Réinitialiser</a>',
            html=True,
        )

    def test_scan_admin_products_keeps_filter_and_row_action_contract(self):
        self.client.force_login(self.superuser)
        component = Product.objects.create(
            sku="SCAN-KIT-COMP",
            name="Composant scan kit",
            qr_code_image="qr_codes/scan_kit_comp.png",
        )
        kit = Product.objects.create(
            sku="SCAN-KIT-001",
            name="Kit scan",
            qr_code_image="qr_codes/scan_kit.png",
        )
        ProductKitItem.objects.create(kit=kit, component=component, quantity=3)

        response = self.client.get(reverse("scan:scan_admin_products"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="scan-filter-actions ui-comp-actions"')
        self.assertContains(response, 'id="scan-admin-products-q"')
        self.assertContains(
            response,
            '<button type="submit" class="scan-submit btn btn-primary">Filtrer</button>',
            html=True,
        )
        self.assertContains(
            response,
            '<a class="btn btn-tertiary scan-scan-btn" href="'
            + reverse("scan:scan_admin_products")
            + '">Réinitialiser</a>',
            html=True,
        )
        self.assertContains(response, 'class="scan-inline scan-inline-gap ui-comp-actions"')
        self.assertContains(
            response,
            '<a class="btn btn-danger scan-scan-btn" href="'
            + reverse("admin:wms_product_delete", args=[kit.id])
            + '">Supprimer</a>',
            html=True,
        )

    def test_scan_out_keeps_scan_shortcuts_and_danger_action_contract(self):
        response = self.client.get(reverse("scan:scan_out"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-scan-target="id_product_code"')
        self.assertContains(response, 'data-scan-target="id_shipment_reference"')
        self.assertContains(response, 'class="scan-out-actions ui-comp-actions"')
        self.assertContains(
            response,
            '<button type="button" class="btn btn-tertiary scan-scan-btn" data-scan-target="id_product_code">Scan</button>',
            html=True,
        )
        self.assertContains(
            response,
            '<button type="submit" class="scan-submit btn btn-danger">Enregistrer suppression</button>',
            html=True,
        )

    def test_scan_bootstrap_nav_uses_title_case_for_state_pages(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vue Stock")
        self.assertContains(response, "Vue Réception")

    def test_scan_nav_includes_planning_link(self):
        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planning")
        self.assertContains(response, reverse("planning:run_list"))

    def test_scan_nav_orders_top_level_tabs_for_standard_staff(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_nav_html(response)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                "Tableau De Bord",
                "Voir Les États",
                "Réception",
                "Préparation",
                "Planning",
                "Suivi Des Expéditions",
                "Gestion",
                "Compte",
            ],
        )
        self.assertNotIn("Facturation", nav_html)
        self.assertNotRegex(nav_html, r">\s*Admin\s*</button>")

    def test_scan_nav_orders_top_level_tabs_for_billing_staff(self):
        billing_group, _ = Group.objects.get_or_create(name=BILLING_STAFF_GROUP_NAME)
        self.staff_user.groups.add(billing_group)
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_nav_html(response)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                "Tableau De Bord",
                "Voir Les États",
                "Réception",
                "Préparation",
                "Planning",
                "Suivi Des Expéditions",
                "Facturation",
                "Gestion",
                "Compte",
            ],
        )
        self.assertNotRegex(nav_html, r">\s*Admin\s*</button>")

    def test_scan_nav_orders_top_level_tabs_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_nav_html(response)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                "Tableau De Bord",
                "Voir Les États",
                "Réception",
                "Préparation",
                "Planning",
                "Suivi Des Expéditions",
                "Facturation",
                "Gestion",
                "Admin",
                "Compte",
            ],
        )
        self.assertRegex(nav_html, r">\s*Admin\s*</button>")

    def test_scan_nav_shows_billing_dropdown_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Facturation")
        self.assertContains(response, "Paramètres")
        self.assertContains(response, "Equivalence")
        self.assertContains(response, "Edition Devis/Facture")

    def test_scan_nav_shows_billing_editor_only_for_billing_staff(self):
        billing_group, _ = Group.objects.get_or_create(name=BILLING_STAFF_GROUP_NAME)
        self.staff_user.groups.add(billing_group)
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Facturation")
        self.assertContains(response, "Edition Devis/Facture")
        self.assertNotContains(response, "Paramètres")
        self.assertNotContains(response, "Equivalence")

    def test_scan_shipment_create_uses_bootstrap_and_preserves_js_hooks(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-form"')
        self.assertContains(response, 'id="shipment-lines"')
        self.assertContains(response, "btn btn-primary")
        self.assertContains(response, 'id="shipment-details-section"')
        self.assertContains(response, "scan-shipment-contact-slot")

    def test_scan_stock_and_shipment_create_use_design_component_classes(self):
        stock_response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(stock_response.status_code, 200)
        self.assertContains(stock_response, "ui-comp-card")
        self.assertContains(stock_response, "ui-comp-title")
        self.assertContains(stock_response, "ui-comp-actions")

        shipment_response = self.client.get(reverse("scan:scan_shipment_create"))
        self.assertEqual(shipment_response.status_code, 200)
        self.assertContains(shipment_response, "ui-comp-card")
        self.assertContains(shipment_response, "ui-comp-title")
        self.assertContains(shipment_response, "ui-comp-panel")
        self.assertContains(shipment_response, "ui-comp-note")

    def test_scan_kits_pages_use_design_component_classes(self):
        kits_view_response = self.client.get(reverse("scan:scan_kits_view"))
        self.assertEqual(kits_view_response.status_code, 200)
        self.assertContains(kits_view_response, "ui-comp-card")
        self.assertContains(kits_view_response, "ui-comp-title")
        self.assertContains(kits_view_response, "ui-comp-count-badge")

        prepare_kits_response = self.client.get(reverse("scan:scan_prepare_kits"))
        self.assertEqual(prepare_kits_response.status_code, 200)
        self.assertContains(prepare_kits_response, "ui-comp-card")
        self.assertContains(prepare_kits_response, "ui-comp-form")
        self.assertContains(prepare_kits_response, "ui-comp-panel")
        self.assertContains(prepare_kits_response, "ui-comp-actions")

    def test_scan_state_tables_use_design_component_classes(self):
        expectations = {
            "scan:scan_cartons_ready": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-count-badge",
            ],
            "scan:scan_shipments_ready": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-count-badge",
            ],
            "scan:scan_receipts_view": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-form",
            ],
        }

        for route_name, markers in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                for marker in markers:
                    self.assertContains(response, marker)

    def test_scan_state_pages_render_status_pill_levels(self):
        Shipment.objects.create(
            shipper_name="Shipper Progress",
            recipient_name="Recipient Progress",
            destination_address="1 rue de la Paix",
            status=ShipmentStatus.DRAFT,
        )
        Shipment.objects.create(
            shipper_name="Shipper Error",
            recipient_name="Recipient Error",
            destination_address="2 rue de la Paix",
            status=ShipmentStatus.PACKED,
            is_disputed=True,
        )
        response = self.client.get(reverse("scan:scan_shipments_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-status-pill")
        self.assertContains(response, "is-progress")
        self.assertContains(response, "is-error")

        Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association X",
            destination_address="3 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
        )
        orders_response = self.client.get(reverse("scan:scan_orders_view"))
        self.assertEqual(orders_response.status_code, 200)
        self.assertContains(orders_response, "ui-comp-status-pill is-warning")

    def test_scan_dashboard_and_tracking_views_use_design_component_classes(self):
        expectations = {
            "scan:scan_dashboard": [
                "ui-comp-card",
                "ui-comp-title",
            ],
            "scan:scan_orders_view": [
                "ui-comp-card",
                "ui-comp-title",
            ],
            "scan:scan_shipments_tracking": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-form",
            ],
        }

        for route_name, markers in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                for marker in markers:
                    self.assertContains(response, marker)

    def test_scan_shipments_tracking_week_filter_uses_extended_input_class(self):
        response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-week-input")

    def test_scan_shipments_tracking_uses_design_classes_for_close_buttons(self):
        Shipment.objects.create(
            shipper_name="Shipper Tracking",
            recipient_name="Recipient Tracking",
            destination_address="1 rue de la Paix",
            status=ShipmentStatus.PLANNED,
        )
        response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-shipment-close-btn")
        self.assertNotContains(response, "background:#e8f7ec")
        self.assertNotContains(response, "background:#fdecec")
        self.assertNotContains(response, "border-color:#9fcfb0")

    def test_scan_shipments_tracking_uses_secondary_style_for_blocked_close_buttons(self):
        Shipment.objects.create(
            shipper_name="Blocked Tracking",
            recipient_name="Blocked Recipient",
            destination_address="1 rue de la Paix",
            status=ShipmentStatus.PLANNED,
        )

        response = self.client.get(reverse("scan:scan_shipments_tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "btn btn-secondary scan-shipment-close-btn is-blocked")
        self.assertNotContains(response, "btn btn-danger scan-shipment-close-btn is-blocked")

    def test_scan_shipments_ready_uses_split_numero_expedition_header_copy(self):
        Shipment.objects.create(
            shipper_name="Header Tracking",
            recipient_name="Header Recipient",
            destination_address="1 rue de la Paix",
            status=ShipmentStatus.DRAFT,
        )
        response = self.client.get(reverse("scan:scan_shipments_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<span>NUMERO</span><br>", html=True)
        self.assertContains(response, "<span>EXPEDITION</span>", html=True)

    def test_scan_bootstrap_css_scopes_shipment_status_variants_with_higher_specificity(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(
            ".scan-bootstrap-enabled .scan-shipment-status-pill.scan-shipment-status--draft",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .scan-shipment-status-pill.scan-shipment-status--planned",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .scan-shipment-close-btn.is-blocked {\n"
            "  --bs-btn-bg: var(--wms-color-btn-secondary-bg);",
            css_content,
        )

    def test_scan_css_does_not_keep_removed_theme_selectors_or_toggle_controls(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.css"
        css_content = css_path.read_text(encoding="utf-8")

        for removed_selector in [
            'data-ui="nova"',
            'data-ui="studio"',
            'data-ui="benev"',
            'data-ui="timeline"',
            'data-ui="spreadsheet"',
            'data-theme="atelier"',
            ".scan-theme-toggle",
            ".scan-ui-toggle",
            ".scan-theme-button",
            ".scan-ui-button",
            ".scan-ui-reset",
        ]:
            with self.subTest(removed_selector=removed_selector):
                self.assertNotIn(removed_selector, css_content)

    def test_scan_superuser_admin_pages_use_design_component_classes(self):
        self.client.force_login(self.superuser)
        expectations = {
            "scan:scan_settings": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-form",
            ],
            "scan:scan_admin_contacts": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-form",
            ],
            "scan:scan_admin_products": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-form",
            ],
            "scan:scan_admin_design": [
                "ui-comp-card",
                "ui-comp-title",
                "ui-comp-form",
            ],
        }

        for route_name, markers in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                for marker in markers:
                    self.assertContains(response, marker)

    def test_scan_admin_contacts_bootstrap_keeps_fallback_links_without_legacy_banner(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Mode legacy désactivé")
        self.assertContains(response, reverse("admin:contacts_contact_changelist"))
        self.assertNotContains(response, 'name="action" value="create_contact"')
        self.assertNotContains(response, 'name="action" value="update_contact"')
        self.assertNotContains(response, 'name="action" value="delete_contact"')

    def test_scan_admin_contacts_js_supports_crud_cards_and_directory_actions(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("data-admin-contacts-crud", js_content)
        self.assertIn("scan-admin-contact-action-panel", js_content)
        self.assertIn("data-contact-action-select", js_content)
        self.assertIn("data-contact-field-group", js_content)
        self.assertIn("data-required-marker", js_content)
        self.assertIn("required.add('entity_type')", js_content)
        self.assertIn("field.disabled = shouldHide", js_content)
        self.assertIn("event.target.closest('[data-contact-action-select=\"1\"]')", js_content)
        self.assertIn("merge_contact", js_content)
        self.assertIn("deactivate_contact", js_content)

    def test_scan_order_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_order"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")

    def test_scan_preparation_forms_use_design_component_classes(self):
        for route_name in [
            "scan:scan_pack",
            "scan:scan_out",
            "scan:scan_stock_update",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "ui-comp-card")
                self.assertContains(response, "ui-comp-title")
                self.assertContains(response, "ui-comp-form")
                if route_name == "scan:scan_pack":
                    self.assertContains(response, "form-check form-switch")
                    self.assertContains(response, "scan-inline-switch")
                    self.assertContains(
                        response,
                        "Autoriser l'ajout avec valeurs standard",
                    )

    def test_scan_pack_js_uses_barcode_label_without_ocr_shortcut(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("Scanner un code barre ou QR Code", js_content)
        self.assertNotIn("ocrBtn.textContent = 'Texte';", js_content)

    def test_scan_shipment_create_js_supports_grouped_contact_selects(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("renderGroupedOptions", js_content)
        self.assertIn("shipment-correspondent-single", js_content)
        self.assertIn("shipper.is_priority_shipper", js_content)
        self.assertIn("recipient_labels_by_destination_id", js_content)
        self.assertIn("separator.textContent = '------';", js_content)
        self.assertIn("Si l'expéditeur souhaité n'apparait pas ici", js_content)
        self.assertIn("Si le destinataire souhaité n'apparait pas ici", js_content)

    def test_scan_shipment_create_js_keeps_unlinked_recipients_out_of_pair_group(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("if (!bindingPairs.length) {\n        return false;\n      }", js_content)
        self.assertNotIn("if (!bindingPairs.length) {\n        return true;\n      }", js_content)

    def test_scan_shipment_create_places_secondary_draft_button_before_primary_submit(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        details_start = content.index('id="shipment-details-section"')
        details_end = content.index("</form>", details_start)
        details_content = content[details_start:details_end]
        self.assertLess(
            details_content.index('name="action" value="save_draft"'),
            details_content.index('class="scan-submit btn btn-primary"'),
        )

    def test_scan_receive_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")

    def test_scan_receive_pallet_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")
        self.assertContains(response, "form-check form-check-inline")
        self.assertContains(response, "id_listing_file_type_pdf")
        self.assertContains(response, "id_listing_file_type_excel")
        self.assertContains(response, "id_listing_file_type_csv")

    def test_scan_receive_pallet_uses_inline_radio_alignment_markers(self):
        response = self.client.get(reverse("scan:scan_receive_pallet"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-radio-inline-group-tight", count=2)
        self.assertContains(response, "scan-radio-inline-choice", count=5)

    def test_scan_receive_association_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")

    def test_scan_misc_pages_use_design_component_classes(self):
        self.client.force_login(self.superuser)

        import_response = self.client.get(reverse("scan:scan_import"))
        self.assertEqual(import_response.status_code, 200)
        self.assertContains(import_response, "ui-comp-card")
        self.assertContains(import_response, "ui-comp-title")
        self.assertContains(import_response, "ui-comp-form")

        list_response = self.client.get(reverse("scan:scan_print_templates"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "ui-comp-card")
        self.assertContains(list_response, "ui-comp-title")

        edit_response = self.client.get(
            reverse("scan:scan_print_template_edit", args=["shipment_note"])
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, "ui-comp-card")
        self.assertContains(edit_response, "ui-comp-title")
        self.assertContains(edit_response, "<form")

        self.client.force_login(self.staff_user)
        faq_response = self.client.get(reverse("scan:scan_faq"))
        self.assertEqual(faq_response.status_code, 200)
        self.assertContains(faq_response, "ui-comp-card")
        self.assertContains(faq_response, "ui-comp-title")

        shipment = Shipment.objects.create(
            shipper_name="Shipper Demo",
            recipient_name="Recipient Demo",
            destination_address="1 rue de la Paix",
        )
        tracking_response = self.client.get(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
        )
        self.assertEqual(tracking_response.status_code, 200)
        self.assertContains(tracking_response, "ui-comp-card")
        self.assertContains(tracking_response, "ui-comp-title")
        self.assertContains(tracking_response, "ui-comp-form")

    def test_scan_remaining_pages_use_design_component_classes(self):
        stock_response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(stock_response.status_code, 200)
        self.assertContains(stock_response, 'class="scan-header ui-comp-panel"')
        self.assertContains(stock_response, 'class="scan-title ui-comp-title">ASF WMS')
        self.assertNotContains(stock_response, "ASF WMS Scan")
        self.assertNotContains(stock_response, "Flux rapides pour mobile et scanner.")
        self.assertContains(
            stock_response,
            'class="scan-nav scan-nav-bootstrap navbar navbar-expand-xl ui-comp-panel"',
        )
        self.assertContains(stock_response, 'data-bs-toggle="dropdown"')
        self.assertContains(stock_response, "scan-nav-account")
        self.assertContains(stock_response, "dropdown-header")
        self.assertNotContains(stock_response, "Essayer interface Next")
        self.assertNotContains(stock_response, 'id="ui-toggle"')
        self.assertNotContains(stock_response, 'id="theme-toggle"')
        self.assertNotContains(stock_response, 'id="ui-reset-default"')
        self.assertNotContains(stock_response, "localStorage.getItem('wms-ui')")
        content = stock_response.content.decode()
        header_start = content.index('<header class="scan-header ui-comp-panel">')
        header_end = content.index("</header>", header_start)
        nav_index = content.index(
            'class="scan-nav scan-nav-bootstrap navbar navbar-expand-xl ui-comp-panel"'
        )
        self.assertGreater(nav_index, header_start)
        self.assertLess(nav_index, header_end)

        ui_lab_response = self.client.get(reverse("scan:scan_ui_lab"))
        self.assertEqual(ui_lab_response.status_code, 200)
        self.assertContains(ui_lab_response, "ui-comp-card")
        self.assertContains(ui_lab_response, "ui-comp-title")
        self.assertContains(ui_lab_response, "ui-comp-form")
        self.assertContains(
            ui_lab_response,
            "https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css",
        )
        self.assertContains(ui_lab_response, "ui-lab-stat-card")
        self.assertContains(ui_lab_response, "ui-lab-activity-item")
        self.assertContains(ui_lab_response, "ui-comp-toolbar")
        self.assertContains(ui_lab_response, "ui-comp-filter")
        self.assertContains(ui_lab_response, "ui-comp-chip-list")
        self.assertContains(ui_lab_response, "ui-comp-status-pill")
        self.assertContains(ui_lab_response, "ui-comp-kpi-card")
        self.assertContains(ui_lab_response, 'id="ui-lab-contract-alert"')
        self.assertContains(ui_lab_response, 'id="ui-lab-contract-panel"')
        self.assertContains(ui_lab_response, 'id="ui-lab-contract-toolbar"')
        self.assertContains(ui_lab_response, 'id="ui-lab-contract-actions"')
        self.assertContains(ui_lab_response, "ui-comp-alert")

        public_link = PublicOrderLink.objects.create(label="Public UI Test")

        public_order_response = self.client.get(
            reverse("scan:scan_public_order", args=[public_link.token])
        )
        self.assertEqual(public_order_response.status_code, 200)
        self.assertContains(public_order_response, "ui-comp-card")
        self.assertContains(public_order_response, "ui-comp-title")
        self.assertContains(public_order_response, "ui-comp-form")

        public_account_response = self.client.get(
            reverse("scan:scan_public_account_request", args=[public_link.token])
        )
        self.assertEqual(public_account_response.status_code, 200)
        self.assertContains(public_account_response, "ui-comp-card")
        self.assertContains(public_account_response, "ui-comp-title")
        self.assertContains(public_account_response, "ui-comp-form")

    def test_scan_public_account_request_uses_shared_actions_and_alert_contract(self):
        public_link = PublicOrderLink.objects.create(label="Public UI Contract")

        response = self.client.get(
            reverse("scan:scan_public_account_request", args=[public_link.token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-actions")
        self.assertContains(response, reverse("scan:scan_public_order", args=[public_link.token]))
        self.assertContains(response, 'class="btn btn-tertiary scan-scan-btn scan-doc-btn"')
        self.assertContains(response, 'class="btn btn-primary scan-submit"')

        error_response = self.client.post(
            reverse("scan:scan_public_account_request", args=[public_link.token]),
            {},
        )

        self.assertEqual(error_response.status_code, 200)
        self.assertContains(error_response, "ui-comp-alert")
        self.assertContains(error_response, "Nom de l&#x27;association requis.")
        self.assertContains(error_response, "Adresse requise.")

    def test_scan_dashboard_uses_bootstrap_filters(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card card border-0")
        self.assertContains(response, "row g-3")
        self.assertContains(response, "btn btn-primary")
        self.assertContains(response, 'name="kpi_start"')
        self.assertContains(response, 'name="kpi_end"')
        self.assertContains(response, 'name="chart_start"')
        self.assertContains(response, 'name="chart_end"')
        self.assertContains(response, 'name="shipment_status"')
        self.assertNotContains(response, 'name="period"')

    def test_scan_forms_keep_requested_controls_on_single_desktop_rows(self):
        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "scan-dashboard-filter-row")
        self.assertContains(dashboard_response, "scan-dashboard-filter-actions-inline")
        self.assertContains(dashboard_response, "scan-dashboard-field")

        stock_response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(stock_response.status_code, 200)
        self.assertContains(stock_response, "scan-stock-filter-row")
        self.assertContains(stock_response, "scan-stock-filter-actions-inline")
        self.assertContains(stock_response, "scan-stock-field")
        self.assertContains(stock_response, "scan-stock-switch-field")

        receive_pallet_response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertEqual(receive_pallet_response.status_code, 200)
        self.assertContains(receive_pallet_response, "scan-receive-pallet-primary-row")
        self.assertContains(receive_pallet_response, "scan-receive-pallet-actions-inline")
        self.assertContains(receive_pallet_response, "scan-receive-pallet-field")

        receive_association_response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(receive_association_response.status_code, 200)
        self.assertContains(receive_association_response, "scan-receive-association-primary-row")
        self.assertContains(receive_association_response, "scan-receive-association-actions-inline")
        self.assertContains(receive_association_response, "scan-receive-association-field")

        stock_update_response = self.client.get(reverse("scan:scan_stock_update"))
        self.assertEqual(stock_update_response.status_code, 200)
        self.assertContains(stock_update_response, "scan-stock-update-main-row")
        self.assertContains(stock_update_response, "scan-stock-update-actions-inline")
        self.assertContains(stock_update_response, "scan-stock-update-primary-field")
        self.assertContains(stock_update_response, "scan-stock-update-readonly-row")

        prepare_kits_response = self.client.get(reverse("scan:scan_prepare_kits"))
        self.assertEqual(prepare_kits_response.status_code, 200)
        self.assertContains(prepare_kits_response, "scan-prepare-kits-main-row")
        self.assertContains(prepare_kits_response, "scan-prepare-kits-actions-inline")
        self.assertContains(prepare_kits_response, "scan-prepare-kits-top-field")
        self.assertContains(prepare_kits_response, "scan-prepare-kits-composition-field")

        pack_response = self.client.get(reverse("scan:scan_pack"))
        self.assertEqual(pack_response.status_code, 200)
        self.assertContains(pack_response, "scan-pack-shipping-row")
        self.assertContains(pack_response, "scan-pack-shipping-actions-inline")
        self.assertContains(pack_response, "scan-pack-shipping-field")

    def test_scan_state_pages_use_bootstrap_card_shell(self):
        for route_name in [
            "scan:scan_cartons_ready",
            "scan:scan_kits_view",
            "scan:scan_shipments_ready",
            "scan:scan_orders_view",
            "scan:scan_receipts_view",
            "scan:scan_shipments_tracking",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "scan-card card border-0")

    def test_scan_receipts_and_tracking_use_bootstrap_form_controls(self):
        receipts_response = self.client.get(reverse("scan:scan_receipts_view"))
        self.assertEqual(receipts_response.status_code, 200)
        self.assertContains(receipts_response, "form-select")
        self.assertContains(receipts_response, 'id="receipt-filter-form"')

        tracking_response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertEqual(tracking_response.status_code, 200)
        self.assertContains(tracking_response, "form-control")
        self.assertContains(tracking_response, "row g-3")
        self.assertContains(tracking_response, "btn btn-primary")

    def test_scan_preparation_pages_use_bootstrap_layout(self):
        for route_name in [
            "scan:scan_prepare_kits",
            "scan:scan_pack",
            "scan:scan_stock_update",
            "scan:scan_out",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "scan-card card border-0")
                self.assertContains(response, "btn btn-tertiary")

    def test_scan_receive_pages_use_bootstrap_layout(self):
        for route_name in [
            "scan:scan_receive",
            "scan:scan_receive_pallet",
            "scan:scan_receive_association",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "scan-card card border-0")
                self.assertContains(response, "form-label")

    def test_scan_order_and_tracking_pages_use_bootstrap_layout(self):
        for route_name in [
            "scan:scan_order",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "scan-card card border-0")
                self.assertContains(response, "btn btn-tertiary")

    def test_scan_superuser_pages_use_bootstrap_layout(self):
        self.client.force_login(self.superuser)
        for route_name in [
            "scan:scan_settings",
            "scan:scan_admin_contacts",
            "scan:scan_admin_products",
            "scan:scan_admin_design",
            "scan:scan_import",
            "scan:scan_print_templates",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "scan-card card border-0")

    def test_scan_routes_still_render_shell_with_bootstrap_enabled(self):
        for route_name in [
            "scan:scan_dashboard",
            "scan:scan_stock",
            "scan:scan_shipment_create",
            "scan:scan_shipments_tracking",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="scan-shell')
                self.assertContains(response, 'class="scan-bootstrap-enabled"')

    def test_non_portal_button_levels_follow_intended_semantics(self):
        self.client.force_login(self.superuser)
        component = Product.objects.create(
            sku="UI-LVL-COMP",
            name="Composant UI Levels",
            qr_code_image="qr_codes/ui_levels_comp.png",
        )
        kit = Product.objects.create(
            sku="UI-LVL-KIT",
            name="Kit UI Levels",
            qr_code_image="qr_codes/ui_levels_kit.png",
        )
        ProductKitItem.objects.create(kit=kit, component=component, quantity=2)

        admin_products_response = self.client.get(reverse("scan:scan_admin_products"))
        self.assertEqual(admin_products_response.status_code, 200)
        self.assertContains(
            admin_products_response,
            '<button type="submit" class="scan-submit btn btn-primary">Filtrer</button>',
            html=True,
        )
        self.assertContains(
            admin_products_response,
            'class="btn btn-danger scan-scan-btn"',
        )
        self.assertContains(
            admin_products_response,
            reverse("admin:wms_product_delete", args=[kit.id]),
        )

        product_labels_response = self.client.get(reverse("scan:scan_product_labels"))
        self.assertEqual(product_labels_response.status_code, 200)
        self.assertContains(
            product_labels_response,
            '<a class="scan-scan-btn btn btn-tertiary" href="'
            + reverse("scan:scan_product_labels")
            + '">Reinitialiser</a>',
            html=True,
        )

        print_template_edit_response = self.client.get(
            reverse("scan:scan_print_template_edit", args=["shipment_note"])
        )
        self.assertEqual(print_template_edit_response.status_code, 200)
        self.assertContains(
            print_template_edit_response,
            '<a class="scan-scan-btn btn btn-tertiary" href="'
            + reverse("scan:scan_print_templates")
            + '">Retour</a>',
            html=True,
        )

        settings_response = self.client.get(reverse("scan:scan_settings"))
        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(
            settings_response,
            'name="action" value="apply_preset" class="scan-submit secondary btn btn-secondary"',
        )
        self.assertContains(
            settings_response,
            'name="action" value="preview" class="scan-submit secondary btn btn-secondary"',
        )

        self.client.force_login(self.staff_user)
        out_response = self.client.get(reverse("scan:scan_out"))
        self.assertEqual(out_response.status_code, 200)
        self.assertContains(
            out_response,
            '<button type="submit" class="scan-submit btn btn-danger">Enregistrer suppression</button>',
            html=True,
        )
        self.assertContains(
            out_response,
            '<button type="button" class="btn btn-tertiary scan-scan-btn" data-scan-target="id_product_code">Scan</button>',
            html=True,
        )

        public_link = PublicOrderLink.objects.create(label="Public UI Levels")
        public_account_response = self.client.get(
            reverse("scan:scan_public_account_request", args=[public_link.token])
        )
        self.assertEqual(public_account_response.status_code, 200)
        self.assertContains(
            public_account_response,
            'class="btn btn-tertiary scan-scan-btn scan-doc-btn"',
        )
        self.assertContains(
            public_account_response,
            reverse("scan:scan_public_order", args=[public_link.token]),
        )

        shipment = Shipment.objects.create(
            shipper_name="Shipper UI",
            recipient_name="Recipient UI",
            destination_address="1 Rue UI",
            status=ShipmentStatus.DRAFT,
        )
        Document.objects.create(
            shipment=shipment,
            doc_type="additional",
            file=SimpleUploadedFile("ui-levels.txt", b"ui levels"),
        )
        shipment_edit_response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )
        self.assertEqual(shipment_edit_response.status_code, 200)
        self.assertContains(
            shipment_edit_response,
            'class="scan-scan-btn btn btn-danger scan-doc-btn">Supprimer</button>',
        )

        shipment_track_response = self.client.get(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
        )
        self.assertEqual(shipment_track_response.status_code, 200)
        self.assertContains(
            shipment_track_response,
            'id="tracking-leave-discard"',
        )
        self.assertContains(
            shipment_track_response,
            'class="scan-scan-btn btn btn-tertiary"',
        )

    def test_scan_base_bootstrap_neutral_controls_use_tertiary_or_secondary_levels(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "navbar-toggler border-0 px-2 btn-tertiary")
        self.assertContains(response, "nav-link dropdown-toggle btn-tertiary")
        self.assertContains(
            response,
            '<button type="button" id="scan-sync-reload" class="btn btn-tertiary btn-sm">Recharger</button>',
            html=True,
        )
        self.assertContains(
            response,
            '<button type="button" id="scan-close" class="btn btn-tertiary btn-sm">Fermer</button>',
            html=True,
        )

    def test_scan_ui_lab_uses_tertiary_buttons_for_neutral_examples(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_ui_lab"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Action tertiaire")
        self.assertContains(response, "btn btn-tertiary p-0")

    def test_scan_ui_lab_exposes_shared_component_catalog_without_runtime_actions(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("scan:scan_admin_design"))
        self.assertContains(response, 'id="ui-lab-component-name"')
        self.assertContains(response, 'name="ui_lab_catalog_live_preview"')
        self.assertContains(response, 'id="ui-lab-contract-alert"')
        self.assertContains(response, 'id="ui-lab-contract-panel"')
        self.assertContains(response, 'id="ui-lab-contract-toolbar"')
        self.assertContains(response, 'id="ui-lab-contract-actions"')
        self.assertContains(
            response,
            'class="form-check form-switch scan-inline-switch scan-inline-switch-wide"',
        )
        self.assertContains(response, 'class="ui-comp-status-pill is-ready"')
        self.assertContains(response, "ui-comp-alert")
        self.assertNotContains(response, 'name="action" value="save"')
        self.assertNotContains(response, 'name="action" value="reset"')

        design_response = self.client.get(reverse("scan:scan_admin_design"))

        self.assertEqual(design_response.status_code, 200)
        self.assertContains(design_response, reverse("scan:scan_ui_lab"))
