import re
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    BillingDocument,
    BillingDocumentKind,
    BillingDocumentLine,
    CartonFormat,
    Destination,
    DocumentReviewStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderReviewStatus,
    OrderStatus,
    PortalAccessGrant,
    PortalAccessRole,
    Product,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceSource,
    RecipientProductPreferenceStatus,
    Shipment,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentStatus,
    ShipmentValidationStatus,
)
from wms.portal_access import ACTIVE_PORTAL_SCOPE_SESSION_KEY, PORTAL_SCOPE_SOURCE_GRANT
from wms.portal_recipient_sync import sync_association_recipient_to_contact
from wms.shipment_party_setup import ensure_shipment_recipient_link, ensure_shipment_shipper


class PortalBootstrapUiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portal-bootstrap-user",
            password="pass1234",
            email="portal-bootstrap@example.com",
        )
        association_contact = Contact.objects.create(
            name="Association Bootstrap",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="association-bootstrap@example.com",
        )
        ContactAddress.objects.create(
            contact=association_contact,
            address_line1="1 Rue Test",
            city="Paris",
            postal_code="75001",
            country="France",
            is_default=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=association_contact,
            must_change_password=False,
        )
        correspondent = Contact.objects.create(
            name="Correspondant Bootstrap",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PBS",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        recipient = AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=destination,
            name="Destinataire Bootstrap",
            structure_name="Structure Bootstrap",
            address_line1="2 Rue Livraison",
            city="Paris",
            country="France",
            is_delivery_contact=True,
            is_active=True,
        )
        sync_association_recipient_to_contact(recipient)
        recipient_organization = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=destination,
        )
        recipient_organization.validation_status = ShipmentValidationStatus.VALIDATED
        recipient_organization.save(update_fields=["validation_status"])
        shipper = ensure_shipment_shipper(
            association_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        ensure_shipment_recipient_link(
            shipper=shipper,
            recipient_organization=recipient_organization,
        )
        AssociationPortalContact.objects.create(
            profile=self.profile,
            position=0,
            title="mr",
            first_name="Admin",
            last_name="BOOTSTRAP",
            email="admin-bootstrap@example.com",
            phone="+33100000001",
            emails="admin-bootstrap@example.com",
            phones="+33100000001",
            address_line1="1 Rue Test",
            city="Paris",
            country="France",
            is_administrative=True,
        )
        AssociationPortalContact.objects.create(
            profile=self.profile,
            position=1,
            title="mrs",
            first_name="Prep",
            last_name="BOOTSTRAP",
            email="prep-bootstrap@example.com",
            phone="+33100000002",
            emails="prep-bootstrap@example.com",
            phones="+33100000002",
            address_line1="1 Rue Test",
            city="Paris",
            country="France",
            is_shipping=True,
        )
        Product.objects.create(
            sku="PORTAL-BOOTSTRAP-PREF-001",
            name="Produit Bootstrap",
            brand="ASF",
            qr_code_image="qr_codes/portal_bootstrap_pref_001.png",
        )
        self.order = Order.objects.create(
            association_contact=association_contact,
            shipper_name="ASF",
            recipient_name="Destinataire Bootstrap",
            destination_address="2 Rue Livraison\n75001 Paris\nFrance",
            destination_country="France",
        )
        self.client.force_login(self.user)

    def _activate_recipient_scope(self):
        recipient = AssociationRecipient.objects.get(structure_name="Structure Bootstrap")
        sync_association_recipient_to_contact(recipient)
        recipient_organization = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=recipient.destination,
        )
        recipient_user = get_user_model().objects.create_user(
            username="portal-bootstrap-scope-recipient",
            password="pass1234",  # pragma: allowlist secret
            email="portal-bootstrap-scope-recipient@example.com",
        )
        grant = PortalAccessGrant.objects.create(
            user=recipient_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_organization,
        )
        self.client.force_login(recipient_user)
        session = self.client.session
        session[ACTIVE_PORTAL_SCOPE_SESSION_KEY] = {
            "source": PORTAL_SCOPE_SOURCE_GRANT,
            "grant_id": grant.id,
        }
        session.save()
        return recipient_organization

    def test_portal_base_includes_bootstrap_assets_when_enabled(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
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
        self.assertContains(response, "scan-bootstrap.css")
        self.assertContains(response, "scan/modules/core.js")
        self.assertContains(response, "scan/modules/table-tools.js")
        self.assertContains(response, "portal-bootstrap.css")
        self.assertContains(response, "portal-bootstrap-enabled")
        self.assertContains(response, "portal_onboarding.js")
        self.assertNotContains(response, 'id="portal-ui-toggle"')
        self.assertNotContains(response, 'id="portal-ui-reset-default"')
        self.assertNotContains(response, "localStorage.getItem('wms-ui')")

    def test_portal_dashboard_uses_bootstrap_table_layout(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, 'data-table-tools="1"')
        self.assertContains(response, "btn btn-tertiary btn-sm")

    def test_portal_dashboard_renders_kpi_cards(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commandes en attente")
        self.assertContains(response, "Corrections demandées")
        self.assertContains(response, "Expéditions en cours")

    def test_portal_dashboard_renders_next_step_guidance_per_order(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Étape suivante")
        self.assertContains(response, "Attendre la validation ASF")

    def test_portal_pages_apply_status_badge_levels(self):
        shipment = Shipment.objects.create(
            shipper_name="ASF",
            recipient_name="Destinataire Bootstrap",
            destination_address="2 Rue Livraison\n75001 Paris\nFrance",
            destination_country="France",
            status=ShipmentStatus.SHIPPED,
        )
        self.order.shipment = shipment
        self.order.status = OrderStatus.READY
        self.order.review_status = OrderReviewStatus.CHANGES_REQUESTED
        self.order.save(update_fields=["shipment", "status", "review_status"])
        OrderDocument.objects.create(
            order=self.order,
            doc_type=OrderDocumentType.OTHER,
            status=DocumentReviewStatus.REJECTED,
            file=SimpleUploadedFile("portal-order-rejected.pdf", b"pdf-content"),
            uploaded_by=self.user,
        )

        dashboard_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "portal-badge is-ready")

        detail_response = self.client.get(
            reverse("portal:portal_order_detail", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "portal-badge is-ready")
        self.assertContains(detail_response, "portal-badge is-info")
        self.assertContains(detail_response, "portal-badge is-warning")
        self.assertContains(detail_response, "portal-badge is-error")

    def test_portal_order_create_uses_bootstrap_form_controls(self):
        response = self.client.get(reverse("portal:portal_order_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "btn btn-primary")

    def test_portal_order_create_keeps_destination_optgroups_and_shared_select_classes(self):
        correspondent = Contact.objects.create(
            name="Correspondant Optgroup",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        response = self.client.get(reverse("portal:portal_order_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Autres destinations")
        self.assertContains(response, "<optgroup", html=False)
        self.assertContains(response, 'id="destination_id"')
        self.assertContains(response, "ui-select--lg")
        self.assertContains(response, "ui-select--sm")

    def test_portal_order_create_breaks_into_named_workflow_sections(self):
        response = self.client.get(reverse("portal:portal_order_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-order-create-intro"')
        self.assertContains(response, 'id="portal-order-create-form"')
        self.assertContains(response, 'id="portal-order-create-routing-step"')
        self.assertContains(response, 'id="portal-order-create-source-step"')
        self.assertContains(response, 'id="portal-order-create-fulfillment-step"')
        self.assertContains(response, 'id="portal-order-create-review-step"')
        self.assertContains(response, 'id="portal-order-create-routing-card"')
        self.assertContains(response, 'id="portal-order-create-shipper-inbound-card"')
        self.assertContains(response, 'id="portal-order-create-ready-cartons-card"')
        self.assertContains(response, 'id="portal-order-create-ready-kits-card"')
        self.assertContains(response, 'id="portal-order-create-unit-products-card"')
        self.assertContains(response, 'id="portal-order-create-review-card"')
        self.assertContains(response, 'id="portal-order-create-submit"')
        self.assertContains(response, 'id="portal-category-filters"')
        self.assertContains(response, 'id="portal-stock-completion-control"')
        self.assertContains(response, 'id="wants_stock_completion"')
        self.assertContains(response, 'id="portal-stock-selection-fields"')
        self.assertContains(response, 'data-stock-selection-panel="1"')
        self.assertContains(response, 'id="portal-recipient-options-data"')
        self.assertContains(response, 'id="portal-product-data"')
        self.assertNotContains(response, "(association)")
        self.assertNotContains(response, '"id": "self"')
        self.assertContains(response, "Je prépare mes propres colis")
        self.assertContains(response, "Vos colis doivent respecter les dimensions ASF")
        self.assertContains(
            response, "Je souhaite compléter mes colis avec des produits du stock ASF"
        )
        self.assertContains(response, "Je certifie que les colis respectent les consignes d'ASF")
        self.assertContains(response, "Type d'expédition")
        self.assertContains(response, "Stock ASF")
        self.assertNotContains(response, "La structure prépare ses propres colis")
        self.assertNotContains(response, "Flux structure")
        self.assertContains(response, "Colis disponibles")
        self.assertContains(response, "Kits disponibles")
        self.assertContains(response, "Produits à l'unité")
        self.assertContains(response, 'id="ready-carton-estimate-total"')

    def test_portal_order_create_hides_late_steps_until_route_is_selected(self):
        response = self.client.get(reverse("portal:portal_order_create"))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r'id="portal-order-create-fulfillment-step"[^>]*data-portal-order-step-hidden="1"',
        )
        self.assertRegex(
            response.content.decode(),
            r'id="portal-order-create-review-step"[^>]*data-portal-order-step-hidden="1"',
        )

    def test_portal_order_create_collapses_shipper_inbound_sections_by_default(self):
        response = self.client.get(reverse("portal:portal_order_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-order-create-shipper-inbound-collapse"')
        self.assertContains(response, 'id="portal-order-create-pickup-collapse"')
        self.assertContains(
            response,
            'id="portal-order-create-shipper-inbound-collapse" class="collapse"',
            html=False,
        )
        self.assertContains(
            response,
            'id="portal-order-create-pickup-collapse" class="collapse"',
            html=False,
        )
        self.assertNotContains(
            response,
            'id="portal-order-create-shipper-inbound-collapse" class="collapse show"',
            html=False,
        )
        self.assertNotContains(
            response,
            'id="portal-order-create-pickup-collapse" class="collapse show"',
            html=False,
        )
        self.assertContains(response, 'id="carton-estimate-total"')

    def test_portal_account_uses_bootstrap_forms_and_tables(self):
        response = self.client.get(reverse("portal:portal_account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-account-form"')
        self.assertContains(response, "form-control")
        self.assertContains(response, "form-select")
        self.assertContains(response, "ui-select--md")
        self.assertContains(response, "btn btn-primary")

    def test_portal_account_breaks_into_named_workflow_sections(self):
        response = self.client.get(reverse("portal:portal_account"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-account-intro"')
        self.assertContains(response, 'id="portal-account-profile-card"')
        self.assertContains(response, 'id="portal-account-billing-card"')
        self.assertContains(response, 'id="portal-account-documents-card"')
        self.assertContains(response, 'id="portal-account-form"')
        self.assertContains(response, 'id="portal-contact-row-template"')
        self.assertContains(response, 'id="add-contact-row"')
        self.assertContains(response, 'value="request_billing_preferences"')
        self.assertContains(response, 'value="upload_account_docs"')

    def test_portal_account_uses_asf_default_partner_label(self):
        response = self.client.get(reverse("portal:portal_account"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compte association")
        self.assertContains(
            response,
            '<label class="form-label" for="id_association_name">Association</label>',
            html=True,
        )
        self.assertNotContains(response, "Compte partenaire")

    def test_portal_base_navigation_includes_billing_link(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("portal:portal_billing"))

    def test_portal_shell_uses_asf_default_partner_label(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portail association")
        self.assertNotContains(response, "Portail partenaire")

    def test_portal_partner_label_uses_runtime_vocabulary_config(self):
        installation = SimpleNamespace(
            vocabulary=SimpleNamespace(portal_partner_label="organisation")
        )

        with mock.patch(
            "wms.templatetags.wms_vocabulary.get_installation_config",
            return_value=installation,
        ):
            dashboard_response = self.client.get(reverse("portal:portal_dashboard"))
            account_response = self.client.get(reverse("portal:portal_account"))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(account_response.status_code, 200)
        self.assertContains(dashboard_response, "Portail organisation")
        self.assertContains(account_response, "Compte organisation")
        self.assertContains(
            account_response,
            '<label class="form-label" for="id_association_name">Organisation</label>',
            html=True,
        )

    def test_portal_shell_separates_primary_navigation_from_utility_and_cta(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-masthead"')
        self.assertContains(response, 'id="portal-masthead-utility"')
        self.assertContains(response, 'id="portal-primary-nav"')
        self.assertContains(response, 'id="portal-order-create-cta"')
        self.assertContains(response, 'id="portal-account-link"')
        self.assertContains(response, 'id="portal-logout-link"')
        self.assertNotContains(response, 'name="language"')
        template_content = (
            Path(settings.BASE_DIR) / "templates" / "portal" / "base.html"
        ).read_text(encoding="utf-8")
        self.assertIn("includes/secondary_shell_masthead.html", template_content)
        self.assertIn("includes/secondary_shell_offcanvas.html", template_content)

        content = response.content.decode()
        nav_match = re.search(
            r'<nav[^>]*id="portal-primary-nav"[^>]*>(.*?)</nav>',
            content,
            re.S,
        )
        self.assertIsNotNone(nav_match)
        nav_content = nav_match.group(1)
        self.assertIn(reverse("portal:portal_dashboard"), nav_content)
        self.assertIn(reverse("portal:portal_billing"), nav_content)
        self.assertIn(reverse("portal:portal_recipients"), nav_content)
        self.assertIn(reverse("portal:portal_account"), nav_content)
        self.assertNotIn(reverse("portal:portal_order_create"), nav_content)
        self.assertNotIn(reverse("portal:portal_logout"), nav_content)

    def test_portal_shell_places_order_create_cta_before_primary_navigation(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        masthead_bottom_match = re.search(
            r'<div class="portal-masthead-bottom d-none d-lg-flex">(.*?)</div>',
            content,
            re.S,
        )
        self.assertIsNotNone(masthead_bottom_match)
        masthead_bottom = masthead_bottom_match.group(1)
        self.assertLess(
            masthead_bottom.index('id="portal-order-create-cta"'),
            masthead_bottom.index('id="portal-primary-nav"'),
        )

    def test_portal_shell_exposes_history_navigation_buttons(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-history-back"')
        self.assertContains(response, 'id="portal-history-forward"')
        self.assertContains(response, "window.history.back()")
        self.assertContains(response, "window.history.forward()")

    def test_portal_shell_exposes_faq_link_for_shipper_scope(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-faq-link"')
        self.assertContains(response, reverse("portal:portal_faq"))
        self.assertContains(response, "FAQ")

    def test_portal_shell_exposes_onboarding_wizard_for_shipper_scope(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-onboarding-wizard"')
        self.assertContains(response, "Portail ASF")
        self.assertContains(response, 'data-portal-onboarding-auto-open="1"')
        self.assertContains(response, 'data-portal-onboarding-preference-url="')
        self.assertContains(response, reverse("portal:portal_onboarding_preference"))
        self.assertContains(response, "Tutoriel expéditeur")
        self.assertContains(response, "Créer un destinataire")
        self.assertContains(response, "Créer une demande d&#x27;expédition / transport")
        self.assertContains(response, "Continuer à me le montrer à la prochaine connexion")

    @override_settings(ORG_BRAND_NAME="ClientOrg")
    def test_portal_onboarding_uses_configured_short_brand_name_in_shell_eyebrow(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-onboarding-wizard"')
        self.assertContains(response, "Portail ClientOrg")
        self.assertNotContains(response, "Portail WHITELABEL_PROBE_BRAND")

    def test_portal_shell_exposes_onboarding_tutorial_link_with_faq_fallback(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-tutorial-link"')
        self.assertContains(response, 'data-portal-onboarding-open="1"')
        self.assertContains(
            response,
            f'href="{reverse("portal:portal_faq")}"',
            html=False,
        )
        self.assertContains(response, "Tutoriel")

    def test_portal_onboarding_wizard_exposes_interaction_controls(self):
        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-onboarding-step-counter"')
        self.assertContains(response, 'id="portal-onboarding-preference-form"')
        self.assertContains(response, 'id="portal-onboarding-show-next"')
        self.assertContains(response, "data-portal-onboarding-prev")
        self.assertContains(response, "data-portal-onboarding-next")
        self.assertContains(response, "data-portal-onboarding-done")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_portal_onboarding_static_assets_define_interactions_and_styles(self):
        js_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal_onboarding.js"
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        js_content = js_path.read_text(encoding="utf-8")
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn("data-portal-onboarding-open", js_content)
        self.assertIn("data-portal-onboarding-next", js_content)
        self.assertIn("show_on_next_login", js_content)
        self.assertIn("fetch(preferenceUrl", js_content)
        self.assertIn(".portal-bootstrap-enabled .portal-onboarding-modal", css_content)
        self.assertIn(".portal-bootstrap-enabled .portal-onboarding-blockers", css_content)
        self.assertIn(".portal-bootstrap-enabled .portal-onboarding-footer", css_content)

    def test_portal_recipient_scope_home_uses_recipient_navigation_contract(self):
        recipient_organization = self._activate_recipient_scope()
        recipient_contact = Contact.objects.create(
            first_name="Mariam",
            last_name="Diop",
            email="mariam.diop@example.com",
            contact_type=ContactType.PERSON,
            organization=recipient_organization.organization,
            is_active=True,
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=recipient_contact,
            is_active=True,
        )

        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portail destinataire")
        self.assertContains(response, 'id="portal-primary-nav"')
        self.assertContains(
            response,
            f'href="{reverse("portal:portal_recipient_profile")}#portal-recipient-profile-contacts"',
            html=False,
        )
        self.assertContains(
            response,
            f'href="{reverse("portal:portal_recipient_profile")}#portal-recipient-profile-documents"',
            html=False,
        )
        self.assertContains(
            response,
            f'href="{reverse("portal:portal_recipient_preferences")}"',
            html=False,
        )
        self.assertNotContains(
            response,
            f'href="{reverse("portal:portal_dashboard")}#portal-recipient-home-contacts"',
            html=False,
        )
        self.assertNotContains(response, reverse("portal:portal_billing"))
        self.assertNotContains(response, reverse("portal:portal_recipients"))
        self.assertNotContains(response, reverse("portal:portal_order_create"))

    def test_portal_recipient_scope_home_uses_bootstrap_cards_and_tables(self):
        recipient_organization = self._activate_recipient_scope()
        recipient_contact = Contact.objects.create(
            first_name="Kadi",
            last_name="Sow",
            email="kadi.sow@example.com",
            phone="+330100200",
            contact_type=ContactType.PERSON,
            organization=recipient_organization.organization,
            is_active=True,
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=recipient_contact,
            is_active=True,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=recipient_organization,
            product=Product.objects.create(name="Kit Recipient Bootstrap"),
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            source=RecipientProductPreferenceSource.PORTAL,
            created_by=self.user,
            updated_by=self.user,
        )

        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-recipient-home-intro"')
        self.assertContains(response, 'id="portal-recipient-home-identity"')
        self.assertContains(response, 'id="portal-recipient-home-contacts"')
        self.assertContains(response, 'id="portal-recipient-home-documents"')
        self.assertContains(response, 'id="portal-recipient-home-preferences"')
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "Référents destinataire")
        self.assertContains(response, "Documents structure")
        self.assertContains(response, "Préférences produits")
        self.assertContains(response, "Kit Recipient Bootstrap")
        self.assertContains(response, reverse("portal:portal_recipient_profile"))
        self.assertContains(response, "Modifier mes informations")
        self.assertContains(response, reverse("portal:portal_recipient_preferences"))
        self.assertContains(response, "Gérer les préférences produits")

    def test_portal_shell_exposes_faq_link_for_recipient_scope(self):
        self._activate_recipient_scope()

        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-faq-link"')
        self.assertContains(response, reverse("portal:portal_faq"))
        self.assertContains(response, "FAQ")

    def test_portal_shell_exposes_onboarding_wizard_for_recipient_scope(self):
        self._activate_recipient_scope()

        response = self.client.get(reverse("portal:portal_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-onboarding-wizard"')
        self.assertContains(response, 'data-portal-onboarding-auto-open="1"')
        self.assertContains(response, "Tutoriel destinataire")
        self.assertContains(response, "Vérifier la fiche structure")
        self.assertContains(response, "Déclarer besoins et refus produits")
        self.assertContains(response, "Documents structure manquants")

    def test_portal_scope_select_does_not_render_onboarding_wizard(self):
        recipient_organization = self._activate_recipient_scope()
        self.client.force_login(self.user)
        PortalAccessGrant.objects.create(
            user=self.user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_organization,
        )

        response = self.client.get(reverse("portal:portal_scope_select"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="portal-onboarding-wizard"')
        self.assertNotContains(response, "Tutoriel expéditeur")
        self.assertNotContains(response, "Tutoriel destinataire")

    def test_portal_recipient_profile_uses_bootstrap_forms_and_document_uploads(self):
        self._activate_recipient_scope()

        response = self.client.get(reverse("portal:portal_recipient_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "portal-page-intro")
        self.assertContains(response, "ui-comp-form")
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(response, 'name="destination_id"')
        self.assertContains(response, 'name="structure_name"')
        self.assertContains(response, 'id="portal-recipient-profile-contacts"')
        self.assertContains(response, "Contact principal")
        self.assertContains(response, 'name="contact_title"')
        self.assertContains(response, 'name="emails"')
        self.assertContains(
            response,
            'class="form-control ui-number-input-compact" type="number" min="0" step="1" id="beneficiary_count"',
        )
        self.assertContains(response, 'name="doc_registration_proof"')
        self.assertContains(response, 'name="doc_statutes"')
        self.assertContains(response, "Modifier mes informations")
        self.assertContains(response, "Documents structure")
        self.assertContains(response, "btn btn-primary")

    def test_portal_billing_pages_use_bootstrap_tables(self):
        billing_document = BillingDocument.objects.create(
            association_profile=self.profile,
            kind=BillingDocumentKind.INVOICE,
            status="issued",
            invoice_number="FAC-2026-777",
            currency="EUR",
        )
        BillingDocumentLine.objects.create(
            document=billing_document,
            line_number=1,
            label="Ligne bootstrap",
            description="Description bootstrap",
            quantity=1,
            unit_price="75.00",
            total_amount="75.00",
        )

        list_response = self.client.get(reverse("portal:portal_billing"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "table table-sm table-hover")
        self.assertContains(list_response, "FAC-2026-777")
        self.assertContains(list_response, "Facture")
        self.assertNotContains(list_response, "Invoice")

        detail_response = self.client.get(
            reverse("portal:portal_billing_detail", args=[billing_document.id])
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "scan-card portal-card card border-0")
        self.assertContains(detail_response, "table table-sm table-hover")
        self.assertContains(detail_response, "btn btn-primary")
        self.assertContains(detail_response, "Type: Facture")

    def test_portal_intro_cards_use_portal_page_intro_spacing_contract(self):
        billing_document = BillingDocument.objects.create(
            association_profile=self.profile,
            kind=BillingDocumentKind.INVOICE,
            status="issued",
            invoice_number="FAC-2026-778",
            currency="EUR",
        )
        BillingDocumentLine.objects.create(
            document=billing_document,
            line_number=1,
            label="Ligne intro",
            quantity=1,
            unit_price="25.00",
            total_amount="25.00",
        )

        dashboard_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "portal-page-intro")

        billing_response = self.client.get(reverse("portal:portal_billing"))
        self.assertEqual(billing_response.status_code, 200)
        self.assertContains(billing_response, "portal-page-intro")

        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(".portal-bootstrap-enabled .portal-page-intro .scan-help {", css_content)
        self.assertIn("margin-bottom: 0;", css_content)

    def test_portal_recipients_uses_bootstrap_forms_and_tables(self):
        response = self.client.get(reverse("portal:portal_recipients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "form-control")
        self.assertContains(response, "form-select")
        self.assertContains(response, "ui-select--lg")
        self.assertContains(response, "ui-select--md")
        self.assertContains(response, "btn btn-primary")

    def test_portal_recipients_uses_bootstrap_switch_controls(self):
        response = self.client.get(reverse("portal:portal_recipients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-check form-switch scan-inline-switch", count=3)

    def test_portal_recipients_renders_structure_compliance_fields(self):
        response = self.client.get(reverse("portal:portal_recipients"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="recipient-structure-row"')
        self.assertContains(response, 'name="legal_form"')
        self.assertContains(response, 'name="beneficiary_count"')
        self.assertContains(
            response,
            'class="form-control ui-number-input-compact" type="number" min="0" step="1" id="beneficiary_count"',
        )
        self.assertContains(response, "Forme juridique")
        self.assertContains(response, "Nombre de bénéficiaires")

    def test_portal_recipients_uses_country_select_and_leading_switch_controls(self):
        response = self.client.get(reverse("portal:portal_recipients"))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r'<select[^>]+id="country"[^>]+name="country"',
        )
        self.assertContains(response, "portal-switch-leading", count=3)

    def test_portal_recipients_page_shows_recipient_status_column(self):
        pending_recipient = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=Destination.objects.get(city="Paris"),
            name="Recipient Pending",
            structure_name="Recipient Pending",
            address_line1="2 Rue Pending",
            city="Paris",
            country="France",
            is_active=True,
        )
        validated_recipient = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=Destination.objects.get(city="Paris"),
            name="Recipient Validated",
            structure_name="Recipient Validated",
            address_line1="3 Rue Validated",
            city="Paris",
            country="France",
            is_active=True,
        )
        sync_association_recipient_to_contact(pending_recipient)
        sync_association_recipient_to_contact(validated_recipient)
        validated_org = ShipmentRecipientOrganization.objects.get(
            organization=validated_recipient.synced_contact,
            destination=validated_recipient.destination,
        )
        validated_org.validation_status = ShipmentValidationStatus.VALIDATED
        validated_org.save(update_fields=["validation_status"])

        response = self.client.get(reverse("portal:portal_recipients"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Statut destinataire")
        self.assertContains(response, "portal-badge is-info")
        self.assertContains(response, "portal-badge is-ready")
        self.assertContains(response, "En attente validation")
        self.assertContains(response, "Validé")

    def test_portal_recipients_keeps_switch_and_action_contract(self):
        response = self.client.get(reverse("portal:portal_recipients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="portal-recipient-contact-fields"')
        self.assertRegex(
            response.content.decode(),
            r'<select[^>]+id="destination_id"[^>]+name="destination_id"[^>]+required',
        )
        self.assertContains(response, 'id="reuse_existing_structure"')
        self.assertContains(response, 'id="notify_deliveries"')
        self.assertContains(response, 'id="is_delivery_contact"')
        self.assertContains(response, 'class="portal-recipient-flags ui-comp-panel"')
        self.assertContains(
            response,
            '<button type="submit" class="scan-submit btn btn-primary">Ajouter</button>',
            html=True,
        )
        self.assertContains(
            response,
            '<a class="btn btn-tertiary btn-sm" href="/portal/recipients/?edit=1">Modifier</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<a class="btn btn-secondary btn-sm" href="/portal/recipients/1/">Ouvrir</a>',
            html=True,
        )

    def test_portal_recipient_detail_uses_bootstrap_cards_and_actions(self):
        response = self.client.get(
            reverse("portal:portal_recipient_detail", kwargs={"recipient_id": 1})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "portal-page-intro")
        self.assertContains(response, "ui-comp-actions")
        self.assertContains(response, "Préférences produits")
        self.assertContains(response, "table table-sm align-middle")
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(
            response,
            'class="form-control recipient-preference-input--quantity ui-number-input-compact"',
        )
        self.assertContains(response, 'id="recipient-preferences-bulk-form"')
        self.assertContains(response, 'data-recipient-preferences-bulk-form="1"')
        self.assertContains(response, 'name="preference_product_ids"')
        self.assertContains(response, 'value="save_recipient_preferences_bulk"')
        self.assertContains(response, "Valider les modifications (0 ligne)")
        self.assertNotContains(response, 'value="save_recipient_preference"')
        self.assertNotContains(response, 'form="recipient-preference-form-')
        self.assertContains(response, 'id="id_preference_q"')
        self.assertContains(response, 'id="id_preference_sort"')
        self.assertContains(response, 'id="recipient-preference-category-l1"')
        self.assertContains(response, 'name="preference_q"')
        self.assertContains(response, 'name="preference_sort"')
        self.assertContains(response, 'id="id_preference_category"')
        self.assertContains(response, 'name="preference_category"')
        self.assertContains(response, "Non précisé")
        self.assertNotContains(response, "Ajouter la préférence")

    def test_portal_recipients_edit_with_recipient_grant_shows_read_only_contract(self):
        recipient = AssociationRecipient.objects.get(structure_name="Structure Bootstrap")
        sync_association_recipient_to_contact(recipient)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=recipient.destination,
        )
        recipient_user = get_user_model().objects.create_user(
            username="portal-bootstrap-recipient",
            password="pass1234",  # pragma: allowlist secret
            email="portal-bootstrap-recipient@example.com",
        )
        PortalAccessGrant.objects.create(
            user=recipient_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=shipment_recipient,
        )

        response = self.client.get(f"{reverse('portal:portal_recipients')}?edit={recipient.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lecture seule")
        self.assertContains(response, 'id="portal-recipient-read-only-banner"')
        self.assertContains(response, 'id="portal-recipient-submit-disabled"')
        self.assertContains(response, 'id="portal-recipient-read-only-fields" disabled')

    def test_portal_recipient_detail_with_recipient_grant_disables_preference_actions(self):
        recipient = AssociationRecipient.objects.get(structure_name="Structure Bootstrap")
        sync_association_recipient_to_contact(recipient)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=recipient.destination,
        )
        recipient_user = get_user_model().objects.create_user(
            username="portal-bootstrap-recipient-detail",
            password="pass1234",  # pragma: allowlist secret
            email="portal-bootstrap-recipient-detail@example.com",
        )
        PortalAccessGrant.objects.create(
            user=recipient_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=shipment_recipient,
        )

        response = self.client.get(
            reverse("portal:portal_recipient_detail", kwargs={"recipient_id": recipient.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lecture seule")
        self.assertContains(response, 'id="portal-recipient-detail-read-only-banner"')
        self.assertNotContains(response, 'value="save_recipient_preference"')

    def test_portal_recipient_preferences_uses_bootstrap_cards_and_actions(self):
        recipient = AssociationRecipient.objects.get(structure_name="Structure Bootstrap")
        sync_association_recipient_to_contact(recipient)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=recipient.destination,
        )
        CartonFormat.objects.create(
            name="Carton standard",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
            is_default=True,
        )
        product = Product.objects.get(name="Produit Bootstrap")
        product.weight_g = 500
        product.volume_cm3 = 1000
        product.save(update_fields=["weight_g", "volume_cm3"])
        RecipientProductPreference.objects.create(
            recipient_organization=shipment_recipient,
            product=Product.objects.create(name="Kit Recipient Preferences Bootstrap"),
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            source=RecipientProductPreferenceSource.PORTAL,
            created_by=self.user,
            updated_by=self.user,
        )
        self._activate_recipient_scope()

        response = self.client.get(reverse("portal:portal_recipient_preferences"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "portal-page-intro")
        self.assertContains(response, "ui-comp-actions")
        self.assertContains(response, "Préférences produits")
        self.assertContains(response, "table table-sm align-middle")
        self.assertContains(response, "recipient-preference-table")
        self.assertContains(response, "recipient-preference-col--estimate")
        self.assertContains(response, "recipient-preference-col--coverage")
        self.assertContains(response, "recipient-preference-col--action")
        self.assertContains(response, "recipient-preference-estimate-heading")
        self.assertContains(response, "recipient-preference-input--status")
        self.assertContains(response, "recipient-preference-input--quantity")
        self.assertContains(response, "recipient-preference-input--period")
        self.assertContains(response, "recipient-preference-input--notes")
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(
            response,
            'class="form-control recipient-preference-input--quantity ui-number-input-compact"',
        )
        self.assertContains(response, 'id="recipient-preferences-bulk-form"')
        self.assertContains(response, 'data-recipient-preferences-bulk-form="1"')
        self.assertContains(response, 'name="preference_product_ids"')
        self.assertContains(response, 'value="save_recipient_preferences_bulk"')
        self.assertContains(response, "Valider les modifications (0 ligne)")
        self.assertNotContains(response, 'value="save_recipient_preference"')
        self.assertNotContains(response, 'form="recipient-preference-form-')
        self.assertContains(response, 'value="delete_recipient_preference"')
        self.assertContains(response, 'id="id_preference_q"')
        self.assertContains(response, 'id="id_preference_sort"')
        self.assertContains(response, 'id="recipient-preference-category-l1"')
        self.assertContains(response, 'name="preference_q"')
        self.assertContains(response, 'name="preference_sort"')
        self.assertContains(response, 'id="id_preference_category"')
        self.assertContains(response, 'name="preference_category"')
        self.assertContains(response, "Kit Recipient Preferences Bootstrap")
        self.assertContains(response, "Qté par colis (estimation)")
        self.assertContains(response, "En cours")
        self.assertNotContains(response, ">Pipeline<", html=False)
        self.assertContains(response, ">16<", html=False)
        self.assertContains(response, ">--<", html=False)

        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(
            ".portal-bootstrap-enabled .recipient-preference-table .recipient-preference-col--action",
            css_content,
        )
        self.assertIn(
            ".portal-bootstrap-enabled .recipient-preference-table .recipient-preference-actions",
            css_content,
        )
        self.assertIn(
            ".portal-bootstrap-enabled .recipient-preferences-bulk-actions",
            css_content,
        )

    def test_portal_recipients_edit_exposes_product_preference_contract(self):
        recipient = AssociationRecipient.objects.get(structure_name="Structure Bootstrap")
        sync_association_recipient_to_contact(recipient)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=recipient.destination,
        )
        product = Product.objects.create(name="Kit Hygiene Bootstrap")
        RecipientProductPreference.objects.create(
            recipient_organization=shipment_recipient,
            product=product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            source=RecipientProductPreferenceSource.PORTAL,
            created_by=self.user,
            updated_by=self.user,
        )

        response = self.client.get(f"{reverse('portal:portal_recipients')}?edit={recipient.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="recipient-product-preferences"')
        self.assertContains(response, 'data-recipient-preference-form="1"')
        self.assertContains(response, 'name="scope_type"')
        self.assertContains(response, 'name="product_id"')
        self.assertContains(response, 'name="category_id"')
        self.assertContains(response, 'name="status"')
        self.assertContains(response, 'name="quantity_target"')
        self.assertContains(
            response,
            'class="form-control ui-number-input-compact" type="number" min="1" step="1" id="pref_quantity_target"',
        )
        self.assertContains(response, 'name="period_unit"')
        self.assertContains(response, "Demandé")
        self.assertContains(response, "Kit Hygiene Bootstrap")

    def test_portal_account_keeps_contact_row_template_and_flags_contract(self):
        response = self.client.get(reverse("portal:portal_account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-contact-row-template"')
        self.assertContains(response, 'name="contact_0_is_administrative"')
        self.assertContains(response, 'name="contact_0_is_shipping"')
        self.assertContains(response, 'name="contact_0_is_billing"')
        self.assertContains(response, 'class="portal-contact-types ui-comp-panel"')
        self.assertContains(
            response,
            '<button type="button" class="scan-scan-btn btn btn-tertiary" id="add-contact-row">Ajouter un autre contact</button>',
            html=True,
        )

    def test_portal_order_detail_uses_bootstrap_tables(self):
        self.order.review_status = OrderReviewStatus.APPROVED
        self.order.save(update_fields=["review_status"])
        response = self.client.get(
            reverse("portal:portal_order_detail", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "btn btn-primary")

    def test_portal_auth_pages_include_bootstrap_assets(self):
        self.client.logout()

        login_response = self.client.get(reverse("portal:portal_login"))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, "family=DM+Sans")
        self.assertContains(login_response, "family=Nunito+Sans")
        self.assertContains(
            login_response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        )
        self.assertContains(login_response, "portal-bootstrap-enabled")
        self.assertContains(login_response, "form-control")
        self.assertContains(login_response, "ui-comp-card")
        self.assertContains(login_response, "ui-comp-title")
        self.assertContains(login_response, "ui-comp-form")
        self.assertContains(login_response, reverse("portal:portal_forgot_password"))
        self.assertContains(login_response, "Mot de passe oubli")
        self.assertContains(login_response, "Première connexion")

        uidb64 = urlsafe_base64_encode(str(self.user.pk).encode())
        set_password_url = reverse(
            "portal:portal_set_password",
            args=[uidb64, default_token_generator.make_token(self.user)],
        )
        set_password_response = self.client.get(set_password_url)
        self.assertEqual(set_password_response.status_code, 200)
        self.assertContains(set_password_response, "family=DM+Sans")
        self.assertContains(set_password_response, "family=Nunito+Sans")
        self.assertContains(set_password_response, "scan-bootstrap.css")
        self.assertContains(set_password_response, "portal-bootstrap.css")
        self.assertContains(set_password_response, "ui-comp-card")
        self.assertContains(set_password_response, "ui-comp-title")
        self.assertContains(set_password_response, "ui-comp-form")

    def test_portal_recovery_pages_include_bootstrap_assets(self):
        self.client.logout()

        forgot_password_response = self.client.get(reverse("portal:portal_forgot_password"))
        self.assertEqual(forgot_password_response.status_code, 200)
        self.assertContains(forgot_password_response, "family=DM+Sans")
        self.assertContains(forgot_password_response, "family=Nunito+Sans")
        self.assertContains(forgot_password_response, "scan-bootstrap.css")
        self.assertContains(forgot_password_response, "portal-bootstrap.css")
        self.assertContains(forgot_password_response, "ui-comp-card")
        self.assertContains(forgot_password_response, "ui-comp-title")
        self.assertContains(forgot_password_response, "ui-comp-form")
        self.assertContains(forgot_password_response, "form-control")
        self.assertContains(forgot_password_response, "btn btn-primary")

    def test_portal_account_request_uses_bootstrap_controls(self):
        self.client.logout()
        response = self.client.get(reverse("portal:portal_account_request"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-bootstrap.css")
        self.assertContains(response, "form-control")
        self.assertContains(response, "btn btn-primary")

    def test_portal_account_request_exposes_shipper_and_recipient_profiles(self):
        self.client.logout()
        response = self.client.get(reverse("portal:portal_account_request"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="account_type"')
        self.assertContains(response, "Expéditeur")
        self.assertContains(response, "Destinataire")
        self.assertNotContains(
            response,
            '<input type="hidden" name="account_type" value="association">',
            html=True,
        )
        self.assertNotContains(response, "Utilisateur WMS")

    def test_portal_account_request_exposes_shipper_stopovers_and_visible_contact_addresses(self):
        self.client.logout()
        correspondent = Contact.objects.create(
            name="Correspondant Stopovers",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        dakar = Destination.objects.create(
            city="Dakar",
            iata_code="DSS",
            country="Sénégal",
            correspondent_contact=correspondent,
            is_active=True,
        )
        paris_belgium = Destination.objects.create(
            city="Paris",
            iata_code="PAB",
            country="Belgique",
            correspondent_contact=correspondent,
            is_active=True,
        )

        response = self.client.get(reverse("portal:portal_account_request"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escales envisagées")
        self.assertContains(response, "Dakar (DSS), Sénégal")
        self.assertContains(response, "Paris (PAB), Belgique")
        self.assertContains(response, "Paris (PBS), France")
        self.assertLess(
            content.index("Dakar (DSS), Sénégal"),
            content.index("Paris (PAB), Belgique"),
        )
        self.assertLess(
            content.index("Paris (PAB), Belgique"),
            content.index("Paris (PBS), France"),
        )
        self.assertContains(response, 'name="shipper_stopover_destination_ids"')
        self.assertContains(response, f'value="{dakar.id}"')
        self.assertContains(response, f'value="{paris_belgium.id}"')
        self.assertContains(response, 'value="other"')
        self.assertContains(response, "Autre escale / escale non listée")
        self.assertContains(
            response,
            '<input class="form-control" type="text" id="admin_contact_address_line1"',
        )
        self.assertContains(
            response,
            '<input class="form-control" type="text" id="preparation_contact_address_line1"',
        )
        self.assertContains(response, 'id="admin_contact_country"')
        self.assertContains(response, 'id="preparation_contact_country"')
        self.assertContains(response, "Premier destinataire (optionnel)")
        self.assertContains(response, "background-color: #fff;")

    def test_portal_pages_use_design_component_classes(self):
        dashboard_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "ui-comp-card")
        self.assertContains(dashboard_response, "ui-comp-title")
        self.assertContains(dashboard_response, "ui-comp-panel")
        self.assertNotContains(dashboard_response, "border-bottom: 1px solid #ddd;")
        self.assertNotContains(dashboard_response, ".portal-table th, .portal-table td")

        order_create_response = self.client.get(reverse("portal:portal_order_create"))
        self.assertEqual(order_create_response.status_code, 200)
        self.assertContains(order_create_response, "ui-comp-card")
        self.assertContains(order_create_response, "ui-comp-title")
        self.assertContains(order_create_response, "ui-comp-form")
        self.assertContains(order_create_response, "ui-comp-actions")

        self.order.review_status = OrderReviewStatus.APPROVED
        self.order.save(update_fields=["review_status"])
        order_detail_response = self.client.get(
            reverse("portal:portal_order_detail", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(order_detail_response.status_code, 200)
        self.assertContains(order_detail_response, "ui-comp-card")
        self.assertContains(order_detail_response, "ui-comp-title")
        self.assertContains(order_detail_response, "ui-comp-form")
        self.assertNotContains(
            order_detail_response, ".portal-tight .portal-card { margin-bottom: 10px; }"
        )

        recipients_response = self.client.get(reverse("portal:portal_recipients"))
        self.assertEqual(recipients_response.status_code, 200)
        self.assertContains(recipients_response, "ui-comp-card")
        self.assertContains(recipients_response, "ui-comp-title")
        self.assertContains(recipients_response, "ui-comp-form")
        self.assertContains(recipients_response, "ui-comp-actions")
        self.assertNotContains(recipients_response, ".portal-recipient-grid-3 {")

        account_response = self.client.get(reverse("portal:portal_account"))
        self.assertEqual(account_response.status_code, 200)
        self.assertContains(account_response, "ui-comp-card")
        self.assertContains(account_response, "ui-comp-title")
        self.assertContains(account_response, "ui-comp-form")
        self.assertContains(account_response, "ui-comp-actions")

        change_password_response = self.client.get(reverse("portal:portal_change_password"))
        self.assertEqual(change_password_response.status_code, 200)
        self.assertContains(change_password_response, "ui-comp-card")
        self.assertContains(change_password_response, "ui-comp-title")
        self.assertContains(change_password_response, "ui-comp-form")

    def test_portal_bootstrap_css_avoids_unnecessary_important_flags(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertNotIn("border: 1px solid var(--border-strong) !important;", css_content)
        self.assertNotIn(
            "border: var(--wms-card-border-width) solid var(--wms-card-border-color) !important;",
            css_content,
        )

    def test_portal_recipient_preference_bulk_actions_stay_visible_in_viewport(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        match = re.search(
            r"\.portal-bootstrap-enabled \.recipient-preferences-bulk-actions \{(?P<body>.*?)\n\}",
            css_content,
            re.S,
        )

        self.assertIsNotNone(match)
        block = match.group("body")
        self.assertIn("position: fixed;", block)
        self.assertIn("left: 50%;", block)
        self.assertIn("transform: translateX(-50%);", block)
        self.assertIn("width: min(calc(100vw - 2rem), var(--wms-container-max-width));", block)

    def test_portal_shell_css_allows_page_scroll_outside_scan_fixed_height_shell(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(".portal-bootstrap-enabled body,", css_content)
        self.assertIn("overflow-y: auto;", css_content)
        self.assertIn(".portal-bootstrap-enabled .scan-shell {", css_content)
        self.assertIn("height: auto;", css_content)

    def test_portal_shell_css_keeps_masthead_row_auto_without_stretching_it(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "portal" / "portal-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")

        self.assertIn(".portal-bootstrap-enabled .portal-shell {", css_content)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr);", css_content)

    def test_portal_button_levels_follow_intended_semantics(self):
        self.client.logout()
        login_response = self.client.get(reverse("portal:portal_login"))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(
            login_response,
            "scan-scan-btn scan-doc-btn btn btn-tertiary",
        )
        self.assertContains(
            login_response,
            reverse("portal:portal_account_request"),
        )
        self.assertContains(
            login_response,
            '<button type="submit" class="scan-submit btn btn-primary">Se connecter</button>',
            html=True,
        )

        self.client.force_login(self.user)
        dashboard_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "btn btn-tertiary btn-sm")
        self.assertContains(
            dashboard_response,
            reverse("portal:portal_order_detail", kwargs={"order_id": self.order.id}),
        )

        recipients_response = self.client.get(reverse("portal:portal_recipients"))
        self.assertEqual(recipients_response.status_code, 200)
        self.assertContains(
            recipients_response,
            'class="btn btn-tertiary btn-sm" href="'
            + reverse("portal:portal_recipients")
            + "?edit=",
        )

        self.order.review_status = OrderReviewStatus.APPROVED
        self.order.save(update_fields=["review_status"])
        OrderDocument.objects.create(
            order=self.order,
            doc_type=OrderDocumentType.OTHER,
            file=SimpleUploadedFile("portal-order-doc.pdf", b"pdf-content"),
            uploaded_by=self.user,
        )
        order_detail_response = self.client.get(
            reverse("portal:portal_order_detail", kwargs={"order_id": self.order.id})
        )
        self.assertEqual(order_detail_response.status_code, 200)
        self.assertContains(order_detail_response, "btn btn-tertiary btn-sm")

        AccountDocument.objects.create(
            association_contact=self.user.association_profile.contact,
            doc_type=AccountDocumentType.OTHER,
            file=SimpleUploadedFile("portal-account-doc.pdf", b"pdf-content"),
            uploaded_by=self.user,
        )
        account_response = self.client.get(reverse("portal:portal_account"))
        self.assertEqual(account_response.status_code, 200)
        self.assertContains(account_response, "btn btn-tertiary btn-sm")

    def test_portal_context_does_not_expose_deprecated_ui_flags(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        with self.assertRaises(KeyError):
            response.context["scan_bootstrap_enabled"]
        with self.assertRaises(KeyError):
            response.context["wms_ui_mode"]
        with self.assertRaises(KeyError):
            response.context["wms_ui_mode_is_next"]
