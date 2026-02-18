from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactTag, ContactType


class ContactModelsTests(TestCase):
    def test_contact_tag_str_and_asf_id_assigned_on_tag_add(self):
        tag = ContactTag.objects.create(
            name="donateur",
            asf_prefix="DON",
            asf_last_number=0,
        )
        organization = Contact.objects.create(
            name="Association Test",
            contact_type=ContactType.ORGANIZATION,
        )

        self.assertEqual(str(tag), "donateur")
        self.assertEqual(organization.asf_id, None)

        organization.tags.add(tag)
        organization.refresh_from_db()
        tag.refresh_from_db()

        self.assertEqual(organization.asf_id, "DON-0001")
        self.assertEqual(tag.asf_last_number, 1)

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
        self.assertEqual([addr.id for addr in effective_addresses], [organization.addresses.get().id])
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

    def test_assign_asf_id_returns_early_for_existing_or_missing_prefix(self):
        prefixed_tag = ContactTag.objects.create(
            name="prefixed",
            asf_prefix="PFX",
            asf_last_number=0,
        )
        contact_with_existing_id = Contact.objects.create(
            name="Org Existing",
            contact_type=ContactType.ORGANIZATION,
            asf_id="PFX-9999",
        )
        contact_with_existing_id.tags.add(prefixed_tag)
        prefixed_tag.refresh_from_db()
        contact_with_existing_id.refresh_from_db()

        self.assertEqual(contact_with_existing_id.asf_id, "PFX-9999")
        self.assertEqual(prefixed_tag.asf_last_number, 0)

        no_prefix_tag = ContactTag.objects.create(name="no-prefix")
        contact_without_prefix = Contact.objects.create(
            name="Org No Prefix",
            contact_type=ContactType.ORGANIZATION,
        )
        contact_without_prefix.tags.add(no_prefix_tag)
        contact_without_prefix.refresh_from_db()

        self.assertEqual(contact_without_prefix.asf_id, None)

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

    def test_recipient_tag_add_auto_links_default_shipper(self):
        shipper_tag = ContactTag.objects.create(name="Expéditeur")
        recipient_tag = ContactTag.objects.create(name="Destinataire")
        default_shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        default_shipper.tags.add(shipper_tag)
        recipient = Contact.objects.create(
            name="Association Dest",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        recipient.tags.add(recipient_tag)

        self.assertEqual(
            list(recipient.linked_shippers.values_list("name", flat=True)),
            ["AVIATION SANS FRONTIERES"],
        )
