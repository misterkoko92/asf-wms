from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)


class DefaultShipperBindingsSignalTests(TestCase):
    def _create_default_shipper(self) -> Contact:
        shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_tag, _ = ContactTag.objects.get_or_create(name="expediteur")
        shipper.tags.add(shipper_tag)
        return shipper

    def _create_correspondent(self) -> Contact:
        correspondent = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent_tag, _ = ContactTag.objects.get_or_create(name="correspondant")
        correspondent.tags.add(correspondent_tag)
        return correspondent

    def _create_destination(self, *, iata_code: str, correspondent: Contact) -> Destination:
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_recipient_org(self, name: str) -> Contact:
        recipient = Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_tag, _ = ContactTag.objects.get_or_create(name="destinataire")
        recipient.tags.add(recipient_tag)
        return recipient

    def test_recipient_role_creation_creates_default_shipper_bindings_for_all_destinations(
        self,
    ):
        default_shipper = self._create_default_shipper()
        correspondent = self._create_correspondent()
        destination_a = self._create_destination(iata_code="ABJ", correspondent=correspondent)
        destination_b = self._create_destination(iata_code="DLA", correspondent=correspondent)
        recipient = self._create_recipient_org("Recipient A")

        with self.captureOnCommitCallbacks(execute=True):
            OrganizationRoleAssignment.objects.create(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            )

        shipper_assignment = OrganizationRoleAssignment.objects.filter(
            organization=default_shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        ).first()
        self.assertIsNotNone(shipper_assignment)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=shipper_assignment,
                all_destinations=True,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_a,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_b,
                is_active=True,
            ).exists()
        )

    def test_destination_creation_creates_binding_for_existing_recipients(self):
        default_shipper = self._create_default_shipper()
        correspondent = self._create_correspondent()
        destination_a = self._create_destination(iata_code="BKO", correspondent=correspondent)
        recipient = self._create_recipient_org("Recipient B")

        with self.captureOnCommitCallbacks(execute=True):
            OrganizationRoleAssignment.objects.create(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            )

        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_a,
                is_active=True,
            ).exists()
        )

        with self.captureOnCommitCallbacks(execute=True):
            destination_b = self._create_destination(
                iata_code="CMN",
                correspondent=correspondent,
            )

        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_b,
                is_active=True,
            ).exists()
        )

    def test_no_default_shipper_keeps_bindings_unchanged(self):
        correspondent = self._create_correspondent()
        self._create_destination(iata_code="TNR", correspondent=correspondent)
        recipient = self._create_recipient_org("Recipient C")

        with self.captureOnCommitCallbacks(execute=True):
            OrganizationRoleAssignment.objects.create(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            )

        self.assertEqual(RecipientBinding.objects.count(), 0)
