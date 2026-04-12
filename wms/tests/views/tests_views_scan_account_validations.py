from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
)


@override_settings(ACCOUNT_REQUEST_VALIDATION_GROUP_NAME="Account_User_Validation")
class ScanAccountValidationViewTests(TestCase):
    def setUp(self):
        self.validator_group = Group.objects.get_or_create(name="Account_User_Validation")[0]
        self.validator_user = get_user_model().objects.create_user(
            username="scan-account-validator",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            email="scan-account-validator@example.org",
        )
        self.validator_group.user_set.add(self.validator_user)
        self.staff_user = get_user_model().objects.create_user(
            username="scan-account-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            email="scan-account-staff@example.org",
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-account-superuser",
            password="pass1234",  # pragma: allowlist secret
            email="scan-account-superuser@example.org",
        )
        self.correspondent = Contact.objects.create(
            name="Correspondant validation",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="BAMAKO",
            iata_code="BKO",
            country="MALI",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.pending_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.SHIPPER,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association Validation",
            email="validation@example.org",
            phone="+22370000000",
            address_line1="1 Rue Validation",
            address_line2="",
            postal_code="",
            city="Bamako",
            country="Mali",
        )
        self.list_url = "/scan/account-validations/"
        self.detail_url = f"/scan/account-validations/{self.pending_request.id}/"

    def test_scan_account_validation_list_requires_validator_access(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)

    def test_scan_account_validation_list_renders_pending_requests_for_validator(self):
        self.client.force_login(self.validator_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Validation expéditeurs")
        self.assertContains(response, self.pending_request.association_name)
        self.assertContains(response, "Traiter")
        self.assertEqual(response.context["active"], "account_validations")

    def test_scan_account_validation_detail_renders_review_form(self):
        self.client.force_login(self.validator_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pending_request.association_name)
        self.assertContains(response, 'name="final_account_type"')
        self.assertContains(response, PublicAccountRequestType.SHIPPER.label)
        self.assertContains(response, "Valider le compte")

    def test_scan_account_validation_detail_can_approve_shipper_as_recipient(self):
        self.client.force_login(self.validator_user)

        response = self.client.post(
            self.detail_url,
            {
                "action": "approve_request",
                "final_account_type": PublicAccountRequestType.RECIPIENT,
                "destination_id": str(self.destination.id),
                "allowed_shipper_ids": [],
                "organization_name": "Association Validation",
                "first_name": "Aicha",
                "last_name": "Traore",
                "email": self.pending_request.email,
                "phone": self.pending_request.phone,
                "legal_form": "association",
                "beneficiary_count": "120",
                "address_line1": self.pending_request.address_line1,
                "address_line2": self.pending_request.address_line2,
                "postal_code": self.pending_request.postal_code,
                "city": self.pending_request.city,
                "country": self.pending_request.country,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.pending_request.refresh_from_db()
        self.assertEqual(self.pending_request.status, PublicAccountRequestStatus.APPROVED)
        self.assertEqual(
            self.pending_request.requested_account_type,
            PublicAccountRequestType.SHIPPER,
        )
        self.assertEqual(self.pending_request.account_type, PublicAccountRequestType.RECIPIENT)
