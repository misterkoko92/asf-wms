from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from contacts.models import Contact, ContactType
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    Destination,
    DocumentReviewStatus,
    DocumentScanStatus,
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

    def test_scan_account_validation_detail_displays_shipper_contact_payloads(self):
        self.pending_request.contact_payloads = {
            "admin": {
                "title": "mr",
                "first_name": "Admin",
                "last_name": "TRANSMIS",
                "email": "admin-transmis@example.org",
                "phone": "+33100000001",
                "address_line1": "1 Rue Admin",
                "address_line2": "",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
            "preparation": {
                "title": "mrs",
                "first_name": "Prep",
                "last_name": "LOGISTIQUE",
                "email": "prep-transmis@example.org",
                "phone": "+33100000002",
                "address_line1": "2 Rue Prep",
                "address_line2": "Batiment B",
                "postal_code": "75002",
                "city": "Paris",
                "country": "France",
            },
        }
        self.pending_request.save(update_fields=["contact_payloads"])
        self.client.force_login(self.validator_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contacts transmis")
        self.assertContains(response, "Contact administratif")
        self.assertContains(response, "Admin TRANSMIS")
        self.assertContains(response, "admin-transmis@example.org")
        self.assertContains(response, "Contact préparation/logistique")
        self.assertContains(response, "Prep LOGISTIQUE")
        self.assertContains(response, "prep-transmis@example.org")
        self.assertContains(response, "2 Rue Prep")

    def test_scan_account_validation_detail_displays_recipient_reception_contact_payload(self):
        self.pending_request.account_type = PublicAccountRequestType.RECIPIENT
        self.pending_request.destination = self.destination
        self.pending_request.contact_payloads = {
            "recipient_reception": {
                "title": "mrs",
                "first_name": "Aicha",
                "last_name": "DIALLO",
                "email": "reception-transmise@example.org",
                "phone": "+22370000001",
                "address_line1": "10 Rue Reception",
                "address_line2": "",
                "postal_code": "",
                "city": "Bamako",
                "country": "Mali",
            }
        }
        self.pending_request.save(update_fields=["account_type", "destination", "contact_payloads"])
        self.client.force_login(self.validator_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contacts transmis")
        self.assertContains(response, "Contact réception")
        self.assertContains(response, "Aicha DIALLO")
        self.assertContains(response, "reception-transmise@example.org")
        self.assertContains(response, "10 Rue Reception")

    def test_scan_account_validation_detail_legacy_request_without_payload_remains_reviewable(
        self,
    ):
        self.pending_request.contact_payloads = {}
        self.pending_request.save(update_fields=["contact_payloads"])
        self.client.force_login(self.validator_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Contacts transmis")
        self.assertContains(response, "Qualification opérateur")
        self.assertContains(response, "Valider le compte")

    def test_scan_account_validation_detail_normalizes_legacy_association_to_shipper(self):
        self.pending_request.account_type = PublicAccountRequestType.ASSOCIATION
        self.pending_request.save(update_fields=["account_type"])
        self.client.force_login(self.validator_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial["final_account_type"],
            PublicAccountRequestType.SHIPPER,
        )
        choice_values = [
            value for value, _label in response.context["form"].fields["final_account_type"].choices
        ]
        self.assertEqual(len(choice_values), 2)
        self.assertCountEqual(
            choice_values,
            [PublicAccountRequestType.RECIPIENT, PublicAccountRequestType.SHIPPER],
        )

    def test_scan_account_validation_detail_exposes_dynamic_sections_and_safe_document_links(
        self,
    ):
        clean_document = AccountDocument.objects.create(
            account_request=self.pending_request,
            doc_type=AccountDocumentType.STATUTES,
            status=DocumentReviewStatus.PENDING,
            file=SimpleUploadedFile("statutes.pdf", b"%PDF-1.4 statutes"),
            scan_status=DocumentScanStatus.CLEAN,
        )
        AccountDocument.objects.create(
            account_request=self.pending_request,
            doc_type=AccountDocumentType.REGISTRATION_PROOF,
            status=DocumentReviewStatus.PENDING,
            file=SimpleUploadedFile("registration-proof.pdf", b"%PDF-1.4 registration proof"),
            scan_status=DocumentScanStatus.PENDING,
            scan_message="Scan antivirus en cours.",
        )
        self.client.force_login(self.validator_user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qualification opérateur")
        self.assertContains(response, "Données métier")
        self.assertContains(response, 'data-account-validation-field="1"')
        self.assertContains(response, 'data-account-validation-required-marker="organization_name"')
        choice_values = [
            value for value, _label in response.context["form"].fields["final_account_type"].choices
        ]
        self.assertEqual(len(choice_values), 2)
        self.assertCountEqual(
            choice_values,
            [PublicAccountRequestType.RECIPIENT, PublicAccountRequestType.SHIPPER],
        )
        self.assertContains(response, clean_document.file.name)
        self.assertContains(response, clean_document.file.url)
        self.assertContains(response, "Quarantaine (scan antivirus en cours).")

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
