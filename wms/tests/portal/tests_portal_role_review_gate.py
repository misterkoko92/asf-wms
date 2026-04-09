from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.admin_account_request_approval import approve_account_request
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    PortalAccessGrant,
    PortalAccessRole,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
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

    def test_recipient_creation_creates_shipment_party_runtime(self):
        destination = self._create_destination("DLA")
        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": str(destination.id),
                "structure_name": "Action contre la faim",
                "contact_title": "",
                "contact_last_name": "",
                "contact_first_name": "",
                "phones": "",
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
