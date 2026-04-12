from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    ShipmentRecipientOrganization,
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
