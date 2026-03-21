from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.admin_contacts_destination_service import (
    build_destination_duplicate_candidates,
    save_destination_from_form,
)
from wms.models import Destination


class AdminContactsDestinationServiceTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Service",
            contact_type=ContactType.PERSON,
            first_name="Correspondant",
            last_name="Service",
            is_active=True,
        )

    def test_create_new_destination_with_correspondent(self):
        destination = save_destination_from_form(
            {
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "correspondent_contact_id": self.correspondent.id,
                "is_active": True,
            }
        )

        self.assertEqual(destination.city, "ABIDJAN")
        self.assertEqual(destination.iata_code, "ABJ")
        self.assertEqual(destination.correspondent_contact, self.correspondent)

    def test_build_duplicate_candidates_returns_existing_destination(self):
        destination = Destination.objects.create(
            city="N'Djamena",
            iata_code="NDJ",
            country="Tchad",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

        candidates = build_destination_duplicate_candidates(
            {"city": "ndjamena", "iata_code": "", "country": "TCHAD"}
        )

        self.assertEqual(candidates, [destination])

    def test_replace_updates_existing_destination(self):
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=self.correspondent,
            is_active=False,
        )

        updated = save_destination_from_form(
            {
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "correspondent_contact_id": self.correspondent.id,
                "is_active": True,
                "duplicate_action": "replace",
                "duplicate_target_id": destination.id,
            }
        )

        destination.refresh_from_db()
        self.assertEqual(updated.id, destination.id)
        self.assertEqual(destination.country, "COTE D'IVOIRE")
        self.assertTrue(destination.is_active)

    def test_merge_keeps_existing_scalar_fields_when_already_populated(self):
        destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        other_correspondent = Contact.objects.create(
            name="Autre Correspondant",
            contact_type=ContactType.PERSON,
            first_name="Autre",
            last_name="Correspondant",
            is_active=True,
        )

        merged = save_destination_from_form(
            {
                "city": "ABIDJAN MODIFIE",
                "iata_code": "ABJ",
                "country": "CI",
                "correspondent_contact_id": other_correspondent.id,
                "is_active": True,
                "duplicate_action": "merge",
                "duplicate_target_id": destination.id,
            }
        )

        destination.refresh_from_db()
        self.assertEqual(merged.id, destination.id)
        self.assertEqual(destination.city, "ABIDJAN")
        self.assertEqual(destination.country, "COTE D'IVOIRE")
        self.assertEqual(destination.correspondent_contact, self.correspondent)

    def test_duplicate_action_rejects_hard_uniqueness_conflict(self):
        Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            save_destination_from_form(
                {
                    "city": "Abidjan",
                    "iata_code": "ABJ",
                    "country": "COTE D'IVOIRE",
                    "correspondent_contact_id": self.correspondent.id,
                    "duplicate_action": "duplicate",
                }
            )
