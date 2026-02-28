from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from wms.models import (
    Location,
    Product,
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_context_exposes_bootstrap_flag(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["scan_bootstrap_enabled"])

    @override_settings(SCAN_BOOTSTRAP_ENABLED=False)
    def test_scan_base_does_not_include_bootstrap_assets_when_disabled(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "scan-bootstrap.css")
        self.assertNotContains(response, "bootstrap@5.3.3")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_base_includes_bootstrap_assets_when_enabled(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-bootstrap.css")
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_stock_uses_bootstrap_layout_and_keeps_table_tools(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "row g-3")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, 'data-table-tools="1"')
        self.assertContains(response, "form-check form-switch")
        self.assertContains(response, "scan-switch-card")
        self.assertContains(response, "id_include_zero")
        self.assertContains(response, "Inclure les produits avec stock")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_bootstrap_nav_uses_title_case_for_state_pages(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vue Stock")
        self.assertContains(response, "Vue R&eacute;ception")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_shipment_create_uses_bootstrap_and_preserves_js_hooks(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-form"')
        self.assertContains(response, 'id="shipment-lines"')
        self.assertContains(response, "btn btn-primary")
        self.assertContains(response, 'id="shipment-details-section"')

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_shipments_tracking_week_filter_uses_extended_input_class(self):
        response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-week-input")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_order_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_order"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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
                    self.assertContains(response, "scan-switch-card")
                    self.assertContains(
                        response,
                        "Autoriser l'ajout avec valeurs standard",
                    )

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_receive_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_receive_association_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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
            reverse("scan:scan_print_template_edit", args=["shipment_label"])
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, "ui-comp-card")
        self.assertContains(edit_response, "ui-comp-title")
        self.assertContains(edit_response, "ui-comp-form")

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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_dashboard_uses_bootstrap_filters(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card card border-0")
        self.assertContains(response, "row g-3")
        self.assertContains(response, "btn btn-primary")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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
                self.assertContains(response, "btn btn-outline-primary")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_scan_order_and_tracking_pages_use_bootstrap_layout(self):
        for route_name in [
            "scan:scan_order",
        ]:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "scan-card card border-0")
                self.assertContains(response, "btn btn-outline-primary")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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
