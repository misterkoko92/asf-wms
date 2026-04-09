from django import forms
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms_admin_contacts_destination import DestinationCrudForm


class DestinationCrudFormTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Destination",
            contact_type=ContactType.PERSON,
            first_name="Correspondant",
            last_name="Destination",
            is_active=True,
        )

    def test_requires_city_iata_and_country(self):
        form = DestinationCrudForm(data={})

        self.assertFalse(form.is_valid())
        self.assertIn("city", form.errors)
        self.assertIn("iata_code", form.errors)
        self.assertIn("country", form.errors)

    def test_accepts_minimal_valid_payload(self):
        form = DestinationCrudForm(
            data={
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "correspondent_contact_id": str(self.correspondent.id),
                "is_active": "1",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_duplicate_decision_when_candidates_are_present(self):
        form = DestinationCrudForm(
            data={
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "duplicate_candidates_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_action", form.errors)

    def test_requires_duplicate_target_for_merge_or_replace(self):
        form = DestinationCrudForm(
            data={
                "city": "ABIDJAN",
                "iata_code": "ABJ",
                "country": "COTE D'IVOIRE",
                "duplicate_candidates_count": "1",
                "duplicate_action": "merge",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("duplicate_target_id", form.errors)

    def test_select_widgets_use_shared_select_size_classes(self):
        form = DestinationCrudForm()

        self.assertIn("ui-select--md", form.fields["country"].widget.attrs["class"])
        self.assertIn(
            "ui-select--lg",
            form.fields["correspondent_contact_id"].widget.attrs["class"],
        )
        self.assertIn("ui-select--md", form.fields["duplicate_action"].widget.attrs["class"])

    def test_country_field_uses_shared_country_choices_sorted_alphabetically(self):
        form = DestinationCrudForm()

        country_field = form.fields["country"]

        self.assertIsInstance(country_field, forms.ChoiceField)
        self.assertEqual(country_field.choices[0], ("", "---------"))
        choice_values = [value for value, _label in country_field.choices[1:]]
        self.assertIn("France", choice_values)
        self.assertIn("Bénin", choice_values)
        self.assertIn("Togo", choice_values)
        self.assertIn("Canada", choice_values)
        self.assertEqual(choice_values, sorted(choice_values, key=lambda value: value.casefold()))
