from django.test import TestCase

from contacts.capabilities import ContactCapabilityType, ensure_contact_capability
from contacts.models import Contact, ContactType
from wms.admin_contacts_crud import (
    build_admin_contacts_forms,
    handle_contact_deactivation,
    handle_contact_merge,
    handle_contact_submission,
    handle_destination_submission,
)
from wms.models import (
    Destination,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class AdminContactsCrudTests(TestCase):
    def setUp(self):
        self.correspondent_org = Contact.objects.create(
            name="Correspondant Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent_person = Contact.objects.create(
            name="Marie Correspondant",
            contact_type=ContactType.PERSON,
            first_name="Marie",
            last_name="Correspondant",
            organization=self.correspondent_org,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent_person,
            is_active=True,
        )

    def test_build_admin_contacts_forms_prefills_shipper_runtime(self):
        shipper_org = Contact.objects.create(
            name="Aviation Sans Frontieres",
            contact_type=ContactType.ORGANIZATION,
            email="asf@example.com",
            phone="0102030405",
            is_active=True,
        )
        referent = Contact.objects.create(
            name="Jean Dupont",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Dupont",
            organization=shipper_org,
            title="M.",
            is_active=True,
        )
        ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=True,
            is_active=True,
        )

        context = build_admin_contacts_forms(edit_contact_id=shipper_org.id)

        self.assertEqual(context["contact_form_mode"], "edit")
        self.assertEqual(context["editing_contact"], shipper_org)
        self.assertEqual(context["contact_form"].initial["business_type"], "shipper")
        self.assertEqual(context["contact_form"].initial["first_name"], "Jean")
        self.assertTrue(context["contact_form"].initial["can_send_to_all"])

    def test_build_admin_contacts_forms_prefills_recipient_person_context(self):
        recipient_org = Contact.objects.create(
            name="Hopital Abidjan",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_person = Contact.objects.create(
            name="Alice Martin",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Martin",
            organization=recipient_org,
            is_active=True,
            use_organization_address=True,
        )
        recipient_runtime = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_runtime,
            contact=recipient_person,
            is_active=True,
        )

        context = build_admin_contacts_forms(edit_contact_id=recipient_person.id)

        self.assertEqual(context["contact_form"].initial["business_type"], "recipient")
        self.assertEqual(context["contact_form"].initial["organization_name"], recipient_org.name)
        self.assertEqual(context["contact_form"].initial["destination_id"], self.destination.id)

    def test_handle_destination_submission_invalid_form_stays_inline(self):
        outcome = handle_destination_submission(
            {
                "city": "",
                "iata_code": "",
                "country": "",
                "correspondent_contact_id": str(self.correspondent_person.id),
            }
        )

        self.assertFalse(outcome.should_redirect)
        self.assertIsNotNone(outcome.destination_form)
        self.assertTrue(outcome.destination_form.errors)

    def test_handle_destination_submission_validation_error_is_attached_to_form(self):
        Destination.objects.create(
            city="BAMAKO",
            iata_code="BKO",
            country="MALI",
            correspondent_contact=self.correspondent_person,
            is_active=True,
        )

        outcome = handle_destination_submission(
            {
                "city": "BAMAKO",
                "iata_code": "BKO",
                "country": "MALI",
                "correspondent_contact_id": str(self.correspondent_person.id),
                "duplicate_action": "duplicate",
            }
        )

        self.assertFalse(outcome.should_redirect)
        self.assertIn(
            "Un conflit exact empêche la duplication de cette destination.",
            outcome.destination_form.non_field_errors(),
        )

    def test_handle_contact_submission_invalid_form_keeps_create_mode(self):
        outcome = handle_contact_submission(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Test",
                "first_name": "Alice",
                "last_name": "Martin",
            }
        )

        self.assertFalse(outcome.should_redirect)
        self.assertEqual(outcome.contact_form_mode, "create")
        self.assertTrue(outcome.contact_form.errors)

    def test_handle_contact_submission_duplicate_review_in_edit_mode(self):
        donor = Contact.objects.create(
            name="Donateur Lumiere",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source = Contact.objects.create(
            name="Donateur Edit",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        outcome = handle_contact_submission(
            {
                "editing_contact_id": str(source.id),
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Lumiere",
                "is_active": "on",
            }
        )

        self.assertFalse(outcome.should_redirect)
        self.assertEqual(outcome.contact_form_mode, "edit")
        self.assertEqual(outcome.editing_contact, source)
        self.assertEqual(outcome.contact_duplicate_candidates, [donor])

    def test_handle_contact_submission_validation_error_is_attached_to_form(self):
        outcome = handle_contact_submission(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Lumiere",
                "duplicate_action": "replace",
                "duplicate_target_id": "9999",
                "is_active": "on",
            }
        )

        self.assertFalse(outcome.should_redirect)
        self.assertIn("La fiche cible est introuvable.", outcome.contact_form.non_field_errors())

    def test_handle_contact_deactivation_reports_invalid_identifier(self):
        outcome = handle_contact_deactivation({"contact_id": "abc"})

        self.assertTrue(outcome.should_redirect)
        self.assertEqual(outcome.message_level, "error")
        self.assertEqual(outcome.message, "Contact introuvable.")

    def test_handle_contact_merge_reports_missing_target(self):
        source = Contact.objects.create(
            name="Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        outcome = handle_contact_merge(
            {"source_contact_id": str(source.id), "target_contact_id": "999"}
        )

        self.assertTrue(outcome.should_redirect)
        self.assertEqual(outcome.message_level, "error")
        self.assertEqual(outcome.message, "Fiche de fusion introuvable.")

    def test_handle_contact_merge_surfaces_validation_error(self):
        source = Contact.objects.create(
            name="Structure Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        target = Contact.objects.create(
            name="Personne Cible",
            contact_type=ContactType.PERSON,
            first_name="Personne",
            last_name="Cible",
            is_active=True,
        )

        outcome = handle_contact_merge(
            {
                "source_contact_id": str(source.id),
                "target_contact_id": str(target.id),
            }
        )

        self.assertTrue(outcome.should_redirect)
        self.assertEqual(outcome.message_level, "error")
        self.assertIn("du même type", outcome.message)

    def test_handle_contact_merge_success_merges_and_returns_message(self):
        source = Contact.objects.create(
            name="Transporteur Source",
            contact_type=ContactType.ORGANIZATION,
            phone="0102030405",
            is_active=True,
        )
        target = Contact.objects.create(
            name="Transporteur Cible",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ensure_contact_capability(source, ContactCapabilityType.TRANSPORTER)

        outcome = handle_contact_merge(
            {
                "source_contact_id": str(source.id),
                "target_contact_id": str(target.id),
            }
        )

        self.assertTrue(outcome.should_redirect)
        self.assertEqual(outcome.message_level, "success")
        source.refresh_from_db()
        target.refresh_from_db()
        self.assertFalse(source.is_active)
        self.assertEqual(target.phone, "0102030405")

    def test_handle_contact_submission_supports_person_donor_creation_with_new_org(self):
        outcome = handle_contact_submission(
            {
                "business_type": "donor",
                "entity_type": ContactType.PERSON,
                "organization_name": "Structure Support",
                "first_name": "Luc",
                "last_name": "Martin",
                "address_line1": "1 rue de test",
                "city": "Paris",
                "country": "France",
                "is_active": "on",
            }
        )

        self.assertTrue(outcome.should_redirect)
        person = Contact.objects.get(first_name="Luc", last_name="Martin")
        self.assertEqual(person.organization.name, "Structure Support")
        self.assertEqual(person.addresses.count(), 1)
