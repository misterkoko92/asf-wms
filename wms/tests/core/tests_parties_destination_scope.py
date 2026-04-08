from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.application.parties import use_cases
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

    def test_update_shared_recipient_profile_reuses_structure_contact_on_new_destination(self):
        association = Contact.objects.create(
            name="Association Scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Correspondant Scope Runtime",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        structure = Contact.objects.create(
            name="Hopital Scope Runtime",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination_a = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV",
            country="Rep. du Congo",
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
            is_active=True,
        )

        result = use_cases.update_recipient_shared_profile(
            association_contact=association,
            destination=destination_b,
            structure_name="Hopital Scope Runtime",
            emails="scope@example.org",
            phones="+22501020304",
            address_line1="1 Rue Scope",
            city="Abidjan",
            country="Cote d'Ivoire",
            persist_projection=False,
            prefer_existing_structure=True,
        )

        self.assertEqual(result.synced_contact.id, structure.id)
        self.assertEqual(result.recipient_organization.organization_id, structure.id)
        self.assertEqual(
            ShipmentRecipientOrganization.objects.filter(organization=structure).count(),
            2,
        )
