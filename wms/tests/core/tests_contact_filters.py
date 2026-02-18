from django.test import TestCase

from contacts.models import Contact, ContactTag
from wms.contact_filters import (
    TAG_RECIPIENT,
    TAG_SHIPPER,
    contacts_with_tags,
    filter_contacts_for_destination,
    filter_recipients_for_shipper,
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

    def test_filter_contacts_for_destination_returns_only_global_when_destination_missing(self):
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

        self.assertEqual(list(filtered), [global_contact])

    def test_contacts_with_tags_matches_accented_shipper_tags(self):
        contact = self._create_contact("Shipper Accent", tags=("expéditeur",))

        results = list(contacts_with_tags(TAG_SHIPPER))

        self.assertEqual(results, [contact])

    def test_contacts_with_tags_matches_whitespace_variant_tags(self):
        contact = self._create_contact("Recipient Spaced", tags=("  destinataire  ",))

        results = list(contacts_with_tags(TAG_RECIPIENT))

        self.assertEqual(results, [contact])

    def test_filter_contacts_for_destination_supports_multi_destination_scope(self):
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=self._create_contact("Correspondent ABJ"),
        )
        scoped = self._create_contact("Scoped Multi")
        scoped.destinations.add(destination)
        queryset = Contact.objects.filter(pk=scoped.pk)

        filtered = filter_contacts_for_destination(queryset, destination)

        self.assertEqual(list(filtered), [scoped])

    def test_filter_contacts_for_destination_includes_global_and_matching_multi_only(self):
        destination = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV",
            country="Rep. du Congo",
            correspondent_contact=self._create_contact("Correspondent BZV"),
        )
        other_destination = Destination.objects.create(
            city="Lome",
            iata_code="LFW",
            country="Togo",
            correspondent_contact=self._create_contact("Correspondent LFW"),
        )
        global_contact = self._create_contact("Global")
        scoped_ok = self._create_contact("Scoped OK")
        scoped_ok.destinations.add(destination)
        scoped_other = self._create_contact("Scoped Other")
        scoped_other.destinations.add(other_destination)

        queryset = Contact.objects.filter(
            pk__in=[global_contact.pk, scoped_ok.pk, scoped_other.pk]
        ).order_by("name")

        filtered = filter_contacts_for_destination(queryset, destination)

        self.assertEqual(list(filtered), [global_contact, scoped_ok])

    def test_filter_contacts_for_destination_supports_legacy_single_destination(self):
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA",
            country="Cameroun",
            correspondent_contact=self._create_contact("Correspondent DLA"),
        )
        legacy_only = self._create_contact("Legacy Scoped", destination=destination)
        queryset = Contact.objects.filter(pk=legacy_only.pk)

        filtered = filter_contacts_for_destination(queryset, destination)

        self.assertEqual(list(filtered), [legacy_only])

    def test_filter_recipients_for_shipper_includes_global_and_explicit_links(self):
        shipper_a = self._create_contact("Shipper A", tags=("expediteur",))
        shipper_b = self._create_contact("Shipper B", tags=("expediteur",))
        global_recipient = self._create_contact(
            "Recipient Global",
            tags=("destinataire",),
        )
        linked_recipient = self._create_contact(
            "Recipient Linked",
            tags=("destinataire",),
        )
        linked_recipient.linked_shippers.add(shipper_a)
        other_recipient = self._create_contact(
            "Recipient Other",
            tags=("destinataire",),
        )
        other_recipient.linked_shippers.add(shipper_b)

        queryset = Contact.objects.filter(
            pk__in=[global_recipient.pk, linked_recipient.pk, other_recipient.pk]
        ).order_by("name")
        filtered = filter_recipients_for_shipper(queryset, shipper_a)

        self.assertEqual(list(filtered), [global_recipient, linked_recipient])
