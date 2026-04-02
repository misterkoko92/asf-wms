from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.application.parties.use_cases import sync_portal_recipient
from wms.models import AssociationRecipient, Destination


class PartiesUseCasesTests(TestCase):
    def test_sync_portal_recipient_returns_structure_and_recipient_scope(self):
        association = Contact.objects.create(
            name="Association V3",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            is_active=True,
            correspondent_contact=Contact.objects.create(
                name="Correspondant BKO",
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            ),
        )
        recipient = AssociationRecipient.objects.create(
            association_contact=association,
            destination=destination,
            name="Hopital V3",
            structure_name="Hopital V3",
            emails="hopital@example.org",
            email="hopital@example.org",
            phones="+22370000000",
            phone="+22370000000",
            address_line1="1 Rue V3",
            city="Bamako",
            country="Mali",
            is_active=True,
        )

        result = sync_portal_recipient(recipient=recipient)

        self.assertIn("synced_contact_id", result)
        self.assertIn("recipient_organization_id", result)
