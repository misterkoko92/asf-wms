from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.forms_admin_contacts_contact import ContactCrudForm
from wms.models import (
    Destination,
    DocumentReviewStatus,
    DocumentScanStatus,
    Product,
    ProductKitItem,
    RecipientStructureDocument,
    RecipientStructureDocumentType,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    WmsRuntimeSettings,
)


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
        self.correspondent = Contact.objects.create(
            name="Correspondant Test",
            email="corr@example.com",
            is_active=True,
        )
        self.orphan_correspondent = Contact.objects.create(
            name="Correspondant Orphelin",
            email="orphan@example.com",
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
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

    def _design_form_payload(self):
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
            "design_color_btn_tertiary_bg": "#f8fcfa",
            "design_color_btn_tertiary_text": "#22322e",
            "design_color_btn_tertiary_border": "#bfd3ca",
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
        return payload

    def test_scan_admin_views_redirect_anonymous_to_admin_login(self):
        for route_name in (
            "scan:scan_admin_contacts",
            "scan:scan_admin_products",
            "scan:scan_admin_design",
            "scan:scan_product_labels",
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
            "scan:scan_product_labels",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 403)

    def test_scan_admin_contacts_renders_admin_management_links(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_admin_contacts"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "admin_contacts")
        self.assertContains(response, "ui-comp-panel")
        self.assertContains(response, 'name="destination_id"')
        self.assertContains(response, reverse("admin:contacts_contact_changelist"))
        self.assertContains(response, reverse("admin:contacts_contact_add"))
        self.assertContains(response, reverse("admin:wms_destination_changelist"))
        self.assertContains(response, self.correspondent.name)
        self.assertContains(response, self.destination.city)
        correspondents = list(response.context["correspondents"])
        self.assertEqual(correspondents, [self.correspondent])
        self.assertNotIn(self.orphan_correspondent, correspondents)

    def test_scan_admin_contacts_tables_use_collapse_and_table_tools(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-admin-table-accordion")
        self.assertContains(response, 'data-table-tools="1"', count=6)
        self.assertNotContains(response, 'scan-admin-table-accordion" open')

    def test_scan_admin_contacts_renders_creation_cards_before_filters(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        destination_index = html.index("Création de destination")
        contact_index = html.index("Création de contact")
        filters_index = html.index("Recherche et filtres")
        self.assertLess(destination_index, filters_index)
        self.assertLess(contact_index, filters_index)
        self.assertContains(response, 'id="scan-admin-create-destination"')
        self.assertContains(response, 'id="scan-admin-create-contact"')
        self.assertNotContains(response, 'id="scan-admin-create-destination" open')
        self.assertNotContains(response, 'id="scan-admin-create-contact" open')
        self.assertContains(response, 'data-required-marker="entity_type"')

    def test_contact_crud_form_uses_country_choices(self):
        form = ContactCrudForm()

        country_field = form.fields["country"]

        self.assertIsInstance(country_field, forms.ChoiceField)
        choice_values = {value for value, _label in country_field.choices}
        self.assertIn("France", choice_values)
        self.assertIn("Bénin", choice_values)
        self.assertIn("Togo", choice_values)
        self.assertIn("Canada", choice_values)

    def test_scan_admin_contacts_renders_country_as_select(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode("utf-8"),
            r'<select[^>]+(?:id="id_country"[^>]+name="country"|name="country"[^>]+id="id_country")',
        )

    def test_scan_admin_contacts_edit_shows_structure_compliance_fields_and_documents(self):
        self.client.force_login(self.superuser)
        contact = Contact.objects.create(
            name="Hopital Validation",
            contact_type="organization",
            legal_form="association",
            beneficiary_count=240,
            is_active=True,
        )
        RecipientStructureDocument.objects.create(
            contact=contact,
            doc_type=RecipientStructureDocumentType.REGISTRATION_PROOF,
            status=DocumentReviewStatus.PENDING,
            file=SimpleUploadedFile("registration-proof.pdf", b"%PDF-1.4 registration proof"),
            scan_status=DocumentScanStatus.PENDING,
            scan_message="Scan antivirus en cours.",
        )
        clean_document = RecipientStructureDocument.objects.create(
            contact=contact,
            doc_type=RecipientStructureDocumentType.STATUTES,
            status=DocumentReviewStatus.PENDING,
            file=SimpleUploadedFile("statutes.pdf", b"%PDF-1.4 statutes"),
            scan_status=DocumentScanStatus.CLEAN,
        )

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {"edit": str(contact.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["contact_form"].initial["legal_form"], "association")
        self.assertEqual(response.context["contact_form"].initial["beneficiary_count"], 240)
        self.assertContains(response, 'name="legal_form"')
        self.assertContains(response, 'name="beneficiary_count"')
        self.assertContains(response, "Documents de structure")
        self.assertContains(response, "Preuve d&#x27;enregistrement")
        self.assertContains(response, "Statut")
        self.assertContains(response, "Quarantaine (scan antivirus en cours).")
        self.assertContains(response, clean_document.file.name)

    def test_scan_admin_contacts_lists_pending_recipient_validations_with_verify_action(self):
        self.client.force_login(self.superuser)
        pending_contact = Contact.objects.create(
            name="Destinataire en attente",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        validated_contact = Contact.objects.create(
            name="Destinataire validé",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_contact = Contact.objects.create(
            name="Expéditeur autorisé",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_referent = Contact.objects.create(
            name="Referent Expéditeur",
            contact_type=ContactType.PERSON,
            first_name="Referent",
            last_name="Expéditeur",
            organization=shipper_contact,
            is_active=True,
        )
        pending_recipient = ShipmentRecipientOrganization.objects.create(
            organization=pending_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=validated_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_contact,
            default_contact=shipper_referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=pending_recipient,
            is_active=True,
        )

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        pending_validations = response.context["pending_recipient_validations"]
        self.assertEqual(
            [item["organization"] for item in pending_validations],
            [pending_contact],
        )
        self.assertContains(response, "Destinataires en attente de validation")
        self.assertContains(response, "<th>Type métier</th>", html=True)
        self.assertContains(response, pending_contact.name)
        self.assertContains(response, "Destinataire")
        self.assertContains(response, self.destination.city)
        self.assertContains(response, shipper_contact.name)
        self.assertContains(
            response,
            f'href="{reverse("scan:scan_admin_contacts")}?edit={pending_contact.id}"',
        )
        self.assertContains(response, "Vérifier")
        self.assertNotContains(response, "Pour lever cette alerte")

    def test_scan_admin_contacts_pending_recipient_edit_uses_validate_label(self):
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

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {"edit": str(pending_contact.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valider le destinataire")
        self.assertNotContains(response, "Mettre à jour le contact")

    def test_scan_admin_contacts_validated_recipient_edit_keeps_update_label(self):
        self.client.force_login(self.superuser)
        validated_contact = Contact.objects.create(
            name="Destinataire validé",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=validated_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {"edit": str(validated_contact.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mettre à jour le contact")
        self.assertNotContains(response, "Valider le destinataire")

    def test_scan_admin_contacts_directory_exposes_inline_actions(self):
        self.client.force_login(self.superuser)
        contact = Contact.objects.create(
            name="Structure Actionnable",
            contact_type="organization",
            is_active=True,
        )

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, contact.name)
        self.assertContains(response, "<th>Actions</th>", html=True)
        self.assertContains(
            response,
            f'id="scan-admin-contact-action-{contact.id}"',
        )
        self.assertContains(response, "scan-admin-contact-action-select")
        self.assertContains(response, "Voir les choix")
        self.assertContains(response, "Modifier")
        self.assertContains(response, "Désactiver")
        self.assertContains(response, "Fusionner")
        self.assertNotContains(response, "Tous les contacts (admin)")
        self.assertNotContains(response, "Ajouter un contact (admin)")
        self.assertNotContains(response, "Destinations (admin)")
        self.assertNotContains(response, "Ajouter destination (admin)")

    def test_scan_settings_menu_holds_admin_tools_while_management_keeps_workflow_links(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_import"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        management_start = html.index('id="scan-sidebar-management-toggle"')
        management_end = html.index("</nav>", management_start)
        management_html = html[management_start:management_end]
        admin_start = html.index('id="scan-masthead-settings-toggle"')
        admin_end = html.index("</nav>", admin_start)
        admin_html = html[admin_start:admin_end]

        self.assertIn(reverse("planning:run_list"), management_html)
        self.assertIn(reverse("scan:scan_billing_editor"), management_html)
        self.assertNotIn(reverse("scan:scan_import"), management_html)
        self.assertNotIn(reverse("scan:scan_admin_contacts"), management_html)
        self.assertIn(reverse("scan:scan_import"), admin_html)
        self.assertIn(reverse("scan:scan_admin_contacts"), admin_html)
        self.assertIn(reverse("scan:scan_product_labels"), admin_html)
        self.assertIn(reverse("scan:scan_out"), admin_html)
        self.assertIn(reverse("scan:scan_billing_settings"), admin_html)
        self.assertIn(reverse("scan:scan_billing_equivalence"), admin_html)

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

    def test_scan_admin_contacts_never_renders_legacy_contact_crud_actions(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="action" value="create_contact"')
        self.assertNotContains(response, 'name="action" value="update_contact"')
        self.assertNotContains(response, 'name="action" value="delete_contact"')
        self.assertNotContains(response, "Mode legacy désactivé")
        self.assertContains(response, reverse("admin:contacts_contact_changelist"))
        self.assertContains(response, reverse("admin:contacts_contact_add"))
        self.assertContains(response, reverse("admin:wms_destination_changelist"))
        self.assertContains(response, reverse("admin:wms_destination_add"))

    def test_scan_admin_contacts_rejects_removed_legacy_create_contact_action(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "create_contact",
                "q": "",
                "contact_type": "all",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Action de contact non reconnue.")

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

    def test_scan_product_labels_page_renders_management_actions_for_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_product_labels"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "product_labels")
        self.assertContains(response, reverse("scan:scan_product_labels"))
        self.assertContains(response, reverse("scan:scan_product_labels_print_labels"))
        self.assertContains(response, reverse("scan:scan_product_labels_print_qr"))
        self.assertContains(response, "Imprimer etiquettes")
        self.assertContains(response, "Imprimer QR")
        self.assertContains(response, "Imprimer les deux")
        self.assertContains(
            response,
            'class="scan-scan-btn btn btn-secondary">Filtrer</button>',
        )
        self.assertContains(
            response,
            'class="scan-scan-btn btn btn-secondary" formaction="'
            + reverse("scan:scan_product_labels_print_labels")
            + '">Imprimer etiquettes</button>',
        )
        self.assertContains(
            response,
            'class="scan-scan-btn btn btn-secondary" formaction="'
            + reverse("scan:scan_product_labels_print_qr")
            + '">Imprimer QR</button>',
        )
        self.assertContains(
            response,
            'class="scan-scan-btn btn btn-secondary" id="scan-print-both">Imprimer les deux</button>',
        )
        self.assertContains(
            response,
            reverse("scan:scan_print_template_edit", args=["product_label"]),
        )
        self.assertContains(
            response,
            reverse("scan:scan_print_template_edit", args=["product_qr"]),
        )

    def test_scan_product_labels_print_labels_uses_selected_products(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_product_labels_print_labels"),
            {
                "selection_mode": "selection",
                "product_ids": [str(self.kit.id)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "print/product_labels.html")
        self.assertContains(response, self.kit.name)
        self.assertNotContains(response, self.component.name)

    def test_scan_product_labels_print_qr_generates_missing_qr(self):
        self.client.force_login(self.superuser)
        product_without_qr = Product.objects.create(
            sku="SCAN-ADMIN-NO-QR",
            name="Gants sans QR",
            qr_code_image="",
        )
        product_without_qr.qr_code_image = ""
        product_without_qr.save(update_fields=["qr_code_image"])

        response = self.client.post(
            reverse("scan:scan_product_labels_print_qr"),
            {
                "selection_mode": "selection",
                "product_ids": [str(product_without_qr.id)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "print/product_qr_labels.html")
        product_without_qr.refresh_from_db()
        self.assertTrue(bool(product_without_qr.qr_code_image))

    def test_scan_product_labels_print_labels_supports_all_filtered_mode(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_product_labels_print_labels"),
            {
                "selection_mode": "all_filtered",
                "q": "Kit",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "print/product_labels.html")
        self.assertContains(response, self.kit.name)
        self.assertNotContains(response, self.component.name)

    def test_scan_product_labels_print_labels_selection_mode_requires_products(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_product_labels_print_labels"),
            {"selection_mode": "selection", "q": "Kit"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(
            response,
            reverse("scan:scan_product_labels") + "?q=Kit",
        )
        message_texts = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn("Aucun produit sélectionné.", message_texts)

    def test_scan_admin_design_renders_direct_design_form_only(self):
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
        self.assertContains(response, "design_color_btn_tertiary_bg")
        self.assertContains(response, "design_color_btn_tertiary_text")
        self.assertContains(response, "design_color_btn_tertiary_border")
        self.assertContains(response, 'id="design-family-foundations"')
        self.assertContains(response, 'id="design-family-buttons"')
        self.assertContains(response, "scan-design-accordion")
        self.assertContains(response, 'data-design-live-preview="1"')
        self.assertContains(response, "Action tertiaire")
        self.assertContains(response, '<select name="design_font_h1"')
        self.assertContains(response, '<option value="DM Sans"')
        self.assertNotContains(response, '<select name="style_preset"')
        self.assertNotContains(response, 'name="style_custom_name"')
        self.assertNotContains(response, '<option value="wms-default"')
        self.assertNotContains(response, '<option value="wms-rect"')
        self.assertNotContains(response, '<option value="wms-contrast"')
        self.assertNotContains(response, '<option value="wms-stream"')
        self.assertNotContains(response, 'value="apply_preset"')
        self.assertNotContains(response, 'value="save_custom_preset"')

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
        self.assertIn(".scan-bootstrap-enabled .btn:not(.btn-sm):not(.btn-lg) {", css_content)
        self.assertIn("display: inline-flex;", css_content)
        self.assertIn("align-items: center;", css_content)
        self.assertNotIn(
            ".scan-bootstrap-enabled .scan-nav.scan-nav-bootstrap .navbar-toggler {\n  border: 1px solid var(--scan-boot-border-strong) !important;",
            css_content,
        )
        self.assertNotIn(
            ".scan-bootstrap-enabled .scan-card.card {\n  border: var(--wms-card-border-width) solid var(--wms-card-border-color) !important;",
            css_content,
        )

    def test_scan_admin_design_post_updates_runtime_design_values(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("scan:scan_admin_design"),
            self._design_form_payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_admin_design"))

        runtime = WmsRuntimeSettings.get_solo()
        self.assertEqual(runtime.design_color_primary, "#3a7f6f")
        self.assertEqual(runtime.design_color_secondary, "#f0caa9")
        self.assertEqual(runtime.design_font_h1, "Manrope")
        self.assertEqual(runtime.design_font_h2, "Manrope")
        self.assertEqual(runtime.design_font_h3, "DM Sans")
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
        self.assertEqual(runtime.design_tokens["color_btn_tertiary_bg"], "#f8fcfa")
        self.assertEqual(runtime.design_tokens["color_btn_tertiary_text"], "#22322e")
        self.assertEqual(runtime.design_tokens["color_btn_tertiary_border"], "#bfd3ca")
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
        self.assertContains(dashboard_response, "--wms-color-btn-tertiary-bg: #f8fcfa;")
        self.assertContains(dashboard_response, "--wms-color-btn-tertiary-border: #bfd3ca;")
        self.assertContains(dashboard_response, "--wms-color-btn-success-hover-bg: #cfe9d8;")
        self.assertContains(dashboard_response, "--wms-color-btn-danger-active-bg: #e8c8c4;")

    def test_scan_admin_design_applies_bootstrap_assets_on_scan_portal_home_and_admin(self):
        self.client.force_login(self.superuser)

        enable_response = self.client.post(
            reverse("scan:scan_admin_design"),
            self._design_form_payload(),
        )
        self.assertEqual(enable_response.status_code, 302)
        self.assertEqual(enable_response.url, reverse("scan:scan_admin_design"))

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
