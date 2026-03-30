from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms import models as wms_models
from wms import portal_recipient_sync
from wms.models import (
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact


class PortalRecipientSyncTests(TestCase):
    def test_module_has_no_marker_based_contact_lookup(self):
        self.assertFalse(hasattr(portal_recipient_sync, "_find_legacy_synced_contact"))
        self.assertFalse(hasattr(portal_recipient_sync, "_find_synced_contact_by_marker"))
        self.assertFalse(hasattr(portal_recipient_sync, "_source_marker"))

    def setUp(self):
        self.association = Contact.objects.create(
            name="Association Test",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Correspondant",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination_a = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV",
            country="Rep. du Congo",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self.destination_b = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_recipient(self):
        payload = {
            "association_contact": self.association,
            "destination": self.destination_a,
            "name": "A.S.L.A.V Congo",
            "structure_name": "A.S.L.A.V Congo",
            "emails": "recipient@example.org; second@example.org",
            "phones": "+242061234567; +33600000000",
            "address_line1": "1 Rue Test",
            "city": "Brazzaville",
            "country": "Rep. du Congo",
            "is_active": True,
        }
        recipient_field_names = {field.name for field in AssociationRecipient._meta.get_fields()}
        if "legal_form" in recipient_field_names:
            payload["legal_form"] = "association"
        if "beneficiary_count" in recipient_field_names:
            payload["beneficiary_count"] = 120
        return AssociationRecipient.objects.create(
            **payload,
        )

    def test_contact_and_portal_recipient_models_expose_structure_compliance_fields(self):
        contact_field_names = {field.name for field in Contact._meta.get_fields()}
        recipient_field_names = {field.name for field in AssociationRecipient._meta.get_fields()}

        self.assertIn("legal_form", contact_field_names)
        self.assertIn("beneficiary_count", contact_field_names)
        self.assertIn("legal_form", recipient_field_names)
        self.assertIn("beneficiary_count", recipient_field_names)

    def test_wms_model_facade_exports_recipient_structure_document_types_and_model(self):
        self.assertTrue(hasattr(wms_models, "RecipientStructureDocumentType"))
        self.assertTrue(hasattr(wms_models, "RecipientStructureDocument"))

    def test_sync_copies_structure_compliance_fields_to_synced_contact(self):
        field_names = {field.name for field in AssociationRecipient._meta.get_fields()}
        if "legal_form" not in field_names or "beneficiary_count" not in field_names:
            self.fail("AssociationRecipient doit exposer legal_form et beneficiary_count.")

        contact_field_names = {field.name for field in Contact._meta.get_fields()}
        if (
            "legal_form" not in contact_field_names
            or "beneficiary_count" not in contact_field_names
        ):
            self.fail("Contact doit exposer legal_form et beneficiary_count.")

        recipient = self._create_recipient()

        synced = sync_association_recipient_to_contact(recipient)
        synced.refresh_from_db()

        self.assertEqual(synced.legal_form, "association")
        self.assertEqual(synced.beneficiary_count, 120)

    def test_recipient_structure_documents_are_unique_per_contact_and_type(self):
        recipient_document_model = getattr(wms_models, "RecipientStructureDocument", None)
        recipient_document_type = getattr(wms_models, "RecipientStructureDocumentType", None)

        self.assertIsNotNone(recipient_document_model)
        self.assertIsNotNone(recipient_document_type)

        contact = Contact.objects.create(
            name="Structure documentée",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_document_model.objects.create(
            contact=contact,
            doc_type=recipient_document_type.REGISTRATION_PROOF,
            status=DocumentReviewStatus.PENDING,
            file=SimpleUploadedFile("registration-proof.pdf", b"%PDF-1.7 proof"),
        )

        with self.assertRaises(IntegrityError):
            recipient_document_model.objects.create(
                contact=contact,
                doc_type=recipient_document_type.REGISTRATION_PROOF,
                status=DocumentReviewStatus.PENDING,
                file=SimpleUploadedFile("registration-proof-duplicate.pdf", b"%PDF-1.7 proof"),
            )

    def test_sync_is_idempotent_for_same_recipient(self):
        recipient = self._create_recipient()

        first = sync_association_recipient_to_contact(recipient)
        second = sync_association_recipient_to_contact(recipient)
        recipient.refresh_from_db()

        self.assertEqual(first.id, second.id)
        self.assertEqual(recipient.synced_contact_id, first.id)
        self.assertEqual(Contact.objects.filter(pk=first.id).count(), 1)
        self.assertNotIn("[recipient_id=", first.notes)
        shipper = ShipmentShipper.objects.get(organization=self.association)
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)
        recipient_organization = ShipmentRecipientOrganization.objects.get(
            organization=first,
            destination=self.destination_a,
        )
        self.assertTrue(recipient_organization.is_active)
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper=shipper,
                recipient_organization=recipient_organization,
                is_active=True,
            ).exists()
        )

    def test_sync_updates_contact_when_recipient_changes_destination(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)
        recipient.destination = self.destination_b
        recipient.structure_name = "A.S.L.A.V Congo Update"
        recipient.name = "A.S.L.A.V Congo Update"
        recipient.save(update_fields=["destination", "structure_name", "name"])

        updated = sync_association_recipient_to_contact(recipient)
        updated.refresh_from_db()
        recipient.refresh_from_db()

        self.assertNotEqual(updated.id, synced.id)
        self.assertEqual(recipient.synced_contact_id, updated.id)
        self.assertEqual(updated.name, "A.S.L.A.V Congo Update")
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=updated,
                destination=self.destination_b,
            ).exists()
        )
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper__organization=self.association,
                recipient_organization__organization=updated,
                recipient_organization__destination=self.destination_b,
                is_active=True,
            ).exists()
        )

    def test_sync_deactivates_binding_when_recipient_is_inactive(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)
        recipient.is_active = False
        recipient.save(update_fields=["is_active"])

        updated = sync_association_recipient_to_contact(recipient)
        recipient.refresh_from_db()

        self.assertEqual(updated.id, synced.id)
        self.assertEqual(recipient.synced_contact_id, synced.id)
        shipper = ShipmentShipper.objects.get(organization=self.association)
        recipient_org = ShipmentRecipientOrganization.objects.get(organization=updated)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        self.assertFalse(link.is_active)
        self.assertFalse(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                is_active=True,
            ).exists()
        )

    def test_sync_switches_default_authorized_contact_when_recipient_contact_changes(self):
        recipient = self._create_recipient()
        synced = sync_association_recipient_to_contact(recipient)

        recipient.contact_first_name = "Lucie"
        recipient.contact_last_name = "Martin"
        recipient.emails = "lucie.martin@example.org"
        recipient.save(
            update_fields=[
                "contact_first_name",
                "contact_last_name",
                "emails",
            ]
        )

        updated = sync_association_recipient_to_contact(recipient)

        self.assertEqual(updated.id, synced.id)
        shipper = ShipmentShipper.objects.get(organization=self.association)
        recipient_org = ShipmentRecipientOrganization.objects.get(organization=updated)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        active_defaults = ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_active=True,
            is_default=True,
        ).select_related("recipient_contact__contact")
        self.assertEqual(active_defaults.count(), 1)
        self.assertEqual(
            active_defaults.first().recipient_contact.contact.email,
            "lucie.martin@example.org",
        )
