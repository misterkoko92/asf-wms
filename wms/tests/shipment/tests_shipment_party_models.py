from django.core.exceptions import ValidationError
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


class ShipmentPartyModelTests(TestCase):
    def _create_organization(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, *, organization: Contact, first_name: str, last_name: str) -> Contact:
        return Contact.objects.create(
            name=f"{first_name} {last_name}",
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=True,
        )

    def _create_destination(self, iata_code: str, *, correspondent_contact: Contact | None = None):
        correspondent_contact = correspondent_contact or self._create_organization(
            f"Correspondant {iata_code}"
        )
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent_contact,
            is_active=True,
        )

    def test_shipment_shipper_requires_matching_default_contact(self):
        organization = self._create_organization("Shipper Org")
        default_contact = self._create_person(
            organization=organization,
            first_name="Alice",
            last_name="Carrier",
        )

        shipper = ShipmentShipper.objects.create(
            organization=organization,
            default_contact=default_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=False,
            is_active=True,
        )

        self.assertEqual(shipper.organization_id, organization.id)
        self.assertEqual(shipper.default_contact_id, default_contact.id)
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)

    def test_recipient_contact_requires_matching_organization(self):
        organization = self._create_organization("Recipient Org")
        destination = self._create_destination("BKO")
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=False,
            is_active=True,
        )
        contact = self._create_person(
            organization=organization,
            first_name="Bob",
            last_name="Receiver",
        )

        recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=contact,
            is_active=True,
        )

        self.assertEqual(recipient_contact.recipient_organization_id, recipient_org.id)
        self.assertEqual(recipient_contact.contact_id, contact.id)

    def test_authorized_recipient_contact_enforces_single_default_per_link(self):
        shipper_org = self._create_organization("Ship Org")
        shipper_default = self._create_person(
            organization=shipper_org,
            first_name="Sally",
            last_name="Ship",
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_default,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=False,
            is_active=True,
        )

        recipient_org = self._create_organization("Recipient Org")
        destination = self._create_destination("ABJ")
        recipient_structure = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=False,
            is_active=True,
        )
        primary_contact = self._create_person(
            organization=recipient_org,
            first_name="Dr",
            last_name="Dupont",
        )
        secondary_contact = self._create_person(
            organization=recipient_org,
            first_name="Dr",
            last_name="Martin",
        )
        primary_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_structure,
            contact=primary_contact,
            is_active=True,
        )
        secondary_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_structure,
            contact=secondary_contact,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_structure,
            is_active=True,
        )

        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=primary_recipient_contact,
            is_default=True,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            ShipmentAuthorizedRecipientContact.objects.create(
                link=link,
                recipient_contact=secondary_recipient_contact,
                is_default=True,
                is_active=True,
            )

    def test_authorized_recipient_contact_full_clean_handles_missing_recipient_contact(self):
        shipper_org = self._create_organization("Ship Org Missing Recipient")
        shipper_default = self._create_person(
            organization=shipper_org,
            first_name="Sally",
            last_name="Ship",
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_default,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=False,
            is_active=True,
        )

        recipient_org = self._create_organization("Recipient Org Missing Recipient")
        destination = self._create_destination("BKO-MISS")
        recipient_structure = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=False,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_structure,
            is_active=True,
        )

        with self.assertRaises(ValidationError) as exc:
            ShipmentAuthorizedRecipientContact(
                link=link,
                is_default=True,
                is_active=True,
            ).full_clean()

        self.assertIn("recipient_contact", exc.exception.message_dict)

    def test_recipient_organization_enforces_single_active_correspondent_per_stopover(self):
        destination = self._create_destination("NSI")
        first_org = self._create_organization("First Correspondent")
        second_org = self._create_organization("Second Correspondent")

        ShipmentRecipientOrganization.objects.create(
            organization=first_org,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            ShipmentRecipientOrganization.objects.create(
                organization=second_org,
                destination=destination,
                validation_status=ShipmentValidationStatus.VALIDATED,
                is_correspondent=True,
                is_active=True,
            )
