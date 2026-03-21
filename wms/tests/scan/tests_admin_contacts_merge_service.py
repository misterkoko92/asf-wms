from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.capabilities import ContactCapabilityType, ensure_contact_capability
from contacts.models import Contact, ContactAddress, ContactType
from wms.admin_contacts_merge_service import (
    _merge_addresses,
    _merge_authorized_contacts,
    _merge_shipper_links,
    merge_contacts,
)
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class AdminContactsMergeServiceTests(TestCase):
    def setUp(self):
        self.correspondent_org = Contact.objects.create(
            name="Correspondant Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent_person = Contact.objects.create(
            name="Corr Admin",
            contact_type=ContactType.PERSON,
            first_name="Corr",
            last_name="Admin",
            organization=self.correspondent_org,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent_person,
            is_active=True,
        )

    def test_merge_organization_reassigns_shipment_shipper(self):
        source = Contact.objects.create(
            name="ASF Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="ASF Target",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source_person = Contact.objects.create(
            name="Jean Source",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Source",
            organization=source,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=source,
            default_contact=source_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        merged = merge_contacts(source_contact=source, target_contact=target)

        shipper.refresh_from_db()
        source.refresh_from_db()
        source_person.refresh_from_db()
        self.assertEqual(merged, target)
        self.assertEqual(shipper.organization, target)
        self.assertEqual(source_person.organization, target)
        self.assertFalse(source.is_active)

    def test_merge_person_reassigns_recipient_contact_and_authorization(self):
        shipper_org = Contact.objects.create(
            name="ASF",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_person = Contact.objects.create(
            name="Jean ASF",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="ASF",
            organization=shipper_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_org_contact = Contact.objects.create(
            name="Hopital Abidjan",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        source_person = Contact.objects.create(
            name="Alice Source",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Source",
            organization=recipient_org_contact,
            is_active=True,
        )
        target_person = Contact.objects.create(
            name="Alice Target",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Target",
            organization=recipient_org_contact,
            is_active=True,
        )
        source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=source_person,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=source_recipient_contact,
            is_default=True,
            is_active=True,
        )

        merged = merge_contacts(source_contact=source_person, target_contact=target_person)

        source_person.refresh_from_db()
        self.assertEqual(merged, target_person)
        self.assertFalse(source_person.is_active)
        migrated_recipient_contact = ShipmentRecipientContact.objects.get(
            recipient_organization=recipient_org,
            contact=target_person,
        )
        self.assertTrue(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                recipient_contact=migrated_recipient_contact,
                is_default=True,
                is_active=True,
            ).exists()
        )

    def test_merge_combines_capabilities_and_addresses_without_duplication(self):
        source = Contact.objects.create(
            name="Donateur Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Donateur Target",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ensure_contact_capability(source, ContactCapabilityType.DONOR)
        ensure_contact_capability(target, ContactCapabilityType.TRANSPORTER)
        ContactAddress.objects.create(
            contact=source,
            address_line1="1 rue du test",
            city="Paris",
            country="France",
            is_default=True,
        )
        ContactAddress.objects.create(
            contact=target,
            address_line1="1 rue du test",
            city="Paris",
            country="France",
            is_default=True,
        )

        merge_contacts(source_contact=source, target_contact=target)

        target.refresh_from_db()
        self.assertTrue(
            target.capabilities.filter(
                capability=ContactCapabilityType.DONOR,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            target.capabilities.filter(
                capability=ContactCapabilityType.TRANSPORTER,
                is_active=True,
            ).exists()
        )
        self.assertEqual(target.addresses.count(), 1)

    def test_merge_addresses_copies_distinct_source_address(self):
        source = Contact.objects.create(
            name="Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Target",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=source,
            label="Siege",
            address_line1="1 rue du test",
            address_line2="Batiment B",
            postal_code="75001",
            city="Paris",
            region="IDF",
            country="France",
            phone="0102030405",
            email="source@example.com",
            is_default=True,
            notes="note",
        )

        _merge_addresses(source, target)

        copied = target.addresses.get()
        self.assertEqual(copied.address_line1, "1 rue du test")
        self.assertEqual(copied.address_line2, "Batiment B")
        self.assertEqual(copied.city, "Paris")
        self.assertEqual(copied.country, "France")
        self.assertTrue(copied.is_default)

    def test_merge_authorized_contacts_retargets_when_target_auth_is_missing(self):
        recipient_org_contact = Contact.objects.create(
            name="Hopital Fusion",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        source_person = Contact.objects.create(
            name="Alice Source",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Source",
            organization=recipient_org_contact,
            is_active=True,
        )
        target_person = Contact.objects.create(
            name="Alice Target",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Target",
            organization=recipient_org_contact,
            is_active=True,
        )
        source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=source_person,
            is_active=True,
        )
        target_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=target_person,
            is_active=True,
        )
        shipper_org = Contact.objects.create(
            name="ASF",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_person = Contact.objects.create(
            name="Jean ASF",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="ASF",
            organization=shipper_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        authorization = ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=source_recipient_contact,
            is_default=True,
            is_active=True,
        )

        _merge_authorized_contacts(
            source_recipient_contact=source_recipient_contact,
            target_recipient_contact=target_recipient_contact,
        )

        authorization.refresh_from_db()
        self.assertEqual(authorization.recipient_contact, target_recipient_contact)
        self.assertTrue(authorization.is_default)

    def test_merge_shipper_links_retargets_authorization_when_target_link_has_no_match(self):
        recipient_org_contact = Contact.objects.create(
            name="Hopital Fusion",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_person = Contact.objects.create(
            name="Alice Recep",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Recep",
            organization=recipient_org_contact,
            is_active=True,
        )
        recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=recipient_person,
            is_active=True,
        )
        source_shipper_org = Contact.objects.create(
            name="Source shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source_shipper_person = Contact.objects.create(
            name="Jean Source",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Source",
            organization=source_shipper_org,
            is_active=True,
        )
        source_shipper = ShipmentShipper.objects.create(
            organization=source_shipper_org,
            default_contact=source_shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        target_shipper_org = Contact.objects.create(
            name="Target shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target_shipper_person = Contact.objects.create(
            name="Jean Target",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Target",
            organization=target_shipper_org,
            is_active=True,
        )
        target_shipper = ShipmentShipper.objects.create(
            organization=target_shipper_org,
            default_contact=target_shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        source_link = ShipmentShipperRecipientLink.objects.create(
            shipper=source_shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        target_link = ShipmentShipperRecipientLink.objects.create(
            shipper=target_shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        authorization = ShipmentAuthorizedRecipientContact.objects.create(
            link=source_link,
            recipient_contact=recipient_contact,
            is_default=True,
            is_active=True,
        )

        _merge_shipper_links(source_link=source_link, target_link=target_link)

        authorization.refresh_from_db()
        self.assertEqual(authorization.link, target_link)
        self.assertFalse(ShipmentShipperRecipientLink.objects.filter(pk=source_link.pk).exists())

    def test_merge_rejects_incompatible_contact_types(self):
        source = Contact.objects.create(
            name="Structure Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Personne Cible",
            contact_type=ContactType.PERSON,
            first_name="Personne",
            last_name="Cible",
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            merge_contacts(source_contact=source, target_contact=target)

    def test_merge_same_contact_returns_target_without_changes(self):
        donor = Contact.objects.create(
            name="Donateur Stable",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        merged = merge_contacts(source_contact=donor, target_contact=donor)

        self.assertEqual(merged, donor)

    def test_merge_person_rejects_different_organizations(self):
        source_org = Contact.objects.create(
            name="Org Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target_org = Contact.objects.create(
            name="Org Cible",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source = Contact.objects.create(
            name="Alice Source",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Source",
            organization=source_org,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Alice Cible",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Cible",
            organization=target_org,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            merge_contacts(source_contact=source, target_contact=target)

    def test_merge_organization_promotes_existing_shipper_and_authorization_flags(self):
        target = Contact.objects.create(
            name="ASF Target",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target_shipper_person = Contact.objects.create(
            name="Jeanne Cible",
            contact_type=ContactType.PERSON,
            first_name="Jeanne",
            last_name="Cible",
            organization=target,
            is_active=True,
        )
        target_shipper = ShipmentShipper.objects.create(
            organization=target,
            default_contact=target_shipper_person,
            validation_status=ShipmentValidationStatus.PENDING,
            can_send_to_all=False,
            is_active=True,
        )
        target_recipient_org_contact = Contact.objects.create(
            name="Hopital Cible",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target_recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=target_recipient_org_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )
        target_recipient_person = Contact.objects.create(
            name="Alice Cible",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Cible",
            organization=target_recipient_org_contact,
            is_active=True,
        )
        target_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=target_recipient_org,
            contact=target_recipient_person,
            is_active=True,
        )
        target_link = ShipmentShipperRecipientLink.objects.create(
            shipper=target_shipper,
            recipient_organization=target_recipient_org,
            is_active=True,
        )
        ShipmentShipper.objects.filter(pk=target_shipper.pk).update(
            default_contact=None,
            is_active=False,
        )

        source = Contact.objects.create(
            name="ASF Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source_person = Contact.objects.create(
            name="Jean Source",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Source",
            organization=source,
            is_active=True,
        )
        source_shipper = ShipmentShipper.objects.create(
            organization=source,
            default_contact=source_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=True,
            is_active=True,
        )
        source_link = ShipmentShipperRecipientLink.objects.create(
            shipper=source_shipper,
            recipient_organization=target_recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=source_link,
            recipient_contact=target_recipient_contact,
            is_default=True,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=target_link,
            recipient_contact=target_recipient_contact,
            is_default=False,
            is_active=False,
        )

        merge_contacts(source_contact=source, target_contact=target)

        target.refresh_from_db()
        target_shipper.refresh_from_db()
        target_link.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertEqual(target_shipper.default_contact, source_person)
        self.assertEqual(target_shipper.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertTrue(target_shipper.can_send_to_all)
        self.assertTrue(target_shipper.is_active)
        merged_authorization = ShipmentAuthorizedRecipientContact.objects.get(
            link=target_link,
            recipient_contact=target_recipient_contact,
        )
        self.assertTrue(merged_authorization.is_active)
        self.assertTrue(merged_authorization.is_default)
        self.assertFalse(ShipmentShipperRecipientLink.objects.filter(pk=source_link.pk).exists())

    def test_merge_organization_reassigns_recipient_runtime_when_target_has_none(self):
        source = Contact.objects.create(
            name="Source Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Target Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        referent = Contact.objects.create(
            name="Jean Source",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Source",
            organization=source,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=source,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=source,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        merge_contacts(source_contact=source, target_contact=target)

        shipper.refresh_from_db()
        recipient_org.refresh_from_db()
        referent.refresh_from_db()
        self.assertEqual(shipper.organization, target)
        self.assertEqual(recipient_org.organization, target)
        self.assertEqual(referent.organization, target)

    def test_merge_organization_updates_existing_recipient_runtime_and_moves_contact_and_link(self):
        shipper_org = Contact.objects.create(
            name="ASF",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_person = Contact.objects.create(
            name="Jean ASF",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="ASF",
            organization=shipper_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        source = Contact.objects.create(
            name="Source Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Target Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target_recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=target,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_correspondent=False,
            is_active=False,
        )
        source_recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=source,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=False,
            is_active=True,
        )
        source_recipient_person = Contact.objects.create(
            name="Alice Source",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Source",
            organization=source,
            is_active=True,
        )
        source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=source_recipient_org,
            contact=source_recipient_person,
            is_active=True,
        )
        source_link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=source_recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=source_link,
            recipient_contact=source_recipient_contact,
            is_default=True,
            is_active=True,
        )

        merge_contacts(source_contact=source, target_contact=target)

        target_recipient_org.refresh_from_db()
        source_recipient_contact.refresh_from_db()
        source_link.refresh_from_db()
        self.assertTrue(target_recipient_org.is_active)
        self.assertEqual(
            target_recipient_org.validation_status,
            ShipmentValidationStatus.VALIDATED,
        )
        self.assertEqual(source_recipient_contact.recipient_organization, target_recipient_org)
        self.assertEqual(source_link.recipient_organization, target_recipient_org)

    def test_merge_person_adopts_source_organization_and_promotes_existing_authorization(self):
        source_org = Contact.objects.create(
            name="Org Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source = Contact.objects.create(
            name="Alice Source",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Source",
            organization=source_org,
            use_organization_address=True,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Alice Target",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Target",
            organization=source_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=source_org,
            default_contact=source,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.destination.correspondent_contact = source
        self.destination.save(update_fields=["correspondent_contact"])
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=source_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=source,
            is_active=True,
        )
        target_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=target,
            is_active=True,
        )
        Contact.objects.filter(pk=target.pk).update(organization=None, is_active=False)
        target.refresh_from_db()
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=source_recipient_contact,
            is_default=True,
            is_active=True,
        )
        existing_authorization = ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=target_recipient_contact,
            is_default=False,
            is_active=False,
        )

        merge_contacts(source_contact=source, target_contact=target)

        target.refresh_from_db()
        shipper.refresh_from_db()
        self.destination.refresh_from_db()
        existing_authorization.refresh_from_db()
        self.assertEqual(target.organization, source_org)
        self.assertTrue(target.use_organization_address)
        self.assertTrue(target.is_active)
        self.assertEqual(shipper.default_contact, target)
        self.assertEqual(self.destination.correspondent_contact, target)
        self.assertTrue(existing_authorization.is_active)
        self.assertTrue(existing_authorization.is_default)
        self.assertFalse(
            ShipmentRecipientContact.objects.filter(pk=source_recipient_contact.pk).exists()
        )

    def test_merge_organization_rejects_recipients_on_different_destinations(self):
        source = Contact.objects.create(
            name="Source Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Target Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_destination = Destination.objects.create(
            city="DAKAR",
            iata_code="DKR",
            country="SENEGAL",
            correspondent_contact=self.correspondent_person,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=source,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=target,
            destination=other_destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            merge_contacts(source_contact=source, target_contact=target)
