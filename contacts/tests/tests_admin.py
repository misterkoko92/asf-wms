from django.contrib.admin.sites import AdminSite, site
from django.test import TestCase

from contacts.admin import ContactAdmin, ContactAdminForm
from contacts.models import Contact, ContactType


class ContactAdminFormTests(TestCase):
    def test_form_does_not_expose_legacy_fields(self):
        form = ContactAdminForm()

        self.assertIn("use_organization_address", form.fields)
        self.assertNotIn("destination", form.fields)
        self.assertNotIn("tags", form.fields)
        self.assertNotIn("destinations", form.fields)
        self.assertNotIn("linked_shippers", form.fields)

    def test_form_init_sets_help_texts(self):
        form = ContactAdminForm()

        self.assertIn("adresse par défaut", form.fields["use_organization_address"].help_text)

    def test_clean_requires_organization_when_using_org_address(self):
        form = ContactAdminForm(
            data={
                "contact_type": ContactType.PERSON,
                "name": "Personne A",
                "use_organization_address": "on",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("organization", form.errors)
        self.assertIn("Sélectionnez une société", form.errors["organization"][0])

    def test_clean_valid_person_form(self):
        organization = Contact.objects.create(
            name="Association A",
            contact_type=ContactType.ORGANIZATION,
        )
        form = ContactAdminForm(
            data={
                "contact_type": ContactType.PERSON,
                "name": "Personne B",
                "organization": organization.id,
                "use_organization_address": "on",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid())


class ContactAdminTests(TestCase):
    def test_admin_configuration_does_not_reference_legacy_fields(self):
        admin_obj = ContactAdmin(Contact, AdminSite())

        self.assertNotIn("tags", admin_obj.list_filter)
        self.assertNotIn("destinations", admin_obj.list_filter)
        self.assertNotIn("tags", admin_obj.list_display)
        self.assertNotIn("destinations_display", admin_obj.list_display)
        flattened_fieldsets = {
            field for _, options in admin_obj.fieldsets for field in options.get("fields", ())
        }
        self.assertNotIn("tags", flattened_fieldsets)
        self.assertNotIn("destinations", flattened_fieldsets)
        self.assertNotIn("linked_shippers", flattened_fieldsets)
