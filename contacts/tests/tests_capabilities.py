from importlib import import_module

from django.apps import apps
from django.db import IntegrityError
from django.test import TestCase

from contacts.models import Contact, ContactType


class ContactCapabilityTests(TestCase):
    def _get_capability_model(self):
        try:
            return apps.get_model("contacts", "ContactCapability")
        except LookupError as exc:
            self.fail(f"ContactCapability model missing: {exc}")

    def _get_capability_type(self):
        try:
            module = import_module("contacts.capabilities")
        except ModuleNotFoundError as exc:
            self.fail(f"contacts.capabilities module missing: {exc}")
        return module.ContactCapabilityType

    def _get_capability_helpers(self):
        try:
            module = import_module("contacts.capabilities")
        except ModuleNotFoundError as exc:
            self.fail(f"contacts.capabilities module missing: {exc}")
        return (
            module.ensure_contact_capability,
            module.active_contacts_for_capability,
            module.active_organizations_for_capability,
        )

    def test_contact_capability_is_unique_per_contact_and_type(self):
        capability_model = self._get_capability_model()
        capability_type = self._get_capability_type()
        contact = Contact.objects.create(
            name="Homeperf Clamart",
            contact_type=ContactType.ORGANIZATION,
        )

        capability_model.objects.create(
            contact=contact,
            capability=capability_type.DONOR,
            is_active=True,
        )

        with self.assertRaises(IntegrityError):
            capability_model.objects.create(
                contact=contact,
                capability=capability_type.DONOR,
                is_active=True,
            )

    def test_capability_helpers_filter_active_contacts_and_organizations(self):
        capability_model = self._get_capability_model()
        capability_type = self._get_capability_type()
        (
            ensure_contact_capability,
            active_contacts_for_capability,
            active_organizations_for_capability,
        ) = self._get_capability_helpers()

        donor_org = Contact.objects.create(
            name="Bastide Nantes",
            contact_type=ContactType.ORGANIZATION,
        )
        donor_person = Contact.objects.create(
            name="Mr Giraud",
            contact_type=ContactType.PERSON,
            first_name="Mr",
            last_name="Giraud",
        )
        inactive_transporter = Contact.objects.create(
            name="DB Schenker",
            contact_type=ContactType.ORGANIZATION,
            is_active=False,
        )

        ensure_contact_capability(donor_org, capability_type.DONOR)
        ensure_contact_capability(donor_person, capability_type.DONOR)
        capability_model.objects.create(
            contact=inactive_transporter,
            capability=capability_type.TRANSPORTER,
            is_active=True,
        )

        self.assertCountEqual(
            active_contacts_for_capability(capability_type.DONOR).values_list("name", flat=True),
            ["Bastide Nantes", "Mr Giraud"],
        )
        self.assertCountEqual(
            active_organizations_for_capability(capability_type.DONOR).values_list(
                "name", flat=True
            ),
            ["Bastide Nantes"],
        )
        self.assertEqual(
            list(
                active_organizations_for_capability(capability_type.TRANSPORTER).values_list(
                    "name", flat=True
                )
            ),
            [],
        )

    def test_ensure_contact_capability_reactivates_existing_row(self):
        capability_model = self._get_capability_model()
        capability_type = self._get_capability_type()
        ensure_contact_capability, _active_contacts, _active_orgs = self._get_capability_helpers()
        contact = Contact.objects.create(
            name="PARRA",
            contact_type=ContactType.PERSON,
            last_name="PARRA",
        )
        capability = capability_model.objects.create(
            contact=contact,
            capability=capability_type.VOLUNTEER,
            is_active=False,
        )

        ensure_contact_capability(contact, capability_type.VOLUNTEER)

        capability.refresh_from_db()
        self.assertTrue(capability.is_active)
