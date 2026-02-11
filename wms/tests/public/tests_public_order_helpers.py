from django.test import TestCase

from contacts.models import Contact, ContactAddress
from wms.contact_filters import TAG_SHIPPER
from wms.public_order_helpers import upsert_public_order_contact


class PublicOrderHelpersTests(TestCase):
    def _form_data(self, **overrides):
        data = {
            "association_name": "Association Test",
            "association_email": "asso@example.com",
            "association_phone": "0102030405",
            "association_line1": "1 Rue Test",
            "association_line2": "Bat A",
            "association_postal_code": "75001",
            "association_city": "Paris",
            "association_country": "France",
            "association_contact_id": "",
        }
        data.update(overrides)
        return data

    def test_upsert_creates_contact_with_shipper_tag_and_default_address(self):
        contact = upsert_public_order_contact(
            self._form_data(association_country="")
        )
        self.assertTrue(contact.is_active)
        self.assertEqual(contact.name, "Association Test")
        self.assertEqual(contact.email, "asso@example.com")
        self.assertEqual(contact.phone, "0102030405")
        self.assertTrue(contact.tags.filter(name=TAG_SHIPPER[0]).exists())
        address = contact.addresses.get()
        self.assertTrue(address.is_default)
        self.assertEqual(address.address_line1, "1 Rue Test")
        self.assertEqual(address.country, "France")

    def test_upsert_updates_existing_contact_and_default_address_by_id(self):
        contact = Contact.objects.create(
            name="Association Existing",
            email="old@example.com",
            phone="0000000000",
            is_active=True,
        )
        address = ContactAddress.objects.create(
            contact=contact,
            address_line1="Old Street",
            city="Old City",
            postal_code="11111",
            country="France",
            is_default=True,
        )

        result = upsert_public_order_contact(
            self._form_data(
                association_contact_id=str(contact.id),
                association_name=contact.name,
                association_email="new@example.com",
                association_phone="0999888777",
                association_line1="2 Rue New",
                association_line2="Etage 3",
                association_postal_code="69000",
                association_city="Lyon",
                association_country="Belgique",
            )
        )

        self.assertEqual(result.id, contact.id)
        contact.refresh_from_db()
        address.refresh_from_db()
        self.assertEqual(contact.email, "new@example.com")
        self.assertEqual(contact.phone, "0999888777")
        self.assertEqual(address.address_line1, "2 Rue New")
        self.assertEqual(address.address_line2, "Etage 3")
        self.assertEqual(address.postal_code, "69000")
        self.assertEqual(address.city, "Lyon")
        self.assertEqual(address.country, "Belgique")
        self.assertEqual(address.email, "new@example.com")
        self.assertEqual(address.phone, "0999888777")

    def test_upsert_falls_back_to_name_match_when_contact_id_is_invalid(self):
        contact = Contact.objects.create(
            name="Association Name Match",
            email="keep@example.com",
            is_active=True,
        )

        result = upsert_public_order_contact(
            self._form_data(
                association_contact_id="999999",
                association_name=contact.name,
                association_email="updated@example.com",
                association_phone="0123456789",
                association_line1="3 Rue Name",
            )
        )

        self.assertEqual(result.id, contact.id)
        self.assertEqual(Contact.objects.count(), 1)
        contact.refresh_from_db()
        self.assertEqual(contact.email, "updated@example.com")
        self.assertEqual(contact.phone, "0123456789")
        address = contact.addresses.get()
        self.assertEqual(address.address_line1, "3 Rue Name")

    def test_upsert_ignorés_inactive_contact_id_and_creates_new_contact(self):
        inactive = Contact.objects.create(
            name="Association Inactive",
            is_active=False,
        )

        result = upsert_public_order_contact(
            self._form_data(
                association_contact_id=str(inactive.id),
                association_name="Association New Active",
            )
        )

        self.assertNotEqual(result.id, inactive.id)
        self.assertEqual(Contact.objects.count(), 2)
        self.assertTrue(result.is_active)
        self.assertEqual(result.name, "Association New Active")

    def test_upsert_creates_address_for_existing_contact_without_any_address(self):
        contact = Contact.objects.create(
            name="Association No Address",
            is_active=True,
        )

        result = upsert_public_order_contact(
            self._form_data(
                association_name=contact.name,
                association_line1="7 Rue Added",
                association_country="",
            )
        )

        self.assertEqual(result.id, contact.id)
        self.assertEqual(contact.addresses.count(), 1)
        address = contact.addresses.get()
        self.assertTrue(address.is_default)
        self.assertEqual(address.address_line1, "7 Rue Added")
        self.assertEqual(address.country, "France")

    def test_upsert_does_not_overwrite_contact_email_or_phone_with_empty_values(self):
        contact = Contact.objects.create(
            name="Association Keep Data",
            email="persist@example.com",
            phone="0600000000",
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=contact,
            address_line1="Current Address",
            city="Paris",
            country="France",
            is_default=True,
        )

        result = upsert_public_order_contact(
            self._form_data(
                association_contact_id=str(contact.id),
                association_name=contact.name,
                association_email="",
                association_phone="",
                association_line1="Updated Address",
            )
        )

        self.assertEqual(result.id, contact.id)
        contact.refresh_from_db()
        self.assertEqual(contact.email, "persist@example.com")
        self.assertEqual(contact.phone, "0600000000")
        address = contact.addresses.get()
        self.assertEqual(address.address_line1, "Updated Address")
