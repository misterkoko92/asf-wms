from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
)


class OrganizationRoleModelTests(TestCase):
    def _create_organization(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def test_organization_role_values_cover_expected_roles(self):
        self.assertEqual(
            set(OrganizationRole.values),
            {
                "shipper",
                "recipient",
                "correspondent",
                "donor",
                "transporter",
            },
        )

    def test_role_assignment_requires_single_primary_contact(self):
        organization = self._create_organization("Org Primary")
        assignment = OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        primary_contact = OrganizationContact.objects.create(
            organization=organization,
            first_name="Alice",
            last_name="Primary",
            email="alice@example.org",
            is_active=True,
        )
        second_contact = OrganizationContact.objects.create(
            organization=organization,
            first_name="Bob",
            last_name="Primary",
            email="bob@example.org",
            is_active=True,
        )

        OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=primary_contact,
            is_primary=True,
            is_active=True,
        )

        with self.assertRaises(ValidationError) as exc:
            OrganizationRoleContact.objects.create(
                role_assignment=assignment,
                contact=second_contact,
                is_primary=True,
                is_active=True,
            )
        self.assertIn("__all__", exc.exception.message_dict)

    def test_active_role_requires_primary_contact_with_email(self):
        organization = self._create_organization("Org Active")
        assignment = OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=OrganizationRole.RECIPIENT,
            is_active=False,
        )
        contact = OrganizationContact.objects.create(
            organization=organization,
            first_name="No",
            last_name="Email",
            email="",
            is_active=True,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=contact,
            is_primary=True,
            is_active=True,
        )

        assignment.is_active = True
        with self.assertRaises(ValidationError) as exc:
            assignment.full_clean()
        self.assertIn("is_active", exc.exception.message_dict)

        contact.email = "recipient@example.org"
        contact.save(update_fields=["email"])

        assignment.full_clean()
        assignment.save()
        self.assertTrue(assignment.is_active)
