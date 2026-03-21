from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.import_services import _get_or_create_destination
from wms.models import Destination, ShipmentRecipientOrganization, ShipmentValidationStatus


class ImportDestinationsTests(TestCase):
    def test_get_or_create_destination_parses_label(self):
        destination = _get_or_create_destination("Paris (CDG) - France")
        self.assertIsNotNone(destination)
        self.assertEqual(destination.city, "Paris")
        self.assertEqual(destination.iata_code, "CDG")
        self.assertEqual(destination.country, "France")
        self.assertEqual(Destination.objects.count(), 1)

    def test_get_or_create_destination_uses_correspondent_contact(self):
        correspondent = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=correspondent,
            destination=Destination.objects.create(
                city="Default",
                iata_code="DEF",
                country="France",
                correspondent_contact=correspondent,
                is_active=True,
            ),
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )

        destination = _get_or_create_destination(
            "Lyon (LYS) - France",
            contact=correspondent,
        )
        self.assertEqual(destination.correspondent_contact_id, correspondent.id)
