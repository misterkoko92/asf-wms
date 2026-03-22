from pathlib import Path

from django.conf import settings
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

    def test_admin_stockmovement_form_includes_bootstrap_buttons(self):
        response = self.client.get(reverse("admin:wms_stockmovement_receive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "wms/admin-bootstrap.css")
        self.assertContains(response, "btn btn-primary")
        self.assertContains(response, "btn btn-outline-secondary")

    def test_admin_stockmovement_form_keeps_primary_and_back_contract(self):
        response = self.client.get(reverse("admin:wms_stockmovement_receive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'class="default btn btn-primary"',
        )
        self.assertContains(
            response,
            'class="submit-row admin-bootstrap-actions ui-comp-actions"',
        )
        self.assertContains(
            response,
            f'href="{reverse("admin:wms_stockmovement_changelist")}" class="btn btn-outline-secondary button"',
        )

    def test_admin_stockmovement_changelist_keeps_action_button_contract(self):
        response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<a class="btn btn-outline-primary btn-sm addlink" href="'
            + reverse("admin:wms_stockmovement_receive")
            + '">Receive stock</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<a class="btn btn-outline-primary btn-sm addlink" href="'
            + reverse("admin:wms_stockmovement_adjust")
            + '">Adjust stock</a>',
            html=True,
        )

    @override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
    def test_admin_stockmovement_views_render_native_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        changelist_response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(changelist_response.status_code, 200)
        self.assertContains(changelist_response, "Receive stock")
        self.assertContains(changelist_response, "Adjust stock")
        self.assertContains(changelist_response, "Transfer stock")
        self.assertContains(changelist_response, "Prepare carton")
        self.assertNotContains(changelist_response, "R&eacute;ception stock")

        form_response = self.client.get(reverse("admin:wms_stockmovement_receive"))
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, "Receive stock")
        self.assertContains(form_response, 'value="Save"')
        self.assertContains(form_response, ">Back<")
        self.assertNotContains(form_response, 'value="Enregistrer"')

    def test_admin_shipment_change_form_includes_bootstrap_doc_actions(self):
        response = self.client.get(reverse("admin:wms_shipment_change", args=[self.shipment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin-bootstrap-docs")
        self.assertContains(response, "btn btn-outline-primary btn-sm")
        self.assertContains(response, "Impression A5")

    def test_admin_shipment_change_form_keeps_document_action_group_contract(self):
        response = self.client.get(reverse("admin:wms_shipment_change", args=[self.shipment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="block admin-bootstrap-doc-links ui-comp-actions"')
        self.assertContains(
            response,
            'class="btn btn-outline-primary btn-sm"',
        )
        self.assertContains(
            response,
            reverse("admin:wms_shipment_print_doc", args=[self.shipment.id, "shipment_note"]),
        )

    def test_admin_bootstrap_css_centers_button_text(self):
        css_path = Path(settings.BASE_DIR) / "wms" / "static" / "wms" / "admin-bootstrap.css"
        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn(".admin-bootstrap-enabled .btn {", css_content)
        self.assertIn("display: inline-flex;", css_content)
        self.assertIn("align-items: center;", css_content)
        self.assertIn("justify-content: center;", css_content)

    def test_admin_templates_keep_bootstrap_assets_without_feature_flag(self):
        response = self.client.get(reverse("admin:wms_stockmovement_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap@5.3.3")
        self.assertContains(response, "wms/admin-bootstrap.css")
