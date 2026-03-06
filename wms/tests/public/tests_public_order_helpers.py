from django.test import TestCase

from contacts.models import Contact, ContactAddress
from wms.models import (
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
)
from wms.public_order_helpers import _resolve_existing_contact, upsert_public_order_contact


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

    def test_upsert_creates_contact_without_legacy_tag_or_address_side_effects(self):
        contact = upsert_public_order_contact(self._form_data(association_country=""))

        self.assertTrue(contact.is_active)
        self.assertEqual(contact.name, "Association Test")
        self.assertEqual(contact.email, "asso@example.com")
        self.assertEqual(contact.phone, "0102030405")
        self.assertEqual(contact.tags.count(), 0)
        self.assertEqual(contact.addresses.count(), 0)

    def test_upsert_updates_existing_contact_by_id_without_mutating_legacy_addresses(self):
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
            email="address-old@example.com",
            phone="0111111111",
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
        self.assertEqual(address.address_line1, "Old Street")
        self.assertEqual(address.city, "Old City")
        self.assertEqual(address.country, "France")
        self.assertEqual(address.email, "address-old@example.com")
        self.assertEqual(address.phone, "0111111111")

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
        self.assertEqual(contact.addresses.count(), 0)

    def test_upsert_ignores_inactive_contact_id_and_creates_new_contact(self):
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
        self.assertEqual(result.tags.count(), 0)
        self.assertEqual(result.addresses.count(), 0)

    def test_upsert_does_not_create_address_for_existing_contact_without_any_address(self):
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
        self.assertEqual(contact.addresses.count(), 0)

    def test_upsert_does_not_overwrite_contact_email_or_phone_with_empty_values(self):
        contact = Contact.objects.create(
            name="Association Keep Data",
            email="persist@example.com",
            phone="0600000000",
            is_active=True,
        )
        address = ContactAddress.objects.create(
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
        address.refresh_from_db()
        self.assertEqual(contact.email, "persist@example.com")
        self.assertEqual(contact.phone, "0600000000")
        self.assertEqual(address.address_line1, "Current Address")

    def test_resolve_existing_contact_returns_none_without_id_or_name(self):
        self.assertIsNone(
            _resolve_existing_contact(
                {
                    "association_contact_id": "",
                    "association_name": "   ",
                }
            )
        )

    def test_upsert_normalizes_active_non_org_contact_and_updates_identity(self):
        contact = Contact.objects.create(
            contact_type="person",
            name="Legacy Person",
            email="legacy@example.com",
            phone="000000",
            is_active=True,
        )

        updated = upsert_public_order_contact(
            self._form_data(
                association_contact_id=str(contact.id),
                association_name="Association Reactivated",
                association_email="reactivated@example.com",
                association_phone="0555666777",
            )
        )

        self.assertEqual(updated.id, contact.id)
        contact.refresh_from_db()
        self.assertEqual(contact.contact_type, "organization")
        self.assertEqual(contact.name, "Association Reactivated")
        self.assertEqual(contact.email, "reactivated@example.com")
        self.assertEqual(contact.phone, "0555666777")

    def test_upsert_updates_org_role_contact_and_activates_assignment(self):
        contact = Contact.objects.create(
            name="Association Role Contact",
            email="role-old@example.com",
            phone="0000",
            is_active=True,
        )
        assignment = OrganizationRoleAssignment.objects.create(
            organization=contact,
            role=OrganizationRole.RECIPIENT,
            is_active=False,
        )
        org_contact = OrganizationContact.objects.create(
            organization=contact,
            first_name="Role",
            last_name="Owner",
            email="role-old@example.com",
            phone="0000",
            is_active=False,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=org_contact,
            is_primary=False,
            is_active=False,
        )

        result = upsert_public_order_contact(
            self._form_data(
                association_name=contact.name,
                association_email="role-new@example.com",
                association_phone="0777888999",
            )
        )

        self.assertEqual(result.id, contact.id)
        assignment.refresh_from_db()
        org_contact.refresh_from_db()
        role_contact = OrganizationRoleContact.objects.get(
            role_assignment=assignment,
            contact=org_contact,
        )
        self.assertTrue(assignment.is_active)
        self.assertEqual(org_contact.email, "role-new@example.com")
        self.assertEqual(org_contact.phone, "0777888999")
        self.assertTrue(org_contact.is_active)
        self.assertTrue(role_contact.is_active)
        self.assertTrue(role_contact.is_primary)
