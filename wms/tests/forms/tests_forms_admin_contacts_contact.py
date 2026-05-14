from django.test import TestCase, override_settings

from contacts.models import Contact, ContactType
from wms.forms_admin_contacts_contact import ContactCrudForm
from wms.models import Destination, ShipmentShipper, ShipmentValidationStatus


class ContactCrudFormTests(TestCase):
    def setUp(self):
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=Contact.objects.create(
                name="Correspondant Admin",
                contact_type=ContactType.PERSON,
                first_name="Corr",
                last_name="Admin",
                is_active=True,
            ),
            is_active=True,
        )
        self.shipper_organization = Contact.objects.create(
            name="Aviation Sans Frontieres",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_referent = Contact.objects.create(
            name="Referent ASF",
            contact_type=ContactType.PERSON,
            first_name="Referent",
            last_name="ASF",
            organization=self.shipper_organization,
            is_active=True,
        )
        ShipmentShipper.objects.create(
            organization=self.shipper_organization,
            default_contact=self.shipper_referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

    def test_shipper_requires_organization_and_default_person(self):
        form = ContactCrudForm(data={"business_type": "shipper"})

        self.assertFalse(form.is_valid())
        self.assertIn("organization_name", form.errors)
        self.assertIn("first_name", form.errors)
        self.assertIn("last_name", form.errors)

    def test_recipient_requires_destination_and_allowed_shipper(self):
        form = ContactCrudForm(
            data={
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("destination_id", form.errors)
        self.assertIn("allowed_shipper_ids", form.errors)

    def test_volunteer_requires_person_identity(self):
        form = ContactCrudForm(data={"business_type": "volunteer"})

        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)
        self.assertIn("last_name", form.errors)

    def test_duplicate_review_requires_decision(self):
        form = ContactCrudForm(
            data={
                "business_type": "donor",
                "entity_type": "organization",
                "organization_name": "Donateur Test",
                "duplicate_candidates_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_action", form.errors)

    def test_duplicate_review_requires_target_for_merge(self):
        form = ContactCrudForm(
            data={
                "business_type": "donor",
                "entity_type": "organization",
                "organization_name": "Donateur Test",
                "duplicate_candidates_count": "1",
                "duplicate_action": "replace",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_target_id", form.errors)

    def test_duplicate_review_requires_keep_and_delete_choices_for_merge(self):
        form = ContactCrudForm(
            data={
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "legal_form": "association",
                "beneficiary_count": "120",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": str(self.destination.id),
                "allowed_shipper_ids": [str(self.shipper_organization.id)],
                "duplicate_candidates_count": "1",
                "duplicate_action": "merge",
                "duplicate_target_id": "12",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_keep_choice", form.errors)
        self.assertIn("duplicate_delete_choice", form.errors)

    def test_duplicate_review_rejects_same_keep_and_delete_choice(self):
        form = ContactCrudForm(
            data={
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "legal_form": "association",
                "beneficiary_count": "120",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": str(self.destination.id),
                "allowed_shipper_ids": [str(self.shipper_organization.id)],
                "duplicate_candidates_count": "1",
                "duplicate_action": "replace",
                "duplicate_target_id": "12",
                "duplicate_keep_choice": "existing",
                "duplicate_delete_choice": "existing",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_delete_choice", form.errors)

    def test_accepts_minimal_recipient_payload(self):
        form = ContactCrudForm(
            data={
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "legal_form": "association",
                "beneficiary_count": "120",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": str(self.destination.id),
                "allowed_shipper_ids": [str(self.shipper_organization.id)],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_donor_requires_explicit_nature_choice(self):
        form = ContactCrudForm(
            data={
                "business_type": "donor",
                "organization_name": "Donateur Test",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("entity_type", form.errors)

    def test_partner_requires_explicit_nature_choice(self):
        form = ContactCrudForm(
            data={
                "business_type": "partner",
                "organization_name": "Partenaire Test",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertNotIn("business_type", form.errors)
        self.assertIn("entity_type", form.errors)

    def test_other_requires_explicit_nature_choice(self):
        form = ContactCrudForm(
            data={
                "business_type": "other",
                "organization_name": "Autre Contact Test",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertNotIn("business_type", form.errors)
        self.assertIn("entity_type", form.errors)

    def test_business_type_choices_include_partner_and_other(self):
        form = ContactCrudForm()

        self.assertIn(("partner", "Partenaire"), form.fields["business_type"].choices)
        self.assertIn(("other", "Autre"), form.fields["business_type"].choices)

    def test_asf_id_label_preserves_asf_default(self):
        form = ContactCrudForm()

        self.assertEqual(form.fields["asf_id"].label, "ASF ID")

    @override_settings(CONTACT_IDENTIFIER_LABEL="Contact ref.")
    def test_asf_id_label_uses_installation_reference_label(self):
        form = ContactCrudForm()

        self.assertEqual(form.fields["asf_id"].label, "Contact ref.")

    def test_business_type_choices_are_sorted_alphabetically(self):
        form = ContactCrudForm()

        choices = list(form.fields["business_type"].choices)

        self.assertEqual(choices[0], ("", "Choisir..."))
        labels = [label for value, label in choices[1:]]
        self.assertEqual(labels, sorted(labels, key=lambda value: value.casefold()))

    def test_business_type_choices_can_be_restricted_for_validation_flows(self):
        form = ContactCrudForm(allowed_business_types=("shipper", "recipient"))

        self.assertEqual(
            [value for value, _label in form.fields["business_type"].choices],
            ["", "recipient", "shipper"],
        )

    def test_allowed_shipper_queryset_only_lists_active_shippers(self):
        active_shipper_org = Contact.objects.create(
            name="ASF Active",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        active_shipper_person = Contact.objects.create(
            name="Jean Active",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Active",
            organization=active_shipper_org,
            is_active=True,
        )
        ShipmentShipper.objects.create(
            organization=active_shipper_org,
            default_contact=active_shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        inactive_shipper_org = Contact.objects.create(
            name="ASF Inactive",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        inactive_shipper_person = Contact.objects.create(
            name="Jean Inactive",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Inactive",
            organization=inactive_shipper_org,
            is_active=True,
        )
        ShipmentShipper.objects.create(
            organization=inactive_shipper_org,
            default_contact=inactive_shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=False,
        )
        Contact.objects.create(
            name="Structure Sans Runtime",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        form = ContactCrudForm()

        queryset_names = list(
            form.fields["allowed_shipper_ids"].queryset.values_list("name", flat=True)
        )
        self.assertEqual(queryset_names, ["ASF Active", "Aviation Sans Frontieres"])

    def test_select_widgets_use_shared_select_size_classes(self):
        form = ContactCrudForm()

        self.assertIn("ui-select--md", form.fields["business_type"].widget.attrs["class"])
        self.assertIn("ui-select--lg", form.fields["destination_id"].widget.attrs["class"])
        self.assertIn("ui-select--xl", form.fields["allowed_shipper_ids"].widget.attrs["class"])
