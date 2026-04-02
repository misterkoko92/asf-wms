from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class PartiesMergeTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.shipper_org = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_person = Contact.objects.create(
            name="Shipper Person",
            first_name="Alice",
            last_name="Shipper",
            contact_type=ContactType.PERSON,
            organization=self.shipper_org,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_org,
            default_contact=self.shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.target_org = Contact.objects.create(
            name="Hopital Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.target_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.target_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.target_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=self.target_recipient_organization,
            is_active=True,
        )
        self.source_org = Contact.objects.create(
            name="Hopital Bamako Duplicate",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.source_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.source_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.source_person = Contact.objects.create(
            name="Source Person",
            first_name="Dr",
            last_name="Source",
            contact_type=ContactType.PERSON,
            organization=self.source_org,
            is_active=True,
        )
        self.source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.source_recipient_organization,
            contact=self.source_person,
            is_active=True,
        )
        self.source_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=self.source_recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=self.source_link,
            recipient_contact=self.source_recipient_contact,
            is_default=True,
            is_active=True,
        )

    def test_merge_recipient_organizations_returns_target_scope(self):
        from wms.parties.merge import merge_recipient_organizations

        result = merge_recipient_organizations(
            source=self.source_recipient_organization,
            target=self.target_recipient_organization,
        )

        self.assertEqual(
            result.target_recipient_organization_id,
            self.target_recipient_organization.id,
        )
        migrated_contact = ShipmentRecipientContact.objects.get(contact=self.source_person)
        self.assertEqual(
            migrated_contact.recipient_organization_id,
            self.target_recipient_organization.id,
        )
