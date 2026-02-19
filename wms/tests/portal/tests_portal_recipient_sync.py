from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from contacts.querysets import contacts_with_tags
from contacts.tagging import TAG_RECIPIENT, TAG_SHIPPER
from wms.models import AssociationRecipient, Destination
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
        self.assertTrue(first.destinations.filter(pk=self.destination_a.id).exists())
        self.assertTrue(first.linked_shippers.filter(pk=self.association.id).exists())
        self.assertTrue(
            contacts_with_tags(TAG_RECIPIENT).filter(pk=first.id).exists()
        )
        self.assertTrue(
            contacts_with_tags(TAG_SHIPPER).filter(pk=self.association.id).exists()
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

        self.assertEqual(updated.id, synced.id)
        self.assertEqual(updated.name, "A.S.L.A.V Congo Update")
        self.assertEqual(
            list(updated.destinations.values_list("id", flat=True)),
            [self.destination_b.id],
        )
        self.assertEqual(updated.destination_id, self.destination_b.id)

    def test_sync_reuses_existing_recipient_tag_alias(self):
        ContactTag.objects.create(name="destinataire")
        recipient = self._create_recipient()

        synced = sync_association_recipient_to_contact(recipient)

        self.assertTrue(
            synced.tags.filter(name__iexact=TAG_RECIPIENT[0]).exists()
            or synced.tags.filter(name__iexact="destinataire").exists()
        )
