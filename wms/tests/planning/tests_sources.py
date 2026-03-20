from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import AssociationProfile, Destination, Shipment, ShipmentStatus
from wms.planning.sources import (
    build_correspondent_reference,
    build_recipient_reference,
    build_shipper_reference,
)


class PlanningSourcesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planning-sources",
            password="pass1234",  # pragma: allowlist secret
        )

    def _create_org(self, name: str, *, email: str = "") -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            email=email,
            is_active=True,
        )

    def _create_person(
        self,
        name: str,
        *,
        organization: Contact,
        email: str = "",
    ) -> Contact:
        first_name, last_name = name.split(" ", 1)
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            email=email,
            is_active=True,
        )

    def _create_shipment(
        self,
        *,
        shipper_contact=None,
        recipient_contact=None,
        correspondent_contact=None,
        destination=None,
    ):
        destination_correspondent = correspondent_contact or self._create_org(
            "Fallback Correspondent"
        )
        destination = destination or Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=destination_correspondent,
            is_active=True,
        )
        return Shipment.objects.create(
            reference=f"EXP-PLAN-{Shipment.objects.count() + 1:03d}",
            status=ShipmentStatus.PACKED,
            shipper_name=shipper_contact.name if shipper_contact else "Shipper Fallback",
            shipper_contact_ref=shipper_contact,
            recipient_name=recipient_contact.name if recipient_contact else "Recipient Fallback",
            recipient_contact_ref=recipient_contact,
            correspondent_name=correspondent_contact.name if correspondent_contact else "",
            correspondent_contact_ref=correspondent_contact,
            destination=destination,
            destination_address="Airport road",
            destination_country=destination.country,
            ready_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            created_by=self.user,
        )

    def test_build_shipper_reference_normalizes_person_contact_to_org(self):
        shipper_org = self._create_org("Association Shipper", email="org@example.com")
        shipper_person = self._create_person(
            "Sam Shipper",
            organization=shipper_org,
            email="sam@example.com",
        )
        profile = AssociationProfile.objects.create(
            user=self.user,
            contact=shipper_org,
            notification_emails="ops@example.com",
        )
        shipment = self._create_shipment(shipper_contact=shipper_person)

        reference = build_shipper_reference(shipment)

        self.assertEqual(reference["contact_id"], shipper_org.id)
        self.assertEqual(reference["contact_name"], "Sam SHIPPER, Association Shipper")
        self.assertEqual(reference["notification_emails"], ["ops@example.com"])
        self.assertEqual(reference["association_profile_id"], profile.id)

    def test_build_recipient_reference_normalizes_person_contact_to_org(self):
        recipient_org = self._create_org("Association Recipient")
        recipient_person = self._create_person(
            "Ana Recipient",
            organization=recipient_org,
            email="ana@example.com",
        )
        shipment = self._create_shipment(recipient_contact=recipient_person)

        reference = build_recipient_reference(shipment)

        self.assertEqual(reference["contact_id"], recipient_org.id)
        self.assertEqual(reference["contact_name"], "Ana RECIPIENT, Association Recipient")

    def test_build_correspondent_reference_normalizes_destination_person_contact(self):
        correspondent_org = self._create_org("Association Correspondent")
        correspondent_person = self._create_person(
            "Cora Correspondent",
            organization=correspondent_org,
            email="cora@example.com",
        )
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA",
            country="CM",
            correspondent_contact=correspondent_person,
            is_active=True,
        )
        shipment = self._create_shipment(destination=destination)

        reference = build_correspondent_reference(shipment)

        self.assertEqual(reference["contact_id"], correspondent_org.id)
        self.assertEqual(reference["contact_name"], "Cora CORRESPONDENT, Association Correspondent")
