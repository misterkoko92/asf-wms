from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.application.parties import use_cases
from wms.models import (
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    Product,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceSource,
    RecipientProductPreferenceStatus,
    RecipientStructureDocument,
    RecipientStructureDocumentType,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
)


class PartiesUseCasesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="parties-use-cases-user",
            password="pass1234",  # pragma: allowlist secret
        )
        self.association = Contact.objects.create(
            name="Association V3",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            name="Correspondant V3",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            is_active=True,
            correspondent_contact=self.correspondent,
        )
        self.product = Product.objects.create(name="Gants V3")

    def test_update_recipient_shared_profile_creates_runtime_and_legacy_projection(self):
        result = use_cases.update_recipient_shared_profile(
            association_contact=self.association,
            destination=self.destination,
            structure_name="Hopital V3",
            contact_first_name="Awa",
            contact_last_name="Diallo",
            emails="hopital@example.org",
            phones="+22370000000",
            address_line1="1 Rue V3",
            city="Bamako",
            country="Mali",
            legal_form="association",
            beneficiary_count=42,
            notes="Besoin urgent",
            notify_deliveries=True,
            is_delivery_contact=True,
            persist_projection=True,
        )

        self.assertEqual(result.recipient_organization.destination, self.destination)
        self.assertEqual(result.synced_contact.name, "Hopital V3")
        self.assertEqual(result.shipment_contact.contact.email, "hopital@example.org")
        self.assertIsNotNone(result.legacy_projection)
        self.assertEqual(result.legacy_projection.synced_contact, result.synced_contact)
        self.assertEqual(AssociationRecipient.objects.count(), 1)

    def test_update_recipient_shared_profile_prefers_structure_asf_id_over_exact_name_match(self):
        legacy_structure = Contact.objects.create(
            name="Hopital V3",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=legacy_structure,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        canonical_structure = Contact.objects.create(
            name="Structure Canonique",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            asf_id="ASF-RECIP-001",
        )

        result = use_cases.update_recipient_shared_profile(
            association_contact=self.association,
            destination=self.destination,
            structure_name="Hopital V3",
            structure_asf_id="ASF-RECIP-001",
            contact_first_name="Awa",
            contact_last_name="Diallo",
            emails="hopital@example.org",
            phones="+22370000000",
            address_line1="1 Rue V3",
            city="Bamako",
            country="Mali",
            persist_projection=False,
        )

        self.assertEqual(result.synced_contact, canonical_structure)

    def test_save_recipient_product_preference_upserts_runtime_row(self):
        shared_profile = use_cases.update_recipient_shared_profile(
            association_contact=self.association,
            destination=self.destination,
            structure_name="Hopital Preferences",
            emails="prefs@example.org",
            phones="+22371111111",
            address_line1="2 Rue Preferences",
            city="Bamako",
            country="Mali",
            persist_projection=False,
        )

        first = use_cases.save_recipient_product_preference(
            recipient_organization=shared_profile.recipient_organization,
            product=self.product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=12,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            notes="Demande initiale",
            source=RecipientProductPreferenceSource.PORTAL,
            user=self.user,
        )
        second = use_cases.save_recipient_product_preference(
            recipient_organization=shared_profile.recipient_organization,
            product=self.product,
            status=RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=18,
            period_unit=RecipientProductPreferencePeriodUnit.MONTH,
            notes="Validation scan",
            source=RecipientProductPreferenceSource.SCAN_ADMIN,
            user=self.user,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            RecipientProductPreference.objects.filter(
                recipient_organization=shared_profile.recipient_organization,
                product=self.product,
            ).count(),
            1,
        )
        second.refresh_from_db()
        self.assertEqual(second.status, RecipientProductPreferenceStatus.ALLOWED)
        self.assertEqual(second.quantity_target, 18)
        self.assertEqual(second.period_unit, RecipientProductPreferencePeriodUnit.MONTH)
        self.assertEqual(second.source, RecipientProductPreferenceSource.SCAN_ADMIN)

    def test_upsert_recipient_structure_documents_replaces_same_type_document(self):
        shared_profile = use_cases.update_recipient_shared_profile(
            association_contact=self.association,
            destination=self.destination,
            structure_name="Hopital Documents",
            emails="docs@example.org",
            phones="+22372222222",
            address_line1="3 Rue Documents",
            city="Bamako",
            country="Mali",
            persist_projection=False,
        )

        first_documents = use_cases.upsert_recipient_structure_documents(
            contact=shared_profile.synced_contact,
            files_by_type={
                RecipientStructureDocumentType.REGISTRATION_PROOF: SimpleUploadedFile(
                    "proof-a.pdf",
                    b"%PDF-1.7 first proof",
                )
            },
            uploaded_by=self.user,
        )
        second_documents = use_cases.upsert_recipient_structure_documents(
            contact=shared_profile.synced_contact,
            files_by_type={
                RecipientStructureDocumentType.REGISTRATION_PROOF: SimpleUploadedFile(
                    "proof-b.pdf",
                    b"%PDF-1.7 replacement proof",
                )
            },
            uploaded_by=self.user,
        )

        self.assertEqual(len(first_documents), 1)
        self.assertEqual(len(second_documents), 1)
        self.assertEqual(first_documents[0].pk, second_documents[0].pk)
        self.assertEqual(
            RecipientStructureDocument.objects.filter(
                contact=shared_profile.synced_contact,
                doc_type=RecipientStructureDocumentType.REGISTRATION_PROOF,
            ).count(),
            1,
        )
        second_documents[0].refresh_from_db()
        self.assertEqual(second_documents[0].status, DocumentReviewStatus.PENDING)

    def test_update_runtime_recipient_profile_updates_runtime_projection_and_documents(self):
        shared_profile = use_cases.update_recipient_shared_profile(
            association_contact=self.association,
            destination=self.destination,
            structure_name="Hopital Runtime",
            contact_first_name="Awa",
            contact_last_name="Diallo",
            emails="runtime@example.org",
            phones="+22373333333",
            address_line1="4 Rue Runtime",
            city="Bamako",
            country="Mali",
            notify_deliveries=False,
            is_delivery_contact=False,
            persist_projection=True,
        )

        result = use_cases.update_runtime_recipient_profile(
            recipient_organization=shared_profile.recipient_organization,
            structure_name="Hopital Runtime Updated",
            contact_title="mr",
            contact_first_name="Moussa",
            contact_last_name="Traore",
            email_values=["updated@example.org", "second@example.org"],
            phone_values=["0102030405", "0607080910"],
            address_line1="5 Rue Runtime",
            address_line2="Bat A",
            postal_code="75010",
            city="Paris",
            country="France",
            legal_form="association",
            beneficiary_count=77,
            notes="Updated runtime profile",
            notify_deliveries=True,
            is_delivery_contact=True,
            uploaded_by=self.user,
            files_by_type={
                RecipientStructureDocumentType.REGISTRATION_PROOF: SimpleUploadedFile(
                    "proof.pdf",
                    b"%PDF-1.7 runtime proof",
                )
            },
        )

        organization = result.recipient_organization.organization
        organization.refresh_from_db()
        self.assertEqual(organization.name, "Hopital Runtime Updated")
        self.assertEqual(organization.legal_form, "association")
        self.assertEqual(organization.beneficiary_count, 77)
        self.assertEqual(organization.notes, "Updated runtime profile")
        address = organization.get_effective_address()
        self.assertIsNotNone(address)
        self.assertEqual(address.address_line1, "5 Rue Runtime")
        self.assertEqual(address.address_line2, "Bat A")
        self.assertEqual(address.postal_code, "75010")
        self.assertEqual(address.city, "Paris")
        self.assertEqual(address.country, "France")
        result.shipment_contact.contact.refresh_from_db()
        self.assertEqual(result.shipment_contact.contact.title, "mr")
        self.assertEqual(result.shipment_contact.contact.first_name, "Moussa")
        self.assertEqual(result.shipment_contact.contact.last_name, "Traore")
        self.assertEqual(result.shipment_contact.contact.email, "updated@example.org")
        self.assertEqual(result.shipment_contact.contact.email2, "second@example.org")
        self.assertEqual(result.shipment_contact.contact.phone, "0102030405")
        self.assertEqual(result.shipment_contact.contact.phone2, "0607080910")
        legacy_projection = AssociationRecipient.objects.get(pk=shared_profile.legacy_projection.pk)
        self.assertTrue(legacy_projection.notify_deliveries)
        self.assertTrue(legacy_projection.is_delivery_contact)
        self.assertEqual(
            RecipientStructureDocument.objects.filter(
                contact=organization,
                doc_type=RecipientStructureDocumentType.REGISTRATION_PROOF,
            ).count(),
            1,
        )
