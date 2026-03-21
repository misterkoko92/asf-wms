from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms_admin_contacts_destination import DestinationCrudForm


class DestinationCrudFormTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Destination",
            contact_type=ContactType.PERSON,
            first_name="Correspondant",
            last_name="Destination",
            is_active=True,
        )

    def test_requires_city_iata_and_country(self):
        form = DestinationCrudForm(data={})

        self.assertFalse(form.is_valid())
        self.assertIn("city", form.errors)
        self.assertIn("iata_code", form.errors)
        self.assertIn("country", form.errors)

    def test_accepts_minimal_valid_payload(self):
        form = DestinationCrudForm(
            data={
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "correspondent_contact_id": str(self.correspondent.id),
                "is_active": "1",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_duplicate_decision_when_candidates_are_present(self):
        form = DestinationCrudForm(
            data={
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "duplicate_candidates_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_action", form.errors)

    def test_requires_duplicate_target_for_merge_or_replace(self):
        form = DestinationCrudForm(
            data={
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "duplicate_candidates_count": "1",
                "duplicate_action": "merge",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_target_id", form.errors)
