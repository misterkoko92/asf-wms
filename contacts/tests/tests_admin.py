from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from contacts.admin import ContactAdmin, ContactAdminForm, ContactTagAdminForm
from contacts.models import Contact, ContactTag, ContactType
from wms.models import Destination


class ContactAdminFormTests(TestCase):
    def test_form_init_sets_help_texts(self):
        form = ContactAdminForm()

        self.assertIn("adresse par défaut", form.fields["use_organization_address"].help_text)
        self.assertIn("Sélection multiple", form.fields["destinations"].help_text)
        self.assertIn("destinataires", form.fields["linked_shippers"].help_text)

    def test_form_init_prefills_default_shipper_for_new_contact(self):
        shipper_tag = ContactTag.objects.create(name="Expéditeur")
        default_shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        default_shipper.tags.add(shipper_tag)

        form = ContactAdminForm()

        self.assertEqual(form.fields["linked_shippers"].initial, [default_shipper.pk])

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

    def test_clean_requires_linked_shipper_for_new_recipient(self):
        recipient_tag = ContactTag.objects.create(name="Destinataire")
        form = ContactAdminForm(
            data={
                "contact_type": ContactType.ORGANIZATION,
                "name": "Destinataire Sans Expediteur",
                "tags": [recipient_tag.id],
                "linked_shippers": [],
                "is_active": "on",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("linked_shippers", form.errors)
        self.assertIn("expéditeur lié", form.errors["linked_shippers"][0].lower())

    def test_save_adds_default_shipper_for_recipient(self):
        shipper_tag = ContactTag.objects.create(name="Expéditeur")
        recipient_tag = ContactTag.objects.create(name="Destinataire")
        default_shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        default_shipper.tags.add(shipper_tag)
        extra_shipper = Contact.objects.create(
            name="Expediteur Local",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        extra_shipper.tags.add(shipper_tag)
        form = ContactAdminForm(
            data={
                "contact_type": ContactType.ORGANIZATION,
                "name": "Destinataire Lie",
                "tags": [recipient_tag.id],
                "linked_shippers": [extra_shipper.id],
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid())
        recipient = form.save()

        self.assertEqual(
            set(recipient.linked_shippers.values_list("id", flat=True)),
            {default_shipper.id, extra_shipper.id},
        )

    def test_save_commit_false_then_save_m2m_adds_default_shipper_for_recipient(self):
        shipper_tag = ContactTag.objects.create(name="Expéditeur")
        recipient_tag = ContactTag.objects.create(name="Destinataire")
        default_shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        default_shipper.tags.add(shipper_tag)
        extra_shipper = Contact.objects.create(
            name="Expediteur 2",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        extra_shipper.tags.add(shipper_tag)
        form = ContactAdminForm(
            data={
                "contact_type": ContactType.ORGANIZATION,
                "name": "Destinataire Lie 2",
                "tags": [recipient_tag.id],
                "linked_shippers": [extra_shipper.id],
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid())
        recipient = form.save(commit=False)
        recipient.save()
        form.save_m2m()

        self.assertEqual(
            set(recipient.linked_shippers.values_list("id", flat=True)),
            {default_shipper.id, extra_shipper.id},
        )


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
    def test_admin_excludes_single_destination_field(self):
        admin_obj = ContactAdmin(Contact, AdminSite())

        self.assertIn("destination", admin_obj.exclude)

    def test_destinations_many_to_many_uses_only_active_destinations(self):
        correspondent = Contact.objects.create(
            name="Correspondent Multi",
            contact_type=ContactType.ORGANIZATION,
        )
        active_destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )
        Destination.objects.create(
            city="Lome",
            iata_code="LFW",
            country="Togo",
            correspondent_contact=correspondent,
            is_active=False,
        )

        admin_obj = ContactAdmin(Contact, AdminSite())
        request = RequestFactory().get("/admin/contacts/contact/add/")
        db_field = Contact._meta.get_field("destinations")

        field = admin_obj.formfield_for_manytomany(db_field, request)

        self.assertEqual(list(field.queryset), [active_destination])
        self.assertFalse(field.widget.can_add_related)
        self.assertFalse(field.widget.can_change_related)
        self.assertFalse(field.widget.can_delete_related)

    def test_destinations_display_returns_global_when_none_selected(self):
        admin_obj = ContactAdmin(Contact, AdminSite())
        contact = Contact.objects.create(
            name="Association Globale",
            contact_type=ContactType.ORGANIZATION,
        )

        self.assertEqual(admin_obj.destinations_display(contact), "Global")
