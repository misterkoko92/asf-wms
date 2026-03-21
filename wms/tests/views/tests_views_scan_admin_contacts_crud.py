from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.capabilities import ContactCapabilityType, ensure_contact_capability
from contacts.models import Contact, ContactType
from wms.models import Destination, ShipmentShipper


class ScanAdminContactsCrudViewTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-admin-crud-superuser",
            password="pass1234",  # pragma: allowlist secret
            email="scan-admin-crud-superuser@example.com",
        )
        self.client.force_login(self.superuser)
        self.correspondent_org = Contact.objects.create(
            name="Correspondant Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent_person = Contact.objects.create(
            name="Marie Correspondant",
            contact_type=ContactType.PERSON,
            first_name="Marie",
            last_name="Correspondant",
            organization=self.correspondent_org,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent_person,
            is_active=True,
        )

    def test_scan_admin_contacts_post_save_destination_creates_destination(self):
        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "save_destination",
                "city": "BAMAKO",
                "iata_code": "BKO",
                "country": "MALI",
                "correspondent_contact_id": str(self.correspondent_person.id),
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Destination.objects.filter(
                city="BAMAKO",
                iata_code="BKO",
                country="MALI",
                correspondent_contact=self.correspondent_person,
                is_active=True,
            ).exists()
        )

    def test_scan_admin_contacts_post_save_destination_requests_duplicate_review(self):
        existing = Destination.objects.create(
            city="N'Djamena",
            iata_code="NDJ",
            country="Tchad",
            correspondent_contact=self.correspondent_person,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "save_destination",
                "city": "Ndjamena",
                "iata_code": "NDJ",
                "country": "TCHAD",
                "correspondent_contact_id": str(self.correspondent_person.id),
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Décision doublon")
        self.assertContains(response, existing.iata_code)
        self.assertEqual(
            response.context["destination_duplicate_candidates"],
            [existing],
        )
        self.assertEqual(Destination.objects.filter(iata_code="NDJ").count(), 1)

    def test_scan_admin_contacts_get_edit_contact_prefills_contact_form(self):
        donor = Contact.objects.create(
            name="Donateur Edit",
            contact_type=ContactType.ORGANIZATION,
            email="donor@example.com",
            phone="0102030405",
            is_active=True,
        )
        ensure_contact_capability(donor, ContactCapabilityType.DONOR)

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {"edit": str(donor.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["contact_form_mode"], "edit")
        self.assertEqual(response.context["editing_contact"], donor)
        self.assertContains(response, 'id="scan-admin-create-contact" open')
        self.assertContains(response, 'value="Donateur Edit"')
        self.assertContains(response, 'value="donor"')

    def test_scan_admin_contacts_post_save_contact_creates_shipper_runtime(self):
        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "save_contact",
                "business_type": "shipper",
                "organization_name": "Aviation Sans Frontieres",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@example.com",
                "phone": "0102030405",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        organization = Contact.objects.get(name="Aviation Sans Frontieres")
        shipper = ShipmentShipper.objects.get(organization=organization)
        self.assertEqual(shipper.default_contact.first_name, "Jean")

    def test_scan_admin_contacts_post_deactivate_contact_marks_contact_inactive(self):
        donor = Contact.objects.create(
            name="Donateur Actif",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "deactivate_contact",
                "contact_id": str(donor.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        donor.refresh_from_db()
        self.assertFalse(donor.is_active)

    def test_scan_admin_contacts_post_merge_contact_deactivates_source(self):
        source = Contact.objects.create(
            name="Transporteur Source",
            contact_type=ContactType.ORGANIZATION,
            phone="0102030405",
            is_active=True,
        )
        target = Contact.objects.create(
            name="Transporteur Cible",
            contact_type=ContactType.ORGANIZATION,
            email="target@example.com",
            is_active=True,
        )
        ensure_contact_capability(source, ContactCapabilityType.TRANSPORTER)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "merge_contact",
                "source_contact_id": str(source.id),
                "target_contact_id": str(target.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        source.refresh_from_db()
        target.refresh_from_db()
        self.assertFalse(source.is_active)
        self.assertEqual(target.phone, "0102030405")
        self.assertTrue(
            target.capabilities.filter(
                capability=ContactCapabilityType.TRANSPORTER,
                is_active=True,
            ).exists()
        )
