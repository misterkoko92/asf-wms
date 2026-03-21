from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.admin_account_request_approval import approve_account_request
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
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
                "notes": "",
                "notify_deliveries": "",
                "is_delivery_contact": "",
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
