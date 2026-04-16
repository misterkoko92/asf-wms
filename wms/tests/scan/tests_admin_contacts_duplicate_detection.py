from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.admin_contacts_duplicate_detection import (
    find_similar_contacts,
    find_similar_destinations,
)
from wms.models import Destination, ShipmentRecipientOrganization, ShipmentShipper


class AdminContactsDuplicateDetectionTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Duplicate",
            contact_type=ContactType.PERSON,
            first_name="Correspondant",
            last_name="Duplicate",
            is_active=True,
        )
        self.destination_abj = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.destination_dkr = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

    def test_finds_destination_duplicate_by_exact_iata(self):
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

        matches = find_similar_destinations(city="Autre", iata_code="BKO", country="France")

        self.assertEqual(matches, [destination])

    def test_finds_destination_duplicate_by_normalized_city_and_country(self):
        destination = Destination.objects.create(
            city="N'Djamena",
            iata_code="NDJ",
            country="Tchad",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

        matches = find_similar_destinations(city="ndjamena", iata_code="", country="TCHAD")

        self.assertEqual(matches, [destination])

    def test_finds_destination_duplicate_with_case_and_accent_tolerance(self):
        destination = Destination.objects.create(
            city="São Tomé",
            iata_code="TMS",
            country="Sao Tome-et-Principe",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

        matches = find_similar_destinations(
            city="Sao Tome",
            iata_code="",
            country="Sao Tome et Principe",
        )

        self.assertEqual(matches, [destination])

    def test_finds_contact_duplicate_by_exact_asf_id(self):
        contact = Contact.objects.create(
            name="Donateur ASF",
            contact_type=ContactType.ORGANIZATION,
            asf_id="ASF-001",
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="donor",
            entity_type=ContactType.ORGANIZATION,
            organization_name="Autre Donateur",
            asf_id="ASF-001",
        )

        self.assertEqual(matches, [contact])

    def test_finds_organization_duplicate_by_normalized_name(self):
        organization = Contact.objects.create(
            name="Hôpital Saint Joseph",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="recipient",
            entity_type=ContactType.ORGANIZATION,
            organization_name="Hopital Saint-Joseph",
        )

        self.assertEqual(matches, [organization])

    def test_ignores_shipper_duplicate_when_requested_type_is_recipient(self):
        shipper_organization = Contact.objects.create(
            name="Asso A",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_referent = Contact.objects.create(
            name="Jean Asso A",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="AssoA",
            organization=shipper_organization,
            is_active=True,
        )
        ShipmentShipper.objects.create(
            organization=shipper_organization,
            default_contact=shipper_referent,
            validation_status="validated",
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="recipient",
            entity_type=ContactType.ORGANIZATION,
            organization_name="Asso A",
            destination_id=self.destination_abj.id,
        )

        self.assertEqual(matches, [])

    def test_recipient_duplicate_requires_same_destination_scope(self):
        recipient_organization = Contact.objects.create(
            name="Hopital Local",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=recipient_organization,
            destination=self.destination_dkr,
            validation_status="validated",
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="recipient",
            entity_type=ContactType.ORGANIZATION,
            organization_name="Hopital Local",
            destination_id=self.destination_abj.id,
        )

        self.assertEqual(matches, [])

    def test_recipient_duplicate_keeps_same_business_type_and_destination(self):
        recipient_organization = Contact.objects.create(
            name="Hopital Local",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=recipient_organization,
            destination=self.destination_abj,
            validation_status="validated",
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="recipient",
            entity_type=ContactType.ORGANIZATION,
            organization_name="Hopital Local",
            destination_id=self.destination_abj.id,
        )

        self.assertEqual(matches, [recipient_organization])

    def test_finds_person_duplicate_by_identity_and_organization(self):
        organization = Contact.objects.create(
            name="Centre Medical Abidjan",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        person = Contact.objects.create(
            name="Alice Martin",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Martin",
            organization=organization,
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="recipient",
            entity_type=ContactType.PERSON,
            organization_name="Centre médical Abidjan",
            first_name="alice",
            last_name="martin",
        )

        self.assertEqual(matches, [person])

    def test_excludes_current_record_in_edit_mode(self):
        organization = Contact.objects.create(
            name="Transporteur Soleil",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        matches = find_similar_contacts(
            business_type="transporter",
            entity_type=ContactType.ORGANIZATION,
            organization_name="Transporteur Soleil",
            exclude_contact_id=organization.id,
        )

        self.assertEqual(matches, [])
