from unittest import mock

from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.contact_filters import TAG_CORRESPONDENT
from wms.import_services_destinations import (
    _generate_destination_code,
    _get_or_create_destination,
    _parse_destination_label,
    _select_default_correspondent,
    _tags_include_correspondent,
)
from wms.models import Destination


class ImportDestinationsExtraTests(TestCase):
    def test_parse_destination_label_variants(self):
        self.assertEqual(_parse_destination_label(None), (None, None, None))
        self.assertEqual(_parse_destination_label(" "), (None, None, None))
        self.assertEqual(
            _parse_destination_label("Paris (CDG) - France"),
            ("Paris", "CDG", "France"),
        )
        self.assertEqual(
            _parse_destination_label("Lome - Togo"),
            ("Lome", None, "Togo"),
        )
        self.assertEqual(_parse_destination_label("CDG"), (None, "CDG", None))
        self.assertEqual(_parse_destination_label("Nouakchott City"), ("Nouakchott City", None, None))

    def test_generate_destination_code_handles_collisions_and_empty_base(self):
        correspondent = Contact.objects.create(
            name="C1",
            contact_type=ContactType.ORGANIZATION,
        )
        Destination.objects.create(city="D1", iata_code="DEST", country="France", correspondent_contact=correspondent)
        Destination.objects.create(city="D2", iata_code="DEST2", country="France", correspondent_contact=correspondent)
        self.assertEqual(_generate_destination_code("DEST"), "DEST3")
        self.assertEqual(_generate_destination_code(""), "DEST3")

    def test_tags_include_correspondent(self):
        self.assertFalse(_tags_include_correspondent([]))
        tag = ContactTag(name=TAG_CORRESPONDENT[0])
        self.assertTrue(_tags_include_correspondent([tag]))

    def test_select_default_correspondent_prefers_existing_then_creates(self):
        tag = ContactTag.objects.create(name=TAG_CORRESPONDENT[0])
        existing = Contact.objects.create(
            name="Existing Correspondent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        existing.tags.add(tag)
        self.assertEqual(_select_default_correspondent().id, existing.id)

        Contact.objects.all().delete()
        ContactTag.objects.all().delete()
        created = _select_default_correspondent()
        self.assertEqual(created.name, "Correspondant par défaut")
        self.assertTrue(created.tags.filter(name__iexact=TAG_CORRESPONDENT[0]).exists())

    def test_get_or_create_destination_core_paths(self):
        self.assertIsNone(_get_or_create_destination(""))

        tag = ContactTag.objects.create(name=TAG_CORRESPONDENT[0])
        correspondent = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent.tags.add(tag)

        existing_iata = Destination.objects.create(
            city="Paris",
            iata_code="CDG",
            country="France",
            correspondent_contact=correspondent,
        )
        self.assertEqual(
            _get_or_create_destination("Paris (CDG) - France").id,
            existing_iata.id,
        )

        existing_city_country = Destination.objects.create(
            city="Lome",
            iata_code="LFW",
            country="Togo",
            correspondent_contact=correspondent,
        )
        self.assertEqual(
            _get_or_create_destination("Lome - Togo").id,
            existing_city_country.id,
        )

        created_with_contact = _get_or_create_destination(
            "Abidjan (ABJ) - Cote d'Ivoire",
            contact=correspondent,
        )
        self.assertEqual(created_with_contact.correspondent_contact_id, correspondent.id)

    def test_get_or_create_destination_uses_unique_city_and_default_correspondent(self):
        default_corr = Contact.objects.create(
            name="Default Corr",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        existing = Destination.objects.create(
            city="Unique City",
            iata_code="UNI",
            country="France",
            correspondent_contact=default_corr,
        )

        with self.subTest("unique_city_without_country"):
            with mock.patch(
                "wms.import_services_destinations._parse_destination_label",
                return_value=("Unique City", None, None),
            ):
                resolved = _get_or_create_destination("ignored")
            self.assertEqual(resolved.id, existing.id)

        with self.subTest("fallback_to_default_correspondent"):
            contact_without_tag = Contact.objects.create(
                name="NoTag",
                contact_type=ContactType.ORGANIZATION,
            )
            with mock.patch(
                "wms.import_services_destinations._select_default_correspondent",
                return_value=default_corr,
            ):
                created = _get_or_create_destination(
                    "Niamey (NIM) - Niger",
                    contact=contact_without_tag,
                    tags=[],
                )
            self.assertEqual(created.correspondent_contact_id, default_corr.id)

    def test_get_or_create_destination_reuses_existing_resolved_city_country(self):
        default_corr = Contact.objects.create(
            name="Default Corr 2",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        existing = Destination.objects.create(
            city="Fallback City",
            iata_code="FALL",
            country="Fallback Country",
            correspondent_contact=default_corr,
        )

        with mock.patch(
            "wms.import_services_destinations._parse_destination_label",
            return_value=(None, None, None),
        ):
            resolved = _get_or_create_destination(
                "ignored label",
                fallback_city="Fallback City",
                fallback_country="Fallback Country",
            )

        self.assertEqual(resolved.id, existing.id)
