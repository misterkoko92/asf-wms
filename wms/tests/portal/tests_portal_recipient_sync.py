from django.test import TestCase

from contacts.models import Contact, ContactType
from wms import portal_recipient_sync
from wms.models import (
    AssociationRecipient,
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipperScope,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact


class PortalRecipientSyncTests(TestCase):
    def test_module_has_no_marker_based_contact_lookup(self):
        self.assertFalse(hasattr(portal_recipient_sync, "_find_legacy_synced_contact"))
        self.assertFalse(hasattr(portal_recipient_sync, "_find_synced_contact_by_marker"))
        self.assertFalse(hasattr(portal_recipient_sync, "_source_marker"))

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
        recipient.refresh_from_db()

        self.assertEqual(first.id, second.id)
        self.assertEqual(recipient.synced_contact_id, first.id)
        self.assertEqual(Contact.objects.filter(pk=first.id).count(), 1)
        self.assertNotIn("[recipient_id=", first.notes)
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

    def test_sync_updates_contact_when_recipient_changes_destination(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)
        recipient.destination = self.destination_b
        recipient.structure_name = "A.S.L.A.V Congo Update"
        recipient.name = "A.S.L.A.V Congo Update"
        recipient.save(update_fields=["destination", "structure_name", "name"])

        updated = sync_association_recipient_to_contact(recipient)
        updated.refresh_from_db()
        recipient.refresh_from_db()

        self.assertNotEqual(updated.id, synced.id)
        self.assertEqual(recipient.synced_contact_id, updated.id)
        self.assertEqual(updated.name, "A.S.L.A.V Congo Update")
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=updated,
                destination=self.destination_b,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=self.association,
                recipient_org=updated,
                destination=self.destination_b,
                is_active=True,
            ).exists()
        )

    def test_sync_deactivates_binding_when_recipient_is_inactive(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)
        recipient.is_active = False
        recipient.save(update_fields=["is_active"])

        updated = sync_association_recipient_to_contact(recipient)
        recipient.refresh_from_db()

        self.assertEqual(updated.id, synced.id)
        self.assertEqual(recipient.synced_contact_id, synced.id)
        shipper = ShipmentShipper.objects.get(organization=self.association)
        recipient_org = ShipmentRecipientOrganization.objects.get(organization=updated)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        self.assertFalse(link.is_active)
        self.assertFalse(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                is_active=True,
            ).exists()
        )

    def test_sync_switches_default_authorized_contact_when_recipient_contact_changes(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)

        recipient.contact_first_name = "Lucie"
        recipient.contact_last_name = "Martin"
        recipient.emails = "lucie.martin@example.org"
        recipient.save(
            update_fields=[
                "contact_first_name",
                "contact_last_name",
                "emails",
            ]
        )

        updated = sync_association_recipient_to_contact(recipient)

        self.assertEqual(updated.id, synced.id)
        shipper = ShipmentShipper.objects.get(organization=self.association)
        recipient_org = ShipmentRecipientOrganization.objects.get(organization=updated)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        active_defaults = ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_active=True,
            is_default=True,
        ).select_related("recipient_contact__contact")
        self.assertEqual(active_defaults.count(), 1)
        self.assertEqual(
            active_defaults.first().recipient_contact.contact.email,
            "lucie.martin@example.org",
        )
