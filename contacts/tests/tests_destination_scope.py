from django.test import TestCase

from contacts.destination_scope import (
    contact_destination_ids,
    contact_primary_destination_id,
    set_contact_destination_scope,
    sync_contact_destination_scope,
)
from contacts.models import Contact, ContactType
from wms.models import Destination


class DestinationScopeTests(TestCase):
    def _create_destination(self, *, suffix):
        correspondent = Contact.objects.create(
            name=f"Correspondant {suffix}",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        return Destination.objects.create(
            city=f"City {suffix}",
            iata_code=f"S{suffix:03d}",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def test_contact_destination_ids_prefers_m2m_scope(self):
        destination_a = self._create_destination(suffix=1)
        destination_b = self._create_destination(suffix=2)
        contact = Contact.objects.create(
            name="Scoped",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination_a,
        )
        contact.destinations.add(destination_b)

        self.assertEqual(contact_destination_ids(contact), [destination_b.id])
        self.assertEqual(contact_primary_destination_id(contact), destination_b.id)

    def test_contact_destination_ids_falls_back_to_legacy_fk(self):
        destination = self._create_destination(suffix=3)
        contact = Contact.objects.create(
            name="Legacy",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination,
        )

        self.assertEqual(contact_destination_ids(contact), [destination.id])
        self.assertEqual(contact_primary_destination_id(contact), destination.id)

    def test_set_contact_destination_scope_updates_legacy_fk(self):
        destination_a = self._create_destination(suffix=4)
        destination_b = self._create_destination(suffix=5)
        contact = Contact.objects.create(
            name="To scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        set_contact_destination_scope(contact=contact, destination_ids=[destination_a.id])
        contact.refresh_from_db()
        self.assertEqual(
            list(contact.destinations.values_list("id", flat=True)),
            [destination_a.id],
        )
        self.assertEqual(contact.destination_id, destination_a.id)

        set_contact_destination_scope(
            contact=contact,
            destination_ids=[destination_a.id, destination_b.id],
        )
        contact.refresh_from_db()
        self.assertEqual(
            sorted(contact.destinations.values_list("id", flat=True)),
            [destination_a.id, destination_b.id],
        )
        self.assertIsNone(contact.destination_id)

    def test_sync_contact_destination_scope_backfills_m2m_from_legacy(self):
        destination = self._create_destination(suffix=6)
        contact = Contact.objects.create(
            name="Backfill",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination,
        )

        sync_contact_destination_scope(contact)
        contact.refresh_from_db()
        self.assertEqual(
            list(contact.destinations.values_list("id", flat=True)),
            [destination.id],
        )
