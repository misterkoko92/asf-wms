from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms_admin_contacts_contact import ContactCrudForm
from wms.models import Destination


class ContactCrudFormTests(TestCase):
    def setUp(self):
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=Contact.objects.create(
                name="Correspondant Admin",
                contact_type=ContactType.PERSON,
                first_name="Corr",
                last_name="Admin",
                is_active=True,
            ),
            is_active=True,
        )
        self.shipper_organization = Contact.objects.create(
            name="Aviation Sans Frontieres",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def test_shipper_requires_organization_and_default_person(self):
        form = ContactCrudForm(data={"business_type": "shipper"})

        self.assertFalse(form.is_valid())
        self.assertIn("organization_name", form.errors)
        self.assertIn("first_name", form.errors)
        self.assertIn("last_name", form.errors)

    def test_recipient_requires_destination_and_allowed_shipper(self):
        form = ContactCrudForm(
            data={
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("destination_id", form.errors)
        self.assertIn("allowed_shipper_ids", form.errors)

    def test_volunteer_requires_person_identity(self):
        form = ContactCrudForm(data={"business_type": "volunteer"})

        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)
        self.assertIn("last_name", form.errors)

    def test_duplicate_review_requires_decision(self):
        form = ContactCrudForm(
            data={
                "business_type": "donor",
                "entity_type": "organization",
                "organization_name": "Donateur Test",
                "duplicate_candidates_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_action", form.errors)

    def test_duplicate_review_requires_target_for_merge(self):
        form = ContactCrudForm(
            data={
                "business_type": "donor",
                "entity_type": "organization",
                "organization_name": "Donateur Test",
                "duplicate_candidates_count": "1",
                "duplicate_action": "replace",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_target_id", form.errors)

    def test_accepts_minimal_recipient_payload(self):
        form = ContactCrudForm(
            data={
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": str(self.destination.id),
                "allowed_shipper_ids": [str(self.shipper_organization.id)],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
