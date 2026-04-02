from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import Destination, ShipmentRecipientOrganization


class PartiesDestinationScopeTests(TestCase):
    def test_same_structure_can_exist_as_recipient_on_two_destinations(self):
        correspondent = Contact.objects.create(
            name="Correspondant Scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        structure = Contact.objects.create(
            name="Hopital Scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination_a = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        destination_b = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )

        ShipmentRecipientOrganization.objects.create(
            organization=structure,
            destination=destination_a,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=structure,
            destination=destination_b,
        )
