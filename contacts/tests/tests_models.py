from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactType


class ContactModelsTests(TestCase):
    def test_person_save_builds_name_and_copies_org_default_address(self):
        organization = Contact.objects.create(
            name="Org A",
            contact_type=ContactType.ORGANIZATION,
        )
        ContactAddress.objects.create(
            contact=organization,
            label="Siege",
            address_line1="10 Rue Principale",
            address_line2="Bat A",
            postal_code="75001",
            city="Paris",
            region="IDF",
            country="France",
            is_default=True,
        )

        person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            name="",
            first_name="Alice",
            last_name="Durand",
            organization=organization,
            use_organization_address=True,
        )

        self.assertEqual(person.name, "Alice Durand")

        person_address = person.addresses.get()
        self.assertTrue(person_address.is_default)
        self.assertEqual(person_address.address_line1, "10 Rue Principale")
        self.assertEqual(person_address.address_line2, "Bat A")
        self.assertEqual(person_address.postal_code, "75001")
        self.assertEqual(person_address.city, "Paris")
        self.assertEqual(person_address.region, "IDF")
        self.assertEqual(person_address.country, "France")

        effective_addresses = list(person.get_effective_addresses())
        self.assertEqual(
            [addr.id for addr in effective_addresses], [organization.addresses.get().id]
        )
        self.assertEqual(person.get_effective_address().id, organization.addresses.get().id)

    def test_contact_address_str_and_sync_people_when_org_default_changes(self):
        organization = Contact.objects.create(
            name="Org B",
            contact_type=ContactType.ORGANIZATION,
        )
        person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Bob",
            last_name="Martin",
            organization=organization,
            use_organization_address=True,
        )

        first_org_address = ContactAddress.objects.create(
            contact=organization,
            label="HQ",
            address_line1="1 Rue A",
            city="Paris",
            country="France",
            is_default=True,
        )
        self.assertEqual(str(first_org_address), "HQ - 1 Rue A, Paris")
        self.assertEqual(person.addresses.count(), 1)
        self.assertEqual(person.addresses.get().address_line1, "1 Rue A")

        ContactAddress.objects.create(
            contact=organization,
            label="Depot",
            address_line1="2 Rue B",
            city="Lyon",
            country="France",
            is_default=True,
        )

        person.refresh_from_db()
        synced_address = person.addresses.get()
        self.assertEqual(synced_address.address_line1, "2 Rue B")
        self.assertEqual(synced_address.city, "Lyon")
        self.assertTrue(synced_address.is_default)
        self.assertEqual(person.addresses.count(), 1)

    def test_pre_delete_organization_unlinks_members_and_appends_note_once(self):
        organization = Contact.objects.create(
            name="Org Legacy",
            contact_type=ContactType.ORGANIZATION,
        )
        person_a = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Claire",
            last_name="A",
            organization=organization,
            use_organization_address=True,
            notes="Note initiale",
        )
        person_b = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="David",
            last_name="B",
            organization=organization,
            use_organization_address=True,
            notes="anciennement : Org Legacy",
        )

        organization.delete()

        person_a.refresh_from_db()
        person_b.refresh_from_db()

        self.assertEqual(person_a.organization, None)
        self.assertFalse(person_a.use_organization_address)
        self.assertIn("Note initiale", person_a.notes)
        self.assertIn("anciennement : Org Legacy", person_a.notes)

        self.assertEqual(person_b.organization, None)
        self.assertFalse(person_b.use_organization_address)
        self.assertEqual(person_b.notes, "anciennement : Org Legacy")

    def test_pre_delete_non_organization_contact(self):
        person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Eva",
            last_name="Solo",
        )

        person.delete()

        self.assertFalse(Contact.objects.filter(pk=person.pk).exists())

    def test_contact_str_and_effective_addresses_without_org_proxy(self):
        contact = Contact.objects.create(
            name="Contact Libre",
            contact_type=ContactType.ORGANIZATION,
        )
        address = ContactAddress.objects.create(
            contact=contact,
            address_line1="40 Rue D",
            city="Nantes",
            country="France",
            is_default=True,
        )

        self.assertEqual(str(contact), "Contact Libre")
        self.assertEqual([addr.id for addr in contact.get_effective_addresses()], [address.id])

    def test_asf_id_is_preserved_when_manually_defined(self):
        contact_with_existing_id = Contact.objects.create(
            name="Org Existing",
            contact_type=ContactType.ORGANIZATION,
            asf_id="PFX-9999",
        )
        contact_with_existing_id.refresh_from_db()

        self.assertEqual(contact_with_existing_id.asf_id, "PFX-9999")

    def test_save_with_org_address_flag_but_no_organization_keeps_no_address(self):
        person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="NoOrg",
            last_name="Proxy",
            use_organization_address=True,
            organization=None,
        )

        self.assertEqual(person.name, "NoOrg Proxy")
        self.assertEqual(person.addresses.count(), 0)
