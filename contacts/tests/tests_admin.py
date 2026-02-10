from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from contacts.admin import ContactAdmin, ContactAdminForm, ContactTagAdminForm
from contacts.models import Contact, ContactTag, ContactType
from wms.models import Destination


class ContactAdminFormTests(TestCase):
    def test_form_init_sets_help_texts(self):
        form = ContactAdminForm()

        self.assertIn("adresse par defaut", form.fields["use_organization_address"].help_text)
        self.assertIn("Laisser vide", form.fields["destination"].help_text)

    def test_clean_requires_tag_for_organization(self):
        form = ContactAdminForm(
            data={
                "contact_type": ContactType.ORGANIZATION,
                "name": "Association Sans Tag",
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("tags", form.errors)
        self.assertIn("Au moins un tag est requis", form.errors["tags"][0])

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
        self.assertIn("Selectionnez une societe", form.errors["organization"][0])

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


class ContactTagAdminFormTests(TestCase):
    def test_form_init_and_clean_asf_prefix(self):
        empty_prefix_form = ContactTagAdminForm(
            data={"name": "donateur", "asf_prefix": "", "asf_last_number": 0}
        )
        self.assertTrue(empty_prefix_form.is_valid())
        self.assertEqual(empty_prefix_form.cleaned_data["asf_prefix"], None)

        normalized_prefix_form = ContactTagAdminForm(
            data={"name": "expediteur", "asf_prefix": " exp ", "asf_last_number": 0}
        )
        self.assertTrue(normalized_prefix_form.is_valid())
        self.assertEqual(normalized_prefix_form.cleaned_data["asf_prefix"], "EXP")
        self.assertIn("Prefix ASF", normalized_prefix_form.fields["asf_prefix"].help_text)


class ContactAdminTests(TestCase):
    def test_destination_foreign_key_uses_only_active_destinations(self):
        correspondent = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
        )
        active_destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=correspondent,
            is_active=False,
        )

        admin_obj = ContactAdmin(Contact, AdminSite())
        request = RequestFactory().get("/admin/contacts/contact/add/")
        db_field = Contact._meta.get_field("destination")

        field = admin_obj.formfield_for_foreignkey(db_field, request)

        self.assertEqual(list(field.queryset), [active_destination])
        self.assertFalse(field.widget.can_add_related)
        self.assertFalse(field.widget.can_change_related)
        self.assertFalse(field.widget.can_delete_related)
