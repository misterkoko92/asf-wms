from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import TestCase, override_settings

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


@override_settings(ACCOUNT_REQUEST_VALIDATION_GROUP_NAME="Account_User_Validation")
class ScanContactValidationsViewTests(TestCase):
    def setUp(self):
        self.validator_group = Group.objects.get_or_create(name="Account_User_Validation")[0]
        self.validator_user = get_user_model().objects.create_user(
            username="scan-contact-validator",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            email="scan-contact-validator@example.org",
        )
        self.validator_group.user_set.add(self.validator_user)
        self.staff_user = get_user_model().objects.create_user(
            username="scan-contact-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            email="scan-contact-staff@example.org",
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-contact-superuser",
            password="pass1234",  # pragma: allowlist secret
            email="scan-contact-superuser@example.org",
        )
        self.correspondent = Contact.objects.create(
            name="Correspondant validations contacts",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.pending_recipient_contact = Contact.objects.create(
            name="Hopital Validation",
            contact_type=ContactType.ORGANIZATION,
            legal_form="association",
            beneficiary_count=120,
            is_active=True,
        )
        self.pending_recipient = ShipmentRecipientOrganization.objects.create(
            organization=self.pending_recipient_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )
        self.hub_url = "/scan/contacts/validations/"
        self.recipient_list_url = "/scan/contacts/validations/recipients/"
        self.recipient_detail_url = (
            f"/scan/contacts/validations/recipients/{self.pending_recipient.id}/"
        )

    def _create_validated_shipper(self):
        shipper_organization = Contact.objects.create(
            name="ASF Validation Contacts",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_referent = Contact.objects.create(
            name="Jean Validation Contacts",
            contact_type=ContactType.PERSON,
            first_name="Jean",
            last_name="Validation",
            organization=shipper_organization,
            is_active=True,
        )
        ShipmentShipper.objects.create(
            organization=shipper_organization,
            default_contact=shipper_referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        return shipper_organization

    def _recipient_validation_payload(
        self,
        *,
        shipper_organization,
        duplicate_action="",
        duplicate_target_id="",
        duplicate_keep_choice="",
        duplicate_delete_choice="",
    ):
        payload = {
            "action": "save_contact",
            "editing_contact_id": str(self.pending_recipient_contact.id),
            "business_type": "recipient",
            "organization_name": self.pending_recipient_contact.name,
            "legal_form": "association",
            "beneficiary_count": "120",
            "first_name": "Aicha",
            "last_name": "Traore",
            "email": "recipient-validation@example.org",
            "phone": "+22370000001",
            "address_line1": "1 Rue Validation",
            "city": "Abidjan",
            "country": "COTE D'IVOIRE",
            "destination_id": str(self.destination.id),
            "allowed_shipper_ids": [str(shipper_organization.id)],
            "is_active": "on",
        }
        if duplicate_action:
            payload["duplicate_candidates_count"] = "1"
            payload["duplicate_action"] = duplicate_action
        if duplicate_target_id:
            payload["duplicate_target_id"] = str(duplicate_target_id)
        if duplicate_keep_choice:
            payload["duplicate_keep_choice"] = duplicate_keep_choice
        if duplicate_delete_choice:
            payload["duplicate_delete_choice"] = duplicate_delete_choice
        return payload

    def _create_validated_recipient_candidate(self, *, shipper_organization, name=None):
        organization = Contact.objects.create(
            name=name or self.pending_recipient_contact.name,
            contact_type=ContactType.ORGANIZATION,
            legal_form="association",
            beneficiary_count=80,
            is_active=True,
        )
        referent = Contact.objects.create(
            name="Alice Existing",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Existing",
            organization=organization,
            is_active=True,
        )
        recipient_runtime = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_runtime,
            contact=referent,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.get(organization=shipper_organization)
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_runtime,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=recipient_contact,
            is_active=True,
            is_default=True,
        )
        return organization

    def test_scan_contact_validations_hub_requires_validation_access(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.hub_url)

        self.assertEqual(response.status_code, 403)

    def test_scan_contact_validations_hub_renders_shipper_surface_for_validator(self):
        PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.SHIPPER,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association Validation Hub",
            email="validation-hub@example.org",
            phone="0102030405",
            address_line1="1 Rue Hub",
            address_line2="",
            postal_code="75001",
            city="Paris",
            country="France",
        )
        self.client.force_login(self.validator_user)

        response = self.client.get(self.hub_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Validation expéditeurs")
        self.assertContains(response, "/scan/account-validations/")

    def test_scan_contact_validations_hub_renders_recipient_surface_for_superuser(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.hub_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Validation destinataires")
        self.assertContains(response, self.recipient_list_url)

    def test_scan_recipient_validation_list_requires_superuser(self):
        self.client.force_login(self.validator_user)

        response = self.client.get(self.recipient_list_url)

        self.assertEqual(response.status_code, 403)

    def test_scan_recipient_validation_list_renders_pending_recipient_queue(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.recipient_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Validation destinataires")
        self.assertContains(response, self.pending_recipient_contact.name)
        self.assertContains(response, self.destination.city)
        self.assertContains(response, self.recipient_detail_url)
        self.assertContains(response, "Ouvrir")

    def test_scan_recipient_validation_detail_renders_summary_and_validation_form(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.recipient_detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pending_recipient_contact.name)
        self.assertContains(response, "Décision ASF")
        self.assertContains(response, "Valider le destinataire")
        self.assertContains(response, self.destination.city)

    def test_scan_recipient_validation_detail_reuses_operator_qualification_gate(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.recipient_detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qualification opérateur")
        self.assertContains(
            response,
            "Corrigez le type final si la demande a été créée avec le mauvais profil",
        )
        self.assertContains(response, 'data-contact-stage="details"')
        self.assertContains(response, 'name="notes"')
        self.assertContains(response, 'rows="2"')
        self.assertEqual(
            [
                value
                for value, _label in response.context["contact_form"]
                .fields["business_type"]
                .choices
            ],
            ["", "recipient", "shipper"],
        )

    def test_scan_recipient_validation_detail_places_duplicate_review_above_context(self):
        shipper_organization = self._create_validated_shipper()
        self._create_validated_recipient_candidate(shipper_organization=shipper_organization)
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            self._recipient_validation_payload(shipper_organization=shipper_organization),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Doublon détecté")
        self.assertContains(response, "Valider le doublon et accepter")
        self.assertContains(response, "Contact à conserver")
        self.assertContains(response, "Contact à supprimer")
        self.assertContains(response, "Déjà dans la base")
        self.assertContains(response, "Nouvel ajout")
        content = response.content.decode()
        self.assertLess(content.index("Doublon détecté"), content.index("Contexte"))

    def test_scan_recipient_validation_detail_can_requalify_pending_recipient_as_shipper(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            {
                "action": "save_contact",
                "editing_contact_id": str(self.pending_recipient_contact.id),
                "business_type": "shipper",
                "organization_name": self.pending_recipient_contact.name,
                "first_name": "Aicha",
                "last_name": "Traore",
                "email": "shipper-validation@example.org",
                "phone": "+22370000001",
                "address_line1": "1 Rue Validation",
                "city": "Abidjan",
                "country": "COTE D'IVOIRE",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.recipient_list_url)
        self.pending_recipient.refresh_from_db()
        self.assertEqual(
            self.pending_recipient.validation_status, ShipmentValidationStatus.REJECTED
        )
        shipper = ShipmentShipper.objects.get(organization=self.pending_recipient_contact)
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)

    def test_scan_recipient_validation_detail_can_merge_duplicate_into_existing_contact(self):
        shipper_organization = self._create_validated_shipper()
        duplicate_target = self._create_validated_recipient_candidate(
            shipper_organization=shipper_organization
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            self._recipient_validation_payload(
                shipper_organization=shipper_organization,
                duplicate_action="merge",
                duplicate_target_id=duplicate_target.id,
                duplicate_keep_choice="existing",
                duplicate_delete_choice="new",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.recipient_list_url)
        duplicate_target.refresh_from_db()
        self.pending_recipient_contact.refresh_from_db()
        self.assertFalse(self.pending_recipient_contact.is_active)
        self.assertEqual(
            ShipmentRecipientOrganization.objects.get(
                organization=duplicate_target,
                destination=self.destination,
            ).validation_status,
            ShipmentValidationStatus.VALIDATED,
        )
        self.assertFalse(
            ShipmentRecipientOrganization.objects.filter(
                organization=self.pending_recipient_contact,
                destination=self.destination,
            ).exists()
        )

    def test_scan_recipient_validation_detail_can_replace_duplicate_with_existing_contact(self):
        shipper_organization = self._create_validated_shipper()
        duplicate_target = self._create_validated_recipient_candidate(
            shipper_organization=shipper_organization
        )
        duplicate_target.email = "existing@example.org"
        duplicate_target.save(update_fields=["email"])
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            self._recipient_validation_payload(
                shipper_organization=shipper_organization,
                duplicate_action="replace",
                duplicate_target_id=duplicate_target.id,
                duplicate_keep_choice="existing",
                duplicate_delete_choice="new",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.recipient_list_url)
        duplicate_target.refresh_from_db()
        self.pending_recipient_contact.refresh_from_db()
        self.assertEqual(duplicate_target.email, "existing@example.org")
        self.assertFalse(self.pending_recipient_contact.is_active)

    def test_scan_recipient_validation_detail_can_duplicate_pending_contact_with_suffix(self):
        shipper_organization = self._create_validated_shipper()
        self._create_validated_recipient_candidate(shipper_organization=shipper_organization)
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            self._recipient_validation_payload(
                shipper_organization=shipper_organization,
                duplicate_action="duplicate",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.recipient_list_url)
        self.pending_recipient_contact.refresh_from_db()
        self.pending_recipient.refresh_from_db()
        self.assertEqual(self.pending_recipient_contact.name, "Hopital Validation - doublon")
        self.assertEqual(
            self.pending_recipient.validation_status,
            ShipmentValidationStatus.VALIDATED,
        )

    @mock.patch(
        "wms.admin_contacts_crud.save_contact_from_form",
        side_effect=IntegrityError("duplicate runtime conflict"),
    )
    def test_scan_recipient_validation_detail_surfaces_merge_conflict_without_500(self, _save_mock):
        shipper_organization = self._create_validated_shipper()
        duplicate_target = Contact.objects.create(
            name=self.pending_recipient_contact.name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            self._recipient_validation_payload(
                shipper_organization=shipper_organization,
                duplicate_action="merge",
                duplicate_target_id=duplicate_target.id,
                duplicate_keep_choice="existing",
                duplicate_delete_choice="new",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Un conflit de données empêche cette résolution de doublon.",
        )
        self.assertContains(response, "Doublon détecté")
        self.pending_recipient.refresh_from_db()
        self.assertEqual(
            self.pending_recipient.validation_status,
            ShipmentValidationStatus.PENDING,
        )

    @mock.patch(
        "wms.admin_contacts_crud.save_contact_from_form",
        side_effect=IntegrityError("duplicate runtime conflict"),
    )
    def test_scan_recipient_validation_detail_surfaces_duplicate_conflict_without_500(
        self, _save_mock
    ):
        shipper_organization = self._create_validated_shipper()
        Contact.objects.create(
            name=self.pending_recipient_contact.name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            self.recipient_detail_url,
            self._recipient_validation_payload(
                shipper_organization=shipper_organization,
                duplicate_action="duplicate",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Un conflit de données empêche cette résolution de doublon.",
        )
        self.assertContains(response, "Doublon détecté")
        self.pending_recipient.refresh_from_db()
        self.assertEqual(
            self.pending_recipient.validation_status,
            ShipmentValidationStatus.PENDING,
        )
