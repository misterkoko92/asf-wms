from unittest import mock

from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.import_services_contacts import import_contacts
from wms.import_utils import parse_str as import_parse_str
from wms.models import Destination


class ImportContactsExtraTests(TestCase):
    def test_import_contacts_updates_contact_type_when_lookup_returns_mismatch(self):
        tag = ContactTag.objects.create(name="donateur")
        person = Contact.objects.create(
            name="Mismatch Contact",
            contact_type=ContactType.PERSON,
        )
        real_filter = Contact.objects.filter

        def filter_side_effect(*args, **kwargs):
            if kwargs.get("name__iexact") == "Mismatch Contact" and "contact_type" in kwargs:
                return mock.Mock(first=mock.Mock(return_value=person))
            return real_filter(*args, **kwargs)

        with mock.patch(
            "wms.import_services_contacts.Contact.objects.filter",
            side_effect=filter_side_effect,
        ):
            created, updated, errors, warnings = import_contacts(
                [
                    {
                        "contact_type": "organization",
                        "name": "Mismatch Contact",
                        "tags": "donateur",
                    }
                ]
            )

        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        person.refresh_from_db()
        self.assertEqual(person.contact_type, ContactType.ORGANIZATION)
        self.assertEqual(list(person.tags.values_list("name", flat=True)), [tag.name])

    def test_import_contacts_reports_missing_lookup_name_after_defensive_join(self):
        class TruthyEmptyString(str):
            def __bool__(self):  # pragma: no cover - behavior tested through branch
                return True

        def parse_str_side_effect(value):
            if value == "__truthy_empty__":
                return TruthyEmptyString("")
            return import_parse_str(value)

        with mock.patch(
            "wms.import_services_contacts.parse_str",
            side_effect=parse_str_side_effect,
        ):
            created, updated, errors, warnings = import_contacts(
                [
                    {
                        "contact_type": "person",
                        "first_name": "__truthy_empty__",
                    }
                ]
            )

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["Ligne 2: Nom contact requis."])

    def test_import_contacts_skips_empty_rows(self):
        rows = [
            {"name": "   ", "tags": "   "},
        ]

        created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(Contact.objects.count(), 0)

    def test_import_contacts_reports_missing_required_name_variants(self):
        rows = [
            {"contact_type": "organization"},
            {"contact_type": "person", "email": "person@example.com"},
        ]

        created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(
            errors,
            [
                "Ligne 2: Nom contact requis.",
                "Ligne 3: Nom ou prenom requis pour un individu.",
            ],
        )

    def test_import_contacts_updates_optional_fields_for_existing_contact(self):
        tag = ContactTag.objects.create(name="donateur")
        contact = Contact.objects.create(
            name="Org Optional",
            contact_type=ContactType.ORGANIZATION,
            phone="old-phone",
            asf_id=None,
            is_active=True,
        )
        contact.tags.add(tag)
        rows = [
            {
                "contact_type": "organization",
                "name": "Org Optional",
                "title": "Mme",
                "role": "Responsable",
                "email": "new@example.com",
                "email2": "new2@example.com",
                "phone": "0102030405",
                "phone2": "0607080910",
                "siret": "12345678901234",
                "vat_number": "FR001",
                "legal_registration_number": "RN-42",
                "asf_id": "ASF-100",
                "notes": "note import",
                "is_active": "non",
            }
        ]

        created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        contact.refresh_from_db()
        self.assertEqual(contact.title, "Mme")
        self.assertEqual(contact.role, "Responsable")
        self.assertEqual(contact.email, "new@example.com")
        self.assertEqual(contact.email2, "new2@example.com")
        self.assertEqual(contact.phone, "0102030405")
        self.assertEqual(contact.phone2, "0607080910")
        self.assertEqual(contact.siret, "12345678901234")
        self.assertEqual(contact.vat_number, "FR001")
        self.assertEqual(contact.legal_registration_number, "RN-42")
        self.assertEqual(contact.asf_id, "ASF-100")
        self.assertEqual(contact.notes, "note import")
        self.assertFalse(contact.is_active)

    def test_import_contacts_person_name_normalization_and_company_link_creation(self):
        rows = [
            {
                "contact_type": "person",
                "name": "Dupont",
                "first_name": "Jean",
                "organization": "Org Person",
                "use_organization_address": True,
            }
        ]
        created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)

        person = Contact.objects.get(name="Jean Dupont")
        self.assertEqual(person.contact_type, ContactType.PERSON)
        self.assertEqual(person.first_name, "Jean")
        self.assertEqual(person.last_name, "Dupont")
        self.assertTrue(person.use_organization_address)
        self.assertIsNotNone(person.organization)
        self.assertEqual(person.organization.name, "Org Person")
        self.assertEqual(person.organization.notes, "créé à l'ajout de Contact")

    def test_import_contacts_person_requires_company_when_using_org_address(self):
        rows = [
            {
                "contact_type": "person",
                "first_name": "Alice",
                "last_name": "Smith",
                "use_organization_address": True,
            }
        ]
        created, updated, errors, warnings = import_contacts(rows)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["Ligne 2: Société requise pour utiliser l'adresse."])

    def test_import_contacts_org_tag_requirement_and_name_fallback(self):
        rows_error = [
            {
                "contact_type": "organization",
                "last_name": "Org Last",
            }
        ]
        created, updated, errors, warnings = import_contacts(rows_error)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["Ligne 2: Tag requis pour une societe."])

        rows_ok = [
            {
                "contact_type": "organization",
                "company": "Org Company",
                "tags": "donateur",
            }
        ]
        created, updated, errors, warnings = import_contacts(rows_ok)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertTrue(Contact.objects.filter(name="Org Company").exists())

    def test_import_contacts_updates_destination_and_preserves_existing_asf_id(self):
        tag = ContactTag.objects.create(name="donateur")
        contact = Contact.objects.create(
            name="Org A",
            contact_type=ContactType.ORGANIZATION,
            asf_id="ASF-OLD",
        )
        contact.tags.add(tag)
        correspondent = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
        )
        destination = Destination.objects.create(
            city="Paris",
            iata_code="CDG",
            country="France",
            correspondent_contact=correspondent,
        )
        with mock.patch(
            "wms.import_services_contacts._get_or_create_destination",
            return_value=destination,
        ) as destination_mock:
            rows = [
                {
                    "contact_type": "organization",
                    "name": "Org A",
                    "asf_id": "ASF-NEW",
                    "destination": "Paris (CDG) - France",
                    "tags": "donateur",
                }
            ]
            created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        contact.refresh_from_db()
        self.assertEqual(contact.asf_id, "ASF-OLD")
        self.assertEqual(
            list(contact.destinations.values_list("id", flat=True)),
            [destination.id],
        )
        self.assertEqual(contact.destination_id, destination.id)
        destination_mock.assert_called_once()

    def test_import_contacts_updates_existing_address(self):
        tag = ContactTag.objects.create(name="donateur")
        contact = Contact.objects.create(
            name="Org Addr",
            contact_type=ContactType.ORGANIZATION,
        )
        contact.tags.add(tag)
        address = ContactAddress.objects.create(
            contact=contact,
            label="Old",
            address_line1="1 Rue",
            address_line2="",
            postal_code="75000",
            city="Paris",
            region="OldRegion",
            country="France",
            phone="01",
            email="old@example.com",
            is_default=False,
            notes="old notes",
        )
        rows = [
            {
                "contact_type": "organization",
                "name": "Org Addr",
                "tags": "donateur",
                "address_line1": "1 Rue",
                "postal_code": "75000",
                "city": "Paris",
                "country": "France",
                "address_label": "HQ",
                "region": "NewRegion",
                "address_phone": "02",
                "address_email": "new@example.com",
                "address_notes": "new notes",
                "address_is_default": True,
            }
        ]
        created, updated, errors, warnings = import_contacts(rows)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(ContactAddress.objects.count(), 1)
        address.refresh_from_db()
        self.assertEqual(address.label, "HQ")
        self.assertEqual(address.region, "NewRegion")
        self.assertEqual(address.phone, "02")
        self.assertEqual(address.email, "new@example.com")
        self.assertEqual(address.notes, "new notes")
        self.assertTrue(address.is_default)

    def test_import_contacts_creates_new_address_and_reports_invalid_bool(self):
        rows = [
            {
                "contact_type": "organization",
                "name": "Org New Address",
                "tags": "donateur",
                "address_line1": "2 Rue",
                "city": "Lyon",
                "postal_code": "69000",
                "country": "France",
                "address_is_default": "yes",
            },
            {
                "contact_type": "organization",
                "name": "Org Bad Bool",
                "tags": "donateur",
                "is_active": "maybe",
            },
        ]
        created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["Ligne 3: Invalid boolean value: maybe"])
        contact = Contact.objects.get(name="Org New Address")
        self.assertEqual(contact.addresses.count(), 1)
        self.assertTrue(contact.addresses.first().is_default)

    def test_import_contacts_supports_multi_destinations_column(self):
        tag = ContactTag.objects.create(name="donateur")
        contact = Contact.objects.create(
            name="Org Multi Dest",
            contact_type=ContactType.ORGANIZATION,
        )
        contact.tags.add(tag)
        correspondent = Contact.objects.create(
            name="Correspondent Dest",
            contact_type=ContactType.ORGANIZATION,
        )
        destination_paris = Destination.objects.create(
            city="Paris",
            iata_code="CDG2",
            country="France",
            correspondent_contact=correspondent,
        )
        destination_lome = Destination.objects.create(
            city="Lome",
            iata_code="LFW2",
            country="Togo",
            correspondent_contact=correspondent,
        )
        with mock.patch(
            "wms.import_services_contacts._get_or_create_destination",
            side_effect=[destination_paris, destination_lome],
        ) as destination_mock:
            rows = [
                {
                    "contact_type": "organization",
                    "name": "Org Multi Dest",
                    "tags": "donateur",
                    "destinations": "Paris (CDG2) - France|Lome (LFW2) - Togo",
                }
            ]
            created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        contact.refresh_from_db()
        self.assertEqual(
            set(contact.destinations.values_list("id", flat=True)),
            {destination_paris.id, destination_lome.id},
        )
        self.assertIsNone(contact.destination_id)
        self.assertEqual(destination_mock.call_count, 2)

    def test_import_contacts_sets_linked_shippers_from_column(self):
        recipient_tag = ContactTag.objects.create(name="destinataire")
        existing_shipper = Contact.objects.create(
            name="Shipper Existing",
            contact_type=ContactType.ORGANIZATION,
        )
        rows = [
            {
                "contact_type": "organization",
                "name": "Recipient Linked Import",
                "tags": "destinataire",
                "linked_shippers": "Shipper Existing|Shipper Created",
            }
        ]

        created, updated, errors, warnings = import_contacts(rows)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        recipient = Contact.objects.get(name="Recipient Linked Import")
        self.assertTrue(recipient.tags.filter(pk=recipient_tag.pk).exists())
        self.assertEqual(
            set(recipient.linked_shippers.values_list("name", flat=True)),
            {"Shipper Existing", "Shipper Created"},
        )
        created_shipper = Contact.objects.get(name="Shipper Created")
        self.assertTrue(
            created_shipper.tags.filter(name__iexact="expediteur").exists()
        )
