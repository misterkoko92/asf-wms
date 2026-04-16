from django.test import TestCase

from contacts.capabilities import ContactCapabilityType
from contacts.models import Contact, ContactCapability, ContactType
from wms.admin_contacts_contact_service import (
    build_contact_duplicate_candidates,
    deactivate_contact,
    save_contact_from_form,
)
from wms.models import (
    AssociationRecipient,
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class AdminContactsContactServiceTests(TestCase):
    def setUp(self):
        self.correspondent = Contact.objects.create(
            name="Correspondant Service",
            contact_type=ContactType.PERSON,
            first_name="Corr",
            last_name="Service",
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )

    def _create_shipper(self, *, organization_name="ASF", first_name="Jean", last_name="Dupont"):
        return save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": organization_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{organization_name.lower().replace(' ', '-')}@example.org",
                "is_active": True,
            }
        )

    def _create_recipient(
        self,
        *,
        shipper_org,
        organization_name,
        first_name,
        last_name,
        email="",
        phone="",
    ):
        return save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": organization_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "is_active": True,
            }
        )

    def test_create_donor_adds_capability(self):
        contact = save_contact_from_form(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Lumiere",
                "is_active": True,
            }
        )

        self.assertEqual(contact.contact_type, ContactType.ORGANIZATION)
        self.assertTrue(
            ContactCapability.objects.filter(
                contact=contact,
                capability=ContactCapabilityType.DONOR,
                is_active=True,
            ).exists()
        )

    def test_create_partner_adds_capability(self):
        contact = save_contact_from_form(
            {
                "business_type": "partner",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Partenaire Lumiere",
                "is_active": True,
            }
        )

        self.assertEqual(contact.contact_type, ContactType.ORGANIZATION)
        self.assertTrue(
            ContactCapability.objects.filter(
                contact=contact,
                capability=ContactCapabilityType.PARTNER,
                is_active=True,
            ).exists()
        )

    def test_create_other_adds_capability(self):
        contact = save_contact_from_form(
            {
                "business_type": "other",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Autre Contact Historique",
                "is_active": True,
            }
        )

        self.assertEqual(contact.contact_type, ContactType.ORGANIZATION)
        self.assertTrue(
            ContactCapability.objects.filter(
                contact=contact,
                capability=ContactCapabilityType.OTHER,
                is_active=True,
            ).exists()
        )

    def test_create_shipper_creates_organization_person_and_runtime(self):
        organization = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "Aviation Sans Frontieres",
                "first_name": "Jean",
                "last_name": "Dupont",
                "email": "jean@example.com",
                "phone": "0102030405",
                "is_active": True,
            }
        )

        shipper = ShipmentShipper.objects.get(organization=organization)
        self.assertEqual(shipper.default_contact.organization, organization)
        self.assertEqual(shipper.default_contact.first_name, "Jean")

    def test_create_recipient_creates_runtime_links_and_default_authorization(self):
        shipper_org = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF",
                "first_name": "Jean",
                "last_name": "Dupont",
                "is_active": True,
            }
        )

        organization = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "is_active": True,
            }
        )

        recipient_org = ShipmentRecipientOrganization.objects.get(organization=organization)
        recipient_contact = ShipmentRecipientContact.objects.get(
            recipient_organization=recipient_org
        )
        shipper = ShipmentShipper.objects.get(organization=shipper_org)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        authorization = ShipmentAuthorizedRecipientContact.objects.get(
            link=link,
            recipient_contact=recipient_contact,
        )
        self.assertTrue(authorization.is_default)
        self.assertTrue(authorization.is_active)

    def test_create_recipient_persists_structure_compliance_fields(self):
        shipper_org = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF",
                "first_name": "Jean",
                "last_name": "Dupont",
                "is_active": True,
            }
        )

        organization = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "is_active": True,
            }
        )

        organization.refresh_from_db()
        self.assertEqual(organization.legal_form, "association")
        self.assertEqual(organization.beneficiary_count, 120)

    def test_edit_existing_recipient_overwrites_shared_fields_and_refreshes_projection(self):
        shipper_org = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF",
                "first_name": "Jean",
                "last_name": "Dupont",
                "is_active": True,
            }
        )
        organization = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Alice",
                "last_name": "Martin",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "is_active": True,
            }
        )
        legacy_projection = AssociationRecipient.objects.create(
            association_contact=shipper_org,
            synced_contact=organization,
            destination=self.destination,
            name="Hopital Abidjan",
            structure_name="Hopital Abidjan",
            contact_first_name="Alice",
            contact_last_name="Martin",
            legal_form="association",
            beneficiary_count=120,
            address_line1="1 Rue Source",
            city="Abidjan",
            country="COTE D'IVOIRE",
            is_active=True,
        )

        updated = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan Renove",
                "first_name": "Aicha",
                "last_name": "Traore",
                "email": "aicha.traore@example.com",
                "phone": "+33111111111",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "public_sector",
                "beneficiary_count": 250,
                "address_line1": "20 Avenue Renovee",
                "city": "Abidjan",
                "country": "COTE D'IVOIRE",
                "is_active": True,
            },
            editing_contact=organization,
        )

        organization.refresh_from_db()
        legacy_projection.refresh_from_db()
        self.assertEqual(updated.id, organization.id)
        self.assertEqual(organization.name, "Hopital Abidjan Renove")
        self.assertEqual(organization.legal_form, "public_sector")
        self.assertEqual(organization.beneficiary_count, 250)
        self.assertEqual(legacy_projection.structure_name, "Hopital Abidjan Renove")
        self.assertEqual(legacy_projection.contact_first_name, "Aicha")
        self.assertEqual(legacy_projection.contact_last_name, "Traore")

    def test_create_correspondent_marks_stopover_and_destination_contact(self):
        organization = save_contact_from_form(
            {
                "business_type": "correspondent",
                "organization_name": "Correspondant ASF ABJ",
                "first_name": "Marie",
                "last_name": "Dupont",
                "destination_id": self.destination.id,
                "is_active": True,
            }
        )

        recipient_org = ShipmentRecipientOrganization.objects.get(organization=organization)
        self.destination.refresh_from_db()
        self.assertTrue(recipient_org.is_correspondent)
        self.assertEqual(self.destination.correspondent_contact.organization, organization)

    def test_replace_existing_contact_overwrites_master_fields(self):
        organization = Contact.objects.create(
            name="Donateur Lumiere",
            contact_type=ContactType.ORGANIZATION,
            email="old@example.com",
            is_active=False,
        )

        updated = save_contact_from_form(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Lumiere",
                "email": "new@example.com",
                "duplicate_action": "replace",
                "duplicate_target_id": organization.id,
                "is_active": True,
            }
        )

        organization.refresh_from_db()
        self.assertEqual(updated.id, organization.id)
        self.assertEqual(organization.email, "new@example.com")
        self.assertTrue(organization.is_active)

    def test_merge_existing_contact_fills_missing_fields_without_overwrite(self):
        organization = Contact.objects.create(
            name="Transporteur Soleil",
            contact_type=ContactType.ORGANIZATION,
            email="existing@example.com",
            phone="",
            is_active=True,
        )

        merged = save_contact_from_form(
            {
                "business_type": "transporter",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Transporteur Soleil",
                "email": "new@example.com",
                "phone": "0102030405",
                "duplicate_action": "merge",
                "duplicate_target_id": organization.id,
                "is_active": True,
            }
        )

        organization.refresh_from_db()
        self.assertEqual(merged.id, organization.id)
        self.assertEqual(organization.email, "existing@example.com")
        self.assertEqual(organization.phone, "0102030405")

    def test_deactivate_contact_sets_is_active_false(self):
        organization = save_contact_from_form(
            {
                "business_type": "donor",
                "entity_type": ContactType.ORGANIZATION,
                "organization_name": "Donateur Test",
                "is_active": True,
            }
        )

        deactivate_contact(organization)

        organization.refresh_from_db()
        self.assertFalse(organization.is_active)

    def test_build_duplicate_candidates_returns_existing_primary_contact(self):
        organization = Contact.objects.create(
            name="Hopital Saint Joseph",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        candidates = build_contact_duplicate_candidates(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Saint-Joseph",
            }
        )

        self.assertEqual(candidates, [organization])

    def test_merge_duplicate_recipient_can_keep_existing_contact(self):
        shipper_org = self._create_shipper()
        existing = self._create_recipient(
            shipper_org=shipper_org,
            organization_name="Hopital Abidjan",
            first_name="Alice",
            last_name="Existing",
            email="existing@example.org",
        )
        source = self._create_recipient(
            shipper_org=shipper_org,
            organization_name="Hopital Abidjan",
            first_name="Aicha",
            last_name="Source",
            phone="+33102030405",
        )
        ShipmentRecipientOrganization.objects.filter(organization=source).update(
            validation_status=ShipmentValidationStatus.PENDING
        )

        resolved = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Aicha",
                "last_name": "Source",
                "phone": "+33102030405",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "duplicate_action": "merge",
                "duplicate_target_id": existing.id,
                "duplicate_keep_choice": "existing",
                "duplicate_delete_choice": "new",
                "is_active": True,
            },
            editing_contact=source,
        )

        existing.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(resolved.id, existing.id)
        self.assertEqual(existing.email, "existing@example.org")
        self.assertEqual(existing.phone, "+33102030405")
        self.assertFalse(source.is_active)
        self.assertFalse(
            ShipmentRecipientOrganization.objects.filter(
                organization=source,
                destination=self.destination,
            ).exists()
        )
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=existing,
                destination=self.destination,
                is_active=True,
            ).exists()
        )

    def test_replace_duplicate_recipient_keeps_existing_without_overwriting_fields(self):
        shipper_org = self._create_shipper()
        existing = self._create_recipient(
            shipper_org=shipper_org,
            organization_name="Hopital Abidjan",
            first_name="Alice",
            last_name="Existing",
            email="existing@example.org",
        )
        source = self._create_recipient(
            shipper_org=shipper_org,
            organization_name="Hopital Abidjan",
            first_name="Aicha",
            last_name="Source",
            email="source@example.org",
        )

        resolved = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Aicha",
                "last_name": "Source",
                "email": "changed@example.org",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "duplicate_action": "replace",
                "duplicate_target_id": existing.id,
                "duplicate_keep_choice": "existing",
                "duplicate_delete_choice": "new",
                "is_active": True,
            },
            editing_contact=source,
        )

        existing.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(resolved.id, existing.id)
        self.assertEqual(existing.email, "existing@example.org")
        self.assertFalse(source.is_active)

    def test_duplicate_recipient_renames_new_contact_before_validation(self):
        shipper_org = self._create_shipper()
        self._create_recipient(
            shipper_org=shipper_org,
            organization_name="Hopital Abidjan",
            first_name="Alice",
            last_name="Existing",
        )
        source = self._create_recipient(
            shipper_org=shipper_org,
            organization_name="Hopital Abidjan",
            first_name="Aicha",
            last_name="Source",
        )

        resolved = save_contact_from_form(
            {
                "business_type": "recipient",
                "organization_name": "Hopital Abidjan",
                "first_name": "Aicha",
                "last_name": "Source",
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_org.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "duplicate_action": "duplicate",
                "is_active": True,
            },
            editing_contact=source,
        )

        source.refresh_from_db()
        self.assertEqual(resolved.id, source.id)
        self.assertTrue(source.is_active)
        self.assertEqual(source.name, "Hopital Abidjan - doublon")

    def test_merge_duplicate_shipper_can_keep_existing_contact(self):
        existing = self._create_shipper(
            organization_name="ASF Doublon",
            first_name="Alice",
            last_name="Existing",
        )
        existing.email = "existing@example.org"
        existing.save(update_fields=["email"])
        source = self._create_shipper(
            organization_name="ASF Doublon",
            first_name="Aicha",
            last_name="Source",
        )

        resolved = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF Doublon",
                "first_name": "Aicha",
                "last_name": "Source",
                "phone": "+33102030405",
                "duplicate_action": "merge",
                "duplicate_target_id": existing.id,
                "duplicate_keep_choice": "existing",
                "duplicate_delete_choice": "new",
                "is_active": True,
            },
            editing_contact=source,
        )

        existing.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(resolved.id, existing.id)
        self.assertEqual(existing.email, "existing@example.org")
        self.assertEqual(existing.phone, "+33102030405")
        self.assertFalse(source.is_active)

    def test_replace_duplicate_shipper_keeps_existing_without_overwriting_fields(self):
        existing = self._create_shipper(
            organization_name="ASF Doublon",
            first_name="Alice",
            last_name="Existing",
        )
        existing.email = "existing@example.org"
        existing.save(update_fields=["email"])
        source = self._create_shipper(
            organization_name="ASF Doublon",
            first_name="Aicha",
            last_name="Source",
        )

        resolved = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF Doublon",
                "first_name": "Aicha",
                "last_name": "Source",
                "email": "changed@example.org",
                "duplicate_action": "replace",
                "duplicate_target_id": existing.id,
                "duplicate_keep_choice": "existing",
                "duplicate_delete_choice": "new",
                "is_active": True,
            },
            editing_contact=source,
        )

        existing.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(resolved.id, existing.id)
        self.assertEqual(existing.email, "existing@example.org")
        self.assertFalse(source.is_active)

    def test_duplicate_shipper_renames_new_contact(self):
        self._create_shipper(
            organization_name="ASF Doublon",
            first_name="Alice",
            last_name="Existing",
        )
        source = self._create_shipper(
            organization_name="ASF Doublon",
            first_name="Aicha",
            last_name="Source",
        )

        resolved = save_contact_from_form(
            {
                "business_type": "shipper",
                "organization_name": "ASF Doublon",
                "first_name": "Aicha",
                "last_name": "Source",
                "duplicate_action": "duplicate",
                "is_active": True,
            },
            editing_contact=source,
        )

        source.refresh_from_db()
        self.assertEqual(resolved.id, source.id)
        self.assertEqual(source.name, "ASF Doublon - doublon")
