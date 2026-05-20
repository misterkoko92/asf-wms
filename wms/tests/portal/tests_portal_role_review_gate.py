from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.admin_account_request_approval import approve_account_request
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    Destination,
    DocumentScanStatus,
    PortalAccessGrant,
    PortalAccessRole,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    RecipientStructureDocument,
    RecipientStructureDocumentType,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_party_setup import ensure_shipment_shipper
from wms.view_permissions import (
    BLOCKED_REASON_COMPLIANCE_REQUIRED,
    BLOCKED_REASON_QUERY_PARAM,
    BLOCKED_REASON_REVIEW_PENDING,
)


class PortalRoleReviewGateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="portal-role-gate",
            email="portal-role-gate@example.org",
            password="pass1234",
        )
        self.contact = Contact.objects.create(
            name="Association Role Gate",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email=self.user.email,
        )
        ContactAddress.objects.create(
            contact=self.contact,
            address_line1="1 Rue Role Gate",
            city="Paris",
            postal_code="75001",
            country="France",
            is_default=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.contact,
            must_change_password=False,
        )
        self.client.force_login(self.user)

        self.recipients_url = reverse("portal:portal_recipients")
        self.order_create_url = reverse("portal:portal_order_create")
        self.account_url = reverse("portal:portal_account")

        self.destination = self._create_destination("BKO")
        self._create_delivery_recipient(
            structure_name="Destinataire Livraison",
            destination=self.destination,
        )

    def _create_destination(self, iata_code: str) -> Destination:
        correspondent = Contact.objects.create(
            name=f"Correspondant {iata_code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_delivery_recipient(self, *, structure_name: str, destination: Destination):
        return AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=destination,
            name=structure_name,
            structure_name=structure_name,
            address_line1="1 Rue Livraison",
            city=destination.city,
            country=destination.country,
            is_delivery_contact=True,
            is_active=True,
        )

    def _activate_shipper(self, *, status=ShipmentValidationStatus.VALIDATED) -> ShipmentShipper:
        return ensure_shipment_shipper(self.profile.contact, validation_status=status)

    def _create_complete_operational_contacts(self):
        AssociationPortalContact.objects.create(
            profile=self.profile,
            title="mr",
            first_name="Admin",
            last_name="CONTACT",
            email="admin-role-gate@example.org",
            phone="+33101010101",
            emails="admin-role-gate@example.org",
            phones="+33101010101",
            address_line1="1 Rue Admin",
            city="Paris",
            country="France",
            is_administrative=True,
            is_active=True,
        )
        AssociationPortalContact.objects.create(
            profile=self.profile,
            title="mrs",
            first_name="Prep",
            last_name="CONTACT",
            email="prep-role-gate@example.org",
            phone="+33202020202",
            emails="prep-role-gate@example.org",
            phones="+33202020202",
            address_line1="2 Rue Prep",
            city="Paris",
            country="France",
            is_shipping=True,
            is_active=True,
        )

    def test_shipper_pending_review_blocks_order_creation(self):
        self._activate_shipper(status=ShipmentValidationStatus.PENDING)

        response = self.client.get(self.order_create_url, follow=True)

        expected_redirect = (
            f"{self.account_url}?{BLOCKED_REASON_QUERY_PARAM}={BLOCKED_REASON_REVIEW_PENDING}"
        )
        self.assertRedirects(response, expected_redirect)
        self.assertContains(response, "Compte expéditeur en cours de revue ASF")

    def test_rejected_shipper_blocks_order_creation(self):
        self._activate_shipper(status=ShipmentValidationStatus.REJECTED)

        response = self.client.get(self.order_create_url, follow=True)

        expected_redirect = (
            f"{self.account_url}?{BLOCKED_REASON_QUERY_PARAM}={BLOCKED_REASON_COMPLIANCE_REQUIRED}"
        )
        self.assertRedirects(response, expected_redirect)
        self.assertContains(response, "documents expéditeur non conformes")

    def test_validated_shipper_without_operational_readiness_blocks_order_creation(self):
        self._activate_shipper(status=ShipmentValidationStatus.VALIDATED)

        response = self.client.get(self.order_create_url, follow=True)

        expected_redirect = f"{self.account_url}?blocked=operational_readiness"
        self.assertRedirects(response, expected_redirect)
        self.assertContains(response, "Contact administratif incomplet")
        self.assertContains(response, "Contact préparation/logistique incomplet")
        self.assertContains(response, "Aucun destinataire validé lié à votre structure")

    def test_recipient_creation_creates_shipment_party_runtime(self):
        destination = self._create_destination("DLA")
        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": str(destination.id),
                "structure_name": "Action contre la faim",
                "contact_title": "mrs",
                "contact_last_name": "Traore",
                "contact_first_name": "Aicha",
                "phones": "+237600000000",
                "emails": "ops-acf@example.org",
                "address_line1": "1 Avenue Recipient",
                "address_line2": "",
                "postal_code": "",
                "city": "Douala",
                "country": "Cameroun",
                "legal_form": "association",
                "beneficiary_count": "120",
                "notes": "",
                "notify_deliveries": "",
                "is_delivery_contact": "",
                "doc_registration_proof": SimpleUploadedFile(
                    "registration-proof.pdf",
                    b"%PDF-1.7 registration proof",
                ),
                "doc_statutes": SimpleUploadedFile(
                    "statutes.pdf",
                    b"%PDF-1.7 statutes",
                ),
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        recipient = AssociationRecipient.objects.get(structure_name="Action contre la faim")
        self.assertIsNotNone(recipient.synced_contact_id)
        recipient_contact = recipient.synced_contact
        shipper = ShipmentShipper.objects.get(organization=self.profile.contact)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=recipient_contact,
            destination=destination,
        )
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertTrue(shipment_recipient.is_active)
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper=shipper,
                recipient_organization=shipment_recipient,
                is_active=True,
            ).exists()
        )

    def test_approve_account_request_creates_validated_shipper(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-role-review",
            email="admin-role-review@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.ASSOCIATION,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association Review Pending",
            email="new-association@example.org",
            phone="",
            address_line1="1 Rue Pending",
            address_line2="",
            postal_code="",
            city="Paris",
            country="France",
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        account_request.refresh_from_db()
        self.assertEqual(account_request.status, PublicAccountRequestStatus.APPROVED)
        shipper = ShipmentShipper.objects.get(organization=account_request.contact)
        self.assertTrue(shipper.is_active)
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)

    def test_approve_shipper_account_request_provisions_operational_contacts(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-role-review-contacts",
            email="admin-role-review-contacts@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.SHIPPER,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association With Contacts",
            email="contacts-association@example.org",
            phone="0102030405",
            address_line1="1 Rue Contacts",
            city="Paris",
            country="France",
            contact_payloads={
                "admin": {
                    "title": "mr",
                    "first_name": "Marc",
                    "last_name": "DURAND",
                    "email": "admin-contact@example.org",
                    "phone": "0600000001",
                    "address_line1": "1 Rue Admin",
                    "address_line2": "",
                    "postal_code": "75001",
                    "city": "Paris",
                    "country": "France",
                },
                "preparation": {
                    "title": "mrs",
                    "first_name": "Claire",
                    "last_name": "MARTIN",
                    "email": "prep-contact@example.org",
                    "phone": "0600000002",
                    "address_line1": "2 Rue Prep",
                    "address_line2": "",
                    "postal_code": "75002",
                    "city": "Paris",
                    "country": "France",
                },
            },
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        profile = AssociationProfile.objects.get(contact=account_request.contact)
        contacts = list(profile.portal_contacts.order_by("position"))
        self.assertEqual(len(contacts), 2)
        self.assertEqual(contacts[0].email, "admin-contact@example.org")
        self.assertEqual(contacts[0].emails, "admin-contact@example.org")
        self.assertEqual(contacts[0].phones, "0600000001")
        self.assertTrue(contacts[0].is_administrative)
        self.assertEqual(contacts[0].address_line1, "1 Rue Admin")
        self.assertEqual(contacts[1].email, "prep-contact@example.org")
        self.assertTrue(contacts[1].is_shipping)
        self.assertEqual(
            profile.notification_emails, "admin-contact@example.org,prep-contact@example.org"
        )

    def test_approve_shipper_account_request_provisions_first_delivery_recipient(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-role-review-recipient",
            email="admin-role-review-recipient@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.SHIPPER,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association With First Recipient",
            email="with-first-recipient@example.org",
            phone="",
            address_line1="1 Rue Pending",
            address_line2="",
            postal_code="",
            city="Paris",
            country="France",
            initial_recipient_payload={
                "destination_id": self.destination.id,
                "structure_name": "Hopital Premier",
                "contact_title": "mrs",
                "contact_first_name": "Aicha",
                "contact_last_name": "Traore",
                "email": "aicha.traore@example.org",
                "phone": "+22370000000",
                "address_line1": "1 Avenue Hopital",
                "address_line2": "",
                "postal_code": "",
                "city": "Bamako",
                "country": "Mali",
                "legal_form": "association",
                "beneficiary_count": 120,
                "notes": "Premier destinataire",
                "is_delivery_contact": True,
            },
            contact_payloads={
                "admin": {
                    "title": "mr",
                    "first_name": "Marc",
                    "last_name": "DURAND",
                    "email": "admin-first-recipient@example.org",
                    "phone": "0600000101",
                    "address_line1": "1 Rue Admin",
                    "city": "Paris",
                    "country": "France",
                },
                "preparation": {
                    "title": "mrs",
                    "first_name": "Claire",
                    "last_name": "MARTIN",
                    "email": "prep-first-recipient@example.org",
                    "phone": "0600000202",
                    "address_line1": "2 Rue Prep",
                    "city": "Paris",
                    "country": "France",
                },
            },
        )
        AccountDocument.objects.create(
            account_request=account_request,
            doc_type=AccountDocumentType.REGISTRATION_PROOF,
            document_scope="initial_recipient",
            file=SimpleUploadedFile(
                "recipient-registration.pdf",
                b"%PDF-1.4 recipient registration",
                content_type="application/pdf",
            ),
            scan_status=DocumentScanStatus.CLEAN,
        )
        AccountDocument.objects.create(
            account_request=account_request,
            doc_type=AccountDocumentType.STATUTES,
            document_scope="initial_recipient",
            file=SimpleUploadedFile(
                "recipient-statutes.pdf",
                b"%PDF-1.4 recipient statutes",
                content_type="application/pdf",
            ),
            scan_status=DocumentScanStatus.CLEAN,
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        account_request.refresh_from_db()
        approved_user = get_user_model().objects.get(email=account_request.email)
        profile = AssociationProfile.objects.get(user=approved_user)
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])

        recipient = AssociationRecipient.objects.get(
            association_contact=account_request.contact,
            structure_name="Hopital Premier",
        )
        self.assertTrue(recipient.is_delivery_contact)
        self.assertEqual(recipient.contact_first_name, "Aicha")
        self.assertEqual(recipient.contact_last_name, "Traore")

        recipient_organization = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=self.destination,
        )
        self.assertEqual(
            recipient_organization.validation_status,
            ShipmentValidationStatus.VALIDATED,
        )
        recipient_documents = RecipientStructureDocument.objects.filter(
            contact=recipient.synced_contact,
        ).order_by("doc_type")
        self.assertEqual(
            {document.doc_type for document in recipient_documents},
            {
                RecipientStructureDocumentType.REGISTRATION_PROOF,
                RecipientStructureDocumentType.STATUTES,
            },
        )
        self.assertEqual(
            {document.scan_status for document in recipient_documents},
            {DocumentScanStatus.PENDING},
        )
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper__organization=account_request.contact,
                recipient_organization=recipient_organization,
                is_active=True,
            ).exists()
        )

        self.client.force_login(approved_user)
        response = self.client.get(self.order_create_url)

        self.assertEqual(response.status_code, 200)
        options_by_id = {
            str(option["id"]): option
            for option in response.context["recipient_options_all"]
            if option["id"] != "self"
        }
        self.assertEqual(
            options_by_id[str(recipient.id)]["allowed_destination_ids"],
            [self.destination.id],
        )

    def test_approve_recipient_account_request_creates_recipient_scope_and_asf_binding(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-recipient-role-review",
            email="admin-recipient-role-review@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        asf_contact = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ensure_shipment_shipper(
            asf_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type="recipient",
            status=PublicAccountRequestStatus.PENDING,
            association_name="Recipient Review Pending",
            email="new-recipient@example.org",
            phone="+22370000000",
            address_line1="1 Rue Recipient",
            address_line2="",
            postal_code="",
            city="Bamako",
            country="Mali",
            destination=self.destination,
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        account_request.refresh_from_db()
        self.assertEqual(account_request.status, PublicAccountRequestStatus.APPROVED)
        approved_user = get_user_model().objects.get(email=account_request.email)
        self.assertFalse(AssociationProfile.objects.filter(user=approved_user).exists())
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=account_request.contact,
            destination=self.destination,
        )
        self.assertEqual(shipment_recipient.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertTrue(shipment_recipient.is_active)
        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=approved_user,
                role=PortalAccessRole.RECIPIENT_ADMIN,
                recipient_organization=shipment_recipient,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            ShipmentRecipientContact.objects.filter(
                recipient_organization=shipment_recipient,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper__organization=asf_contact,
                recipient_organization=shipment_recipient,
                is_active=True,
            ).exists()
        )

    def test_approve_recipient_account_request_rejects_missing_destination(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-recipient-missing-destination",
            email="admin-recipient-missing-destination@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.RECIPIENT,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Recipient Missing Destination",
            email="recipient-missing-destination@example.org",
            phone="+22370000000",
            address_line1="1 Rue Recipient",
            address_line2="",
            postal_code="",
            city="Bamako",
            country="Mali",
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertFalse(ok)
        self.assertEqual(reason, "destination manquante")

    def test_approve_recipient_account_request_rejects_missing_default_shipper(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-recipient-missing-shipper",
            email="admin-recipient-missing-shipper@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.RECIPIENT,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Recipient Missing Default Shipper",
            email="recipient-missing-shipper@example.org",
            phone="+22370000000",
            address_line1="1 Rue Recipient",
            address_line2="",
            postal_code="",
            city="Bamako",
            country="Mali",
            destination=self.destination,
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertFalse(ok)
        self.assertEqual(reason, "expediteur ASF manquant")

    def test_approve_account_request_can_review_shipper_request_as_recipient(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-reviewed-recipient",
            email="admin-reviewed-recipient@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        shipper_contact = Contact.objects.create(
            name="Expediteur autorise review",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ensure_shipment_shipper(
            shipper_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.SHIPPER,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Request Reviewed As Recipient",
            email="reviewed-as-recipient@example.org",
            phone="+22373333333",
            address_line1="1 Rue Review",
            address_line2="",
            postal_code="",
            city="Bamako",
            country="Mali",
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
            review_overrides={
                "final_account_type": PublicAccountRequestType.RECIPIENT,
                "destination_id": self.destination.id,
                "allowed_shipper_ids": [shipper_contact.id],
                "legal_form": "association",
                "beneficiary_count": 120,
                "first_name": "Aicha",
                "last_name": "Traore",
            },
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        account_request.refresh_from_db()
        self.assertEqual(account_request.status, PublicAccountRequestStatus.APPROVED)
        self.assertEqual(account_request.requested_account_type, PublicAccountRequestType.SHIPPER)
        self.assertEqual(account_request.account_type, PublicAccountRequestType.RECIPIENT)
        self.assertEqual(
            account_request.review_snapshot["final_account_type"],
            PublicAccountRequestType.RECIPIENT,
        )
        self.assertEqual(account_request.review_snapshot["destination_id"], self.destination.id)
        self.assertEqual(
            account_request.review_snapshot["allowed_shipper_ids"],
            [shipper_contact.id],
        )
        approved_user = get_user_model().objects.get(email=account_request.email)
        self.assertFalse(AssociationProfile.objects.filter(user=approved_user).exists())
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=account_request.contact,
            destination=self.destination,
        )
        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=approved_user,
                role=PortalAccessRole.RECIPIENT_ADMIN,
                recipient_organization=shipment_recipient,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper__organization=shipper_contact,
                recipient_organization=shipment_recipient,
                is_active=True,
            ).exists()
        )

    def test_approve_recipient_account_request_reactivates_existing_scope_objects(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-recipient-reactivation",
            email="admin-recipient-reactivation@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        prior_reviewer = get_user_model().objects.create_user(
            username="prior-recipient-reviewer",
            email="prior-recipient-reviewer@example.org",
            password="pass1234",
            is_staff=True,
        )
        approved_user = get_user_model().objects.create_user(
            username="reactivated-recipient@example.org",
            email="reactivated-recipient@example.org",
            password="pass1234",
            is_active=False,
        )
        asf_contact = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        asf_shipper = ensure_shipment_shipper(
            asf_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        recipient_contact = Contact.objects.create(
            name="Recipient Reactivation Scope",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email=approved_user.email,
            phone="+22361111111",
        )
        primary_person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            organization=recipient_contact,
            first_name="Primary",
            last_name="Recipient",
            name="Primary Recipient",
            email="old-recipient@example.org",
            phone="+22362222222",
            is_active=True,
            use_organization_address=True,
        )
        recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=recipient_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=primary_person,
            is_active=True,
        )
        PortalAccessGrant.objects.create(
            user=approved_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_organization,
            is_active=False,
            reviewed_by=prior_reviewer,
        )
        ShipmentRecipientOrganization.objects.filter(pk=recipient_organization.pk).update(
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=False,
        )
        ShipmentRecipientContact.objects.filter(pk=shipment_recipient_contact.pk).update(
            is_active=False
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.RECIPIENT,
            status=PublicAccountRequestStatus.PENDING,
            association_name=recipient_contact.name,
            email=approved_user.email,
            phone="+22370000000",
            address_line1="1 Rue Reactivation",
            address_line2="",
            postal_code="",
            city="Bamako",
            country="Mali",
            destination=self.destination,
            contact=recipient_contact,
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        approved_user.refresh_from_db()
        recipient_organization.refresh_from_db()
        shipment_recipient_contact.refresh_from_db()
        grant = PortalAccessGrant.objects.get(
            user=approved_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_organization,
        )
        primary_person.refresh_from_db()

        self.assertTrue(approved_user.is_active)
        self.assertEqual(
            recipient_organization.validation_status, ShipmentValidationStatus.VALIDATED
        )
        self.assertTrue(recipient_organization.is_active)
        self.assertTrue(shipment_recipient_contact.is_active)
        self.assertEqual(grant.reviewed_by, admin_user)
        self.assertEqual(grant.created_by, admin_user)
        self.assertIsNotNone(grant.reviewed_at)
        self.assertTrue(grant.is_active)
        self.assertEqual(primary_person.email, approved_user.email)
        self.assertEqual(primary_person.phone, account_request.phone)
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper=asf_shipper,
                recipient_organization=recipient_organization,
                is_active=True,
            ).exists()
        )
