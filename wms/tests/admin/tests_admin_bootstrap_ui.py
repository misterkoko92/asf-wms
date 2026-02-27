from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import Destination, Shipment


class AdminBootstrapUiTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="admin-bootstrap",
            password="pass1234",
            email="admin-bootstrap@example.com",
        )
        self.client.force_login(self.superuser)

        self.correspondent = Contact.objects.create(
            name="Correspondant Admin Bootstrap",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Paris",
            iata_code="ADB",
            country="France",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.shipment = Shipment.objects.create(
            shipper_name="ASF",
            recipient_name="Destinataire",
            destination=self.destination,
            destination_address="1 Rue Test",
            destination_country="France",
        )

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_admin_stockmovement_changelist_includes_bootstrap_assets(self):
        response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        )
        self.assertContains(response, "wms/admin-bootstrap.css")
        self.assertContains(response, "admin-bootstrap-enabled")
        self.assertContains(response, "btn btn-outline-primary btn-sm")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_admin_stockmovement_form_includes_bootstrap_buttons(self):
        response = self.client.get(reverse("admin:wms_stockmovement_receive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "wms/admin-bootstrap.css")
        self.assertContains(response, "btn btn-primary")
        self.assertContains(response, "btn btn-outline-secondary")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_admin_shipment_change_form_includes_bootstrap_doc_actions(self):
        response = self.client.get(
            reverse("admin:wms_shipment_change", args=[self.shipment.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin-bootstrap-docs")
        self.assertContains(response, "btn btn-outline-primary btn-sm")
        self.assertContains(response, "Impression A5")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=False)
    def test_admin_templates_do_not_include_bootstrap_assets_when_disabled(self):
        response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "bootstrap@5.3.3")
        self.assertNotContains(response, "wms/admin-bootstrap.css")
