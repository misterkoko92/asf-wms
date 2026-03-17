from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationRecipient,
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact


class PortalRecipientSyncTests(TestCase):
    def setUp(self):
        self.association = Contact.objects.create(
            name="Association Test",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Correspondant",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination_a = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV",
            country="Rep. du Congo",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self.destination_b = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_recipient(self):
        return AssociationRecipient.objects.create(
            association_contact=self.association,
            destination=self.destination_a,
            name="A.S.L.A.V Congo",
            structure_name="A.S.L.A.V Congo",
            emails="recipient@example.org; second@example.org",
            phones="+242061234567; +33600000000",
            address_line1="1 Rue Test",
            city="Brazzaville",
            country="Rep. du Congo",
            is_active=True,
        )

    def test_sync_is_idempotent_for_same_recipient(self):
        recipient = self._create_recipient()

        first = sync_association_recipient_to_contact(recipient)
        second = sync_association_recipient_to_contact(recipient)

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            Contact.objects.filter(
                notes__startswith=f"[Portail association][recipient_id={recipient.id}]"
            ).count(),
            1,
        )
        recipient_assignment = OrganizationRoleAssignment.objects.get(
            organization=first,
            role=OrganizationRole.RECIPIENT,
        )
        shipper_assignment = OrganizationRoleAssignment.objects.get(
            organization=self.association,
            role=OrganizationRole.SHIPPER,
        )
        self.assertTrue(recipient_assignment.is_active)
        self.assertFalse(shipper_assignment.is_active)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=shipper_assignment,
                destination=self.destination_a,
                all_destinations=False,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=self.association,
                recipient_org=first,
                destination=self.destination_a,
                is_active=True,
            ).exists()
        )
        self.assertFalse(first.tags.exists())
        self.assertFalse(first.destinations.exists())
        self.assertFalse(first.linked_shippers.exists())
        self.assertFalse(self.association.tags.exists())
        self.assertFalse(self.association.destinations.exists())

    def test_sync_updates_contact_when_recipient_changes_destination(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)
        recipient.destination = self.destination_b
        recipient.structure_name = "A.S.L.A.V Congo Update"
        recipient.name = "A.S.L.A.V Congo Update"
        recipient.save(update_fields=["destination", "structure_name", "name"])

        updated = sync_association_recipient_to_contact(recipient)
        updated.refresh_from_db()

        self.assertEqual(updated.id, synced.id)
        self.assertEqual(updated.name, "A.S.L.A.V Congo Update")
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=self.association,
                recipient_org=updated,
                destination=self.destination_b,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            RecipientBinding.objects.filter(
                shipper_org=self.association,
                recipient_org=updated,
                destination=self.destination_a,
                is_active=True,
            ).exists()
        )

    def test_sync_deactivates_binding_when_recipient_is_inactive(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)
        recipient.is_active = False
        recipient.save(update_fields=["is_active"])

        updated = sync_association_recipient_to_contact(recipient)

        self.assertEqual(updated.id, synced.id)
        self.assertFalse(
            RecipientBinding.objects.filter(
                shipper_org=self.association,
                recipient_org=updated,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            OrganizationRoleAssignment.objects.get(
                organization=updated,
                role=OrganizationRole.RECIPIENT,
            ).is_active
        )
