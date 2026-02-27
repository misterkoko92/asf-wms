from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import AssociationProfile, AssociationRecipient, Destination, Order


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
        Order.objects.create(
            association_contact=association_contact,
            shipper_name="ASF",
            recipient_name="Destinataire Bootstrap",
            destination_address="2 Rue Livraison\n75001 Paris\nFrance",
            destination_country="France",
        )
        self.client.force_login(self.user)

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_portal_base_includes_bootstrap_assets_when_enabled(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
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

    @override_settings(SCAN_BOOTSTRAP_ENABLED=False)
    def test_portal_base_does_not_include_bootstrap_assets_when_disabled(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "bootstrap@5.3.3")
        self.assertNotContains(response, "scan-bootstrap.css")
        self.assertNotContains(response, "portal-bootstrap.css")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_portal_dashboard_uses_bootstrap_table_layout(self):
        response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scan-card portal-card card border-0")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, 'data-table-tools="1"')
        self.assertContains(response, "btn btn-outline-primary btn-sm")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_portal_order_create_uses_bootstrap_form_controls(self):
        response = self.client.get(reverse("portal:portal_order_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-select")
        self.assertContains(response, "form-control")
        self.assertContains(response, "table table-sm table-hover")
        self.assertContains(response, "btn btn-primary")
