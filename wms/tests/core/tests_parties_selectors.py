from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
)
from wms.parties.selectors import (
    active_recipient_contacts_for_destination,
    validated_recipient_organizations_for_destination,
)


class PartiesSelectorsTests(TestCase):
    def setUp(self):
        self.destination = Destination.objects.create(
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

    def test_validated_recipient_organizations_for_destination_filters_active_validated_rows(self):
        valid_org = Contact.objects.create(
            name="Hopital Valide",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        inactive_scope_org = Contact.objects.create(
            name="Hopital Scope Inactif",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        pending_org = Contact.objects.create(
            name="Hopital En Attente",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            is_active=True,
            correspondent_contact=Contact.objects.create(
                name="Correspondant DKR",
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            ),
        )

        expected = ShipmentRecipientOrganization.objects.create(
            organization=valid_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=inactive_scope_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=False,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=pending_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=Contact.objects.create(
                name="Hopital Autre Destination",
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            ),
            destination=other_destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        rows = list(validated_recipient_organizations_for_destination(self.destination))

        self.assertEqual(rows, [expected])

    def test_active_recipient_contacts_for_destination_filters_inactive_people(self):
        organization = Contact.objects.create(
            name="Hopital Contacts",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        active_person = Contact.objects.create(
            name="Claire Martin",
            first_name="Claire",
            last_name="Martin",
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=True,
        )
        inactive_link_person = Contact.objects.create(
            name="Jean Dupont",
            first_name="Jean",
            last_name="Dupont",
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=True,
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=active_person,
            is_active=True,
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=inactive_link_person,
            is_active=False,
        )

        rows = list(active_recipient_contacts_for_destination(destination=self.destination))

        self.assertEqual(rows, [active_person])
