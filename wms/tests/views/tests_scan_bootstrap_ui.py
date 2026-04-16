import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.billing_permissions import BILLING_STAFF_GROUP_NAME
from wms.forms import ScanListingEntryForm
from wms.models import (
    Destination,
    Document,
    Location,
    Order,
    OrderReviewStatus,
    OrderStatus,
    PreparationCartonProposal,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationProposalSource,
    PreparationRun,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    Product,
    ProductCategory,
    ProductKitItem,
    ProductLot,
    ProductLotStatus,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    PublicOrderLink,
    Receipt,
    ReceiptType,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceStatus,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentValidationStatus,
    Warehouse,
)


class ScanBootstrapUiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff_user = get_user_model().objects.create_user(
            username="scan-bootstrap-staff",
            password="pass1234",
            is_staff=True,
        )
        cls.validator_user = get_user_model().objects.create_user(
            username="scan-bootstrap-validator",
            password="pass1234",
            is_staff=True,
            email="scan-bootstrap-validator@example.com",
        )
        Group.objects.get_or_create(name="Account_User_Validation")[0].user_set.add(
            cls.validator_user
        )
        cls.superuser = get_user_model().objects.create_superuser(
            username="scan-bootstrap-admin",
            password="pass1234",
            email="scan-bootstrap-admin@example.com",
        )
        cls.correspondent = Contact.objects.create(
            name="Correspondant Bootstrap",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        cls.warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        cls.destination = Destination.objects.create(
            city="BRAZZAVILLE",
            iata_code="BZV",
            country="REP. DU CONGO",
            correspondent_contact=cls.correspondent,
            is_active=True,
        )
        location = Location.objects.create(
            warehouse=cls.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        cls.product = Product.objects.create(
            sku="BOOT-001",
            name="Produit Bootstrap",
            default_location=location,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=cls.product,
            lot_code="LOT-BOOT-001",
            received_on=date(2026, 1, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=12,
            location=location,
        )

    def setUp(self):
        self.client.force_login(self.staff_user)

    def _scan_sidebar_html(self, response):
        content = response.content.decode()
        nav_start = content.index('id="scan-sidebar-nav"')
        nav_end = content.index("</nav>", nav_start)
        return content[nav_start:nav_end]

    def _scan_utility_nav_html(self, response):
        content = response.content.decode()
        nav_start = content.index('id="scan-utility-nav"')
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
        self.assertContains(response, "scan/modules/core.js")
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

    def test_scan_sidebar_exposes_run_magasin_link_in_preparation_group(self):
        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self.assertIn(reverse("scan:scan_preparation_run_list"), nav_html)
        self.assertIn("Runs magasin", nav_html)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                "Préparer des kits",
                "Préparer des colis",
                "Préparation expédition",
                "Runs magasin",
            ],
        )

    def test_scan_sidebar_exposes_listing_link_in_reception_group(self):
        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self.assertIn(reverse("scan:scan_receive_listing"), nav_html)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                "Réception palette",
                "Listing",
                "Réception association",
            ],
        )

    def test_scan_sidebar_exposes_account_validations_for_validator(self):
        PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.SHIPPER,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association Pending Review",
            email="pending-review@example.com",
            phone="0102030405",
            address_line1="1 Rue Pending",
            address_line2="",
            postal_code="75001",
            city="Paris",
            country="France",
        )
        self.client.force_login(self.validator_user)

        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self.assertIn('id="scan-sidebar-contacts-toggle"', nav_html)
        self.assertIn("/scan/contacts/validations/", nav_html)
        self.assertIn("Validations", nav_html)
        self.assertContains(response, "Nouvelles demandes de compte en attente")
        self.assertContains(response, "/scan/account-validations/")

    def test_scan_templates_load_targeted_modules_only_on_needed_pages(self):
        stock_response = self.client.get(reverse("scan:scan_stock"))
        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        shipment_response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(stock_response.status_code, 200)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(shipment_response.status_code, 200)

        self.assertNotContains(stock_response, "scan/modules/dashboard.js")
        self.assertNotContains(stock_response, "scan/modules/shipments.js")
        self.assertContains(dashboard_response, "scan/modules/dashboard.js")
        self.assertNotContains(dashboard_response, "scan/modules/shipments.js")
        self.assertContains(shipment_response, "scan/modules/shipments.js")

    def test_scan_stock_uses_bootstrap_layout_and_avoids_local_table_tools(self):
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "row g-3")
        self.assertContains(response, "table table-sm table-hover")
        self.assertNotContains(response, 'data-table-tools="1"')
        self.assertContains(response, "form-check form-switch")
        self.assertContains(response, "scan-inline-switch")
        self.assertContains(response, "scan-switch-control")
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

    def test_scan_stock_places_category_filters_on_dedicated_row_before_actions(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'class="scan-field scan-stock-field scan-stock-category-field col-12"',
        )
        content = response.content.decode()
        self.assertLess(
            content.index("scan-stock-category-field"),
            content.index("scan-stock-filter-actions-inline"),
        )

        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(
            ".scan-bootstrap-enabled .scan-stock-filter-row .scan-stock-category-field {",
            css_content,
        )
        self.assertIn("grid-column: 1 / -1;", css_content)

    def test_scan_stock_exposes_multi_level_category_filters(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-stock-category-l1"')
        self.assertContains(response, 'id="scan-stock-category-l2"')
        self.assertContains(response, 'id="scan-stock-category-l3"')
        self.assertContains(response, 'id="scan-stock-category-l4"')
        self.assertContains(response, 'id="scan-stock-category-filters"')
        self.assertContains(response, 'type="hidden" id="id_category" name="category"')

    def test_scan_stock_applies_shared_select_size_classes_to_filters(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_warehouse"')
        self.assertContains(response, 'id="id_sort"')
        self.assertContains(response, 'id="scan-stock-category-l1"')
        self.assertContains(response, "ui-select--md")
        self.assertContains(response, "ui-select--sm")

    def test_scan_stock_shows_product_open_action_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<th>Actions</th>", html=True)
        self.assertContains(
            response,
            '<a class="scan-scan-btn btn btn-tertiary btn-sm" href="'
            + reverse("admin:wms_product_change", args=[self.product.id])
            + '" target="_blank" rel="noopener">Ouvrir</a>',
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

    def test_scan_nav_places_planning_under_management_group(self):
        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        utility_nav_html = self._scan_utility_nav_html(response)
        self.assertNotIn(reverse("planning:run_list"), utility_nav_html)
        nav_html = self._scan_sidebar_html(response)
        self.assertIn("Planning", nav_html)
        self.assertIn(reverse("planning:run_list"), nav_html)

    def test_scan_recipient_needs_page_uses_bootstrap_filters_sidebar_and_tooltips(self):
        recipient_org = Contact.objects.create(
            name="Hopital Prioritaire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            first_name="Alice",
            last_name="Need",
            contact_type=ContactType.PERSON,
            organization=recipient_org,
            is_active=True,
        )
        authorized_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient,
            contact=recipient_contact,
            is_active=True,
        )
        shipper_org = Contact.objects.create(
            name="Expediteur Bootstrap",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_contact = Contact.objects.create(
            first_name="Eva",
            last_name="Shipper",
            contact_type=ContactType.PERSON,
            organization=shipper_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=authorized_recipient_contact,
            is_default=True,
            is_active=True,
        )
        category = ProductCategory.objects.create(name="Medical")
        product = Product.objects.create(
            sku="BOOT-NEEDS-001",
            name="Produit Prioritaire",
            category=category,
            qr_code_image="qr_codes/boot-needs-001.png",
            is_active=True,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=recipient,
            product=product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-BOOT-NEEDS-001",
            received_on=date(2026, 1, 2),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=2,
            location=Location.objects.first(),
        )

        response = self.client.get(reverse("scan:scan_recipient_needs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vue Besoins")
        self.assertContains(response, 'id="scan-sidebar-stocks-group"')
        self.assertContains(response, reverse("scan:scan_recipient_needs"))
        self.assertContains(response, 'name="destination"')
        self.assertContains(response, 'name="recipient"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="need_status"')
        self.assertContains(response, 'name="priority"')
        self.assertContains(response, "Expediteur(s) lie(s)")
        self.assertContains(response, "Disponibilite Stock")
        self.assertContains(response, "Priorite")
        self.assertContains(response, "Periode")
        self.assertContains(response, "Semaine")
        self.assertContains(response, "Preparer la selection")
        self.assertContains(response, 'name="selected_row_keys"')
        self.assertContains(response, 'data-bs-toggle="tooltip"')
        self.assertContains(response, "priority_help")

    def test_scan_nav_renders_expandable_sidebar_shell(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-brand-desktop"')
        self.assertContains(response, 'id="scan-brand-mobile"')
        self.assertContains(response, 'id="scan-sidebar-toggle"')
        self.assertContains(response, 'id="scan-sidebar-offcanvas"')
        self.assertContains(response, 'id="scan-sidebar-nav"')
        self.assertContains(response, 'id="scan-faq-link"')
        self.assertContains(response, 'id="scan-masthead-settings-toggle"')
        self.assertContains(response, 'id="scan-masthead-account-toggle"')
        self.assertContains(response, 'id="scan-sidebar-stocks-toggle"')
        self.assertContains(response, 'id="scan-sidebar-receiving-toggle"')
        self.assertContains(response, 'id="scan-sidebar-preparation-toggle"')
        self.assertContains(response, 'id="scan-sidebar-management-toggle"')
        self.assertContains(response, 'id="scan-sidebar-stocks-group"')
        self.assertContains(response, 'id="scan-sidebar-management-group"')
        self.assertContains(
            response,
            'id="scan-sidebar-management-group"',
        )
        self.assertNotContains(
            response,
            'class="scan-nav scan-nav-bootstrap navbar navbar-expand-xl"',
        )

    def test_scan_masthead_exposes_history_navigation_buttons(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-history-back"')
        self.assertContains(response, 'id="scan-history-forward"')
        self.assertContains(response, "window.history.back()")
        self.assertContains(response, "window.history.forward()")

    def test_scan_nav_renders_shipments_group_instead_of_single_link(self):
        response = self.client.get(reverse("scan:scan_shipments_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-sidebar-shipments-toggle"')
        self.assertContains(response, 'id="scan-sidebar-shipments-group"')
        self.assertContains(response, "Dossiers")
        self.assertContains(response, "Suivi des expéditions")
        self.assertNotContains(response, 'id="scan-sidebar-shipments"')

    def test_scan_masthead_shows_pending_recipient_validation_notification(self):
        self.client.force_login(self.superuser)
        pending_contact = Contact.objects.create(
            name="Destinataire en attente",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=pending_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )

        response = self.client.get(reverse("scan:scan_import"))

        self.assertEqual(response.status_code, 200)
        utility_nav_html = self._scan_utility_nav_html(response)
        self.assertIn('id="scan-masthead-notifications"', utility_nav_html)
        self.assertIn("/scan/contacts/validations/recipients/", utility_nav_html)
        self.assertIn("ui-comp-count-badge", utility_nav_html)
        self.assertIn(">1</span>", utility_nav_html)

    def test_scan_nav_orders_primary_sections_for_standard_staff(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                'id="scan-sidebar-dashboard"',
                'id="scan-sidebar-stocks-toggle"',
                'id="scan-sidebar-receiving-toggle"',
                'id="scan-sidebar-preparation-toggle"',
                'id="scan-sidebar-shipments-toggle"',
                'id="scan-sidebar-contacts-toggle"',
                'id="scan-sidebar-management-toggle"',
            ],
        )
        self.assertNotIn("Compte", nav_html)
        self.assertNotIn('id="scan-masthead-settings-toggle"', nav_html)
        self.assertNotIn('id="scan-sidebar-billing"', nav_html)
        self.assertContains(response, 'id="scan-masthead-account-toggle"')

    def test_scan_nav_orders_primary_sections_for_billing_staff(self):
        billing_group, _ = Group.objects.get_or_create(name=BILLING_STAFF_GROUP_NAME)
        self.staff_user.groups.add(billing_group)
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                'id="scan-sidebar-dashboard"',
                'id="scan-sidebar-stocks-toggle"',
                'id="scan-sidebar-receiving-toggle"',
                'id="scan-sidebar-preparation-toggle"',
                'id="scan-sidebar-shipments-toggle"',
                'id="scan-sidebar-contacts-toggle"',
                'id="scan-sidebar-management-toggle"',
            ],
        )
        self.assertNotIn("Compte", nav_html)
        self.assertNotIn('id="scan-masthead-settings-toggle"', nav_html)
        self.assertNotIn('id="scan-sidebar-billing"', nav_html)
        self.assertContains(response, reverse("planning:run_list"))
        self.assertContains(response, "Edition Devis/Facture")
        self.assertNotContains(response, "Paramètres")
        self.assertNotContains(response, "Equivalence")

    def test_scan_nav_orders_primary_sections_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self._assert_nav_labels_in_order(
            nav_html,
            [
                'id="scan-sidebar-dashboard"',
                'id="scan-sidebar-stocks-toggle"',
                'id="scan-sidebar-receiving-toggle"',
                'id="scan-sidebar-preparation-toggle"',
                'id="scan-sidebar-shipments-toggle"',
                'id="scan-sidebar-contacts-toggle"',
                'id="scan-sidebar-management-toggle"',
            ],
        )
        self.assertNotIn("Compte", nav_html)
        self.assertNotIn('id="scan-masthead-settings-toggle"', nav_html)
        self.assertNotIn('id="scan-sidebar-billing"', nav_html)
        self.assertContains(response, 'id="scan-masthead-settings-toggle"')
        self.assertContains(response, 'id="scan-masthead-account-toggle"')

    def test_scan_nav_shows_billing_entries_under_management_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        nav_html = self._scan_sidebar_html(response)
        self.assertIn("Planning", nav_html)
        self.assertIn("Edition Devis/Facture", nav_html)
        self.assertNotIn("Paramètres", nav_html)
        self.assertNotIn("Equivalence", nav_html)
        self.assertContains(response, "Général")
        self.assertContains(response, "Produit")
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
        nav_html = self._scan_sidebar_html(response)
        self.assertIn("Planning", nav_html)
        self.assertIn("Edition Devis/Facture", nav_html)
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

    def test_scan_shipment_create_uses_wave3_workflow_contracts(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-details-actions"')
        self.assertContains(response, 'class="scan-choice-actions ui-comp-actions"')
        self.assertContains(response, "scan-message error ui-comp-alert scan-hidden")

    def test_scan_shipment_edit_uses_wave3_follow_up_contracts(self):
        association = Contact.objects.create(
            name="Association Wave 3 UI",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipment = Shipment.objects.create(
            shipper_name=association.name,
            shipper_contact_ref=association,
            recipient_name="Recipient UI",
            destination_address="1 Rue UI",
            status=ShipmentStatus.DRAFT,
        )
        Document.objects.create(
            shipment=shipment,
            doc_type="additional",
            file=SimpleUploadedFile("wave3-ui.txt", b"wave3"),
        )

        response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-dossier-header"')
        self.assertContains(response, 'id="shipment-dossier-edit-panel"')
        self.assertContains(response, 'id="shipment-tracking-actions"')
        self.assertContains(response, 'id="shipment-dossier-grouped-print-actions"')
        self.assertContains(response, 'id="shipment-dossier-paper-print-actions"')
        self.assertContains(response, 'id="shipment-dossier-pdf-export-actions"')
        self.assertContains(
            response,
            'id="shipment-dossier-grouped-print-actions" class="ui-comp-actions shipment-dossier-document-actions"',
        )
        self.assertContains(
            response,
            'id="shipment-dossier-paper-print-actions" class="ui-comp-actions shipment-dossier-document-actions"',
        )
        self.assertContains(
            response,
            'id="shipment-dossier-pdf-export-actions" class="ui-comp-actions shipment-dossier-document-actions"',
        )
        self.assertContains(response, 'id="shipment-additional-document-upload-actions"')
        self.assertContains(response, 'id="shipment-additional-document-list"')
        self.assertContains(response, 'data-local-document-helper-link="1"', count=5)
        self.assertContains(
            response,
            '<button type="submit" class="scan-scan-btn btn btn-secondary">Uploader</button>',
            html=True,
        )
        self.assertContains(
            response,
            'class="scan-scan-btn btn btn-danger scan-doc-btn">Supprimer</button>',
        )

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

    def test_scan_shipments_tracking_renders_summary_cards_and_next_action_column(self):
        response = self.client.get(reverse("scan:scan_shipments_tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-shipments-tracking-summary"')
        self.assertContains(response, "<th>À faire</th>", html=True)

    def test_scan_orders_view_renders_summary_cards_and_action_column(self):
        Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Action",
            destination_address="3 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
        )

        response = self.client.get(reverse("scan:scan_orders_view"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-orders-view-summary"')
        self.assertContains(response, "<th>Prochaine étape</th>", html=True)
        self.assertContains(response, "<th>Actions</th>", html=True)
        self.assertContains(response, ">Ouvrir<", html=False)
        self.assertNotContains(response, 'name="review_status"')
        self.assertNotContains(response, "Modifier:")
        self.assertNotContains(response, "Refus:")

    def test_scan_order_detail_uses_design_component_classes(self):
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Detail",
            destination_address="5 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )

        response = self.client.get(reverse("scan:scan_order_detail", args=[order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "Contacts & Destination")
        self.assertContains(response, "Revue de commande")
        self.assertContains(response, "Mettre à jour")
        self.assertContains(response, "Créer les colis et l&#x27;expédition")

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
        self.assertContains(
            response,
            '<span class="scan-shipments-ready-head-label">NUMERO</span><br>',
        )
        self.assertContains(
            response,
            '<span class="scan-shipments-ready-head-label">EXPEDITION</span>',
        )

    def test_scan_faq_uses_dossiers_vocabulary_for_shipment_list(self):
        response = self.client.get(reverse("scan:scan_faq"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dossiers")
        self.assertNotContains(response, "Vue Expéditions")

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

    def test_scan_bootstrap_css_defines_shared_select_contract(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(".scan-bootstrap-enabled .form-select {", css_content)
        self.assertIn("background-image:", css_content)
        self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--sm", css_content)
        self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--md", css_content)
        self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--lg", css_content)
        self.assertIn(".scan-bootstrap-enabled .form-select.ui-select--xl", css_content)

    def test_shared_number_input_keeps_value_clear_of_left_controls(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        core_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "modules" / "core.js"
        core_content = core_path.read_text(encoding="utf-8")

        self.assertIn(
            ".scan-bootstrap-enabled .ui-number-input {\n  --ui-number-input-btn-width: 1.15rem;",
            css_content,
        )
        self.assertIn(
            "--ui-number-input-controls-gap: 0.14rem;",
            css_content,
        )
        self.assertIn(
            "--ui-number-input-controls-inset: 0.3rem;",
            css_content,
        )
        self.assertIn(
            "--ui-number-input-value-offset:",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .ui-number-input .form-control,\n"
            ".scan-bootstrap-enabled .ui-number-input-input {\n"
            "  min-width: 0;\n"
            "  padding-left: calc(var(--wms-input-padding-x) + var(--ui-number-input-value-offset));",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .ui-number-input.is-compact {\n"
            "  --ui-number-input-btn-width: 1rem;",
            css_content,
        )
        self.assertIn("function syncNumberInputLayout(input, wrapper, controls) {", core_content)
        self.assertIn("input.style.paddingLeft = reservedPaddingPx;", core_content)
        self.assertIn("input.style.paddingInlineStart = reservedPaddingPx;", core_content)

    def test_scan_bootstrap_css_keeps_recipient_preference_table_headers_balanced(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(
            ".scan-bootstrap-enabled .recipient-preference-table .recipient-preference-col--estimate {\n"
            "  min-width: 7.75rem;\n"
            "  white-space: normal;",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .recipient-preference-table .recipient-preference-col--status {\n"
            "  min-width: 11rem;",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .recipient-preference-table .recipient-preference-col--quantity {\n"
            "  width: 7.75rem;",
            css_content,
        )
        self.assertIn(
            ".scan-bootstrap-enabled .recipient-preference-estimate-heading {\n"
            "  display: inline-block;\n"
            "  max-width: 8.25rem;",
            css_content,
        )

    def test_scan_shell_css_blocks_horizontal_overflow_in_scroll_region(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(
            ".scan-bootstrap-enabled .scan-body {\n"
            "  min-width: 0;\n"
            "  min-height: 0;\n"
            "  overflow-y: auto;\n"
            "  overflow-x: hidden;\n"
            "  overscroll-behavior-x: none;",
            css_content,
        )

    def test_scan_shell_css_restores_page_scroll_on_mobile(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(
            "@media (max-width: 992px) {\n"
            "  .scan-bootstrap-enabled body,\n"
            "  body.scan-bootstrap-enabled {\n"
            "    height: auto;\n"
            "    min-height: 100dvh;\n"
            "    overflow-y: auto;\n"
            "    overflow-x: hidden;\n"
            "  }",
            css_content,
        )

    def test_scan_prepare_kits_uses_full_width_top_panel_contract(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(
            ".scan-bootstrap-enabled .scan-prepare-kits-main-row .scan-prepare-kits-top-panel-full {",
            css_content,
        )
        self.assertNotIn("max-width: min(100%, 62rem);", css_content)

    def test_scan_field_css_contract_excludes_checkbox_and_radio_inputs(self):
        css_path = (
            Path(settings.BASE_DIR)
            / "wms"
            / "static"
            / "scan"
            / "css"
            / "partials"
            / "auth-public.css"
        )
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn('.scan-field input:not([type="checkbox"]):not([type="radio"]),', css_content)
        self.assertNotIn(
            ".scan-field input,\n.scan-field select,\n.scan-field textarea {", css_content
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
        self.assertIn("data-contact-stage", js_content)
        self.assertIn("required.add('entity_type')", js_content)
        self.assertIn("field.disabled = shouldHide", js_content)
        self.assertIn("detailsReady", js_content)
        self.assertIn("event.target.closest('[data-contact-action-select=\"1\"]')", js_content)
        self.assertIn("merge_contact", js_content)
        self.assertIn("deactivate_contact", js_content)

    def test_scan_admin_contacts_breaks_into_named_workflow_sections(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-admin-contacts-intro"')
        self.assertContains(response, 'id="scan-admin-contacts-create-destination"')
        self.assertContains(response, 'id="scan-admin-contacts-create-contact"')
        self.assertContains(response, 'id="scan-admin-contacts-filters"')
        self.assertContains(response, 'id="scan-admin-contacts-directory-card"')
        self.assertContains(response, 'id="scan-admin-contacts-correspondents-card"')
        self.assertContains(response, "ui-comp-card", count=6)
        self.assertContains(response, 'data-admin-contacts-crud="1"')
        self.assertContains(response, 'data-table-tools="1"', count=2)
        content = response.content.decode()
        directory_match = re.search(
            r'(<div id="scan-admin-contacts-directory-card".*?)<div id="scan-admin-contacts-correspondents-card"',
            content,
            re.S,
        )
        self.assertIsNotNone(directory_match)
        self.assertIn('data-table-tools="1"', directory_match.group(1))
        self.assertContains(response, 'id="scan-admin-contact-action-panel"')
        self.assertNotContains(response, 'id="scan-admin-contacts-cockpit"')
        self.assertContains(response, reverse("admin:contacts_contact_changelist"))
        self.assertContains(response, reverse("admin:wms_destination_changelist"))

    def test_scan_contacts_roles_cockpit_stacks_read_only_tables_one_per_line(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_contacts_roles"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        cockpit_match = re.search(
            r'(<div id="scan-admin-contacts-cockpit".*?)</section>',
            content,
            re.S,
        )
        self.assertIsNotNone(cockpit_match)
        cockpit_content = cockpit_match.group(1)
        tables_section, actions_section = cockpit_content.split("<hr>", 1)
        self.assertNotIn('class="col-12 col-xl-6"', tables_section)
        self.assertEqual(tables_section.count('class="col-12">'), 4)
        self.assertNotIn('class="col-12 col-xl-4"', actions_section)
        self.assertEqual(actions_section.count("contact-roles-action-block"), 3)

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
                    self.assertContains(response, "scan-switch-control")
                    self.assertContains(
                        response,
                        "Autoriser l'ajout avec valeurs standard",
                    )

    def test_scan_preparation_run_pages_keep_bootstrap_review_contracts(self):
        shipper_org = Contact.objects.create(
            name="Association Source UI",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=Contact.objects.create(
                first_name="Alice",
                last_name="Source",
                email="alice.source.ui@example.com",
                organization=shipper_org,
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        recipient_org = Contact.objects.create(
            name="Association Dest UI",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Contact.objects.create(
            first_name="Corinne",
            last_name="Dest UI",
            email="corinne.dest.ui@example.com",
            organization=recipient_org,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        recipient = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin bootstrap",
            created_by=self.staff_user,
        )
        PreparationShipperRule.objects.create(
            parameter_set=parameter_set,
            shipper=shipper,
            mode=PreparationShipperMode.ASF_AUTO_ALLOWED,
        )
        PreparationDestinationRule.objects.create(
            parameter_set=parameter_set,
            destination=self.destination,
            max_equivalent_units_per_flight=12,
            max_usable_flights_per_week=2,
            max_equivalent_units_per_week=20,
            max_shipments_per_week=3,
            fairness_weight="1.10",
        )
        run = PreparationRun.objects.create(
            parameter_set=parameter_set,
            created_by=self.staff_user,
            target_equivalent_units=20,
            target_shipment_count=2,
            target_shipment_size_units=10,
            min_shipment_size_units=5,
            max_shipment_size_units=12,
            flight_window_start=date(2026, 5, 18),
            flight_window_end=date(2026, 5, 24),
        )
        proposal = PreparationShipmentProposal.objects.create(
            run=run,
            shipper=shipper,
            recipient_organization=recipient,
            destination=self.destination,
            sequence=1,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            equivalent_units_total=8,
            rationale={"reasons": ["requested need covered"]},
        )
        PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=8,
            equivalent_units_total=8,
            rationale={"score_reasons": ["requested need covered"]},
        )

        create_response = self.client.get(reverse("scan:scan_preparation_run_create"))
        config_response = self.client.get(reverse("scan:scan_preparation_parameter_set_config"))
        detail_response = self.client.get(
            reverse("scan:scan_preparation_run_detail", args=[run.id])
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, "ui-comp-card")
        self.assertContains(create_response, "ui-comp-title")
        self.assertContains(create_response, "ui-comp-form")
        self.assertContains(create_response, 'type="date"')
        self.assertContains(create_response, 'id="prep-select-all-shippers"')

        self.assertEqual(config_response.status_code, 200)
        self.assertContains(config_response, "ui-comp-card")
        self.assertContains(config_response, "ui-comp-title")
        self.assertContains(config_response, "ui-comp-form")
        self.assertContains(config_response, "Configuration du jeu de paramètres")
        self.assertContains(
            config_response, 'name="destination_rules-0-allowed_weekdays_selection"'
        )
        self.assertContains(config_response, 'id="prep-weekday-dropdown-0"')
        self.assertContains(config_response, 'data-bs-toggle="tooltip"')
        self.assertContains(config_response, 'onchange="this.form.submit()"')
        self.assertContains(config_response, 'title="Nombre maximal de colis équivalents')
        self.assertContains(config_response, 'title="Le poids d&#x27;équité augmente ou réduit')
        self.assertContains(
            config_response,
            'title="Ne rien sélectionner pour utiliser tous les jours disponibles."',
        )
        self.assertNotContains(
            config_response,
            "Ne rien sélectionner pour utiliser tous les jours disponibles.</div>",
        )
        self.assertNotContains(config_response, ">Ouvrir<")

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "ui-comp-card")
        self.assertContains(detail_response, "ui-comp-title")
        self.assertContains(detail_response, "ui-comp-form")
        self.assertContains(detail_response, "ui-comp-actions")
        self.assertContains(detail_response, 'data-table-tools="1"')
        self.assertContains(detail_response, 'name="selected_shipment_ids"')
        self.assertContains(detail_response, 'name="selected_carton_ids"')
        self.assertContains(detail_response, 'value="convert_accepted"')

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

    def test_scan_shipment_create_js_marks_preassignment_overlay_active_when_visible(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("mismatchOverlay.classList.toggle('active', visible);", js_content)

    def test_scan_shipment_create_js_keeps_unlinked_recipients_out_of_pair_group(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan.js"
        js_content = js_path.read_text(encoding="utf-8")

        self.assertIn("if (!bindingPairs.length) {\n        return false;\n      }", js_content)
        self.assertNotIn("if (!bindingPairs.length) {\n        return true;\n      }", js_content)

    def test_scan_shipment_create_places_multi_product_button_before_primary_submit(self):
        response = self.client.get(reverse("scan:scan_shipment_create"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        details_start = content.index('id="shipment-details-section"')
        details_end = content.index("</form>", details_start)
        details_content = content[details_start:details_end]
        self.assertLess(
            details_content.index('name="action" value="create_pack"'),
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
        self.assertNotContains(response, "ui-comp-file-input")
        self.assertNotContains(response, "id_listing_file_type_pdf")

    def test_scan_receive_listing_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive_listing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")
        self.assertContains(response, 'id="scan-receive-listing-intake-card"')
        self.assertContains(response, 'name="listing_entry_file_type"')
        self.assertContains(response, 'name="listing_entry_receipt_id"')
        self.assertContains(
            response, "Attention : il est obligatoire de lier l'import à une réception."
        )
        self.assertContains(response, reverse("scan:scan_receive_pallet"))
        self.assertContains(response, ">Créer une réception<")
        self.assertContains(response, "scan-listing-intake-form")
        self.assertContains(response, "scan-listing-intake-receipt-select")
        self.assertNotContains(response, 'id="scan-receive-listing-pdf-card"')
        self.assertNotContains(response, 'id="scan-receive-listing-excel-card"')
        self.assertNotContains(response, 'id="scan-receive-listing-csv-card"')
        self.assertNotContains(response, 'id="scan-receive-listing-receipt-draft-card"')
        self.assertNotContains(response, 'id="scan-receive-listing-incomplete-products-card"')

        pending_session = self.client.session
        linked_receipt = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.warehouse,
            received_on=date(2026, 1, 10),
            pallet_count=2,
            source_contact=self.correspondent,
            carrier_contact=self.correspondent,
        )
        pending_session["pallet_listing_pending"] = {
            "token": "tok-analysis",
            "extension": ".pdf",
            "file_path": "/tmp/fake-listing.pdf",
            "entry_file_type": "pdf",
            "file_type": "pdf",
            "receipt_id": linked_receipt.id,
            "pdf_analysis": {
                "total_pages": 2,
                "mode": "mixed",
                "pages": [
                    {
                        "number": 1,
                        "extractable": True,
                        "has_text": True,
                        "has_table": True,
                        "line_count": 2,
                        "column_count": 2,
                        "extraction_strategy": "table",
                        "preview_text": "Nom  Qte | Mask  3",
                    },
                    {
                        "number": 2,
                        "extractable": False,
                        "has_text": False,
                        "has_table": False,
                        "line_count": 0,
                        "column_count": 0,
                        "extraction_strategy": "none",
                        "preview_text": "",
                    },
                ],
                "extractable_pages": [1],
                "recommended_pages": {"mode": "detected", "start": 1, "end": 1, "pages": [1]},
            },
            "pdf_pages": {"mode": "detected", "start": 1, "end": 1, "pages": [1], "total": 2},
        }
        pending_session.save()
        response = self.client.get(reverse("scan:scan_receive_listing"))
        self.assertContains(response, 'id="scan-receive-listing-analysis-card"')
        self.assertContains(response, 'id="scan-receive-listing-pdf-card"')
        self.assertContains(response, "scan-receive-listing-analysis-card")
        self.assertNotContains(response, 'id="scan-receive-listing-excel-card"')
        self.assertNotContains(response, 'id="scan-receive-listing-csv-card"')
        self.assertContains(response, 'name="listing_pdf_pages_mode"')
        self.assertContains(response, 'id="listing_pdf_page_start"')
        self.assertContains(response, 'id="listing_pdf_page_end"')
        self.assertContains(response, "Pages détectées")
        self.assertContains(response, 'value="detected"')
        self.assertContains(response, "Nom  Qte | Mask  3")
        self.assertContains(response, "Méthode")

    def test_scan_receive_listing_hides_incomplete_product_rows_before_confirmed_import(self):
        Product.objects.create(
            name="Produit Incomplet",
            is_incomplete=True,
            qr_code_image="qr_codes/incomplete.png",
        )

        response = self.client.get(reverse("scan:scan_receive_listing"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="scan-receive-listing-incomplete-products-card"')
        self.assertNotContains(response, "Produit Incomplet")
        self.assertNotContains(response, "Ouvrir")

    def test_scan_receive_listing_renders_incomplete_product_rows_after_confirmed_import(self):
        product = Product.objects.create(
            name="Produit Incomplet",
            is_incomplete=True,
            qr_code_image="qr_codes/incomplete-post-import.png",
        )

        session = self.client.session
        session["pallet_listing_last_incomplete_product_ids"] = [product.id]
        session.save()

        response = self.client.get(reverse("scan:scan_receive_listing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-receive-listing-incomplete-products-card"')
        self.assertContains(response, "Produit Incomplet")
        self.assertContains(response, "Ouvrir")

    def test_scan_receive_listing_suggestions_stage_renders_batch_actions_and_counter(self):
        listing_context = {
            "active": "receive_listing",
            "listing_entry_form": ScanListingEntryForm(),
            "listing_stage": "suggestions",
            "listing_columns": [],
            "listing_rows": [
                {
                    "index": 2,
                    "values": {
                        "name": "Braun Thermometre frontal",
                        "brand": "",
                        "ean": "1234567890123",
                        "quantity": "3",
                        "rack_color": "",
                    },
                    "fields": [
                        {"name": "name", "value": "Braun Thermometre frontal", "existing": ""},
                        {"name": "brand", "value": "", "existing": ""},
                        {"name": "ean", "value": "1234567890123", "existing": ""},
                    ],
                    "locations": [],
                    "existing": {"sku": "SKU-42", "name": "Thermomètre Braun"},
                    "match_type": "EAN",
                    "match_options": [
                        {
                            "value": "product:42",
                            "label": "SKU-42 - Thermomètre Braun",
                            "data": {"sku": "SKU-42", "name": "Thermomètre Braun"},
                        }
                    ],
                    "default_match": "product:42",
                    "match_badge": "Match auto EAN",
                    "status_label": "Produit connu",
                    "completion_labels": ["Marque"],
                    "completion_summary": "Marque",
                    "line_suggestions": [],
                }
            ],
            "listing_group_suggestions": [
                {
                    "id": "brand:braun",
                    "field_name": "brand",
                    "field_label": "Marque",
                    "proposed_value": "BRAUN",
                    "confidence": "Forte",
                    "source": "Base + Batch",
                    "preview_rows": [
                        {
                            "row_key": "row-2",
                            "index": 2,
                            "ean": "1234567890123",
                            "name": "Braun Thermometre frontal",
                            "current_value": "-",
                            "proposed_value": "BRAUN",
                            "linked_product": "SKU-42 - Thermomètre Braun",
                        }
                    ],
                }
            ],
            "listing_errors": [],
            "listing_token": "tok-review",
            "listing_suggestions_total_count": 1,
            "listing_meta": {},
            "review_fields": [("name", "Nom"), ("brand", "Marque"), ("ean", "EAN")],
            "location_fields": [],
            "show_rack_color_column": False,
            "listing_sheet_names": [],
            "listing_sheet_name": "",
            "listing_header_row": 1,
            "listing_pdf_pages_mode": "all",
            "listing_pdf_page_start": "",
            "listing_pdf_page_end": "",
            "listing_pdf_total_pages": "",
            "listing_pdf_analysis": None,
            "listing_file_type": "pdf",
            "listing_entry_file_type": "pdf",
            "listing_entry_receipt_id": "",
            "listing_selected_receipt": None,
            "listing_focus_card_id": "scan-receive-listing-suggestions-card",
            "show_incomplete_products_card": False,
        }

        with mock.patch(
            "wms.views_scan_receipts.build_receive_listing_state",
            return_value={"response": None},
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receive_listing_context",
                return_value=listing_context,
            ):
                response = self.client.get(reverse("scan:scan_receive_listing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-receive-listing-suggestions-card"')
        self.assertContains(response, 'id="scan-receive-listing-suggestions-block"')
        self.assertNotContains(response, 'id="scan-receive-listing-review-table-card"')
        self.assertContains(response, "Suggestions détectées")
        self.assertContains(response, "Champ proposé")
        self.assertContains(response, "Indice de correspondance")
        self.assertContains(response, "Voir les lignes")
        self.assertContains(response, "Suggestions cochées :")
        self.assertContains(response, "Braun Thermometre frontal")
        self.assertContains(response, "SKU-42 - Thermomètre Braun")
        self.assertContains(
            response,
            'Les suggestions non traitées restent visibles dans la page "MAJ Stock" et pourront être traitées ultérieurement.',
        )
        self.assertContains(response, "Accepter les propositions sélectionnées", count=1)
        self.assertContains(response, "Refuser les propositions sélectionnées", count=1)
        self.assertNotContains(response, "Valider tous les imports cochés")

        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "scan" / "scan-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(".scan-bootstrap-enabled .scan-listing-step-actions {", css_content)
        self.assertIn("flex-wrap: nowrap;", css_content)
        self.assertIn(".scan-bootstrap-enabled .scan-listing-step-actions > * {", css_content)
        self.assertIn("flex: 1 1 0;", css_content)

    def test_scan_receive_listing_review_stage_renders_compact_review_table(self):
        listing_context = {
            "active": "receive_listing",
            "listing_entry_form": ScanListingEntryForm(),
            "listing_stage": "review",
            "listing_columns": [],
            "listing_rows": [
                {
                    "index": 2,
                    "values": {
                        "name": "Braun Thermometre frontal",
                        "brand": "BRAUN",
                        "ean": "1234567890123",
                        "quantity": "3",
                        "rack_color": "",
                    },
                    "fields": [
                        {
                            "name": "name",
                            "label": "Nom",
                            "value": "Braun Thermometre frontal",
                            "source": "Braun Thermometre frontal",
                            "existing": "",
                        },
                        {
                            "name": "brand",
                            "label": "Marque",
                            "value": "BRAUN",
                            "source": "",
                            "existing": "",
                        },
                        {
                            "name": "ean",
                            "label": "EAN",
                            "value": "1234567890123",
                            "source": "1234567890123",
                            "existing": "",
                        },
                    ],
                    "locations": [],
                    "existing": {"sku": "SKU-42", "name": "Thermomètre Braun"},
                    "match_type": "EAN",
                    "match_options": [
                        {
                            "value": "product:42",
                            "label": "SKU-42 - Thermomètre Braun",
                            "data": {"sku": "SKU-42", "name": "Thermomètre Braun"},
                        }
                    ],
                    "default_match": "product:42",
                    "match_badge": "Match auto EAN",
                    "status_label": "Produit connu",
                    "completion_labels": ["Marque"],
                    "completion_summary": "Marque",
                    "line_suggestions": [],
                }
            ],
            "listing_group_suggestions": [],
            "listing_errors": [],
            "listing_token": "tok-review",
            "listing_suggestions_total_count": 0,
            "listing_meta": {},
            "review_fields": [("name", "Nom"), ("brand", "Marque"), ("ean", "EAN")],
            "location_fields": [],
            "show_rack_color_column": False,
            "listing_sheet_names": [],
            "listing_sheet_name": "",
            "listing_header_row": 1,
            "listing_pdf_pages_mode": "all",
            "listing_pdf_page_start": "",
            "listing_pdf_page_end": "",
            "listing_pdf_total_pages": "",
            "listing_pdf_analysis": None,
            "listing_file_type": "pdf",
            "listing_entry_file_type": "pdf",
            "listing_entry_receipt_id": "",
            "listing_selected_receipt": None,
            "listing_focus_card_id": "scan-receive-pallet-review-card",
            "show_incomplete_products_card": False,
        }

        with mock.patch(
            "wms.views_scan_receipts.build_receive_listing_state",
            return_value={"response": None},
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receive_listing_context",
                return_value=listing_context,
            ):
                response = self.client.get(reverse("scan:scan_receive_listing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-receive-listing-review-table-card"')
        self.assertNotContains(response, 'id="scan-receive-listing-suggestions-card"')
        self.assertContains(response, "Match auto EAN")
        self.assertContains(response, "Champs complétés")
        self.assertContains(response, "Valider tous les imports cochés")
        self.assertContains(response, "Annuler l'import")

    def test_scan_stock_update_exposes_collapsed_stock_card_and_open_incomplete_cockpit(self):
        response = self.client.get(reverse("scan:scan_stock_update"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-stock-update-toggle"')
        self.assertContains(response, 'data-bs-target="#scan-stock-update-collapse"')
        self.assertContains(response, 'id="scan-stock-update-collapse"')
        self.assertContains(response, 'id="scan-stock-update-incomplete-products-card"')
        self.assertContains(response, 'id="scan-stock-update-incomplete-toggle"')
        self.assertContains(response, 'data-bs-target="#scan-stock-update-incomplete-collapse"')
        self.assertContains(response, 'id="scan-stock-update-incomplete-collapse"')
        self.assertContains(response, "Toutes les réceptions")

    def test_scan_stock_update_embeds_single_incomplete_products_title_and_bulk_script(self):
        response = self.client.get(reverse("scan:scan_stock_update"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produits incomplets", count=1)
        self.assertContains(response, "syncBulkValueVisibility")

    def test_scan_stock_update_renders_incomplete_product_suggestions_card(self):
        category = ProductCategory.objects.create(name="Thermomètres")
        for index in range(1, 4):
            Product.objects.create(
                sku=f"BRAUN-UI-{index}",
                name=f"Produit Braun UI {index}",
                brand="BRAUN",
                category=category,
                default_location=self.product.default_location,
                tva=Decimal("0.055"),
                qr_code_image=f"qr_codes/braun-ui-{index}.png",
            )
        for index in range(1, 4):
            Product.objects.create(
                name=f"BRAUN Thermometre UI {index}",
                is_incomplete=True,
                qr_code_image=f"qr_codes/braun-ui-incomplete-{index}.png",
            )

        response = self.client.get(reverse("scan:scan_stock_update"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-stock-update-suggestions-card"')
        self.assertContains(response, "Suggestions détectées")
        self.assertContains(response, "Appliquer aux produits proposés")

    def test_scan_receive_pallet_uses_toggle_button_radio_groups(self):
        session = self.client.session
        session["pallet_listing_pending"] = {
            "token": "tok-toggle",
            "extension": ".pdf",
            "file_path": "/tmp/fake-listing.pdf",
            "entry_file_type": "pdf",
            "file_type": "pdf",
            "pdf_analysis": {
                "total_pages": 3,
                "mode": "mixed",
                "pages": [
                    {
                        "number": 1,
                        "extractable": True,
                        "has_text": True,
                        "has_table": True,
                        "line_count": 2,
                        "column_count": 2,
                        "extraction_strategy": "table",
                        "preview_text": "Nom  Qte",
                    }
                ],
                "extractable_pages": [1, 2],
                "recommended_pages": {"mode": "detected", "start": 1, "end": 2, "pages": [1, 2]},
            },
            "pdf_pages": {"mode": "detected", "start": 1, "end": 2, "pages": [1, 2], "total": 3},
        }
        session.save()
        response = self.client.get(reverse("scan:scan_receive_listing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'class="scan-toggle-btn-group scan-toggle-btn-group--compact"',
            count=1,
        )
        self.assertContains(
            response,
            'class="btn btn-outline-secondary scan-toggle-btn"',
            count=3,
        )
        self.assertContains(response, "btn-check", count=3)

    def test_scan_receive_pallet_breaks_into_named_workflow_sections(self):
        response = self.client.get(reverse("scan:scan_receive_pallet"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-receive-pallet-create-card"')
        self.assertContains(response, "scan-receive-pallet-primary-row")
        self.assertContains(response, "scan-receive-pallet-actions-inline")
        self.assertNotContains(response, 'id="scan-receive-pallet-listing-upload-card"')
        self.assertNotContains(response, 'id="listing_file"')
        self.assertContains(response, reverse("scan:scan_receive_listing"))
        self.assertContains(response, ">Listing<")

    def test_scan_receive_association_page_uses_design_component_classes(self):
        response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-title")
        self.assertContains(response, "ui-comp-form")
        self.assertContains(response, "ui-comp-file-input")

    def test_scan_receive_surfaces_expose_observation_and_conformity_controls(self):
        pallet_response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertEqual(pallet_response.status_code, 200)
        self.assertContains(pallet_response, 'name="observation"')
        self.assertContains(pallet_response, 'name="is_non_conform"')
        self.assertContains(pallet_response, 'class="form-check form-switch mb-0"')
        self.assertContains(pallet_response, ">Non conforme<")

        association_response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(association_response.status_code, 200)
        self.assertContains(association_response, "Observation")
        self.assertContains(association_response, 'name="is_non_conform"')
        self.assertContains(association_response, 'class="form-check form-switch mb-0"')
        self.assertContains(association_response, ">Non conforme<")

    def test_scan_file_upload_surfaces_use_shared_file_input_component(self):
        self.client.force_login(self.superuser)
        shipment = Shipment.objects.create(
            reference="EXP-BOOT-FILE",
            shipper_name="ASF",
            recipient_name="Dest",
            destination_address="1 Rue Test",
            status=ShipmentStatus.DRAFT,
            created_by=self.superuser,
        )

        listing_session = self.client.session
        listing_session["pallet_listing_pending"] = {
            "token": "tok-file-input",
            "entry_file_type": "csv",
            "file_type": "csv",
        }
        listing_session.save()
        receive_listing_response = self.client.get(reverse("scan:scan_receive_listing"))
        self.assertEqual(receive_listing_response.status_code, 200)
        self.assertContains(receive_listing_response, "ui-comp-file-input")

        receive_association_response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(receive_association_response.status_code, 200)
        self.assertContains(receive_association_response, "ui-comp-file-input")

        import_response = self.client.get(reverse("scan:scan_import"))
        self.assertEqual(import_response.status_code, 200)
        self.assertContains(import_response, "ui-comp-file-input", count=6)

        shipment_edit_response = self.client.get(
            reverse("scan:scan_shipment_edit", args=[shipment.id])
        )
        self.assertEqual(shipment_edit_response.status_code, 200)
        self.assertContains(shipment_edit_response, "ui-comp-file-input")

    def test_scan_receive_surfaces_break_into_named_workflow_sections(self):
        receive_response = self.client.get(reverse("scan:scan_receive"))
        self.assertEqual(receive_response.status_code, 200)
        self.assertContains(receive_response, 'id="scan-receive-select-card"')
        self.assertContains(receive_response, 'id="scan-receive-create-card"')
        self.assertContains(receive_response, 'id="scan-receive-empty-card"')
        self.assertContains(receive_response, 'value="select_receipt"')
        self.assertContains(receive_response, 'value="create_receipt"')

        active_receipt = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.warehouse,
            received_on=date(2026, 2, 1),
        )
        active_response = self.client.get(
            reverse("scan:scan_receive"),
            {"receipt": str(active_receipt.id)},
        )
        self.assertEqual(active_response.status_code, 200)
        self.assertContains(active_response, 'id="scan-receive-active-card"')
        self.assertContains(active_response, 'id="scan-receive-add-line-card"')
        self.assertContains(active_response, 'id="scan-receive-lines-card"')

        association_response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(association_response.status_code, 200)
        self.assertContains(association_response, 'id="scan-receive-association-create-card"')
        self.assertContains(association_response, "scan-receive-association-primary-row")
        self.assertContains(association_response, "scan-receive-association-actions-inline")
        self.assertContains(association_response, 'id="association-lines-data"')
        self.assertContains(association_response, 'id="association-lines-errors"')

        association_receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=self.warehouse,
            received_on=date(2026, 2, 2),
        )
        association_active_response = self.client.get(
            reverse("scan:scan_receive_association"),
            {"receipt_id": str(association_receipt.id)},
        )
        self.assertEqual(association_active_response.status_code, 200)
        self.assertContains(
            association_active_response,
            'id="scan-receive-association-allocations-card"',
        )

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

    def test_scan_import_page_breaks_into_named_workflow_sections(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_import"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-imports-intro"')
        self.assertContains(response, 'id="scan-imports-products"')
        self.assertContains(response, 'id="scan-imports-locations"')
        self.assertContains(response, 'id="scan-imports-categories"')
        self.assertContains(response, 'id="scan-imports-warehouses"')
        self.assertContains(response, 'id="scan-imports-contacts"')
        self.assertContains(response, 'id="scan-imports-users"')
        self.assertContains(response, "ui-comp-card", count=7)
        self.assertContains(response, "ui-comp-form")
        self.assertContains(response, "ui-comp-actions")
        self.assertContains(response, 'name="action" value="product_single"')
        self.assertContains(response, 'name="action" value="product_file"')
        self.assertContains(response, 'id="product_file"')
        self.assertContains(response, 'name="stock_mode"')
        self.assertContains(response, 'id="stock_mode_movement"')
        self.assertContains(response, 'id="stock_mode_overwrite"')
        self.assertContains(response, "scan-toggle-btn-group")
        self.assertContains(response, "scan-toggle-btn")
        self.assertContains(response, "btn-check")
        self.assertContains(
            response,
            reverse("scan:scan_import") + "?export=products",
        )
        self.assertContains(response, 'id="scan-import-selector-data"')

    def test_scan_import_pending_review_uses_named_review_section(self):
        self.client.force_login(self.superuser)
        matched_product = Product.objects.create(
            sku="IMPORT-REVIEW-001",
            name="Produit revue import",
            qr_code_image="qr_codes/import_review.png",
        )
        session = self.client.session
        session["product_import_pending"] = {
            "token": "pending-import-review",
            "matches": [
                {
                    "row_index": 2,
                    "match_type": "sku",
                    "match_ids": [matched_product.id],
                    "row_summary": {
                        "sku": "IMPORT-REVIEW-001",
                        "name": "Produit import revue",
                        "brand": "ASF",
                        "quantity": 4,
                        "location": "Main A-01-001",
                    },
                }
            ],
            "default_action": "update",
            "quantity_mode": "movement",
        }
        session.save()

        response = self.client.get(reverse("scan:scan_import"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-imports-product-review"')
        self.assertContains(response, 'name="action" value="product_confirm"')
        self.assertContains(response, 'name="pending_token" value="pending-import-review"')
        self.assertContains(response, 'name="cancel" value="1"')

    def test_scan_remaining_pages_use_design_component_classes(self):
        stock_response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(stock_response.status_code, 200)
        self.assertContains(stock_response, 'class="scan-header ui-comp-panel"')
        self.assertContains(stock_response, 'id="scan-brand-desktop"')
        self.assertContains(stock_response, 'id="scan-brand-mobile"')
        self.assertNotContains(stock_response, "ASF WMS Scan")
        self.assertNotContains(stock_response, "Flux rapides pour mobile et scanner.")
        self.assertContains(
            stock_response,
            'id="scan-sidebar-nav"',
        )
        self.assertContains(stock_response, 'id="scan-utility-nav"')
        self.assertContains(stock_response, 'id="scan-sidebar-dashboard"')
        self.assertContains(stock_response, 'id="scan-sidebar-stocks-toggle"')
        self.assertContains(stock_response, 'data-bs-toggle="dropdown"')
        self.assertContains(stock_response, 'id="scan-masthead-account-toggle"')
        self.assertContains(stock_response, "dropdown-header")
        self.assertNotContains(stock_response, "Essayer interface Next")
        self.assertNotContains(stock_response, 'id="ui-toggle"')
        self.assertNotContains(stock_response, 'id="theme-toggle"')
        self.assertNotContains(stock_response, 'id="ui-reset-default"')
        self.assertNotContains(stock_response, "localStorage.getItem('wms-ui')")
        content = stock_response.content.decode()
        header_start = content.index('<header class="scan-header ui-comp-panel">')
        header_end = content.index("</header>", header_start)
        utility_index = content.index('id="scan-utility-nav"')
        nav_index = content.index('id="scan-sidebar-nav"')
        self.assertGreater(utility_index, header_start)
        self.assertLess(utility_index, header_end)
        self.assertGreater(nav_index, header_end)

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
        self.assertContains(error_response, "Nom de la structure requis.")
        self.assertContains(error_response, "Adresse requise.")

    def test_scan_dashboard_uses_bootstrap_filters(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card card border-0")
        self.assertContains(response, "row g-3")
        self.assertContains(response, "btn btn-primary")
        self.assertContains(response, 'name="kpi_start"')
        self.assertContains(response, 'name="kpi_end"')
        self.assertNotContains(response, 'name="chart_start"')
        self.assertNotContains(response, 'name="chart_end"')
        self.assertNotContains(response, 'name="shipment_status"')
        self.assertNotContains(response, 'name="period"')

    def test_scan_dashboard_renders_cockpit_header_toolbar_and_sections(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-dashboard-page-header"')
        self.assertContains(response, 'id="scan-dashboard-toolbar"')
        self.assertNotContains(response, 'id="scan-dashboard-toolbar-advanced"')
        self.assertContains(response, 'id="scan-dashboard-section-nav"')
        self.assertContains(response, 'id="scan-dashboard-priorities"')
        self.assertContains(response, 'id="scan-dashboard-pilotage"')
        self.assertContains(response, 'id="scan-dashboard-flow"')
        self.assertContains(response, 'id="scan-dashboard-health"')

    def test_scan_dashboard_exposes_cockpit_layout_class_hooks(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-dashboard-page-header")
        self.assertContains(response, "scan-dashboard-toolbar")
        self.assertContains(response, "scan-dashboard-priority-grid")
        self.assertContains(response, "scan-dashboard-pilotage-grid")
        self.assertContains(response, "scan-dashboard-flow-grid")
        self.assertContains(response, "scan-dashboard-health-grid")
        self.assertContains(response, "scan-dashboard-section-nav")

    def test_scan_dashboard_keeps_low_stock_table_inside_stock_flow_section(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        stock_start = content.index('id="scan-dashboard-stock"')
        cartons_start = content.index('id="scan-dashboard-cartons"')
        stock_section = content[stock_start:cartons_start]

        self.assertIn("Top 10 des produits sous le seuil global", stock_section)
        self.assertIn('class="scan-table table table-sm table-hover"', stock_section)

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
        self.assertContains(prepare_kits_response, "scan-prepare-kits-top-panel-full")
        self.assertContains(prepare_kits_response, "scan-prepare-kits-top-inner")
        self.assertContains(prepare_kits_response, "scan-prepare-kits-top-field")
        self.assertContains(prepare_kits_response, "scan-prepare-kits-composition-field")

        pack_response = self.client.get(reverse("scan:scan_pack"))
        self.assertEqual(pack_response.status_code, 200)
        self.assertContains(pack_response, "scan-pack-shipping-row")
        self.assertContains(pack_response, "scan-pack-shipping-actions-inline")
        self.assertContains(pack_response, "scan-pack-shipping-field")

    def test_scan_pack_uses_shipment_select_contract(self):
        destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        Shipment.objects.create(
            reference="260012",
            status=ShipmentStatus.DRAFT,
            shipper_name="ASF",
            recipient_name="Dest",
            destination=destination,
            destination_address="1 Rue Test",
            destination_country="Mauritanie",
            created_by=self.staff_user,
        )

        response = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r'<select[^>]+id="id_shipment_reference"[^>]+name="shipment_reference"',
        )
        self.assertContains(response, "260012 - NKC")
        self.assertContains(response, 'id="id_confirm_defaults"')
        self.assertRegex(
            response.content.decode(),
            r'<input[^>]+id="id_confirm_defaults"[^>]+checked',
        )

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

    def test_scan_receipt_detail_uses_bootstrap_card_shell(self):
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=self.warehouse,
        )

        response = self.client.get(reverse("scan:scan_receipt_detail", args=[receipt.id]))

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
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="scan-sidebar-toggle"')
        self.assertContains(response, "btn btn-tertiary btn-sm scan-sidebar-toggle")
        self.assertContains(response, 'id="scan-faq-link"')
        self.assertContains(response, 'id="scan-masthead-settings-toggle"')
        self.assertContains(response, 'id="scan-masthead-account-toggle"')
        self.assertContains(
            response, "btn btn-tertiary btn-sm dropdown-toggle scan-utility-trigger"
        )
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
        self.assertContains(response, "ui_file_input")
        self.assertContains(response, "ui-comp-file-input")
        self.assertContains(response, 'id="ui-lab-contract-alert"')
        self.assertContains(response, 'id="ui-lab-contract-panel"')
        self.assertContains(response, 'id="ui-lab-contract-toolbar"')
        self.assertContains(response, 'id="ui-lab-contract-actions"')
        self.assertContains(response, 'id="ui-lab-contract-shipment-workflow"')
        self.assertContains(response, 'id="ui-lab-contract-shipment-docs"')
        self.assertContains(response, 'id="ui-lab-contract-shipment-overlay"')
        self.assertContains(
            response,
            'class="form-check form-switch scan-inline-switch scan-inline-switch-wide"',
        )
        self.assertContains(response, "scan-switch-control")
        self.assertContains(response, 'class="ui-comp-status-pill is-ready"')
        self.assertContains(response, "ui-comp-alert")
        self.assertNotContains(response, 'name="action" value="save"')
        self.assertNotContains(response, 'name="action" value="reset"')

        design_response = self.client.get(reverse("scan:scan_admin_design"))

        self.assertEqual(design_response.status_code, 200)
        self.assertContains(design_response, reverse("scan:scan_ui_lab"))

    def test_scan_ui_lab_exposes_shared_select_size_classes(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-toolbar-status"')
        self.assertContains(response, "ui-select--sm")
        self.assertContains(response, "ui-select--lg")

    def test_scan_ui_lab_exposes_shared_number_input_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-contract-number-input"')
        self.assertContains(response, 'id="ui-lab-number-input-contract"')
        self.assertContains(response, 'id="ui-lab-number-input-demo"')
        self.assertContains(response, 'id="ui-lab-number-input-compact-demo"')
        self.assertContains(response, 'data-ui-number-input-demo="1"')
        self.assertContains(response, 'data-ui-number-input-compact-demo="1"')
        self.assertContains(response, "ui-number-input")
        self.assertContains(response, "ui-number-input-controls")
        self.assertContains(response, "ui-number-input-btn")
        self.assertContains(response, "ui-number-input-compact")

    def test_scan_ui_lab_exposes_recommended_toolbar_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-toolbar-demo"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-query"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-status"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-toggle"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-primary-action"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-panel"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-chips"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-table"')
        self.assertContains(response, 'id="ui-lab-toolbar-demo-table-caption"')
        self.assertNotContains(response, 'name="action" value="filter"')

    def test_scan_ui_lab_exposes_recommended_table_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-table-demo"')
        self.assertContains(response, 'id="ui-lab-table-demo-table"')
        self.assertContains(response, 'id="ui-lab-table-demo-caption"')
        self.assertContains(response, 'id="ui-lab-table-demo-action-1"')
        self.assertContains(response, "ui-comp-status-pill")
        self.assertContains(response, "Référence")
        self.assertContains(response, "Association")
        self.assertContains(response, "Destination")
        self.assertContains(response, "Priorité")
        self.assertContains(response, "Action")
        self.assertNotContains(response, 'id="ui-lab-table-demo-select-all"')

    def test_scan_ui_lab_exposes_recommended_empty_state_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-empty-state-demo"')
        self.assertContains(response, 'id="ui-lab-empty-state-demo-title"')
        self.assertContains(response, 'id="ui-lab-empty-state-demo-body"')
        self.assertContains(response, 'id="ui-lab-empty-state-demo-action"')
        self.assertContains(response, "Aucune réception sélectionnée")
        self.assertNotContains(response, 'id="ui-lab-empty-state-demo-error"')
        self.assertNotContains(response, 'name="action" value="retry"')

    def test_scan_ui_lab_exposes_recommended_page_header_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-page-header-demo"')
        self.assertContains(response, 'id="ui-lab-page-header-demo-title"')
        self.assertContains(response, 'id="ui-lab-page-header-demo-body"')
        self.assertContains(response, 'id="ui-lab-page-header-demo-primary-action"')
        self.assertContains(response, "Gestion des expéditions")
        self.assertNotContains(response, 'id="ui-lab-page-header-demo-breadcrumbs"')
        self.assertNotContains(response, 'id="ui-lab-page-header-demo-search"')

    def test_scan_ui_lab_exposes_recommended_document_actions_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-document-actions-demo"')
        self.assertContains(response, 'id="ui-lab-document-actions-demo-title"')
        self.assertContains(response, 'id="ui-lab-document-actions-demo-body"')
        self.assertContains(response, 'id="ui-lab-document-actions-demo-action-1"')
        self.assertContains(response, "Documents d'expédition")
        self.assertNotContains(response, 'id="ui-lab-document-actions-demo-primary-action"')
        self.assertNotContains(response, 'id="ui-lab-document-actions-demo-upload"')

    def test_scan_ui_lab_exposes_recommended_workflow_action_bar_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo"')
        self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo-body"')
        self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo-primary-action"')
        self.assertContains(response, 'id="ui-lab-workflow-action-bar-demo-secondary-action"')
        self.assertContains(response, "Valider l'étape")
        self.assertNotContains(response, 'id="ui-lab-workflow-action-bar-demo-search"')
        self.assertNotContains(response, 'id="ui-lab-workflow-action-bar-demo-document-action"')

    def test_scan_ui_lab_exposes_recommended_global_navigation_demo_contract(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-demo-global-navigation"')
        self.assertContains(response, 'id="ui-lab-demo-global-navigation-utility"')
        self.assertContains(response, 'id="ui-lab-demo-global-navigation-primary"')
        self.assertContains(response, 'id="ui-lab-demo-global-navigation-menu-toggle"')
        self.assertContains(response, "Navigation globale recommandée")
        self.assertContains(response, "Tableau de bord")
        self.assertContains(response, "Stocks")
        self.assertContains(response, "Réception")
        self.assertContains(response, "Préparation")
        self.assertContains(response, "Expéditions")
        self.assertContains(response, "Gestion")
        self.assertContains(response, "Compte")
        self.assertNotContains(response, 'name="action" value="logout"')

    def test_scan_ui_lab_exposes_governance_tiers_for_stable_and_converging_contracts(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-governance-core"')
        self.assertContains(response, 'id="ui-lab-governance-convergence"')
        self.assertContains(response, "Core stable")
        self.assertContains(response, "En convergence")
        self.assertContains(response, "ui-comp-card")
        self.assertContains(response, "ui-comp-panel")
        self.assertContains(response, "ui-comp-actions")
        self.assertContains(response, "ui_button")
        self.assertContains(response, "ui_field")
        self.assertContains(response, "ui_alert")
        self.assertContains(response, "ui_status_badge")
        self.assertContains(response, "ui_switch")

    def test_scan_ui_lab_exposes_core_stable_usage_rules_block(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_ui_lab"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ui-lab-core-stable-rules"')
        self.assertContains(response, "Règles d'usage du Core stable")
        self.assertContains(response, "ui_button")
        self.assertContains(response, "ui-comp-actions")
        self.assertContains(response, "Un seul primary par zone d'action")
