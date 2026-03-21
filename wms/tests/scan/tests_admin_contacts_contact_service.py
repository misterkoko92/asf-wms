from django.test import TestCase

from contacts.capabilities import ContactCapabilityType
from contacts.models import Contact, ContactCapability, ContactType
from wms.admin_contacts_contact_service import (
    build_contact_duplicate_candidates,
    deactivate_contact,
    save_contact_from_form,
)
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
)


class AdminContactsContactServiceTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Service",
            contact_type=ContactType.PERSON,
            first_name="Corr",
            last_name="Service",
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

    def test_create_donor_adds_capability(self):
        contact = save_contact_from_form(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Lumiere",
                "is_active": True,
            }
        )

        self.assertEqual(contact.contact_type, ContactType.ORGANIZATION)
        self.assertTrue(
            ContactCapability.objects.filter(
                contact=contact,
                capability=ContactCapabilityType.DONOR,
                is_active=True,
            ).exists()
        )

    def test_create_shipper_creates_organization_person_and_runtime(self):
        organization = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "Aviation Sans Frontieres",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@example.com",
                "phone": "0102030405",
                "is_active": True,
            }
        )

        shipper = ShipmentShipper.objects.get(organization=organization)
        self.assertEqual(shipper.default_contact.organization, organization)
        self.assertEqual(shipper.default_contact.first_name, "Jean")

    def test_create_recipient_creates_runtime_links_and_default_authorization(self):
        shipper_org = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF",
                "first_name": "Jean",
                "last_name": "Dupont",
                "is_active": True,
            }
        )

        organization = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "is_active": True,
            }
        )

        recipient_org = ShipmentRecipientOrganization.objects.get(organization=organization)
        recipient_contact = ShipmentRecipientContact.objects.get(
            recipient_organization=recipient_org
        )
        shipper = ShipmentShipper.objects.get(organization=shipper_org)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        authorization = ShipmentAuthorizedRecipientContact.objects.get(
            link=link,
            recipient_contact=recipient_contact,
        )
        self.assertTrue(authorization.is_default)
        self.assertTrue(authorization.is_active)

    def test_create_correspondent_marks_stopover_and_destination_contact(self):
        organization = save_contact_from_form(
            {
                "business_type": "correspondent",
                "organization_name": "Correspondant ASF ABJ",
                "first_name": "Marie",
                "last_name": "Dupont",
                "destination_id": self.destination.id,
                "is_active": True,
            }
        )

        recipient_org = ShipmentRecipientOrganization.objects.get(organization=organization)
        self.destination.refresh_from_db()
        self.assertTrue(recipient_org.is_correspondent)
        self.assertEqual(self.destination.correspondent_contact.organization, organization)

    def test_replace_existing_contact_overwrites_master_fields(self):
        organization = Contact.objects.create(
            name="Donateur Lumiere",
            contact_type=ContactType.ORGANIZATION,
            email="old@example.com",
            is_active=False,
        )

        updated = save_contact_from_form(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Lumiere",
                "email": "new@example.com",
                "duplicate_action": "replace",
                "duplicate_target_id": organization.id,
                "is_active": True,
            }
        )

        organization.refresh_from_db()
        self.assertEqual(updated.id, organization.id)
        self.assertEqual(organization.email, "new@example.com")
        self.assertTrue(organization.is_active)

    def test_merge_existing_contact_fills_missing_fields_without_overwrite(self):
        organization = Contact.objects.create(
            name="Transporteur Soleil",
            contact_type=ContactType.ORGANIZATION,
            email="existing@example.com",
            phone="",
            is_active=True,
        )

        merged = save_contact_from_form(
            {
                "business_type": "transporter",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Transporteur Soleil",
                "email": "new@example.com",
                "phone": "0102030405",
                "duplicate_action": "merge",
                "duplicate_target_id": organization.id,
                "is_active": True,
            }
        )

        organization.refresh_from_db()
        self.assertEqual(merged.id, organization.id)
        self.assertEqual(organization.email, "existing@example.com")
        self.assertEqual(organization.phone, "0102030405")

    def test_deactivate_contact_sets_is_active_false(self):
        organization = save_contact_from_form(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Test",
                "is_active": True,
            }
        )

        deactivate_contact(organization)

        organization.refresh_from_db()
        self.assertFalse(organization.is_active)

    def test_build_duplicate_candidates_returns_existing_primary_contact(self):
        organization = Contact.objects.create(
            name="Hopital Saint Joseph",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        candidates = build_contact_duplicate_candidates(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Saint-Joseph",
            }
        )

        self.assertEqual(candidates, [organization])
