from django.test import TestCase

from contacts.models import Contact, ContactTag
from wms.contact_filters import (
    TAG_RECIPIENT,
    TAG_SHIPPER,
    contacts_with_tags,
    filter_contacts_for_destination,
)
from wms.models import Destination


class ContactFiltersTests(TestCase):
    def _create_contact(self, name, *, is_active=True, destination=None, tags=()):
        contact = Contact.objects.create(
            name=name,
            is_active=is_active,
            destination=destination,
        )
        for tag_name in tags:
            tag, _ = ContactTag.objects.get_or_create(name=tag_name)
            contact.tags.add(tag)
        return contact

    def test_contacts_with_tags_returns_active_contacts_when_tags_missing(self):
        self._create_contact("Zulu")
        self._create_contact("Alpha")
        self._create_contact("Inactive", is_active=False)

        results = list(contacts_with_tags(None))

        self.assertEqual([item.name for item in results], ["Alpha", "Zulu"])

    def test_filter_contacts_for_destination_returns_input_queryset_when_destination_missing(self):
        destination = Destination.objects.create(
            city="Paris",
            iata_code="CDG-TCF",
            country="France",
            correspondent_contact=self._create_contact("Correspondent"),
        )
        allowed = self._create_contact("Allowed", destination=destination)
        global_contact = self._create_contact("Global", destination=None)
        queryset = Contact.objects.filter(pk__in=[allowed.pk, global_contact.pk]).order_by("name")

        filtered = filter_contacts_for_destination(queryset, None)

        self.assertEqual(list(filtered), [allowed, global_contact])

    def test_contacts_with_tags_matches_accented_shipper_tags(self):
        contact = self._create_contact("Shipper Accent", tags=("expéditeur",))

        results = list(contacts_with_tags(TAG_SHIPPER))

        self.assertEqual(results, [contact])

    def test_contacts_with_tags_matches_whitespace_variant_tags(self):
        contact = self._create_contact("Recipient Spaced", tags=("  destinataire  ",))

        results = list(contacts_with_tags(TAG_RECIPIENT))

        self.assertEqual(results, [contact])
