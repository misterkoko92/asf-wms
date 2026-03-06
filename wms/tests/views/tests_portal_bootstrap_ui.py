from pathlib import Path

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
    AssociationProfile,
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderReviewStatus,
    OrderStatus,
)


@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
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
        AssociationProfile.objects.create(
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
        AssociationRecipient.objects.create(
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
        self.order = Order.objects.create(
            association_contact=association_contact,
            shipper_name="ASF",
            recipient_name="Destinataire Bootstrap",
            destination_address="2 Rue Livraison\n75001 Paris\nFrance",
            destination_country="France",
        )
        self.client.force_login(self.user)

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
        self.assertContains(response, "portal-bootstrap.css")
        self.assertContains(response, "portal-bootstrap-enabled")
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

    def test_portal_pages_apply_status_badge_levels(self):
        self.order.status = OrderStatus.READY
        self.order.review_status = OrderReviewStatus.CHANGES_REQUESTED
        self.order.save(update_fields=["status", "review_status"])
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
        self.assertContains(detail_response, "portal-badge is-warning")
        self.assertContains(detail_response, "portal-badge is-error")

    def test_portal_order_create_uses_bootstrap_form_controls(self):
        response = self.client.get(reverse("portal:portal_order_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "btn btn-primary")

    def test_portal_account_uses_bootstrap_forms_and_tables(self):
        response = self.client.get(reverse("portal:portal_account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="portal-account-form"')
        self.assertContains(response, "form-control")
        self.assertContains(response, "form-select")
        self.assertContains(response, "btn btn-primary")

    def test_portal_recipients_uses_bootstrap_forms_and_tables(self):
        response = self.client.get(reverse("portal:portal_recipients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "form-control")
        self.assertContains(response, "form-select")
        self.assertContains(response, "btn btn-primary")

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
        self.assertContains(login_response, "Premi&egrave;re connexion")

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
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(response, "btn btn-primary")

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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=False)
    def test_portal_base_does_not_render_legacy_controls_when_setting_is_disabled(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap@5.3.3")
        self.assertContains(response, "scan-bootstrap.css")
        self.assertContains(response, "portal-bootstrap.css")
        self.assertNotContains(response, 'id="portal-ui-toggle"')
        self.assertNotContains(response, 'id="portal-ui-reset-default"')
        self.assertNotContains(response, "Essayer interface Next")
